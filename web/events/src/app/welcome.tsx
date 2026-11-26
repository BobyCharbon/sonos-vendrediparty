import { useEffect, useState } from 'react';
import { router } from 'expo-router';
import { View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { SignedIn } from '@/components/SignedIn';
import { Button, Loading, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { pendingLinkDestination } from '@/lib/destination';
import { hasCompleteIdentity } from '@/lib/profile';

/** Compte connecté sans accès aux événements : profil complet, puis confirmation que le compte est connecté. */
export default function Welcome() {
  const { profile, signOut } = useAuth();
  const [editing, setEditing] = useState(false);
  const complete = hasCompleteIdentity(profile);
  // Connexion faite depuis un lien (événement public, invitation…) : la page y retourne aussitôt. Pas de « Faisons
  // connaissance » ici entre-temps (la saisie commencée était perdue au retour sur le lien) ; 2 s au plus, par sécurité.
  const [leaving, setLeaving] = useState(pendingLinkDestination);
  useEffect(() => {
    if (!leaving) return;
    const timer = setTimeout(() => setLeaving(false), 2000);
    return () => clearTimeout(timer);
  }, [leaving]);
  if (leaving && !complete) return <Loading />;

  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 24 }}>
      {profile?.status === 'banned' ? (
        <View style={{ gap: 12 }}>
          <Title size={32}>Accès retiré</Title>
          <T muted>Ton accès a été retiré par un admin du groupe.</T>
        </View>
      ) : complete && !editing ? (
        <View style={{ gap: 20 }}>
          <Title size={32}>Les événements où tu es invité</Title>
          <SignedIn name={profile?.display_name} />
          <Button label="Modifier mes informations" variant="ghost" onPress={() => setEditing(true)} />
        </View>
      ) : profile ? (
        <View style={{ gap: 20 }}>
          <View style={{ gap: 8 }}>
            <Title size={32}>Faisons connaissance</Title>
            <T muted>Quelques infos pour que les autres te reconnaissent.</T>
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
