import { EventForm } from '@/components/EventForm';
import { NotAllowed } from '@/components/NotAllowed';
import { useAuth } from '@/lib/auth';

export default function NewEvent() {
  const { can } = useAuth();
  if (!can('events.create')) {
    return <NotAllowed title="Tu ne peux pas proposer d’événement" text="Ton rôle ne permet pas de créer un événement. Demande à un admin si tu veux en organiser un." />;
  }
  return <EventForm />;
}
