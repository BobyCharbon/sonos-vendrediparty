import { router, useLocalSearchParams, type Href } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Label, Note, hatched, TopBar } from '@/components/agenda/Bits';
import { GroupTile } from '@/components/GroupBits';
import { SheetBackdrop, SheetTop, useSheetDrag, useSheetSignal, useSheetTop } from '@/components/SheetGesture';
import { Avatar, Button, ErrorText, Screen, Skeleton, T } from '@/components/ui';
import {
  addDays, addMonths, dayKey, dayOfMonth, longDay, MODES, monthStart, monthTitle, personState, rankDays, rpc,
  savePrefs, shortDay, tinyDay, weekStart, zdate,
  type Candidate, type FreeMember, type FreeMode, type GroupFree, type Prefs, type Sharing,
} from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { groupName } from '@/lib/groups';
import { duration, enter, transition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/**
 * « Qui est libre ? » (maquette A choisie par l'admin le 23.11) : le calendrier des mois, jours dans l'ordre (lun → dim),
 * aujourd'hui entouré ; chaque jour dit « n/6 » et se colore d'autant plus vert qu'il y a de monde libre ; le meilleur
 * jour est encadré de néon. Au-dessus : combien de soirs réunissent au moins ~60 % de ceux qui partagent, et « Le mieux ».
 * Toucher un jour ouvre une feuille : qui est disponible / occupé, en mots, puis « Organiser » ou « Faire voter » (on coche
 * 2–3 jours). Le soir 18 h – 23 h, la journée 8 h – 17 h. On ne compte que ceux qui partagent ; « Les autres membres »
 * grisés, sans aucun texte. Période : les 60 jours que la base partage (`agenda_group_free`).
 */
/** « sam. 5 déc. » */
const lowDay = (key: string) => shortDay(key).replace(/^./, (c) => c.toLowerCase());
const WEEK_HEAD = ['lun', 'mar', 'mer', 'jeu', 'ven', 'sam', 'dim'];

export default function FreeScreen() {
  const me = useMe();
  const p = useLocalSearchParams<{ group?: string }>();
  const today = dayKey(new Date());
  const [modePick, setMode] = useState<FreeMode | null>(null);
  const [picked, setPicked] = useState<string | null>(typeof p.group === 'string' ? p.group : null);
  const [open, setOpen] = useState<string | null>(null);
  const [voting, setVoting] = useState(false);
  const [picks, setPicks] = useState<string[]>([]);
  const [hintHidden, setHintHidden] = useState(false);

  const base = useQuery(async () => {
    const [sharing, prefs] = await Promise.all([rpc<Sharing>('agenda_sharing'), rpc<Prefs>('agenda_prefs_get').catch((): Prefs => ({}))]);
    return { sharing, prefs };
  }, []);
  const groups = base.data?.sharing.groups ?? [];
  const group = picked && groups.some((g) => g.id === picked) ? picked
    : base.data?.prefs.free_group && groups.some((g) => g.id === base.data!.prefs.free_group) ? base.data.prefs.free_group
    : (groups.find((g) => !g.system) ?? groups[0])?.id ?? null;
  const mode: FreeMode = modePick ?? base.data?.prefs.free_mode ?? 'evening';

  // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule fois par jour
  const from = useMemo(() => new Date(), [today]);
  const free = useQuery(async () => (group ? rpc<GroupFree>('agenda_group_free', { grp: group, from_ts: from.toISOString(), days: 60 }) : null), [group, from.getTime()]);
  useSignal([`user:${me.id}`], () => { void base.reload(); void free.reload(); });

  const data = free.data;
  const sharing = data?.members.filter((m) => m.shares) ?? [];
  const others = data?.members.filter((m) => !m.shares) ?? [];
  const ranked = useMemo(() => (data ? rankDays(data, mode) : []), [data, mode]);
  const byKey = useMemo(() => new Map(ranked.map((c) => [c.key, c])), [ranked]);
  const best: Candidate | undefined = ranked[0]?.free ? ranked[0] : undefined;
  // Seuil d'un « bon » jour : 60 % de ceux qui partagent, 2 au moins, mais jamais plus qu'eux (sinon « 0 soir où au moins 1
  // sur 1 est libre » alors que la grille est verte : audit du 24.11).
  const need = Math.max(1, Math.min(sharing.length, Math.max(2, Math.ceil(sharing.length * 0.6))));
  const goodCount = ranked.filter((c) => c.free >= need).length;
  const lastKey = data ? dayKey(new Date(new Date(data.to).getTime() - 1)) : today;
  const months: string[] = [];
  for (let m = monthStart(today); m <= monthStart(lastKey) && months.length < 4; m = addMonths(m, 1)) months.push(m);
  const word = mode === 'evening' ? 'soir' : 'jour';
  const opened = open ? byKey.get(open) : undefined;
  const states = opened ? sharing.map((m) => ({ m, s: personState(m, opened.key, mode) })) : [];
  const freeRows = states.filter((x) => x.s.available);
  const busyRows = states.filter((x) => !x.s.available);
  const gname = data ? groupName(data.group) : '';
  const chosen = picks.map((k) => byKey.get(k)).filter((c): c is Candidate => !!c).sort((a, b) => a.start.getTime() - b.start.getTime());

  function choose(g: string) {
    setPicked(g);
    setOpen(null);
    setVoting(false);
    setPicks([]);
    void savePrefs({ free_group: g });
  }
  function tap(key: string) {
    if (!voting) return setOpen(key);
    setPicks((cur) => (cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key]));
  }
  function startVote(key?: string) {
    setOpen(null);
    setVoting(true);
    setPicks(key ? [key] : ranked.filter((c) => c.free > 0).slice(0, 3).map((c) => c.key));
  }
  function organise(c: Candidate) {
    if (!group) return;
    const q = `group=${group}&title=${encodeURIComponent(`Soirée ${gname}`)}&start=${encodeURIComponent(c.start.toISOString())}&end=${encodeURIComponent(c.end.toISOString())}`;
    setOpen(null);
    router.push(`/event/new?${q}` as Href);
  }
  function poll() {
    if (!group) return;
    const dates = chosen.map((c) => c.start.toISOString()).join(',');
    router.push(`/event/new?group=${group}&title=${encodeURIComponent(`Soirée ${gname}`)}${dates ? `&poll=${encodeURIComponent(dates)}` : '&poll='}` as Href);
  }

  return (
    <Screen>
      <TopBar back="Agenda" fallback="/agenda" title="Qui est libre ?" />
      <ErrorText error={base.error ?? free.error} />
      {base.data && !groups.length ? (
        <View style={st.empty}>
          <T size={40}>👥</T>
          <T size={18} weight="bold" style={{ textAlign: 'center' }}>Qui est libre ? marche avec un groupe.</T>
          <Button label="Créer un groupe" onPress={() => router.push('/group/new')} />
        </View>
      ) : null}

      {groups.length ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -16, flexGrow: 0 }}
          contentContainerStyle={{ gap: 14, paddingHorizontal: 16, paddingVertical: 4 }} accessibilityRole="tablist">
          {groups.map((g) => {
            const on = g.id === group;
            return (
              <Pressable key={g.id} accessibilityRole="tab" aria-selected={on} accessibilityState={{ selected: on }} accessibilityLabel={groupName(g)}
                testID={`free-group-${g.id}`} onPress={() => choose(g.id)} style={st.bubble}>
                <View style={[st.ring, on && st.ringOn, transition('border-color', duration.fast)]}><GroupTile group={g} size={58} style={{ borderRadius: 29 }} /></View>
                <T size={12} weight={on ? 'bold' : 'medium'} color={on ? colors.text : colors.textSoft} numberOfLines={2} style={{ textAlign: 'center' }}>{groupName(g)}</T>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}

      {group ? (
        <View style={st.seg} accessibilityRole="radiogroup" accessibilityLabel="Moment">
          {(['evening', 'day'] as FreeMode[]).map((k) => (
            <Pressable key={k} accessibilityRole="radio" aria-checked={mode === k} accessibilityState={{ checked: mode === k }} testID={`free-mode-${k}`}
              onPress={() => { setMode(k); setOpen(null); void savePrefs({ free_mode: k }); }}
              style={[st.segItem, mode === k && st.segOn, transition('background-color', duration.fast)]}>
              <Text numberOfLines={1} style={{ color: mode === k ? colors.text : colors.textSoft, fontSize: 13, ...font.semibold }}>
                {k === 'evening' ? `🌙 Le soir · ${MODES.evening.label}` : `☀️ La journée · ${MODES.day.label}`}
              </Text>
            </Pressable>
          ))}
        </View>
      ) : null}

      {group && !data && !free.error ? <Skeleton height={300} radius={radius.lg} /> : null}

      {data ? (
        <>
          {!data.i_share && !hintHidden && !base.data?.prefs.share_hint_dismissed ? (
            <View style={[st.hint, enter('drop')]} testID="free-share-hint">
              <T size={14} style={{ flex: 1 }}>Toi, tu ne partages pas encore avec ce groupe.</T>
              <Button small label="Partager mes dispos" onPress={() => router.push(`/agenda/share?group=${group}` as Href)} />
              <Pressable accessibilityRole="button" accessibilityLabel="Masquer ce rappel" onPress={() => { setHintHidden(true); void savePrefs({ share_hint_dismissed: true }); }}
                style={st.hintX}><T muted size={16}>✕</T></Pressable>
            </View>
          ) : null}

          {!sharing.length ? (
            <View style={[st.empty, enter('fade')]} testID="free-nobody">
              <T size={36}>🌙</T>
              <T size={19} weight="bold" style={{ textAlign: 'center' }}>Personne ne partage encore ses dispos dans {gname}</T>
              <T size={14} color={colors.textSoft} style={{ textAlign: 'center' }}>Tu peux quand même faire voter le groupe : chacun dit quelles dates lui vont.</T>
            </View>
          ) : (
            <>
              <View style={st.summary} testID="free-summary">
                <T size={30} weight="bold" color={colors.mint} style={{ fontVariant: ['tabular-nums'] }}>{goodCount}</T>
                <T size={14} color={colors.textSoft} style={{ flex: 1 }}>
                  {word}{goodCount > 1 ? 's' : ''} où <Text style={{ color: colors.text, ...font.bold }}>{need === sharing.length ? (need > 1 ? `tous les ${need}` : '1 sur 1') : `au moins ${need} sur ${sharing.length}`}</Text> {need > 1 ? 'sont libres' : 'est libre'} d’ici le {tinyDay(lastKey)} {monthTitle(lastKey, lastKey).toLowerCase()}
                </T>
              </View>
              {best ? (
                <Pressable accessibilityRole="button" testID="free-best" onPress={() => tap(best.key)}
                  accessibilityLabel={`Le mieux : ${longDay(best.key)}, ${MODES[mode].label}, ${best.free} disponible${best.free > 1 ? 's' : ''} sur ${best.sharing}`}
                  style={st.bestCard}>
                  <View style={{ flex: 1, gap: 2 }}>
                    <T size={11} weight="bold" color={colors.accentSoft} style={{ letterSpacing: 0.8 }}>★ LE MIEUX</T>
                    <T size={16} weight="bold">{longDay(best.key)} · {MODES[mode].label}</T>
                  </View>
                  <View style={st.bestPill}><T size={14} weight="bold" color={colors.onMint}>{best.free}/{best.sharing}</T></View>
                </Pressable>
              ) : (
                <T muted style={{ textAlign: 'center', padding: 12 }}>Aucun {word} où quelqu’un est disponible sur cette période.</T>
              )}
              {sharing.length < 3 && data.members.length > sharing.length ? (
                <Note>Seulement {sharing.length} sur {data.members.length} partagent : il manque des infos.</Note>
              ) : null}

              {voting ? (
                <View style={[st.voteBar, enter('drop')]} testID="free-vote-bar">
                  <T size={14} style={{ flex: 1 }}>Coche 2 ou 3 {word}s pour le vote</T>
                  <Pressable accessibilityRole="button" onPress={() => { setVoting(false); setPicks([]); }} style={st.voteCancel}>
                    <T size={14} weight="bold" color={colors.accentSoft}>Annuler</T>
                  </Pressable>
                </View>
              ) : null}

              {months.map((m) => (
                <MonthGrid key={m} month={m} today={today} last={lastKey} byKey={byKey} best={best?.key} need={need}
                  word={word} picks={voting ? picks : []} onTap={tap} />
              ))}
              <T muted size={12}>Plus c’est vert, plus il y a de monde libre. Le meilleur {word} est encadré en rose.</T>
            </>
          )}

          {others.length ? (
            <View style={{ gap: 8 }} testID="free-others">
              <Label>{sharing.length ? 'Les autres membres' : 'Les membres'}</Label>
              <View style={st.othersRow}>
                {others.map((m) => (
                  <View key={m.id} style={st.other} accessibilityLabel={m.me ? 'Toi' : m.name}>
                    <View style={{ opacity: 0.45 }}><Avatar id={m.id} name={m.name} photo={m.avatar_url} size={40} /></View>
                    <T size={12} color={colors.muted} numberOfLines={1}>{m.me ? 'Toi' : m.name.split(' ')[0]}</T>
                  </View>
                ))}
              </View>
            </View>
          ) : null}

          {sharing.length ? <Note icon="🔒" color={colors.mint}>Tu vois seulement Disponible ou Occupé, jamais pourquoi.</Note> : null}

          <View style={{ gap: 10, marginTop: 4 }}>
            {voting ? (
              <>
                {chosen.length ? (
                  <View style={st.chips}>
                    {chosen.map((c) => (
                      <View key={c.key} style={[st.chip, c.key === best?.key && st.chipBest]}>
                        <T size={13} weight="bold">{c.key === best?.key ? '★ ' : ''}{lowDay(c.key)}</T>
                        <T size={13} weight="bold" color={colors.mint}>{c.free}/{c.sharing}</T>
                      </View>
                    ))}
                  </View>
                ) : null}
                <Button label={chosen.length ? `🗳️ Faire voter le groupe (${chosen.length} date${chosen.length > 1 ? 's' : ''})` : '🗳️ Faire voter le groupe'} onPress={poll} />
              </>
            ) : (
              <Button variant={best ? 'secondary' : 'primary'} label="🗳️ Faire voter le groupe" onPress={() => (sharing.length ? startVote() : poll())} />
            )}
            {!sharing.length || !data.i_share ? <Button variant="secondary" label="Partager les miennes" onPress={() => router.push(`/agenda/share?group=${group}` as Href)} /> : null}
            <Note>Party n’envoie aucun rappel aux membres.</Note>
          </View>
        </>
      ) : null}

      {opened ? (
        <DaySheet onClose={() => setOpen(null)} title={longDay(opened.key)} sub={`${mode === 'evening' ? 'Le soir' : 'La journée'} · ${MODES[mode].label} · ${gname}`}
          isBest={opened.key === best?.key} free={freeRows.length} total={sharing.length}>
          <PeopleSection title={`Disponibles · ${freeRows.length}`} rows={freeRows} day={opened.key} mode={mode} />
          {busyRows.length ? <PeopleSection title={`Occupés · ${busyRows.length}`} rows={busyRows} day={opened.key} mode={mode} /> : null}
          <Button label={`Organiser le ${lowDay(opened.key)}`} onPress={() => organise(opened)} />
          <Button variant="secondary" label="🗳️ Faire voter le groupe" onPress={() => startVote(opened.key)} />
        </DaySheet>
      ) : null}
    </Screen>
  );
}

/** Un mois : semaines lun → dim, depuis la semaine d'aujourd'hui ; chaque jour « n/6 » sur un vert plus ou moins plein. */
function MonthGrid({ month, today, last, byKey, best, need, word, picks, onTap }: {
  month: string; today: string; last: string; byKey: Map<string, Candidate>; best?: string; need: number; word: string;
  picks: string[]; onTap: (key: string) => void;
}) {
  const next = addMonths(month, 1);
  const first = weekStart(month < today ? today : month);
  const weeks: string[][] = [];
  for (let w = first; w < next; w = addDays(w, 7)) weeks.push(Array.from({ length: 7 }, (_, i) => addDays(w, i)));
  const good = [...byKey.values()].filter((c) => c.key >= month && c.key < next && c.free >= need).length;
  return (
    <View style={{ gap: 8 }} testID={`free-month-${month.slice(0, 7)}`}>
      <View style={{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' }}>
        <T size={20} weight="bold">{monthTitle(month, today)}</T>
        <T muted size={13}>{good} {word}{good > 1 ? 's' : ''} · {need} libre{need > 1 ? 's' : ''} ou plus</T>
      </View>
      <View style={st.weekRow}>
        {WEEK_HEAD.map((d, i) => <T key={d} size={12} weight="semibold" color={i >= 5 ? colors.lavender : colors.muted} style={st.head}>{d}</T>)}
      </View>
      {weeks.map((week) => (
        <View key={week[0]} style={st.weekRow}>
          {week.map((key) => {
            if (key < month || key >= next) return <View key={key} style={st.cellSlot} />;
            const c = byKey.get(key);
            const isToday = key === today;
            const on = picks.includes(key);
            if (!c) {
              return (
                <View key={key} style={st.cellSlot}>
                  <View style={[st.cell, st.cellOff, isToday && st.cellToday]}>
                    <T size={15} color={colors.muted} style={{ opacity: key < today || key > last ? 0.55 : 0.9 }}>{dayOfMonth(key)}</T>
                  </View>
                </View>
              );
            }
            const r = c.sharing ? c.free / c.sharing : 0;
            const dark = r >= 0.85;
            const isBest = key === best;
            return (
              <View key={key} style={st.cellSlot}>
                <Pressable accessibilityRole="button" testID={`free-card-${key}`} accessibilityState={{ selected: on }}
                  accessibilityLabel={`${isBest ? 'Le mieux : ' : ''}${isToday ? 'aujourd’hui, ' : ''}${longDay(key)}, ${c.free} disponible${c.free > 1 ? 's' : ''} sur ${c.sharing}`}
                  onPress={() => onTap(key)}
                  style={({ pressed }) => [st.cell, { backgroundColor: c.free ? `rgba(91,227,166,${(0.12 + 0.78 * r * r).toFixed(2)})` : colors.surface },
                    isToday && st.cellToday, isBest && st.cellBest, pressed && { opacity: 0.75 }, transition('opacity', duration.fast)]}>
                  <T size={15} weight="bold" color={dark ? colors.onMint : colors.text} style={{ fontVariant: ['tabular-nums'] }}>{dayOfMonth(key)}</T>
                  <T size={10} weight="semibold" color={dark ? colors.onMint : colors.textSoft} style={{ fontVariant: ['tabular-nums'] }}>{c.free}/{c.sharing}</T>
                  {isToday ? <View style={st.todayTag}><Text style={st.todayText}>auj.</Text></View> : null}
                  {on ? <View style={st.tick}><Text style={{ color: '#fff', fontSize: 11, ...font.bold }}>✓</Text></View> : null}
                </Pressable>
              </View>
            );
          })}
        </View>
      ))}
    </View>
  );
}

/** Feuille du bas d'un jour (SheetGesture : glisser vers le bas, ✕, fond qui ferme). */
function DaySheet({ onClose, title, sub, isBest, free, total, children }: {
  onClose: () => void; title: string; sub: string; isBest: boolean; free: number; total: number; children: React.ReactNode;
}) {
  const card = useRef<View>(null);
  const overlay = useRef<ScrollView>(null);
  const sheetTop = useSheetTop();
  useSheetDrag(true, onClose, card, overlay);
  useSheetSignal(true);
  return (
    <Modal visible transparent animationType="fade" onRequestClose={onClose}>
      <View style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={onClose} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel={title} testID="free-day-sheet">
          <SheetTop onClose={onClose} />
          <ScrollView ref={overlay} contentContainerStyle={{ gap: 12 }}>
            <View style={{ gap: 4 }}>
              <T size={22} weight="bold">{title}</T>
              <T muted size={13}>{sub}</T>
            </View>
            <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
              <View style={[st.sumFree, !free && { backgroundColor: colors.surface2 }]}><T size={14} weight="bold" color={free ? colors.mint : colors.textSoft}>{free ? '✓ ' : ''}{free} / {total} disponible{free > 1 ? 's' : ''}</T></View>
              {isBest ? <View style={st.sumBest}><T size={14} weight="bold" color={colors.accentSoft}>★ Le mieux</T></View> : null}
            </View>
            {children}
          </ScrollView>
        </View>
      </View>
    </Modal>
  );
}

const BAR_W = 104;

function PeopleSection({ title, rows, day, mode }: { title: string; rows: { m: FreeMember; s: ReturnType<typeof personState> }[]; day: string; mode: FreeMode }) {
  const cfg = MODES[mode];
  const ticks = cfg.ticks;
  return (
    <View style={{ gap: 4 }}>
      <Label right={<View style={{ width: BAR_W, flexDirection: 'row', justifyContent: 'space-between' }}>{ticks.map((t) => <T key={t} size={11} muted>{t}</T>)}</View>}>{title}</Label>
      {rows.map(({ m, s }) => {
        const bs = zdate(day, cfg.bar[0]).getTime();
        const be = zdate(day, cfg.bar[1]).getTime();
        const x = (ms: number) => ((ms - bs) / (be - bs)) * BAR_W;
        const label = `${m.me ? 'Toi' : m.name} : ${s.available ? s.text.toLowerCase() : `occupé ${s.text}`}`;
        return (
          <View key={m.id} style={st.person} accessibilityLabel={label} testID={`free-person-${m.id}`}>
            <Avatar id={m.id} name={m.name} photo={m.avatar_url} size={40} />
            <View style={{ flex: 1, minWidth: 0, gap: 3 }}>
              <T size={16} weight="semibold" numberOfLines={1}>{m.me ? 'Toi' : m.name}</T>
              {s.available ? <T size={13} weight="semibold" color={colors.mint} numberOfLines={1}>✓ {s.text}</T> : (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <View style={[st.busyTag, hatched]}><Text style={{ color: '#fff', fontSize: 12, ...font.bold }}>Occupé</Text></View>
                  <T size={13} color={colors.textSoft} numberOfLines={1}>{s.text}</T>
                </View>
              )}
            </View>
            <View style={st.bar} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
              {s.busyIn.map(([a, b]) => <View key={a} style={[st.barBusy, hatched, { left: x(a), width: Math.max(3, x(b) - x(a)) }]} />)}
              <View style={[st.barFrame, { left: x(zdate(day, cfg.core[0]).getTime()), width: x(zdate(day, cfg.core[1]).getTime()) - x(zdate(day, cfg.core[0]).getTime()) }]} />
            </View>
          </View>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  bubble: { width: 76, alignItems: 'center', gap: 6 },
  ring: { padding: 3, borderRadius: 40, borderWidth: 2.5, borderColor: 'transparent' },
  ringOn: { borderColor: colors.accent },
  seg: { flexDirection: 'row', padding: 3, gap: 2, borderRadius: 14, backgroundColor: colors.surface },
  segItem: { flex: 1, minHeight: 42, borderRadius: 11, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8,
    borderBottomWidth: 2, borderBottomColor: 'transparent' },
  segOn: { backgroundColor: colors.surface2, borderBottomColor: colors.accent },
  hint: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, borderRadius: radius.md, backgroundColor: colors.lavenderDim, flexWrap: 'wrap' },
  hintX: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  empty: { alignItems: 'center', gap: 10, padding: 22, borderRadius: radius.lg, backgroundColor: colors.surface },
  summary: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: radius.lg, backgroundColor: colors.mintDim,
    borderWidth: 1, borderColor: 'rgba(91,227,166,0.35)' },
  bestCard: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface,
    borderWidth: 1.5, borderColor: colors.accent, shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 14 },
  bestPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill, backgroundColor: colors.mint },
  voteBar: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingLeft: 14, borderRadius: radius.md, borderWidth: 1, borderColor: colors.accent, backgroundColor: colors.accentDim },
  voteCancel: { minHeight: 44, paddingHorizontal: 14, justifyContent: 'center' },
  weekRow: { flexDirection: 'row', gap: 5 },
  head: { flex: 1, textAlign: 'center' },
  cellSlot: { flex: 1, minWidth: 0 },
  cell: { height: 52, borderRadius: 12, alignItems: 'center', justifyContent: 'center', gap: 1, borderWidth: 2, borderColor: 'transparent' },
  cellOff: { backgroundColor: 'transparent' },
  cellToday: { borderColor: colors.text },
  cellBest: { borderColor: colors.accent, shadowColor: colors.accent, shadowOpacity: 0.6, shadowRadius: 10 },
  todayTag: { position: 'absolute', top: -8, paddingHorizontal: 4, borderRadius: 6, backgroundColor: colors.text },
  todayText: { color: colors.bg, fontSize: 9, ...font.bold },
  tick: { position: 'absolute', top: -6, right: -4, width: 18, height: 18, borderRadius: 9, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accent },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: { flexDirection: 'row', gap: 6, paddingHorizontal: 12, paddingVertical: 8, borderRadius: radius.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  chipBest: { borderColor: colors.accent },
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.86)', justifyContent: 'flex-end', alignItems: 'center' },
  sheet: { width: '100%', maxWidth: 520, maxHeight: '88%', gap: 8, padding: 20, paddingBottom: 28, borderTopLeftRadius: radius.lg, borderTopRightRadius: radius.lg,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  sumFree: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: 'rgba(91,227,166,0.14)' },
  sumBest: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.accent },
  person: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, borderBottomWidth: 1, borderBottomColor: colors.line },
  busyTag: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, borderWidth: 1, borderColor: 'rgba(185,167,255,0.6)' },
  bar: { width: BAR_W, height: 28, borderRadius: 8, backgroundColor: '#2F8A63', overflow: 'hidden' },
  barBusy: { position: 'absolute', top: 0, bottom: 0 },
  barFrame: { position: 'absolute', top: 2, bottom: 2, borderRadius: 7, borderWidth: 2, borderColor: '#fff' },
  othersRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 },
  other: { width: 56, alignItems: 'center', gap: 4 },
});
