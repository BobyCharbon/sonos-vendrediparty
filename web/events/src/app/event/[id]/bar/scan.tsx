import { useLocalSearchParams } from 'expo-router';

import { BarScanner } from '@/components/bar/BarScanner';
import { BarSoon } from '@/components/bar/BarSoon';
import { barOn } from '@/lib/features';

/** « Scanner au bar » : barmans de la soirée et organisateurs. */
export default function BarScanRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return barOn ? <BarScanner eventId={id} /> : <BarSoon />;
}
