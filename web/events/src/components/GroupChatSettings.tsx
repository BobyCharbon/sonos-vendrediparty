import { router } from 'expo-router';
import { useState } from 'react';
import { Linking, Platform, Pressable, ScrollView, Text, View } from 'react-native';

import { Avatar, Button, ErrorText, Rows, Section, Segmented, T, ToggleRow } from './ui';
import { dialable, type EveryoneBy, type NotifyLevel } from '@/lib/chats';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

type Member = { id: string; name: string; photo: string | null; admin: boolean; organizer?: boolean; creator: boolean; phone: string | null };

type Props = {
  groupId: string;
  notify: NotifyLevel;
  member: boolean;
  canNameAdmins: boolean;
  /** Admin du groupe : nomme les organisateurs et choisit qui peut écrire @tout. */
  isAdmin?: boolean;
  everyone?: EveryoneBy;
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
  mentions: 'Seulement quand on te cite (@surnom), qu’on te répond ou que quelqu’un écrit @tout.',
  none: 'Aucune notification de ce groupe, même citée.',
};

const EVERYONE: { key: EveryoneBy; label: string }[] = [
  { key: 'all', label: 'Tous les membres' },
  { key: 'staff', label: 'Admins et organisateurs' },
];

/** Infos du groupe : notifications (par défaut : mentions seulement), membres et admins. */
export function GroupChatSettings({ groupId, notify, member, canNameAdmins, isAdmin = false, everyone = 'all', members, onChanged }: Props) {
  const [level, setLevel] = useState<NotifyLevel>(notify);
  const [everyoneBy, setEveryoneBy] = useState<EveryoneBy>(everyone);
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

  async function changeEveryone(next: EveryoneBy) {
    const previous = everyoneBy;
    setEveryoneBy(next);
    setError(null);
    const { error } = await supabase.rpc('set_group_everyone_tag', { grp: groupId, who: next });
    if (error) {
      setEveryoneBy(previous);
      return setError('Seuls les admins du groupe choisissent qui peut écrire @tout.');
    }
    onChanged();
  }

  async function toggleOrganizer(m: Member, organizer: boolean) {
    setError(null);
    const { error } = await supabase.rpc('set_group_organizer', { grp: groupId, member: m.id, organizer });
    if (error) setError('Seuls les admins du groupe nomment les organisateurs.');
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
      <Section title="@tout dans ce groupe">
        {isAdmin ? <Segmented options={EVERYONE} value={everyoneBy} onChange={(k) => void changeEveryone(k)} />
          : <T>{EVERYONE.find((e) => e.key === everyoneBy)?.label}</T>}
        <T muted size={13}>Qui peut écrire @tout pour prévenir tout le groupe. @annonce (message épinglé en haut, envoyé à tous) est réservé aux admins et organisateurs.{isAdmin ? '' : ' Les admins du groupe choisissent.'}</T>
      </Section>
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
                {m.creator ? <T muted size={12}>Créateur · Admin</T> : m.admin ? <T muted size={12}>Admin</T> : m.organizer ? <T muted size={12}>Organisateur</T> : null}
              </View>
              {canNameAdmins && !m.creator ? (
                <ToggleRow label="Admin du groupe" hint="Épingle et supprime les messages, fait et retire les annonces"
                  value={m.admin} onChange={(v) => void toggleAdmin(m, v)} />
              ) : null}
              {isAdmin && !m.creator && !m.admin ? (
                <ToggleRow label="Organisateur" hint="Fait des annonces (@annonce) et les retire"
                  value={Boolean(m.organizer)} onChange={(v) => void toggleOrganizer(m, v)} />
              ) : null}
            </View>
          ))}
        </Rows>
        <T muted size={12}>Les numéros affichés sont ceux que chacun montre dans ce groupe (Réglages › Groupes). Touche un numéro pour appeler.</T>
        {/* Même écran que Réglages › Groupes : ajouter ou inviter des membres, liens d'invitation. */}
        {member ? <Button small variant="secondary" label="Gérer le groupe (membres, invitations)" onPress={() => router.push(`/groups?open=${groupId}`)} /> : null}
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
