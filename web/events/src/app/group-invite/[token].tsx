import { useLocalSearchParams } from 'expo-router';

import { InviteScreen } from '@/components/InviteScreen';

/** Lien d'invitation d'un groupe : on crée son compte (ou on se connecte) et on rejoint le groupe. */
export default function GroupInvite() {
  const { token } = useLocalSearchParams<{ token: string }>();
  return <InviteScreen kind="group" token={token} />;
}
