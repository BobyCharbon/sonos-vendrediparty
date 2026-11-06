import { useLocalSearchParams } from 'expo-router';

import { InviteStep, parseSuggested } from '@/components/InviteStep';

/** Étape 2 « Les invités » de « Créer avec l'IA » : ouverte par l'app iPhone juste après l'enregistrement du brouillon. */
export default function InviteEvent() {
  const { id, suggested } = useLocalSearchParams<{ id: string; suggested?: string }>();
  return <InviteStep eventId={id} suggested={parseSuggested(suggested)} />;
}
