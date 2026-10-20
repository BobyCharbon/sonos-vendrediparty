import { useRef, useState } from 'react';
import type { ImagePickerAsset } from 'expo-image-picker';
import { router } from 'expo-router';
import { View } from 'react-native';

import { Button, Card, ErrorText, Field, Screen, T, Title } from '@/components/ui';
import { ProfilePhotoField } from '@/components/ProfilePhotoField';
import { useAuth } from '@/lib/auth';
import { hasCompleteIdentity } from '@/lib/profile';
import { PROFILE_PHOTOS, uploadProfilePhoto } from '@/lib/photos';
import { check, supabase } from '@/lib/supabase';

/** Inscription : nom et prénom (privés), surnom et photo, puis attente de validation par un admin. */
export default function Welcome() {
  const { profile, refreshProfile, signOut } = useAuth();
  const [firstName, setFirstName] = useState(profile?.first_name ?? '');
  const [lastName, setLastName] = useState(profile?.last_name ?? '');
  const [nickname, setNickname] = useState(profile?.display_name ?? '');
  const [photo, setPhoto] = useState<ImagePickerAsset | null>(null);
  const [step, setStep] = useState<'identity' | 'nickname' | 'waiting'>(hasCompleteIdentity(profile) ? 'waiting' : 'identity');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saving = useRef(false);
  const identity = { first_name: firstName.trim(), last_name: lastName.trim(), display_name: nickname.trim(), avatar_url: photo?.uri ?? profile?.avatar_url ?? null };

  async function save() {
    if (!profile || saving.current || !hasCompleteIdentity(identity)) return;
    saving.current = true;
    setBusy(true);
    setError(null);
    let uploaded: string | null = null;
    try {
      if (photo) uploaded = await uploadProfilePhoto(profile.id, photo);
      check(await supabase.from('profiles').update({ ...identity, avatar_url: uploaded ?? profile.avatar_url }).eq('id', profile.id).select('id').single());
      await refreshProfile();
      setStep('waiting');
    } catch (e) {
      if (uploaded) await supabase.storage.from(PROFILE_PHOTOS).remove([uploaded]).catch(() => {});
      setError(e instanceof Error ? e.message : 'Tes informations n’ont pas pu être enregistrées. Vérifie ta connexion puis réessaie.');
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 24 }}>
      {profile?.status === 'banned' ? (
        <View style={{ gap: 12 }}>
          <Title size={32}>Accès retiré</Title>
          <T muted>Ton accès a été retiré par un admin du groupe.</T>
        </View>
      ) : step === 'waiting' ? (
        <View style={{ gap: 20 }}>
          <Title size={32}>Demande envoyée</Title>
          <T>Merci {profile?.display_name}, ton profil est prêt.</T>
          <Card>
            <T weight="semibold">En attente d’autorisation</T>
            <T muted>Un admin doit valider ton accès avant que tu puisses voir les événements du groupe.</T>
            <T muted size={13}>Cette page se met à jour automatiquement après validation.</T>
            <Button label="Vérifier mon accès" variant="secondary" onPress={refreshProfile} />
          </Card>
          <Button label="Modifier mes informations" variant="ghost" onPress={() => { setError(null); setStep('identity'); }} />
        </View>
      ) : (
        <View style={{ gap: 20 }}>
          <View style={{ gap: 8 }}>
            <Title size={32}>{step === 'identity' ? 'Faisons connaissance' : 'Ton nom dans le groupe'}</Title>
            <T muted>{step === 'identity'
              ? 'Ton nom et ton prénom permettent aux admins de reconnaître ta demande.'
              : 'Ton surnom sera affiché dans les événements, les réponses et les discussions.'}</T>
          </View>
          <View style={{ gap: 14 }}>
            {step === 'identity' ? (
              <>
                <Field label="Nom" value={lastName} onChangeText={setLastName} autoComplete="family-name" autoCapitalize="words" maxLength={100} />
                <Field label="Prénom" value={firstName} onChangeText={setFirstName} autoComplete="given-name" autoCapitalize="words" maxLength={100} />
                <T muted size={13}>Ces informations sont visibles uniquement par toi et les admins.</T>
                <Button label="Continuer" disabled={!firstName.trim() || !lastName.trim()} onPress={() => setStep('nickname')} />
              </>
            ) : (
              <>
                <Field label="Surnom" value={nickname} onChangeText={setNickname} maxLength={40} editable={!busy} autoFocus onSubmitEditing={save} />
                <ProfilePhotoField userId={profile!.id} name={nickname} currentPhoto={profile?.avatar_url ?? null} photo={photo} onChange={setPhoto} disabled={busy} />
                <ErrorText error={error} />
                <Button label={profile?.status === 'active' ? 'Enregistrer et continuer' : 'Demander l’accès'} onPress={save} loading={busy} disabled={!hasCompleteIdentity(identity)} />
                <Button label="Retour au nom et prénom" variant="ghost" disabled={busy} onPress={() => { setError(null); setStep('identity'); }} />
              </>
            )}
          </View>
        </View>
      )}
      <View style={{ gap: 4 }}>
        <Button label="Se déconnecter" variant="ghost" disabled={busy} onPress={signOut} />
        <Button label="Confidentialité" variant="ghost" onPress={() => router.push('/privacy')} />
        <Button label="Supprimer mon compte" variant="ghost" disabled={busy} onPress={() => router.push('/settings/account')} />
      </View>
    </Screen>
  );
}
