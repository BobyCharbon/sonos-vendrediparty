import { useLocalSearchParams } from 'expo-router';

import { EventGifts } from '@/components/EventGifts';

/** Cadeaux Zicou de l'événement : règlement et chances pour tous, préparation pour l'admin et l'organisateur. */
export default function EventGiftsScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <EventGifts eventId={id} />;
}
