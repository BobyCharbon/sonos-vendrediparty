import { router } from 'expo-router';
import { useRef, useState } from 'react';
import type { ImagePickerAsset } from 'expo-image-picker';
import { View } from 'react-native';

import { Avatar, Button, Card, ErrorText, Field, LinkRow, Screen, s, T, Title } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { check, supabase } from '@/lib/supabase';
import { ProfilePhotoField } from '@/components/ProfilePhotoField';
import { hasCompleteIdentity } from '@/lib/profile';
import { PROFILE_PHOTOS, uploadProfilePhoto } from '@/lib/photos';

const roleLabel = { admin: 'Admin', coadmin: 'Co-admin', member: 'Membre' } as const;

export default function Profile() {
  const me = useMe();
  const { refreshProfile, signOut } = useAuth();
  const [name, setName] = useState(me.display_name);
  const [firstName, setFirstName] = useState(me.first_name ?? '');
  const [lastName, setLastName] = useState(me.last_name ?? '');
  const [photo, setPhoto] = useState<ImagePickerAsset | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const saving = useRef(false);

  async function saveName() {
    const identity = { first_name: firstName.trim(), last_name: lastName.trim(), display_name: name.trim(), avatar_url: photo?.uri ?? me.avatar_url };
    if (saving.current || !hasCompleteIdentity(identity)) return;
    saving.current = true;
    setBusy(true);
    setError(null);
    let uploaded: string | null = null;
    try {
      if (photo) uploaded = await uploadProfilePhoto(me.id, photo);
      check(await supabase.from('profiles').update({ ...identity, avatar_url: uploaded ?? me.avatar_url }).eq('id', me.id).select('id').single());
      await refreshProfile();
      setPhoto(null);
    } catch (e) {
      if (uploaded) await supabase.storage.from(PROFILE_PHOTOS).remove([uploaded]).catch(() => {});
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
          <Avatar id={me.id} name={me.display_name} photo={me.avatar_url} size={48} />
          <View>
            <T weight="bold" size={17}>{me.display_name}</T>
            <T muted size={13}>{roleLabel[me.role]} · {me.phone ? `+${me.phone.replace(/^\+/, '')}` : ''}</T>
          </View>
        </View>
        <Field label="Nom" value={lastName} onChangeText={setLastName} autoComplete="family-name" autoCapitalize="words" maxLength={100} editable={!busy} />
        <Field label="Prénom" value={firstName} onChangeText={setFirstName} autoComplete="given-name" autoCapitalize="words" maxLength={100} editable={!busy} />
        <T muted size={13}>Ton nom et ton prénom sont visibles uniquement par toi et les admins.</T>
        <Field label="Surnom" value={name} onChangeText={setName} maxLength={40} editable={!busy} />
        <ProfilePhotoField userId={me.id} name={name} currentPhoto={me.avatar_url} photo={photo} onChange={setPhoto} disabled={busy} />
        <ErrorText error={error} />
        {photo || name.trim() !== me.display_name || firstName.trim() !== (me.first_name ?? '') || lastName.trim() !== (me.last_name ?? '')
          ? <Button label="Enregistrer" onPress={saveName} loading={busy} disabled={!hasCompleteIdentity({ first_name: firstName, last_name: lastName, display_name: name, avatar_url: photo?.uri ?? me.avatar_url })} /> : null}
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
