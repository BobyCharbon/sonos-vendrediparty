import { useLocalSearchParams } from 'expo-router';

import { InviteStep, parseIds, parseVisibility } from '@/components/InviteStep';

/**
 * Étape 2 « Qui est invité » de « Créer avec l'IA » : ouverte par l'app iPhone juste après l'enregistrement du brouillon.
 * ?audience=&groups= : ce que la personne a dit à l'IA de qui voit (pré-réglage) ; ?suggested= : les personnes citées.
 */
export default function InviteEvent() {
  const { id, audience, groups, suggested } = useLocalSearchParams<{ id: string; audience?: string; groups?: string; suggested?: string }>();
  return <InviteStep eventId={id} preset={{ visibility: parseVisibility(audience), groups: parseIds(groups), suggested: parseIds(suggested) }} />;
}
