import { useLocalSearchParams } from 'expo-router';

import { EventEntry } from '@/components/EventEntry';

/** Billet ouvert par l'appareil photo du téléphone (lien du QR) : il est validé aussitôt. */
export default function EventScanTicketScreen() {
  const { id, token } = useLocalSearchParams<{ id: string; token: string }>();
  return <EventEntry eventId={id} initialToken={/^[0-9a-f]{64}$/i.test(token ?? '') ? token : undefined} />;
}
