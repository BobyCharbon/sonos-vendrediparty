import { useLocalSearchParams } from 'expo-router';

import { BarRecapScreen } from '@/components/bar/BarRecapScreen';
import { BarSoon } from '@/components/bar/BarSoon';
import { barOn } from '@/lib/features';

/** « Récapitulatif du bar » : organisateur, co-organisateurs, admin (la base refuse les autres). */
export default function BarRecapRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return barOn ? <BarRecapScreen eventId={id} /> : <BarSoon />;
}
