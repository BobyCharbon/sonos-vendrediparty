import { Stack } from 'expo-router';

import { Empty, Screen } from '@/components/ui';

/** Production, hors bêta-testeurs : les Discussions sont « Bientôt », comme les Événements. */
export function ChatsSoon() {
  return (
    <Screen>
      <Stack.Screen options={{ title: 'Discussions' }} />
      <Empty>💬 Les discussions arrivent bientôt.</Empty>
    </Screen>
  );
}
