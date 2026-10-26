import { IdentityForm } from '@/components/IdentityForm';
import { Screen, T } from '@/components/ui';
import { useAuth } from '@/lib/auth';

/** Réglages → Mon profil : prénom, nom, surnom et photo (ouvert depuis la carte du compte, comme sur iPhone). */
export default function Profile() {
  const { profile } = useAuth();
  if (!profile) return null;
  return (
    <Screen edges={[]}>
      <T muted size={14}>Ton surnom et ta photo te suivent dans les jeux et les événements.</T>
      <IdentityForm profile={profile} submitLabel="Enregistrer" />
    </Screen>
  );
}
