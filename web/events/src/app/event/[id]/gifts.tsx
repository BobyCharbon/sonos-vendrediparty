import { Redirect, useLocalSearchParams } from 'expo-router';

import { EventGifts } from '@/components/EventGifts';
import { compagnonOn } from '@/lib/features';

/** Cadeaux Zicou de l'événement : règlement et chances pour tous, préparation pour l'admin et l'organisateur. */
export default function EventGiftsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return compagnonOn ? <EventGifts eventId={id} /> : <Redirect href={`/event/${id}`} />;
}
