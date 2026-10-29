import { useState } from 'react';
import { ScrollView, View } from 'react-native';

import { Avatar, ErrorText, Rows, Section, Segmented, T, ToggleRow } from './ui';
import type { NotifyLevel } from '@/lib/chats';
import { supabase } from '@/lib/supabase';

type Member = { id: string; name: string; photo: string | null; admin: boolean; creator: boolean };

type Props = {
  groupId: string;
  notify: NotifyLevel;
  member: boolean;
  canNameAdmins: boolean;
  members: Member[];
  onChanged: () => void;
};

const LEVELS: { key: NotifyLevel; label: string }[] = [
  { key: 'all', label: 'Tout' },
  { key: 'mentions', label: 'Mentions' },
  { key: 'none', label: 'Rien' },
];

const LEVEL_HINT: Record<NotifyLevel, string> = {
  all: 'Une notification pour chaque message du groupe.',
  mentions: 'Seulement quand on te cite (@surnom), qu’on te répond ou qu’un admin écrit @tout.',
  none: 'Aucune notification de ce groupe, même citée.',
};

/** Infos du groupe : notifications (par défaut : mentions seulement), membres et admins. */
export function GroupChatSettings({ groupId, notify, member, canNameAdmins, members, onChanged }: Props) {
  const [level, setLevel] = useState<NotifyLevel>(notify);
  const [error, setError] = useState<string | null>(null);

  async function changeLevel(next: NotifyLevel) {
    const previous = level;
    setLevel(next);
    setError(null);
    const { error } = await supabase.rpc('set_group_chat_notify', { grp: groupId, level: next });
    if (error) {
      setLevel(previous);
      return setError('Le réglage n’a pas pu être enregistré. Réessaie.');
    }
    onChanged();
  }

  async function toggleAdmin(m: Member, admin: boolean) {
    setError(null);
    const { error } = await supabase.rpc('set_group_admin', { grp: groupId, member: m.id, admin });
    if (error) setError('Seul le créateur du groupe nomme les admins.');
    onChanged();
  }

  return (
    <ScrollView contentContainerStyle={{ padding: 16, gap: 18 }}>
      {member ? (
        <Section title="Notifications">
          <Segmented options={LEVELS} value={level} onChange={(k) => void changeLevel(k)} />
          <T muted size={13}>{LEVEL_HINT[level]}</T>
        </Section>
      ) : null}
      <Section title={`${members.length} membre${members.length > 1 ? 's' : ''}`}>
        <Rows>
          {members.map((m) => (
            canNameAdmins && !m.creator ? (
              <ToggleRow key={m.id} label={m.name} hint="Admin du groupe : épingle et supprime les messages, peut écrire @tout"
                value={m.admin} onChange={(v) => void toggleAdmin(m, v)} />
            ) : (
              <View key={m.id} style={{ flexDirection: 'row', gap: 10, alignItems: 'center', paddingVertical: 10 }}>
                <Avatar id={m.id} name={m.name} photo={m.photo} />
                <T style={{ flex: 1 }}>{m.name}</T>
                {m.creator ? <T muted size={12}>Créateur</T> : m.admin ? <T muted size={12}>Admin</T> : null}
              </View>
            )
          ))}
        </Rows>
      </Section>
      <ErrorText error={error} />
    </ScrollView>
  );
}
