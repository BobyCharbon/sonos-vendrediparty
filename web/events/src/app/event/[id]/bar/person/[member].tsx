import { useLocalSearchParams } from 'expo-router';

import { BarPersonScreen } from '@/components/bar/BarPersonScreen';
import { BarSoon } from '@/components/bar/BarSoon';
import { barOn } from '@/lib/features';

/** Réservations d'une personne (organisateurs, depuis « Direct »). */
export default function BarPersonRoute() {
  const { id, member } = useLocalSearchParams<{ id: string; member: string }>();
  return barOn ? <BarPersonScreen eventId={id} member={member} /> : <BarSoon />;
}
