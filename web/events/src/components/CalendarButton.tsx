import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { calendarPlatform, googleCalendarUrl, icsUrl, nativeCalendar, openGoogleCalendar, openIcs, pollDatesIcsUrl, upcomingDates } from '@/lib/calendar';
import { duration, enter, pressTransition, transition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import type { EventRow } from '@/lib/types';

import { T } from './ui';

type Ev = Pick<EventRow, 'id' | 'title' | 'description' | 'starts_at' | 'ends_at' | 'location_name' | 'location_address'>;

/**
 * Ajout à l’agenda en un geste :
 * iPhone/iPad → feuille « Ajouter au calendrier » d’Apple ; Android → Google Agenda ;
 * ordinateur → choix entre fichier .ics (Apple, Outlook) et Google Agenda.
 */
export function CalendarButton({ event, prominent = false }: { event: Ev; prominent?: boolean }) {
  const [platform] = useState(calendarPlatform);
  const [choices, setChoices] = useState(false);
  const ics = icsUrl(event);
  const google = googleCalendarUrl(event);
  if (!ics || !google) return null;

  const primary = () => {
    if (platform === 'ios') openIcs(ics);
    else if (platform === 'android') openGoogleCalendar(google);
    else setChoices((v) => !v);
  };
  const alt = platform === 'ios'
    ? { label: 'Google Agenda', run: () => openGoogleCalendar(google) }
    : platform === 'android'
      ? { label: 'Autre agenda (.ics)', run: () => openIcs(ics) }
      : null;

  return (
    <View style={{ gap: 8 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Ajouter à mon agenda"
        accessibilityState={{ expanded: platform === 'desktop' ? choices : undefined }}
        onPress={primary}
        style={({ pressed }) => [st.button, transition('background-color, border-color, transform, opacity', duration.slow), prominent ? st.prominent : st.quiet, pressed && { opacity: 0.8, transform: [{ scale: 0.98 }] }]}
      >
        <T size={17}>📆</T>
        <T size={15} style={{ ...font.bold }} color={prominent ? colors.onAccent : colors.text}>Ajouter à mon agenda</T>
      </Pressable>
      {platform === 'desktop' && choices ? (
        <View style={[{ flexDirection: 'row', gap: 8 }, enter('drop')]}>
          <Choice label="Apple · Outlook (.ics)" onPress={() => openIcs(ics)} />
          <Choice label="Google Agenda" onPress={() => openGoogleCalendar(google)} />
        </View>
      ) : null}
      {alt ? (
        <Pressable accessibilityRole="button" onPress={alt.run} style={st.alt}>
          <T size={12} muted>Autre choix : <T size={12} weight="semibold" color={colors.textSoft}>{alt.label}</T></T>
        </Pressable>
      ) : null}
    </View>
  );
}

/**
 * Sondage de dates : toutes les dates proposées dans l’agenda en un toucher, chacune « À confirmer » (avis 9ddbdea7fe8f).
 * App iPhone : directement dans le calendrier (une autorisation la première fois) ; la date fixée, l’app garde la bonne
 * et retire les autres toute seule. Navigateur : un seul fichier .ics (l’iPhone propose « Tout ajouter »).
 */
export function PollDatesCalendarButton({ event, dates }: {
  event: Pick<EventRow, 'id' | 'title' | 'description' | 'location_name' | 'location_address'>;
  dates: { id: string; starts_at: string; ends_at?: string | null }[];
}) {
  const [native] = useState(nativeCalendar);
  const [inCalendar, setInCalendar] = useState(0);
  const [busy, setBusy] = useState(false);
  const [denied, setDenied] = useState(false);
  const upcoming = upcomingDates(dates);
  const n = upcoming.length;
  useEffect(() => {
    if (!native) return;
    let alive = true;
    native.status(event.id).then((r) => { if (alive) setInCalendar(r.added ?? 0); }).catch(() => undefined);
    return () => { alive = false; };
  }, [native, event.id, n]);
  const url = pollDatesIcsUrl(event, dates);
  if (!url || !n) return null;
  const done = native && inCalendar >= n;

  async function add() {
    if (!native) return openIcs(url!);
    setBusy(true);
    try {
      const where = [event.location_name, event.location_address].filter(Boolean).join(', ');
      const r = await native.add({ eventId: event.id, title: event.title, location: where, notes: (event.description ?? '').slice(0, 1500),
        url: `${window.location.origin}/events/event/${event.id}`,
        dates: upcoming.map((d) => ({ id: d.id, start: d.starts_at, end: d.ends_at ?? '' })) });
      if (r.denied) setDenied(true);
      else setInCalendar(r.total ?? n);
    } catch {
      openIcs(url!);  // app plus ancienne : le fichier .ics, comme dans le navigateur
    } finally {
      setBusy(false);
    }
  }

  const label = done ? (n > 1 ? `Les ${n} dates sont dans ton agenda` : 'La date est dans ton agenda')
    : n > 1 ? `Mettre les ${n} dates dans mon agenda` : 'Mettre la date dans mon agenda';
  const hint = denied ? 'Party n’a pas accès à ton calendrier : autorise-le dans Réglages › Party › Calendriers.'
    : native ? 'Notées « À confirmer ». Quand la date sera fixée, Party gardera la bonne et retirera les autres.'
      : 'Notées « À confirmer » : garde le créneau ; une fois la date fixée, supprime les autres.';
  return (
    <View style={{ gap: 4 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={label}
        accessibilityState={{ disabled: !!done || busy }}
        disabled={!!done || busy}
        onPress={() => void add()}
        style={({ pressed }) => [st.button, st.quiet, transition('background-color, transform, opacity', duration.slow), pressed && { opacity: 0.8, transform: [{ scale: 0.98 }] }]}
      >
        <T size={17}>{done ? '✓' : '📆'}</T>
        <T size={15} style={{ ...font.bold }} color={done ? colors.textSoft : colors.text}>{busy ? 'Ajout…' : label}</T>
      </Pressable>
      <T muted size={12} style={{ textAlign: 'center' }}>{hint}</T>
    </View>
  );
}

function Choice({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [st.choice, pressTransition, pressed && { opacity: 0.8, transform: [{ scale: 0.97 }] }]}>
      <T size={13} style={{ ...font.bold }}>{label}</T>
    </Pressable>
  );
}

const st = StyleSheet.create({
  button: { minHeight: 52, borderRadius: radius.md, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 16, borderWidth: 1 },
  prominent: { backgroundColor: colors.coral, borderColor: colors.coral },
  quiet: { backgroundColor: colors.fill, borderColor: 'transparent' },
  choice: { flex: 1, minHeight: 44, borderRadius: radius.md, borderWidth: 1, borderColor: 'transparent', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8, backgroundColor: colors.fill },
  alt: { alignSelf: 'center', minHeight: 44, justifyContent: 'center', paddingHorizontal: 8 },
});
