import { useState } from 'react';
import { router } from 'expo-router';
import { View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { JoinRequest } from '@/components/JoinRequest';
import { Button, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { hasCompleteIdentity } from '@/lib/profile';

/** Compte connecté mais pas (encore) membre : profil complet, puis demande d'adhésion avec un mot facultatif. */
export default function Welcome() {
  const { profile, refreshProfile, signOut, eventsSoon } = useAuth();
  const [editing, setEditing] = useState(false);
  const complete = hasCompleteIdentity(profile);

  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 24 }}>
      {profile?.status === 'banned' ? (
        <View style={{ gap: 12 }}>
          <Title size={32}>Accès retiré</Title>
          <T muted>Ton accès a été retiré par un admin du groupe.</T>
        </View>
      ) : eventsSoon ? (
        <View style={{ gap: 12 }}>
          <Title size={32}>Bientôt</Title>
          <T muted>Tu fais partie du groupe. Les sorties sont pour l’instant réservées aux bêta-testeurs.</T>
        </View>
      ) : complete && !editing ? (
        <View style={{ gap: 20 }}>
          <Title size={32}>Les sorties du groupe</Title>
          <T>Salut {profile?.display_name} 👋</T>
          <JoinRequest />
          <Button label="Vérifier mon accès" variant="secondary" onPress={refreshProfile} />
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
