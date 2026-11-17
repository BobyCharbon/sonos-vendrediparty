import { useLocalSearchParams } from 'expo-router';

import { EventForm } from '@/components/EventForm';
import { NotAllowed } from '@/components/NotAllowed';
import { useAuth } from '@/lib/auth';

export default function NewEvent() {
  const { can } = useAuth();
  // « Créer un événement pour le groupe » (page du groupe) : ?group=<id>.
  // « Organiser le sam. 28 » / « Faire voter le groupe » (Agenda › Qui est libre ?) : titre, début, fin ou dates du sondage.
  const { group, title, start, end, poll } = useLocalSearchParams<{ group?: string; title?: string; start?: string; end?: string; poll?: string }>();
  if (!can('events.create')) {
    return <NotAllowed title="Tu ne peux pas proposer d’événement" text="Ton rôle ne permet pas de créer un événement. Demande à un admin si tu veux en organiser un." />;
  }
  const iso = (v: unknown) => (typeof v === 'string' && !Number.isNaN(Date.parse(v)) ? v : undefined);
  const prefill = typeof title === 'string' || iso(start) || typeof poll === 'string' ? {
    title: typeof title === 'string' ? title.slice(0, 120) : undefined, starts: iso(start), ends: iso(end),
    poll: typeof poll === 'string' ? poll.split(',').filter((x) => iso(x)).slice(0, 10) : undefined,
  } : undefined;
  return <EventForm group={typeof group === 'string' && /^[0-9a-f-]{36}$/i.test(group) ? group : undefined} prefill={prefill} />;
}
