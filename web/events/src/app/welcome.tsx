import { useState } from 'react';
import { router } from 'expo-router';
import { View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { Button, Card, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { hasCompleteIdentity } from '@/lib/profile';

/** Inscription : prénom, nom, surnom et photo sur une seule page, puis attente de validation par un admin. */
export default function Welcome() {
  const { profile, refreshProfile, signOut } = useAuth();
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
          <Title size={32}>Demande envoyée</Title>
          <T>Merci {profile?.display_name}, ton profil est prêt.</T>
          <Card>
            <T weight="semibold">En attente d’autorisation</T>
            <T muted>Un admin doit valider ton accès avant que tu puisses voir les événements du groupe.</T>
            <T muted size={13}>Cette page se met à jour automatiquement après validation.</T>
            <Button label="Vérifier mon accès" variant="secondary" onPress={refreshProfile} />
          </Card>
          <Button label="Modifier mes informations" variant="ghost" onPress={() => setEditing(true)} />
        </View>
      ) : profile ? (
        <View style={{ gap: 20 }}>
          <View style={{ gap: 8 }}>
            <Title size={32}>Faisons connaissance</Title>
            <T muted>Quelques infos pour que le groupe te reconnaisse.</T>
          </View>
          <IdentityForm profile={profile} submitLabel={profile.status === 'active' ? 'Enregistrer et continuer' : 'Demander l’accès'} onSaved={() => setEditing(false)} />
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
