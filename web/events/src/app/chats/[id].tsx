import { Stack, useLocalSearchParams } from 'expo-router';

import { GroupChat } from '@/components/GroupChat';
import { Empty, Screen } from '@/components/ui';

const GROUP_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function GroupChatRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  if (typeof id !== 'string' || !GROUP_ID.test(id)) {
    return (
      <Screen>
        <Stack.Screen options={{ title: 'Discussion' }} />
        <Empty>Cette discussion n’existe pas.</Empty>
      </Screen>
    );
  }
  return <GroupChat key={id} id={id} />;
}
