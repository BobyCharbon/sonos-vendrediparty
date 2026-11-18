import { useLocalSearchParams } from 'expo-router';

import { SacScreen } from '@/components/pronos/list/SacScreen';

/** « Ton sac » d'un groupe (`?group=<id>`) ou d'une soirée (`?event=<id>`) : solde, remontée, historique à soi seul. */
export default function PronoSac() {
  const { group, event } = useLocalSearchParams<{ group?: string; event?: string }>();
  return <SacScreen group={group} event={event} />;
}
