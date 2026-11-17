import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';

import { TopBar } from '@/components/agenda/Bits';
import { RequestDetail } from '@/components/agenda/Requests';
import { Button, ErrorText, Screen, Skeleton, T, Toast } from '@/components/ui';
import { agoText, errorText, rpc, type Booking } from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { radius } from '@/lib/theme';

const DONE: Record<string, string> = {
  accept: 'Accepté : le rendez-vous est dans ton agenda.', refuse: 'Refusé : le créneau se libère, tout est effacé.',
  block: 'Expéditeur bloqué, demande refusée.', report: 'Signalement envoyé, demande refusée.', cancel: 'Rendez-vous annulé.',
};

/** Demande reçue (maquette 6c) : ouverte depuis la liste ou la notification « Nouvelle demande de rendez-vous ». */
export default function RequestScreen() {
  const me = useMe();
  const p = useLocalSearchParams<{ id: string }>();
  const { data, error, loading, reload } = useQuery(async () => (await rpc<Booking[]>('agenda_booking_requests')).find((b) => b.id === p.id) ?? null, [p.id]);
  useSignal([`user:${me.id}`], reload);
  const [toast, setToast] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const linkCut = async () => {
    if (!data) return;
    try { await rpc('agenda_link_set', { id: data.link_id, action: 'bookings_off' }); setToast('Demandes coupées pour ce lien.'); } catch (e) { setErr(errorText(e)); }
  };
  return (
    <Screen>
      <TopBar back="Mes liens" fallback="/agenda/links" title="Demande reçue"
        subtitle={data ? `Par ton lien « ${data.link_name} » · ${agoText(data.created_at)}` : undefined} />
      <ErrorText error={error ?? err} />
      {loading && !data ? <Skeleton height={300} radius={radius.lg} /> : null}
      {!loading && !data && !error ? <T muted>Cette demande n’existe plus : refusée, annulée ou effacée.</T> : null}
      {data ? <RequestDetail b={data} onDone={async (what) => { setToast(DONE[what] ?? null); await reload(); }} /> : null}
      {data ? <Button variant="ghost" label="Couper les demandes de ce lien" onPress={() => void linkCut()} /> : null}
      {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
    </Screen>
  );
}
