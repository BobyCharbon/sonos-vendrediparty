import { router } from 'expo-router';
import { useState } from 'react';
import { ScrollView, View } from 'react-native';

import { Avatar, Button, ConfirmButton, ErrorText, Section, T, ToggleRow } from './ui';
import type { NotifyLevel } from '@/lib/chats';
import { type ReportTarget } from '@/lib/moderation';
import { ReportSheet } from './ReportSheet';
import { supabase } from '@/lib/supabase';

type Props = {
  chatId: string;
  other: { id: string; name: string; photo: string | null };
  notify: NotifyLevel;
  blocked: boolean;
  onChanged: () => void;
};

/** Infos d'un message direct (conversation privée à deux, 4.11) : la personne (sa fiche), les notifications de cette
 * conversation (tout ou rien) et le blocage. Personne d'autre ne lit cette conversation, ni les admins. */
export function DirectChatSettings({ chatId, other, notify, blocked, onChanged }: Props) {
  const [on, setOn] = useState(notify !== 'none');
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportTarget | null>(null);

  async function changeNotify(next: boolean) {
    setOn(next);
    setError(null);
    const { error } = await supabase.rpc('set_direct_chat_notify', { chat: chatId, level: next ? 'all' : 'none' });
    if (error) {
      setOn(!next);
      return setError('Le réglage n’a pas pu être enregistré. Réessaie.');
    }
    onChanged();
  }

  async function setBlocked(next: boolean) {
    setError(null);
    // Même table que le blocage commun à toute l'app (public.direct_blocks).
    const { error } = await supabase.rpc('set_direct_block', { target: other.id, blocked: next });
    if (error) return setError(next ? 'Le blocage n’a pas pu être enregistré.' : 'Le déblocage n’a pas pu être enregistré.');
    onChanged();
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 16, gap: 18 }}>
      <View style={{ alignItems: 'center', gap: 8 }}>
        <Avatar id={other.id} name={other.name} photo={other.photo} size={88} profile={false} />
        <T weight="bold" size={20}>{other.name}</T>
        <Button small variant="secondary" label="Voir la fiche" onPress={() => router.push(`/member/${other.id}`)} />
      </View>
      <Section title="Notifications">
        <ToggleRow label="Nouveaux messages" hint="« Nouveau message de … » pour chaque message de cette conversation"
          value={on} onChange={(v) => void changeNotify(v)} />
      </Section>
      <Section title="Confidentialité">
        <T muted size={13}>Conversation privée : seuls vous deux la lisez.</T>
        {blocked ? (
          <Button small variant="secondary" label={`Débloquer ${other.name}`} onPress={() => void setBlocked(false)} />
        ) : (
          <ConfirmButton small label={`Bloquer ${other.name}`} confirmLabel="Confirmer le blocage" onConfirm={() => setBlocked(true)} />
        )}
        <T muted size={12}>Une personne bloquée ne peut plus t’écrire (et toi non plus), ni te citer, t’inviter ou voir ta fiche ; elle n’en est pas prévenue. L’historique reste.</T>
        <Button small variant="ghost" label={`Signaler ${other.name}`} onPress={() => setReport({ kind: 'profile', id: other.id, label: other.name })} />
      </Section>
      <ReportSheet target={report} onClose={() => setReport(null)} />
      <ErrorText error={error} />
    </ScrollView>
  );
}
