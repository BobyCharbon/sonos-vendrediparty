import { router, useLocalSearchParams, type Href } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Label, Note, hatched, TopBar } from '@/components/agenda/Bits';
import { GroupTile } from '@/components/GroupBits';
import { Avatar, Button, ErrorText, Screen, Skeleton, T } from '@/components/ui';
import {
  addMonths, dayKey, MODES, monthShort, monthStart, personState, rankDays, rpc, savePrefs, shortDay, tinyDay, zdate,
  type Candidate, type FreeMember, type FreeMode, type GroupFree, type Prefs, type Sharing,
} from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { groupName } from '@/lib/groups';
import { duration, enter, transition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/**
 * « Qui est libre ? » (maquettes 5A, 5B, 7C) : un groupe, le soir ou la journée, ce mois-ci ou le suivant. Cartes « Le
 * mieux » (dès 3 personnes qui partagent) puis « Ensuite » ; une ligne par personne qui partage (Disponible / Occupé, en
 * mots, et une barre rayée) ; « Les autres membres » grisés, sans aucun texte. On ne compte que ceux qui partagent.
 * Fin : « Organiser le sam. 28 » (création d'événement, groupe et date remplis) ou « Faire voter le groupe (3 dates) ».
 */
export default function FreeScreen() {
  const me = useMe();
  const p = useLocalSearchParams<{ group?: string }>();
  const today = dayKey(new Date());
  const [modePick, setMode] = useState<FreeMode | null>(null);
  const [month, setMonth] = useState(0);
  const [picked, setPicked] = useState<string | null>(typeof p.group === 'string' ? p.group : null);
  const [chosen, setChosen] = useState<string | null>(null);
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

  const [from, days] = useMemo(() => {
    const now = new Date();
    if (!month) return [now, Math.max(1, Math.ceil((zdate(addMonths(today, 1)).getTime() - now.getTime()) / 86400_000))];
    const start = zdate(addMonths(today, 1));
    return [start, Math.round((zdate(addMonths(today, 2)).getTime() - start.getTime()) / 86400_000)];
  }, [month, today]);
  const free = useQuery(async () => (group ? rpc<GroupFree>('agenda_group_free', { grp: group, from_ts: from.toISOString(), days }) : null), [group, from.getTime(), days]);
  useSignal([`user:${me.id}`], () => { void base.reload(); void free.reload(); });

  const data = free.data;
  const sharing = data?.members.filter((m) => m.shares) ?? [];
  const others = data?.members.filter((m) => !m.shares) ?? [];
  const ranked = useMemo(() => (data ? rankDays(data, mode).filter((c) => c.free > 0) : []), [data, mode]);
  const cards = ranked.slice(0, 6);
  const current: Candidate | undefined = cards.find((c) => c.key === chosen) ?? cards[0];
  const vote = [...ranked.slice(0, 3)].sort((a, b) => a.start.getTime() - b.start.getTime());
  const best = sharing.length >= 3;
  const states = current ? sharing.map((m) => ({ m, s: personState(m, current.key, mode) })) : [];
  const freeRows = states.filter((x) => x.s.available);
  const busyRows = states.filter((x) => !x.s.available);
  const gname = data ? groupName(data.group) : '';

  function choose(g: string) {
    setPicked(g);
    setChosen(null);
    void savePrefs({ free_group: g });
  }
  function organise() {
    if (!current || !group) return;
    const q = `group=${group}&title=${encodeURIComponent(`Soirée ${gname}`)}&start=${encodeURIComponent(current.start.toISOString())}&end=${encodeURIComponent(current.end.toISOString())}`;
    router.push(`/event/new?${q}` as Href);
  }
  function poll() {
    if (!group) return;
    const dates = vote.map((c) => c.start.toISOString()).join(',');
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
        <View style={st.filters}>
          <View style={[st.seg, { flex: 1 }]} accessibilityRole="radiogroup" accessibilityLabel="Moment">
            {(['evening', 'day'] as FreeMode[]).map((k) => (
              <Pressable key={k} accessibilityRole="radio" aria-checked={mode === k} accessibilityState={{ checked: mode === k }} onPress={() => { setMode(k); setChosen(null); void savePrefs({ free_mode: k }); }}
                style={[st.segItem, mode === k && st.segOn, transition('background-color', duration.fast)]}>
                <Text numberOfLines={1} style={{ color: mode === k ? colors.text : colors.textSoft, fontSize: 13, ...font.semibold }}>{k === 'evening' ? '🌙 Le soir' : 'La journée'}</Text>
              </Pressable>
            ))}
          </View>
          <View style={st.seg} accessibilityRole="radiogroup" accessibilityLabel="Mois">
            {[0, 1].map((k) => (
              <Pressable key={k} accessibilityRole="radio" aria-checked={month === k} accessibilityLabel={k ? 'Le mois prochain' : 'Ce mois-ci'} accessibilityState={{ checked: month === k }}
                onPress={() => { setMonth(k); setChosen(null); }} style={[st.segItem, { flex: 0, minWidth: 54, paddingHorizontal: 10 }, month === k && st.segOn]}>
                <Text style={{ color: month === k ? colors.text : colors.textSoft, fontSize: 14, ...font.semibold }}>{monthShort(addMonths(monthStart(today), k))}</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : null}

      {group && !data && !free.error ? <Skeleton height={140} radius={radius.lg} /> : null}

      {data ? (
        <>
          {sharing.length ? (
            <View style={st.who}>
              <View style={{ flexDirection: 'row' }}>
                {sharing.slice(0, 7).map((m, i) => (
                  <View key={m.id} style={{ marginLeft: i ? -8 : 0, borderRadius: 99, borderWidth: 2, borderColor: colors.surface }}>
                    <Avatar id={m.id} name={m.name} photo={m.avatar_url} size={28} profile={false} />
                  </View>
                ))}
              </View>
              <View style={{ flex: 1 }}>
                <T size={15} weight="bold">{sharing.length} personne{sharing.length > 1 ? 's' : ''} partage{sharing.length > 1 ? 'nt' : ''}</T>
                <T muted size={13}>leurs dispos avec ce groupe</T>
              </View>
            </View>
          ) : null}

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
          ) : null}

          {sharing.length && !cards.length ? <T muted style={{ textAlign: 'center', padding: 12 }}>Aucun {mode === 'evening' ? 'soir' : 'jour'} où quelqu’un est disponible sur cette période.</T> : null}

          {cards.length ? (
            <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -16, flexGrow: 0 }}
              contentContainerStyle={{ gap: 10, paddingHorizontal: 16 }}>
              {cards.map((c, i) => {
                const on = c === current;
                const top = i === 0 && best;
                return (
                  <Pressable key={c.key} accessibilityRole="button" accessibilityState={{ selected: on }} testID={`free-card-${c.key}`}
                    accessibilityLabel={`${top ? 'Le mieux : ' : ''}${shortDay(c.key)}, ${MODES[mode].core[0] / 60} h à ${MODES[mode].core[1] / 60} h, ${c.free} disponible${c.free > 1 ? 's' : ''} sur ${c.sharing}`}
                    onPress={() => setChosen(c.key)}
                    style={[st.card, top && st.cardBest, on && st.cardOn, enter('rise', i), transition('border-color, background-color', duration.fast)]}>
                    <T size={12} weight="bold" color={top ? '#FFD36B' : colors.muted} style={{ letterSpacing: 0.8 }}>{top ? '★ LE MIEUX' : 'ENSUITE'}</T>
                    <T size={20} weight="bold">{shortDay(c.key)}</T>
                    <T size={14} color={colors.textSoft}>{`${MODES[mode].core[0] / 60} h – ${MODES[mode].core[1] / 60} h`}</T>
                    <T size={13} weight="bold" color={colors.mint}>✓ {c.free} disponible{c.free > 1 ? 's' : ''} <Text style={{ color: colors.muted, ...font.medium }}>sur {c.sharing}</Text></T>
                  </Pressable>
                );
              })}
            </ScrollView>
          ) : null}

          {sharing.length && sharing.length < 3 && data.members.length > sharing.length ? (
            <Note>Seulement {sharing.length} sur {data.members.length} partagent : il manque des infos.</Note>
          ) : null}

          {current ? (
            <>
              <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
                <View style={st.sumFree}><T size={14} weight="bold" color={colors.mint}>✓ {freeRows.length} disponible{freeRows.length > 1 ? 's' : ''} sur {sharing.length}</T></View>
                {busyRows.length ? <View style={st.sumBusy}><View style={[st.miniHatch, hatched]} /><T size={14} weight="bold">{busyRows.length} occupé{busyRows.length > 1 ? 's' : ''}</T></View> : null}
                <T muted size={13}>· {tinyDay(current.key)}</T>
              </View>
              <PeopleSection title={`Disponibles · ${freeRows.length}`} rows={freeRows} day={current.key} mode={mode} />
              {busyRows.length ? <PeopleSection title={`Occupés · ${busyRows.length}`} rows={busyRows} day={current.key} mode={mode} /> : null}
            </>
          ) : null}

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
            {current ? <Button label={`Organiser le ${tinyDay(current.key)}`} onPress={organise} /> : null}
            <Button variant={current ? 'secondary' : 'primary'} label={vote.length >= 2 ? `🗳️ Faire voter le groupe (${vote.length} dates)` : '🗳️ Faire voter le groupe'} onPress={poll} />
            {!sharing.length || !data.i_share ? <Button variant="secondary" label="Partager les miennes" onPress={() => router.push(`/agenda/share?group=${group}` as Href)} /> : null}
            <Note>Party n’envoie aucun rappel aux membres.</Note>
          </View>
        </>
      ) : null}
    </Screen>
  );
}

const BAR_W = 104;

function PeopleSection({ title, rows, day, mode }: { title: string; rows: { m: FreeMember; s: ReturnType<typeof personState> }[]; day: string; mode: FreeMode }) {
  const cfg = MODES[mode];
  const ticks = mode === 'evening' ? ['18 h', '21 h', '0 h'] : ['8 h', '16 h', '0 h'];
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
  filters: { flexDirection: 'row', gap: 8 },
  seg: { flexDirection: 'row', padding: 3, gap: 2, borderRadius: 14, backgroundColor: colors.surface },
  segItem: { flex: 1, minHeight: 42, borderRadius: 11, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8,
    borderBottomWidth: 2, borderBottomColor: 'transparent' },
  segOn: { backgroundColor: colors.surface2, borderBottomColor: colors.accent },
  who: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: radius.lg, backgroundColor: colors.surface },
  hint: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 12, borderRadius: radius.md, backgroundColor: colors.lavenderDim, flexWrap: 'wrap' },
  hintX: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  empty: { alignItems: 'center', gap: 10, padding: 22, borderRadius: radius.lg, backgroundColor: colors.surface },
  card: { width: 180, gap: 4, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1.5, borderColor: colors.line },
  cardBest: { backgroundColor: '#3A2340', borderColor: 'rgba(255,211,107,0.5)' },
  cardOn: { borderColor: '#FFD36B', shadowColor: '#FFD36B', shadowOpacity: 0.3, shadowRadius: 14 },
  sumFree: { paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: 'rgba(91,227,166,0.14)' },
  sumBusy: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 12, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.surface2 },
  miniHatch: { width: 14, height: 14, borderRadius: 3 },
  person: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, borderBottomWidth: 1, borderBottomColor: colors.line },
  busyTag: { paddingHorizontal: 6, paddingVertical: 2, borderRadius: 6, borderWidth: 1, borderColor: 'rgba(185,167,255,0.6)' },
  bar: { width: BAR_W, height: 28, borderRadius: 8, backgroundColor: '#2F8A63', overflow: 'hidden' },
  barBusy: { position: 'absolute', top: 0, bottom: 0 },
  barFrame: { position: 'absolute', top: 2, bottom: 2, borderRadius: 7, borderWidth: 2, borderColor: '#fff' },
  othersRow: { flexDirection: 'row', flexWrap: 'wrap', gap: 14 },
  other: { width: 56, alignItems: 'center', gap: 4 },
});

