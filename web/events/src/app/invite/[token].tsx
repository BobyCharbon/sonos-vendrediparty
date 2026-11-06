import { useLocalSearchParams } from 'expo-router';

import { InviteCardScreen } from '@/components/InviteCardScreen';
import { InviteScreen } from '@/components/InviteScreen';
import { invitesV2On } from '@/lib/features';

/** Lien d'invitation à un événement. Invitations v2 (bêta) : la carte lisible sans compte et la réponse en une fois ;
 * sinon l'ancien parcours (événement sur invitation : inscription, profil complet, puis l'événement). */
export default function EventInvite() {
  const { token } = useLocalSearchParams<{ token: string }>();
  return invitesV2On ? <InviteCardScreen token={token} /> : <InviteScreen kind="event" token={token} />;
}
