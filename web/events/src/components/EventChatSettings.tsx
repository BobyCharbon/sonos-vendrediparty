import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, View } from 'react-native';

import { Avatar, ErrorText, Section, T, ToggleRow } from './ui';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

export type EventPerson = { id: string; name: string; photo: string | null; rsvp: string | null; organizer: boolean; invited: boolean };

type Props = {
  eventId: string;
  me: string;
  muted: boolean;
  /** Organisation de l'événement (ou admin) : citations spéciales expliquées ; invités sans réponse visibles. */
  staff: boolean;
  people: EventPerson[];
  onChanged: () => void;
};

/** Infos de la discussion d'un événement : mes notifications (le même réglage que la fiche, event_mutes), les citations
 * de l'organisation, puis les personnes par réponse. Les invités sans réponse ne sont listés que pour l'organisation
 * (event_chat_people ne les donne qu'à elle : règle du 11.11). */
export function EventChatSettings({ eventId, me, muted, staff, people, onChanged }: Props) {
  const [on, setOn] = useState(!muted);
  const [error, setError] = useState<string | null>(null);

  async function changeNotify(next: boolean) {
    setOn(next);
    setError(null);
    const { error } = next
      ? await supabase.from('event_mutes').delete().eq('event_id', eventId).eq('user_id', me)
      : await supabase.from('event_mutes').insert({ event_id: eventId, user_id: me });
    if (error) {
      setOn(!next);
      return setError('Le réglage n’a pas pu être enregistré. Réessaie.');
    }
    onChanged();
  }

  const rest = people.filter((p) => !p.organizer);
  const buckets = [
    { title: 'Organisation', list: people.filter((p) => p.organizer) },
    { title: 'Présents', list: rest.filter((p) => p.rsvp === 'yes') },
    { title: 'Peut-être', list: rest.filter((p) => p.rsvp === 'maybe') },
    { title: 'Pas présents', list: rest.filter((p) => p.rsvp === 'no') },
    { title: 'Invités sans réponse', list: rest.filter((p) => !p.rsvp && p.invited) },
    { title: 'Autres personnes de la discussion', list: rest.filter((p) => !p.rsvp && !p.invited) },
  ].filter((b) => b.list.length);

  return (
    <ScrollView contentContainerStyle={{ padding: 16, gap: 18 }}>
      <Section title="Notifications">
        <ToggleRow label="Notifications de cet événement"
          hint={on ? 'Selon tes réglages : chaque message, ou seulement quand on te cite (@surnom, @toutlemonde, @present, annonce) ou te répond.'
            : 'Coupées : aucune notification de cet événement, même quand on te cite (le même réglage que sur sa fiche).'}
          value={on} onChange={(v) => void changeNotify(v)} />
        <ErrorText error={error} />
      </Section>
      {staff ? (
        <Section title="Réservé à l’organisation">
          <T size={14}>👥 <T size={14} weight="bold">@toutlemonde</T> prévient tous les invités et participants.</T>
          <T size={14}>✅ <T size={14} weight="bold">@present</T> prévient les présents et les peut-être.</T>
          <T size={14}>📣 <T size={14} weight="bold">Annonce</T> (bouton 📣 ou @annonce) : épinglée en haut, envoyée à tous.</T>
          <T muted size={13}>Tu peux aussi épingler un message, ou retirer celui d’un autre, depuis ses actions (⋯).</T>
        </Section>
      ) : null}
      {buckets.map((b) => (
        <Section key={b.title} title={`${b.title} · ${b.list.length}`}>
          {b.list.map((p) => (
            <Pressable key={p.id} accessibilityRole="link" accessibilityLabel={`Profil de ${p.name}`} onPress={() => router.push(`/member/${p.id}`)}
              style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 4 }, pressed && { opacity: 0.7 }]}>
              <Avatar id={p.id} name={p.name} photo={p.photo} size={34} profile={false} />
              <T style={{ flex: 1 }} numberOfLines={1}>{p.name}</T>
              {p.id === me ? <T muted size={12}>Toi</T> : null}
            </Pressable>
          ))}
        </Section>
      ))}
      {!buckets.length ? <View><T muted style={{ color: colors.muted }}>Personne pour l’instant.</T></View> : null}
    </ScrollView>
  );
}
