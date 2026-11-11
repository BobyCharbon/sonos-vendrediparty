import { useLocalSearchParams } from 'expo-router';

import { BarSoon } from '@/components/bar/BarSoon';
import { MyBarScreen } from '@/components/bar/MyBarScreen';
import { barOn } from '@/lib/features';

/** « Mon bar » : solde, QR unique, carte et commande (invité noté Présent). */
export default function MyBarRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return barOn ? <MyBarScreen eventId={id} /> : <BarSoon />;
}
