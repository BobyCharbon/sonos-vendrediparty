import { Stack } from 'expo-router';

import { Empty, Screen } from '@/components/ui';
import { storeApp } from '@/lib/features';

/** Bar de la soirée éteint (production, app/features.py : data-bar="off") : une ancienne adresse ne mène à rien. */
export function BarSoon() {
  return (
    <Screen>
      <Stack.Screen options={{ title: storeApp ? 'Party' : 'Bar de la soirée' }} />
      {/* App App Store (refus Apple 1.4.3) : le bar n'existe pas dans l'app, jamais de « bientôt ». */}
      <Empty>{storeApp ? 'Cette page n’est pas disponible dans l’app.' : 'Le bar de la soirée arrive bientôt.'}</Empty>
    </Screen>
  );
}
