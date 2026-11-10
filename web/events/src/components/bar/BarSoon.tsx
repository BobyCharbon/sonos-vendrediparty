import { Stack } from 'expo-router';

import { Empty, Screen } from '@/components/ui';

/** Bar de la soirée éteint (production, app/features.py : data-bar="off") : une ancienne adresse ne mène à rien. */
export function BarSoon() {
  return (
    <Screen>
      <Stack.Screen options={{ title: 'Bar de la soirée' }} />
      <Empty>Le bar de la soirée arrive bientôt.</Empty>
    </Screen>
  );
}
