import { useLocalSearchParams } from 'expo-router';

import { InviteScreen } from '@/components/InviteScreen';

/** Lien d'invitation d'un événement sur invitation (réservé à un groupe) : rejoindre cet événement seulement. */
export default function EventInvite() {
  const { token } = useLocalSearchParams<{ token: string }>();
  return <InviteScreen kind="event" token={token} />;
}
