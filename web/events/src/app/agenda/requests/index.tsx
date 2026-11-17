import { useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Divider, Group, Label, TopBar } from '@/components/agenda/Bits';
import { RequestCard } from '@/components/agenda/Requests';
import { Button, ErrorText, Screen, Skeleton, T, Toast, ToggleRow } from '@/components/ui';
import { errorText, rpc, type Booking, type Links } from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { supabase } from '@/lib/supabase';
import { radius } from '@/lib/theme';

const DONE: Record<string, string> = {
  accept: 'Accepté : le rendez-vous est dans ton agenda.', refuse: 'Refusé : le créneau se libère, tout est effacé.',
  block: 'Expéditeur bloqué, demande refusée.', report: 'Signalement envoyé, demande refusée.', cancel: 'Rendez-vous annulé.',
};

/**
 * Demandes reçues (maquette 6E) : d'un lien (?link=) ou de tous. En haut, les deux réglages du lien : « Demandes de
 * rendez-vous » (Couper / rallumer) et « Me prévenir des demandes » (même interrupteur que Réglages › Notifications).
 */
export default function RequestsScreen() {
  const me = useMe();
  const p = useLocalSearchParams<{ link?: string }>();
  const linkId = typeof p.link === 'string' && /^[0-9a-f-]{36}$/i.test(p.link) ? p.link : null;
  const { data, error, reload } = useQuery(async () => {
    const [requests, links] = await Promise.all([
      rpc<Booking[]>('agenda_booking_requests', linkId ? { link: linkId } : {}),
      rpc<Links>('agenda_links'),
    ]);
    return { requests, links, link: links.links.find((l) => l.id === linkId) ?? null };
  }, [linkId]);
  useSignal([`user:${me.id}`], reload);
  const [toast, setToast] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const link = data?.link;
  const pending = data?.requests.filter((r) => r.status === 'pending') ?? [];
  const decided = data?.requests.filter((r) => r.status !== 'pending') ?? [];

  async function setBooking(on: boolean) {
    if (!link) return;
    try { await rpc('agenda_link_set', { id: link.id, action: on ? 'bookings_on' : 'bookings_off' }); await reload(); setToast(on ? 'Demandes rallumées.' : 'Demandes coupées pour ce lien.'); }
    catch (e) { setErr(errorText(e)); }
  }
  async function setNotify(v: boolean) {
    await supabase.from('notification_prefs').update({ booking_requests: v }).eq('user_id', me.id);
    await reload();
  }
  async function done(what: string) {
    setToast(DONE[what] ?? null);
    await reload();
  }

  return (
    <Screen>
      <TopBar back={linkId ? 'Mes liens' : 'Agenda'} fallback={linkId ? '/agenda/links' : '/agenda'} title="Demandes reçues"
        subtitle={link ? `Par le lien « ${link.name} »` : undefined} />
      <ErrorText error={error ?? err} />
      {!data && !error ? <Skeleton height={160} radius={radius.lg} /> : null}
      {data ? (
        <Group>
          {link ? (
            <View style={{ paddingHorizontal: 14 }}>
              <ToggleRow label="Demandes de rendez-vous" hint="La personne choisit un moment, c’est toi qui acceptes." value={link.booking_enabled} onChange={(v) => void setBooking(v)} />
            </View>
          ) : null}
          {link ? <Divider /> : null}
          <View style={{ paddingHorizontal: 14 }}>
            <ToggleRow label="Me prévenir des demandes" hint="Notification sans nom ni message · aussi dans Réglages › Notifications" value={data.links.notify !== false} onChange={(v) => void setNotify(v)} />
          </View>
        </Group>
      ) : null}

      {data ? <Label>{pending.length ? `${pending.length} demande${pending.length > 1 ? 's' : ''} en attente` : 'Aucune demande en attente'}</Label> : null}
      {data && !data.requests.length ? <T muted style={{ paddingHorizontal: 4 }}>Quand quelqu’un demande un rendez-vous par ton lien, il apparaît ici. Le créneau lui est réservé 48 h.</T> : null}
      {pending.map((b, i) => <RequestCard key={b.id} b={b} index={i} onDone={done} />)}
      {decided.length ? <Label>Déjà répondu</Label> : null}
      {decided.map((b, i) => <RequestCard key={b.id} b={b} index={i} onDone={done} />)}

      {link?.booking_enabled ? <Button variant="ghost" label="Couper les demandes de ce lien" onPress={() => void setBooking(false)} /> : null}
      {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
    </Screen>
  );
}
