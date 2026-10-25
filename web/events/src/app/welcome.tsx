import { useState } from 'react';
import { router } from 'expo-router';
import { View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { SignedIn } from '@/components/SignedIn';
import { Button, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { hasCompleteIdentity } from '@/lib/profile';

/** Compte connecté sans accès aux événements : profil complet, puis confirmation que le compte est connecté. */
export default function Welcome() {
  const { profile, signOut } = useAuth();
  const [editing, setEditing] = useState(false);
  const complete = hasCompleteIdentity(profile);

  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 24 }}>
      {profile?.status === 'banned' ? (
        <View style={{ gap: 12 }}>
          <Title size={32}>Accès retiré</Title>
          <T muted>Ton accès a été retiré par un admin du groupe.</T>
        </View>
      ) : complete && !editing ? (
        <View style={{ gap: 20 }}>
          <Title size={32}>Les événements du groupe</Title>
          <SignedIn name={profile?.display_name} />
          <Button label="Modifier mes informations" variant="ghost" onPress={() => setEditing(true)} />
        </View>
      ) : profile ? (
        <View style={{ gap: 20 }}>
          <View style={{ gap: 8 }}>
            <Title size={32}>Faisons connaissance</Title>
            <T muted>Quelques infos pour que le groupe te reconnaisse.</T>
          </View>
          <IdentityForm profile={profile} submitLabel="Continuer" onSaved={() => setEditing(false)} />
        </View>
      ) : null}
      <View style={{ gap: 4 }}>
        <Button label="Se déconnecter" variant="ghost" onPress={signOut} />
        <Button label="Confidentialité" variant="ghost" onPress={() => router.push('/privacy')} />
        <Button label="Supprimer mon compte" variant="ghost" onPress={() => router.push('/settings/account')} />
      </View>
    </Screen>
  );
}
