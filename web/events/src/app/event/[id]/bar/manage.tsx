import { useLocalSearchParams } from 'expo-router';

import { BarManage } from '@/components/bar/BarManage';
import { BarSoon } from '@/components/bar/BarSoon';
import { barOn } from '@/lib/features';

/** « Gérer le bar » : organisateur, co-organisateurs, admin. */
export default function BarManageRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return barOn ? <BarManage eventId={id} /> : <BarSoon />;
}
