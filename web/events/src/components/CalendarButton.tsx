import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import {
  addToAgenda, agendaLink, calendarPlatform, googleCalendarUrl, icsUrl, openGoogleCalendar, openIcs, pollDatesOnce,
  type AddDatesResult, type AgendaLink, type CalendarPlatform,
} from '@/lib/calendar';
import { duration, enter, pressTransition, transition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import type { EventRow } from '@/lib/types';

import { T } from './ui';
import { AGENDA_DONE } from './ValidateDates';

type Ev = Pick<EventRow, 'id' | 'title' | 'description' | 'starts_at' | 'ends_at' | 'location_name' | 'location_address'>;
type Via = CalendarPlatform | 'google';

/**
 * « Ajouter à mon agenda » (retours de l'admin du 11.11.2026) : l'événement entre dans le calendrier « Vendredi Party »
 * de la personne, que son agenda relit tout seul. Date, heure, lieu, titre ou description changent : son agenda suit.
 * Première fois : l'agenda propose de s'abonner (iPhone, Mac, Outlook par webcal ; Android et Google par Google Agenda) ;
 * ensuite un toucher suffit, et chaque réponse Présent / Peut-être y met l'événement toute seule (`answer` : relu à chaque
 * réponse). Sondage de dates (`dates` : les dates votées Oui / Si besoin, sinon toutes) : le même bouton abonne, puis les
 * dates votées arrivent toutes seules, « À confirmer ». Sans compte ou base injoignable : l'ancien ajout ponctuel (.ics ou Google Agenda).
 */
export function CalendarButton({ event, prominent = false, answer = null, dates }: {
  event: Ev; prominent?: boolean; answer?: string | null; dates?: { id: string; starts_at: string; ends_at?: string | null }[];
}) {
  const [platform] = useState(calendarPlatform);
  const [choices, setChoices] = useState(false);
  const [link, setLink] = useState<AgendaLink | null>(null);
  const [result, setResult] = useState<AddDatesResult | null>(null);
  const [busy, setBusy] = useState(false);
  const ics = icsUrl(event);
  const google = googleCalendarUrl(event);

  useEffect(() => {
    let alive = true;
    // Demandé à l'avance : le toucher ouvre ensuite l'agenda sans attendre (Safari bloque une ouverture trop tardive).
    void agendaLink(event.id).then((l) => { if (alive) setLink(l); });
    return () => { alive = false; };
  }, [event.id, answer]);

  const poll = !event.starts_at && !!dates?.length;
  if (!poll && (!ics || !google)) return null;
  const inAgenda = !!link?.added && link.subscribed;

  const once = (via: Via): AddDatesResult | Promise<AddDatesResult> => {
    if (poll || !ics || !google) return pollDatesOnce(event, dates ?? []);
    if (via === 'google' || via === 'android') openGoogleCalendar(google);
    else openIcs(ics);
    return 'file';
  };
  const add = async (via: Via) => {
    setBusy(true);
    try {
      const r = await addToAgenda(event.id, link, () => once(via), via);
      setResult(r);
      if (r === 'added' || r === 'subscribed') setLink((l) => (l ? { ...l, added: true } : l));
    } finally {
      setBusy(false);
    }
  };
  const primary = () => {
    if (busy) return;
    if (link?.subscribed || platform !== 'desktop') void add(platform);
    else setChoices((v) => !v);
  };
  const alt = link?.subscribed || (poll && !link) ? null : platform === 'ios'
    ? { label: 'Google Agenda', via: 'google' as Via }
    : platform === 'android'
      ? { label: 'Autre agenda', via: 'ios' as Via }
      : null;
  const label = inAgenda ? '✓ Dans ton agenda' : busy ? 'Ajout…' : 'Ajouter à mon agenda';
  const strong = prominent && !inAgenda;

  return (
    <View style={{ gap: 8 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={inAgenda ? 'Déjà dans ton agenda, mis à jour tout seul' : 'Ajouter à mon agenda'}
        accessibilityState={{ disabled: inAgenda || busy, expanded: platform === 'desktop' && !link?.subscribed ? choices : undefined }}
        disabled={inAgenda || busy}
        onPress={primary}
        style={({ pressed }) => [st.button, transition('background-color, border-color, transform, opacity', duration.slow), strong ? st.prominent : st.quiet, pressed && { opacity: 0.8, transform: [{ scale: 0.98 }] }]}
      >
        {inAgenda ? null : <T size={17}>📆</T>}
        <T size={15} style={{ ...font.bold }} color={strong ? colors.onAccent : inAgenda ? colors.mint : colors.text}>{label}</T>
      </Pressable>
      {inAgenda && !result ? <T size={12} muted style={st.center}>Se met à jour tout seul si l’événement change.</T> : null}
      {result && result !== 'file' ? (
        <T size={12} weight="semibold" color={result === 'denied' ? colors.coralSoft : colors.mint} style={st.center}>{AGENDA_DONE[result]}</T>
      ) : null}
      {platform === 'desktop' && choices && !link?.subscribed ? (
        <View style={[{ flexDirection: 'row', gap: 8 }, enter('drop')]}>
          <Choice label="Apple · Outlook" onPress={() => void add('desktop')} />
          <Choice label="Google Agenda" onPress={() => void add('google')} />
        </View>
      ) : null}
      {alt && !inAgenda && (!result || result === 'file') ? (
        <Pressable accessibilityRole="button" onPress={() => void add(alt.via)} style={st.alt}>
          <T size={12} muted>Autre choix : <T size={12} weight="semibold" color={colors.textSoft}>{alt.label}</T></T>
        </Pressable>
      ) : null}
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
  center: { textAlign: 'center' },
});
