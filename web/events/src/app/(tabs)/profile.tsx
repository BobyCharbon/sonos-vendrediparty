import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { Avatar, Button, Card, ErrorText, Field, LinkRow, Screen, s, T, Title } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { check, supabase } from '@/lib/supabase';

const roleLabel = { admin: 'Admin', coadmin: 'Co-admin', member: 'Membre' } as const;

export default function Profile() {
  const me = useMe();
  const { refreshProfile, signOut } = useAuth();
  const [name, setName] = useState(me.display_name);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const saving = useRef(false);

  async function saveName() {
    if (saving.current || !name.trim()) return;
    saving.current = true;
    setBusy(true);
    setError(null);
    try {
      check(await supabase.from('profiles').update({ display_name: name.trim() }).eq('id', me.id));
      await refreshProfile();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  return (
    <Screen edges={[]}>
      <Title>Profil</Title>
      <Card>
        <View style={s.row}>
          <Avatar id={me.id} name={me.display_name} size={48} />
          <View>
            <T weight="bold" size={17}>{me.display_name}</T>
            <T muted size={13}>{roleLabel[me.role]} · {me.phone ? `+${me.phone.replace(/^\+/, '')}` : ''}</T>
          </View>
        </View>
        <Field label="Prénom" value={name} onChangeText={setName} maxLength={40} editable={!busy} />
        <ErrorText error={error} />
        {name.trim() && name.trim() !== me.display_name ? <Button label="Enregistrer" onPress={saveName} loading={busy} /> : null}
      </Card>

      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <LinkRow
          label="Mes abonnements"
          hint="Catégories et tags qui t’intéressent"
          onPress={() => router.push('/settings/subscriptions')}
        />
        <View style={s.divider} />
        <LinkRow label="Notifications" hint="Ce que tu reçois, et quand" onPress={() => router.push('/settings/notifications')} />
        <View style={s.divider} />
        <LinkRow label="Confidentialité" hint="Tes données et tes choix" onPress={() => router.push('/privacy')} />
        <View style={s.divider} />
        <LinkRow label="Gérer mon compte" hint="Suppression du compte" onPress={() => router.push('/settings/account')} />
      </Card>

      <Button label="Se déconnecter" variant="danger" onPress={signOut} />
    </Screen>
  );
}
