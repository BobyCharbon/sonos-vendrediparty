import { useLocalSearchParams } from 'expo-router';

import { EventEntry } from '@/components/EventEntry';

/** Entrée de l'événement : scanner les billets (organisateurs et admins). */
export default function EventScanScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <EventEntry eventId={id} />;
}
