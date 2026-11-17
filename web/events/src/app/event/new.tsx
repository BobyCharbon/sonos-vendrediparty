import { useLocalSearchParams } from 'expo-router';

import { EventForm } from '@/components/EventForm';
import { NotAllowed } from '@/components/NotAllowed';
import { useAuth } from '@/lib/auth';

export default function NewEvent() {
  const { can } = useAuth();
  // « Créer un événement pour le groupe » (page du groupe) : ?group=<id>.
  const { group } = useLocalSearchParams<{ group?: string }>();
  if (!can('events.create')) {
    return <NotAllowed title="Tu ne peux pas proposer d’événement" text="Ton rôle ne permet pas de créer un événement. Demande à un admin si tu veux en organiser un." />;
  }
  return <EventForm group={typeof group === 'string' && /^[0-9a-f-]{36}$/i.test(group) ? group : undefined} />;
}
