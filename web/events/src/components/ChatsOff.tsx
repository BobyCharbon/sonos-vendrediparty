import { Stack } from 'expo-router';

import { Empty, Screen } from '@/components/ui';

/** Discussions éteintes (production, app/features.py) : une ancienne adresse /chats ne mène nulle part. */
export function ChatsOff() {
  return (
    <Screen>
      <Stack.Screen options={{ title: 'Discussions' }} />
      <Empty>Cette page n’existe pas.</Empty>
    </Screen>
  );
}
