import { router, type Href } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { T } from '@/components/ui';
import {
  addDays, dayAbbr, dayOfMonth, durationText, entriesOn, eveningFree, hm, isoWeekday, longDay, minutesOf, overlapOf,
  sameMonth, WEEK_LETTERS, weekStart, zdate, type DayKey, type Entry,
} from '@/lib/agenda';
import { duration, enter, pressTransition, transition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import { AnswerTag } from './Bits';

/**
 * Les trois vues de l'agenda (maquettes 2A, 2C, 2D) : la semaine en jours empilés (lisible en portrait), le jour avec ses
 * heures et ses trous « Libre », le mois dont le jour touché s'ouvre dessous. Chaque élément dit sa source en mots ; une
 * soirée Party dit la réponse en mots ; un sondage est en pointillé, « 🗳️ À voter ».
 */

type WebStyle = Record<string, unknown>;
const web = (s: WebStyle) => s as object;

/** Ouvrir un élément : rendez-vous → sa fiche ; soirée ou sondage → la fiche de l'événement. */
export function openEntry(e: Entry) {
  if (e.kind === 'item' && e.item) router.push(`/agenda/item?id=${e.item.id}&occ=${encodeURIComponent(e.start.toISOString())}` as Href);
  else if (e.eventId) router.push(`/event/${e.eventId}` as Href);
}

function entryLabel(e: Entry, all: Entry[]): string {
  const when = e.allDay ? 'toute la journée' : `${hm(e.start)} à ${hm(e.end)}`;
  const answer = e.kind === 'party' ? `, ${e.cancelled ? 'annulé' : e.answer === 'yes' ? 'Présent' : e.answer === 'maybe' ? 'Peut-être' : e.answer === 'no' ? 'Pas présent' : e.organizer ? 'tu organises' : 'à répondre'}` : '';
  const clash = overlapOf(e, all);
  return `${e.kind === 'poll' ? 'À voter : ' : ''}${e.title}, ${when}, ${e.source}${answer}${clash ? `, en même temps que ${clash.title}` : ''}`;
}

/** Carte d'une soirée Party (dégradé, emoji, « 21:00 · Chez Chloé », réponse en mots). */
export function PartyCard({ e, compact }: { e: Entry; compact?: boolean }) {
  const poll = e.kind === 'poll';
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={entryLabel(e, [])} onPress={() => openEntry(e)}
      style={({ pressed }) => [poll ? st.pollCard : st.partyCard, compact && { paddingVertical: 10 }, pressTransition, pressed && { opacity: 0.85 }]}>
      <View style={[st.icon, poll && { backgroundColor: 'rgba(255,79,154,0.12)' }]}><Text style={{ fontSize: 20 }}>{poll ? '🗳️' : e.icon || '🎉'}</Text></View>
      <View style={{ flex: 1, minWidth: 0, gap: 3 }}>
        <T weight="bold" size={16} numberOfLines={2}>{e.title}</T>
        <T size={13} color={colors.textSoft} numberOfLines={1}>{e.allDay ? 'Toute la journée' : hm(e.start)}{e.place ? ` · ${e.place}` : ''}</T>
        {poll ? <View style={st.vote}><Text style={{ color: colors.accentSoft, fontSize: 13, ...font.bold }}>🗳️ À voter</Text></View>
          : <AnswerTag answer={e.answer} organizer={e.organizer} cancelled={e.cancelled} />}
      </View>
    </Pressable>
  );
}

/** Ligne d'un rendez-vous dans la semaine : heure, filet de la couleur du calendrier ET son nom écrit. */
function WeekLine({ e, all, past }: { e: Entry; all: Entry[]; past: boolean }) {
  const clash = overlapOf(e, all);
  const tappable = e.kind === 'item';
  return (
    <Pressable accessibilityRole={tappable ? 'link' : 'text'} accessibilityLabel={entryLabel(e, all)} disabled={!tappable} onPress={() => openEntry(e)}
      style={({ pressed }) => [st.line, past && { opacity: 0.55 }, pressed && { opacity: 0.7 }]}>
      <T size={15} color={colors.textSoft} style={st.lineTime}>{e.allDay ? 'Journée' : hm(e.start)}</T>
      <View style={[st.bar, { backgroundColor: e.color }]} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <T size={16} weight="semibold" numberOfLines={2}>{e.title}</T>
        {clash ? <T size={12} color={colors.coralSoft}>⚠️ En même temps que « {clash.title} »</T> : null}
      </View>
      <T size={12} muted numberOfLines={1} style={{ maxWidth: 110, textAlign: 'right' }}>{e.source.split(' · ')[0]}</T>
    </Pressable>
  );
}

/** Semaine : un jour par ligne (jamais 7 colonnes coupées en portrait). */
export function WeekView({ start, entries, today, empty }: { start: DayKey; entries: Entry[]; today: DayKey; empty: boolean }) {
  const days = Array.from({ length: 7 }, (_, i) => addDays(start, i));
  return (
    <View testID="agenda-week">
      {days.map((key, i) => {
        const list = entriesOn(entries, key);
        const isToday = key === today;
        const past = key < today;
        const party = list.filter((e) => e.kind === 'party' || e.kind === 'poll');
        const lines = list.filter((e) => e.kind !== 'party' && e.kind !== 'poll');
        const free = !past && eveningFree(entries, key);
        return (
          <View key={key} style={[st.dayRow, i > 0 && st.dayRowLine, enter('rise', i)]} testID={`week-day-${key}`}>
            <View style={st.dayHead} accessibilityLabel={`${isToday ? 'Aujourd’hui, ' : ''}${longDay(key)}`}>
              <T size={12} weight="bold" color={isToday ? colors.accent : colors.muted} style={{ letterSpacing: 0.6 }}>{dayAbbr(key)}</T>
              <View style={[st.dayNum, isToday && st.dayNumToday]}>
                <T size={20} weight="bold" color={isToday ? '#fff' : past ? colors.muted : colors.text}>{dayOfMonth(key)}</T>
              </View>
            </View>
            <View style={{ flex: 1, minWidth: 0, gap: 8 }}>
              {lines.map((e) => <WeekLine key={e.key} e={e} all={list} past={past} />)}
              {party.map((e) => <PartyCard key={e.key} e={e} />)}
              {free ? (
                <Pressable accessibilityRole="button" accessibilityLabel={`${longDay(key)} : soirée libre. Ajouter un rendez-vous`}
                  onPress={() => router.push(`/agenda/item?day=${key}&from=19:00` as Href)}
                  style={({ pressed }) => [st.freeChip, pressed && { opacity: 0.7 }]}>
                  <Text style={{ color: colors.lavender, fontSize: 14, ...font.semibold }}>🌙 {empty ? 'Libre' : 'Soirée libre'}</Text>
                </Pressable>
              ) : null}
              {!list.length && !free ? <T muted size={14} style={{ paddingVertical: 8 }}>—</T> : null}
            </View>
          </View>
        );
      })}
    </View>
  );
}

/** Bande des 7 jours (vue Jour) : le jour choisi en rond néon, des points pour les jours occupés. */
export function DayStrip({ selected, entries, today, onPick }: { selected: DayKey; entries: Entry[]; today: DayKey; onPick: (k: DayKey) => void }) {
  const start = weekStart(selected);
  return (
    <View style={st.strip} accessibilityRole="tablist">
      {Array.from({ length: 7 }, (_, i) => addDays(start, i)).map((key) => {
        const on = key === selected;
        const dots = entriesOn(entries, key).slice(0, 3);
        return (
          <Pressable key={key} accessibilityRole="tab" aria-selected={on} accessibilityState={{ selected: on }}
            accessibilityLabel={`${key === today ? 'Aujourd’hui, ' : ''}${longDay(key)}`} onPress={() => onPick(key)} style={st.stripDay}>
            <T size={11} weight="bold" color={key === today ? colors.accent : colors.muted}>{dayAbbr(key)}</T>
            <View style={[st.stripNum, on && st.stripOn, transition('background-color', duration.fast)]}>
              <T size={17} weight="bold" color={on ? '#fff' : key === today ? colors.accent : colors.text}>{dayOfMonth(key)}</T>
            </View>
            <View style={{ flexDirection: 'row', gap: 2, height: 5 }}>
              {dots.map((e) => <View key={e.key} style={[st.dot, { backgroundColor: e.color }]} />)}
            </View>
          </Pressable>
        );
      })}
    </View>
  );
}

const HOUR = 52;

type Placed = { e: Entry; top: number; height: number; col: number; cols: number };

/** Vue Jour : les heures, les rendez-vous à leur place, et les trous « Libre · 1 h  + Ajouter » (jamais une zone vide muette). */
export function DayTimeline({ day, entries, today }: { day: DayKey; entries: Entry[]; today: DayKey }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 60_000); return () => clearInterval(t); }, []);
  const list = entriesOn(entries, day);
  const allDay = list.filter((e) => e.allDay);
  const timed = list.filter((e) => !e.allDay);
  const dayStart = zdate(day).getTime();
  const dayEnd = zdate(addDays(day, 1)).getTime();
  const firstMin = timed.reduce((m, e) => Math.min(m, e.start.getTime() <= dayStart ? 0 : minutesOf(e.start)), 8 * 60);
  const startH = Math.floor(firstMin / 60);
  const y = (ms: number) => ((Math.max(dayStart, Math.min(dayEnd, ms)) - dayStart) / 60000 / 60 - startH) * HOUR;

  const placed = useMemo(() => {
    const sorted = [...timed].sort((a, b) => a.start.getTime() - b.start.getTime());
    const out: Placed[] = [];
    let cluster: Placed[] = [];
    let clusterEnd = 0;
    const flush = () => { const n = Math.max(1, ...cluster.map((p) => p.col + 1)); cluster.forEach((p) => { p.cols = n; }); cluster = []; };
    for (const e of sorted) {
      if (e.start.getTime() >= clusterEnd) flush();
      const used = new Set(cluster.filter((p) => p.e.end.getTime() > e.start.getTime()).map((p) => p.col));
      let col = 0;
      while (used.has(col)) col++;
      const p = { e, top: y(e.start.getTime()), height: Math.max(30, y(e.end.getTime()) - y(e.start.getTime()) - 3), col, cols: 1 };
      cluster.push(p);
      out.push(p);
      clusterEnd = Math.max(clusterEnd, e.end.getTime());
    }
    flush();
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries, day]);

  // Trous d'au moins 1 h (de 8 h, ou de maintenant, à minuit) : « Libre · 1 h » et « + Ajouter » (heure déjà remplie).
  const gaps = useMemo(() => {
    const busy = timed.filter((e) => e.kind !== 'poll' && e.busy).map((e) => [e.start.getTime(), e.end.getTime()] as [number, number])
      .sort((a, b) => a[0] - b[0]);
    const half = 30 * 60000;
    let cursor = Math.max(zdate(day, 8 * 60).getTime(), Math.ceil(now / half) * half);
    const out: [number, number][] = [];
    for (const [s, e] of busy) {
      if (s - cursor >= 3600_000) out.push([cursor, s]);
      cursor = Math.max(cursor, e);
    }
    if (dayEnd - cursor >= 3600_000) out.push([cursor, dayEnd]);
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [entries, day, now]);

  const hours = Array.from({ length: 24 - startH + 1 }, (_, i) => startH + i);
  const height = (24 - startH) * HOUR;
  return (
    <View style={{ gap: 8 }} testID="agenda-day">
      {allDay.map((e) => (e.kind === 'party' ? <PartyCard key={e.key} e={e} compact /> : (
        <Pressable key={e.key} accessibilityRole="link" accessibilityLabel={entryLabel(e, list)} onPress={() => openEntry(e)}
          style={[st.allDay, { borderLeftColor: e.color }]}>
          <T weight="semibold">{e.title}</T><T muted size={12}>Toute la journée · {e.source}</T>
        </Pressable>
      )))}
      <View style={{ height, marginLeft: 46, position: 'relative' }}>
        {hours.map((h) => (
          <View key={h} pointerEvents="none" style={[st.hourLine, { top: (h - startH) * HOUR }]}>
            <T size={11} color={colors.muted} style={st.hourText}>{`${String(h % 24).padStart(2, '0')}:00`}</T>
          </View>
        ))}
        {gaps.map(([s, e]) => {
          const evening = minutesOf(new Date(s)) >= 18 * 60;
          const mins = Math.round((e - s) / 60000);
          const label = `${evening ? '🌙 ' : ''}Libre · ${durationText(mins)}`;
          const from = hm(new Date(s));
          return (
            <View key={s} style={[st.gap, { top: y(s) + 2, height: Math.max(44, y(e) - y(s) - 4) }]}>
              <Text style={{ color: colors.textSoft, fontSize: 14, ...font.semibold, flex: 1 }}>{label}</Text>
              <Pressable accessibilityRole="button" accessibilityLabel={`Libre de ${from} à ${hm(new Date(e))}. Ajouter un rendez-vous`}
                onPress={() => router.push(`/agenda/item?day=${day}&from=${from}` as Href)}
                style={({ pressed }) => [st.gapAdd, pressTransition, pressed && { opacity: 0.8 }]}>
                <Text style={{ color: colors.text, fontSize: 14, ...font.bold }}>+ Ajouter</Text>
              </Pressable>
            </View>
          );
        })}
        {placed.map(({ e, top, height: h, col, cols }) => {
          const party = e.kind === 'party';
          const poll = e.kind === 'poll';
          const clash = overlapOf(e, list);
          return (
            <Pressable key={e.key} accessibilityRole={e.kind === 'item' || party || poll ? 'link' : 'text'} accessibilityLabel={entryLabel(e, list)}
              disabled={!(e.kind === 'item' || party || poll)} onPress={() => openEntry(e)}
              style={[st.block, { top, height: h, left: `${(col / cols) * 100}%`, width: `${100 / cols}%` } as object,
                party ? st.blockParty : poll ? st.blockPoll : { backgroundColor: `${e.color}33`, borderLeftColor: e.color }]}>
              <T size={party ? 17 : 14} weight="bold" numberOfLines={h > 60 ? 2 : 1} color={party ? '#fff' : colors.text}>{poll ? '🗳️ ' : ''}{e.title}</T>
              {h > 40 ? (
                <T size={12} color={party ? 'rgba(255,255,255,0.9)' : colors.textSoft} numberOfLines={1}>
                  {party ? `${hm(e.start)} – ${hm(e.end)}${e.place ? ` · ${e.place}` : ''}` : `${e.source} · ${hm(e.start)} – ${hm(e.end)}`}
                </T>
              ) : null}
              {party && h > 76 ? <AnswerTag answer={e.answer} organizer={e.organizer} cancelled={e.cancelled} /> : null}
              {clash && h > 60 && !party ? <T size={11} color={colors.coralSoft}>⚠️ En même temps que « {clash.title} »</T> : null}
            </Pressable>
          );
        })}
        {day === today && now >= dayStart && now < dayEnd ? (
          <View pointerEvents="none" style={[st.nowLine, { top: y(now) }]} accessibilityLabel={`Maintenant, ${hm(new Date(now))}`}>
            <View style={st.nowDot} />
          </View>
        ) : null}
      </View>
    </View>
  );
}

/** Mois : grille, points (jamais lus un à un), emoji des soirées ; le jour touché s'ouvre dessous. */
export function MonthView({ month, entries, today, selected, onPick }: {
  month: DayKey; entries: Entry[]; today: DayKey; selected: DayKey; onPick: (k: DayKey) => void;
}) {
  const start = weekStart(month);
  const days = Array.from({ length: 42 }, (_, i) => addDays(start, i));
  const weeks = Array.from({ length: 6 }, (_, w) => days.slice(w * 7, w * 7 + 7)).filter((w, i) => i < 5 || sameMonth(w[0], month));
  const list = entriesOn(entries, selected);
  return (
    <View style={{ gap: 14 }} testID="agenda-month">
      <View>
        <View style={st.monthHead}>
          {WEEK_LETTERS.map((_, i) => (
            <T key={i} size={11} weight="bold" color={colors.muted} style={st.monthHeadCell}>{['LUN', 'MAR', 'MER', 'JEU', 'VEN', 'SAM', 'DIM'][i]}</T>
          ))}
        </View>
        {weeks.map((w) => (
          <View key={w[0]} style={st.monthRow}>
            {w.map((key) => {
              const own = sameMonth(key, month);
              const day = entriesOn(entries, key);
              const party = day.find((e) => e.kind === 'party');
              const on = key === selected;
              const isToday = key === today;
              const weekend = isoWeekday(key) >= 6;
              const said = day.filter((e) => e.kind === 'party').map((e) => `${e.title}${e.answer === 'yes' ? ', Présent' : ''}`).join(', ');
              return (
                <Pressable key={key} accessibilityRole="button" accessibilityState={{ selected: on }}
                  accessibilityLabel={`${isToday ? 'Aujourd’hui, ' : ''}${longDay(key)}, ${day.length ? `${day.length} moment${day.length > 1 ? 's' : ''}` : 'rien'}${said ? `, dont ${said}` : ''}`}
                  onPress={() => onPick(key)} style={[st.monthCell, weekend && { backgroundColor: 'rgba(255,255,255,0.025)' }]}>
                  <View style={[st.monthNum, isToday && st.dayNumToday, on && !isToday && st.monthSel]}>
                    <T size={16} weight={isToday || on ? 'bold' : 'medium'} color={isToday ? '#fff' : own ? colors.text : colors.muted}>{dayOfMonth(key)}</T>
                  </View>
                  <View style={{ flexDirection: 'row', gap: 3, height: 6 }}>
                    {day.slice(0, 3).map((e) => (
                      <View key={e.key} style={[st.dot, e.kind === 'poll' ? { borderWidth: 1.5, borderColor: colors.accent } : { backgroundColor: e.color }]} />
                    ))}
                  </View>
                  {party ? <Text style={st.monthIcon} accessibilityElementsHidden>{party.icon || '🎉'}</Text> : null}
                </Pressable>
              );
            })}
          </View>
        ))}
      </View>
      <View style={{ gap: 8 }} testID="month-day">
        <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 8 }}>
          <T size={19} weight="bold">{longDay(selected).replace(/ \S+$/, '')}</T>
          <T muted size={13}>{list.length ? `${list.length} moment${list.length > 1 ? 's' : ''}` : 'rien de prévu'}</T>
        </View>
        {list.map((e) => (e.kind === 'party' || e.kind === 'poll' ? <PartyCard key={e.key} e={e} compact /> : (
          <Pressable key={e.key} accessibilityRole={e.kind === 'item' ? 'link' : 'text'} accessibilityLabel={entryLabel(e, list)}
            disabled={e.kind !== 'item'} onPress={() => openEntry(e)}
            style={({ pressed }) => [st.moment, { borderLeftColor: e.color }, pressed && { opacity: 0.8 }]}>
            <View style={{ width: 48 }}>
              <T size={14} weight="bold">{e.allDay ? 'Jour' : hm(e.start)}</T>
              {!e.allDay ? <T size={12} muted>{hm(e.end)}</T> : null}
            </View>
            <View style={{ flex: 1, minWidth: 0 }}>
              <T size={15} weight="semibold" numberOfLines={2}>{e.title}</T>
              <T size={12} muted numberOfLines={1}>{e.source}</T>
            </View>
          </Pressable>
        )))}
        {!list.length ? (
          <Pressable accessibilityRole="button" onPress={() => router.push(`/agenda/item?day=${selected}` as Href)} style={st.freeChip}>
            <Text style={{ color: colors.lavender, fontSize: 14, ...font.semibold }}>🌙 Libre · + Ajouter un rendez-vous</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  dayRow: { flexDirection: 'row', gap: 14, paddingVertical: 12 },
  dayRowLine: { borderTopWidth: 1, borderTopColor: colors.line },
  dayHead: { width: 44, alignItems: 'center', gap: 4 },
  dayNum: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  dayNumToday: { backgroundColor: colors.accent, shadowColor: colors.accent, shadowOpacity: 0.5, shadowRadius: 10 },
  line: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 36 },
  lineTime: { width: 48, fontVariant: ['tabular-nums'] },
  bar: { width: 3, alignSelf: 'stretch', borderRadius: 2, minHeight: 22 },
  partyCard: web({ flexDirection: 'row', gap: 12, alignItems: 'center', padding: 12, borderRadius: radius.lg, borderWidth: 1,
    borderColor: 'rgba(255,79,154,0.45)', backgroundColor: '#3A1C45',
    backgroundImage: 'linear-gradient(135deg, rgba(255,79,154,0.30), rgba(120,60,160,0.25))' }),
  pollCard: { flexDirection: 'row', gap: 12, alignItems: 'center', padding: 12, borderRadius: radius.lg, borderWidth: 1.5,
    borderStyle: 'dashed', borderColor: 'rgba(255,79,154,0.6)', backgroundColor: 'rgba(255,79,154,0.05)' },
  icon: { width: 44, height: 44, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.14)', alignItems: 'center', justifyContent: 'center' },
  vote: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 3, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.accent },
  freeChip: { alignSelf: 'flex-start', minHeight: 40, paddingHorizontal: 12, justifyContent: 'center', borderRadius: 12, borderWidth: 1,
    borderStyle: 'dashed', borderColor: 'rgba(185,167,255,0.5)' },
  strip: { flexDirection: 'row', justifyContent: 'space-between' },
  stripDay: { flex: 1, alignItems: 'center', gap: 4, minHeight: 64, paddingVertical: 2 },
  stripNum: { width: 38, height: 38, borderRadius: 19, alignItems: 'center', justifyContent: 'center' },
  stripOn: { backgroundColor: colors.accent, shadowColor: colors.accent, shadowOpacity: 0.55, shadowRadius: 12 },
  dot: { width: 6, height: 6, borderRadius: 3 },
  hourLine: { position: 'absolute', left: 0, right: 0, height: 1, backgroundColor: colors.line },
  hourText: { position: 'absolute', left: -46, top: -7, width: 40, textAlign: 'right' },
  gap: { position: 'absolute', left: 0, right: 0, flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 12,
    borderRadius: 12, borderWidth: 1, borderStyle: 'dashed', borderColor: 'rgba(185,167,255,0.45)', backgroundColor: 'rgba(21,16,42,0.85)' },
  gapAdd: { minHeight: 36, paddingHorizontal: 12, borderRadius: radius.pill, backgroundColor: colors.surface2, justifyContent: 'center' },
  block: { position: 'absolute', padding: 8, borderRadius: 10, borderLeftWidth: 3, gap: 2, overflow: 'hidden' },
  blockParty: web({ borderLeftWidth: 0, backgroundColor: colors.accent, backgroundImage: 'linear-gradient(135deg, #FF6FAE, #D92A73)',
    shadowColor: colors.accent, shadowOpacity: 0.4, shadowRadius: 14 }),
  blockPoll: { borderLeftWidth: 0, borderWidth: 1.5, borderStyle: 'dashed', borderColor: colors.accent, backgroundColor: 'rgba(255,79,154,0.08)' },
  allDay: { padding: 10, borderRadius: 10, borderLeftWidth: 3, backgroundColor: colors.surface },
  nowLine: { position: 'absolute', left: -4, right: 0, height: 2, backgroundColor: colors.accent },
  nowDot: { position: 'absolute', left: -4, top: -4, width: 10, height: 10, borderRadius: 5, backgroundColor: colors.accent },
  monthHead: { flexDirection: 'row', paddingBottom: 6 },
  monthHeadCell: { flex: 1, textAlign: 'center' },
  monthRow: { flexDirection: 'row', borderTopWidth: 1, borderTopColor: colors.line },
  monthCell: { flex: 1, minHeight: 52, alignItems: 'center', paddingTop: 6, gap: 3 },
  monthNum: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
  monthSel: { borderWidth: 2, borderColor: colors.accent },
  monthIcon: { position: 'absolute', top: 0, right: 2, fontSize: 12 },
  moment: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 12, borderRadius: 14, backgroundColor: colors.surface, borderLeftWidth: 3 },
});
