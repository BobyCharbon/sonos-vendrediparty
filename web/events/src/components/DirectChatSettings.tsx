import { router } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { C, cf, Icon, web, type IconName } from './chats/conversation/kit';
import { Avatar, ConfirmButton, ErrorText, ToggleRow } from './ui';
import type { NotifyLevel } from '@/lib/chats';
import { blocksChanged, type ReportTarget } from '@/lib/moderation';
import { pressTransition } from '@/lib/motion';
import { ReportSheet } from './ReportSheet';
import { supabase } from '@/lib/supabase';

type Props = {
  chatId: string;
  other: { id: string; name: string; photo: string | null };
  notify: NotifyLevel;
  blocked: boolean;
  onChanged: () => void;
  /** Mini-profil de la personne (même feuille que partout ailleurs) : toucher sa photo. */
  onProfile?: () => void;
};

/** Infos d'un message direct (conversation privée à deux, 4.11 ; graphisme « Néon club », 18.11) : la personne
 * (mini-profil, fiche), les notifications de cette conversation (tout ou rien), le blocage et le signalement.
 * Personne d'autre ne lit cette conversation, ni les admins. */
export function DirectChatSettings({ chatId, other, notify, blocked, onChanged, onProfile }: Props) {
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
    blocksChanged(other.id, next);
    onChanged();
  }

  return (
    <ScrollView style={{ backgroundColor: C.bg }} contentContainerStyle={{ padding: 16, gap: 16, width: '100%', maxWidth: 640, alignSelf: 'center' }}>
      <View style={[{ alignItems: 'center', gap: 10, paddingVertical: 22, borderRadius: 24, borderWidth: 1, borderColor: 'rgba(185,167,255,0.18)' },
        web({ backgroundColor: C.s1, backgroundImage: 'radial-gradient(120% 90% at 50% 0%, rgba(123,108,246,0.28), transparent 65%)' })]}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Profil de ${other.name}`} disabled={!onProfile} onPress={onProfile}
          style={[{ borderRadius: 52, padding: 3 }, web({ backgroundImage: `linear-gradient(135deg, ${C.lavA}, ${C.lavB})` })]}>
          <Avatar id={other.id} name={other.name} photo={other.photo} size={92} profile={false} />
        </Pressable>
        <Text accessibilityRole="header" style={[cf.display, { color: C.t1, fontSize: 26, textAlign: 'center' }]}>{other.name}</Text>
        <Pill label="Voir la fiche" icon="person" onPress={() => router.push(`/member/${other.id}`)} />
      </View>
      <Group title="Notifications">
        <ToggleRow label="Nouveaux messages" hint="« Nouveau message de … » pour chaque message de cette conversation"
          value={on} onChange={(v) => void changeNotify(v)} />
      </Group>
      <Group title="Confidentialité">
        <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
          <Icon name="lock" size={18} color={C.lav} />
          <Text style={[cf.text, { color: C.t2, fontSize: 14, flex: 1 }]}>Conversation privée : seuls vous deux la lisez, ni les admins ni Party.</Text>
        </View>
        {blocked ? (
          <Pill label={`Débloquer ${other.name}`} icon="block" onPress={() => void setBlocked(false)} />
        ) : (
          <ConfirmButton small label={`Bloquer ${other.name}`} confirmLabel="Confirmer le blocage" onConfirm={() => setBlocked(true)} />
        )}
        <Text style={[cf.text, { color: C.t3, fontSize: 12, lineHeight: 17 }]}>
          Une personne bloquée ne peut plus t’écrire (et toi non plus), ni te citer, t’inviter ou voir ta fiche ; elle n’en est pas prévenue. L’historique reste.
        </Text>
        <Pill label={`Signaler ${other.name}`} icon="flag" danger onPress={() => setReport({ kind: 'profile', id: other.id, label: other.name })} />
      </Group>
      <ReportSheet target={report} onClose={() => setReport(null)} />
      <ErrorText error={error} />
    </ScrollView>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={{ gap: 12, padding: 16, borderRadius: 22, backgroundColor: C.s1, borderWidth: 1, borderColor: C.line }}>
      <Text accessibilityRole="header" style={[cf.label, { color: C.t2, fontSize: 12 }]}>{title}</Text>
      {children}
    </View>
  );
}

function Pill({ label, icon, onPress, danger = false }: { label: string; icon: IconName; onPress: () => void; danger?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
      style={({ pressed }) => [{ minHeight: 44, paddingHorizontal: 16, borderRadius: 22, flexDirection: 'row', alignItems: 'center', gap: 8, alignSelf: 'flex-start',
        backgroundColor: C.glass, borderWidth: 1, borderColor: danger ? 'rgba(255,122,138,0.35)' : C.glassLine }, pressTransition, pressed && { opacity: 0.7 }]}>
      <Icon name={icon} size={18} color={danger ? C.danger : C.lav} />
      <Text style={[cf.semibold, { color: danger ? C.danger : C.t1, fontSize: 15 }]}>{label}</Text>
    </Pressable>
  );
}
