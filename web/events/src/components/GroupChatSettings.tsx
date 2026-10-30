import { useState } from 'react';
import { Linking, Platform, Pressable, ScrollView, Text, View } from 'react-native';

import { Avatar, ErrorText, Rows, Section, Segmented, T, ToggleRow } from './ui';
import { dialable, type NotifyLevel } from '@/lib/chats';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

type Member = { id: string; name: string; photo: string | null; admin: boolean; creator: boolean; phone: string | null };

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
            <View key={m.id}>
              <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center', paddingVertical: 10 }}>
                <Avatar id={m.id} name={m.name} photo={m.photo} />
                <View style={{ flex: 1, gap: 2 }}>
                  <T>{m.name}</T>
                  <PhoneLink phone={m.phone} name={m.name} />
                </View>
                {m.creator ? <T muted size={12}>Créateur</T> : m.admin ? <T muted size={12}>Admin</T> : null}
              </View>
              {canNameAdmins && !m.creator ? (
                <ToggleRow label="Admin du groupe" hint="Épingle et supprime les messages, peut écrire @tout"
                  value={m.admin} onChange={(v) => void toggleAdmin(m, v)} />
              ) : null}
            </View>
          ))}
        </Rows>
        <T muted size={12}>Les numéros affichés sont ceux que chacun montre dans ce groupe (Réglages › Groupes). Touche un numéro pour appeler.</T>
      </Section>
      <ErrorText error={error} />
    </ScrollView>
  );
}

/** Numéro montré dans ce groupe : un toucher appelle (iPhone, Android, ou l'app d'appel de l'ordinateur). */
function PhoneLink({ phone, name }: { phone: string | null; name: string }) {
  const number = dialable(phone);
  if (!number) return null;
  const label = `Appeler ${name} au ${number}`;
  if (Platform.OS === 'web') {
    // Vrai lien <a href="tel:…"> ouvert depuis la page entière (le module vit dans un cadre de Party).
    const web = { href: `tel:${number}`, hrefAttrs: { target: '_top' } } as object;
    return (
      <Text accessibilityRole="link" accessibilityLabel={label} {...web}
        style={{ color: colors.accent, fontSize: 14, fontWeight: '600' }}>📞 {number}</Text>
    );
  }
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={label} hitSlop={6} onPress={() => void Linking.openURL(`tel:${number}`)}>
      <T size={14} weight="semibold" color={colors.accent}>📞 {number}</T>
    </Pressable>
  );
}
