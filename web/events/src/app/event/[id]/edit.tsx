import { useLocalSearchParams } from 'expo-router';

import { EventForm } from '@/components/EventForm';

export default function EditEvent() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <EventForm eventId={id} />;
}
