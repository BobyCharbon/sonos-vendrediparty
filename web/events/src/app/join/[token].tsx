import { useLocalSearchParams } from 'expo-router';

import { AppJoinScreen } from '@/components/AppJoinScreen';

/** Lien personnel d'invitation dans Party : « X t'invite sur Party », lisible avant connexion. */
export default function JoinParty() {
  const { token } = useLocalSearchParams<{ token: string }>();
  return <AppJoinScreen token={token} />;
}
