import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { calendarPlatform, googleCalendarUrl, icsUrl, openGoogleCalendar, openIcs, pollDatesIcsUrl } from '@/lib/calendar';
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
 * Un seul fichier : l’iPhone affiche la liste et « Tout ajouter » ; Android et ordinateur l’ouvrent avec l’agenda choisi.
 */
export function PollDatesCalendarButton({ event, dates }: {
  event: Pick<EventRow, 'id' | 'title' | 'description' | 'location_name' | 'location_address'>;
  dates: { id: string; starts_at: string; ends_at?: string | null }[];
}) {
  const url = pollDatesIcsUrl(event, dates);
  if (!url) return null;
  const n = (url.match(/[?&]d=/g) ?? []).length;
  return (
    <View style={{ gap: 4 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={n > 1 ? `Mettre les ${n} dates dans mon agenda` : 'Mettre la date dans mon agenda'}
        onPress={() => openIcs(url)}
        style={({ pressed }) => [st.button, st.quiet, transition('background-color, transform, opacity', duration.slow), pressed && { opacity: 0.8, transform: [{ scale: 0.98 }] }]}
      >
        <T size={17}>📆</T>
        <T size={15} style={{ ...font.bold }}>{n > 1 ? `Mettre les ${n} dates dans mon agenda` : 'Mettre la date dans mon agenda'}</T>
      </Pressable>
      <T muted size={12} style={{ textAlign: 'center' }}>Notées « À confirmer » : garde le créneau ; une fois la date fixée, supprime les autres.</T>
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
