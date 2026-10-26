import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { calendarPlatform, googleCalendarUrl, icsUrl, openGoogleCalendar, openIcs } from '@/lib/calendar';
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
        style={({ pressed }) => [st.button, prominent ? st.prominent : st.quiet, pressed && { opacity: 0.8 }]}
      >
        <T size={17}>📆</T>
        <T size={15} style={{ ...font.bold }} color={prominent ? colors.onAccent : colors.text}>Ajouter à mon agenda</T>
      </Pressable>
      {platform === 'desktop' && choices ? (
        <View style={{ flexDirection: 'row', gap: 8 }}>
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

function Choice({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} style={({ pressed }) => [st.choice, pressed && { opacity: 0.8 }]}>
      <T size={13} style={{ ...font.bold }}>{label}</T>
    </Pressable>
  );
}

const st = StyleSheet.create({
  button: { minHeight: 52, borderRadius: radius.md, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 16, borderWidth: 1 },
  prominent: { backgroundColor: colors.coral, borderColor: colors.coral },
  quiet: { backgroundColor: colors.surface, borderColor: colors.lineStrong },
  choice: { flex: 1, minHeight: 44, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 8, backgroundColor: colors.bg },
  alt: { alignSelf: 'center', minHeight: 32, justifyContent: 'center', paddingHorizontal: 8 },
});
