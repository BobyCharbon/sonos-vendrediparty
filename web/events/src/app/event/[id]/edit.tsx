import { useLocalSearchParams } from 'expo-router';

import { EventForm } from '@/components/EventForm';
import { NotAllowed } from '@/components/NotAllowed';
import { Loading } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { supabase } from '@/lib/supabase';

type Access = { created_by: string; status: string; event_organizers: { user_id: string }[] } | null;

export default function EditEvent() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const me = useMe();
  const { can } = useAuth();
  // Même règle que le bouton « Modifier » de la fiche (la base reste la garde) : sinon une page claire, pas le formulaire.
  const { data, loading } = useQuery(async () => {
    const { data: ev } = await supabase.from('events').select('created_by, status, event_organizers(user_id)').eq('id', id).maybeSingle();
    return (ev as Access) ?? null;
  }, [id]);
  if (loading && !data) return <Loading />;
  const organizer = !!data && (data.created_by === me.id || data.event_organizers.some((o) => o.user_id === me.id));
  const allowed = can('events.manage_all') || (organizer && (data!.status !== 'published' || can('events.edit_own_published')));
  if (!allowed) {
    return <NotAllowed title="Tu ne peux pas modifier cet événement" text="Seuls ses organisateurs (et les admins) peuvent le modifier. Tu peux le consulter et y répondre depuis sa fiche." />;
  }
  return <EventForm eventId={id} />;
}
