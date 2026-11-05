import { Stack } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatTime } from '@/lib/format';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import { checkInTicket, confirmPayment, fetchCheckins, issueTicket, parseScanned, setArrival, setPaid, type TicketPerson } from '@/lib/tickets';

import { PersonName } from './PersonName';
import { ScanControls, ScanVerdict, type Verdict } from './TicketScanner';
import { IssueButton, TicketsManager } from './TicketsManager';
import { Avatar, Button, ErrorText, Screen, Section, T, Title } from './ui';

type EventHead = {
  id: string; title: string; price_chf: number | null; max_participants: number | null;
  created_by: string; event_organizers: { user_id: string }[];
  /** Option « Billets QR » (migration 20261104233000 ; absente avant : éteinte). */
  tickets_enabled?: boolean;
};

/** Retour au toucher : un choc pour « entre », trois pour « attention ». */
function buzz(ok: boolean) {
  try { navigator.vibrate?.(ok ? 30 : [60, 80, 60, 80, 60]); } catch { /* Pas de vibreur. */ }
}

/**
 * Entrée d'un événement (organisateur, co-organisateurs, admins) : scanner les billets, voir qui est arrivé,
 * cocher « payé ». `initialToken` : billet ouvert par l'appareil photo du téléphone (lien du QR).
 */
export function EventEntry({ eventId, initialToken }: { eventId: string; initialToken?: string }) {
  const [verdict, setVerdict] = useState<Verdict | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const last = useRef<{ text: string; at: number } | null>(null);
  const { can, profile } = useAuth();

  const { data, reload, error: loadError } = useQuery(async () => {
    const [ev, people] = await Promise.all([
      supabase.from('events').select('id, title, price_chf, max_participants, created_by, tickets_enabled, event_organizers(user_id)').eq('id', eventId).single(),
      fetchCheckins(eventId),
    ]);
    return { event: must(ev) as EventHead, people };
  }, [eventId]);
  // Caméra : droit « Scanner les billets », ou organisateur / co-organisateur / admin de l'événement.
  // Avec seulement « Confirmer les paiements », la liste et les paiements restent, sans caméra (la base refuserait le scan).
  const organizes = !!data && !!profile
    && (data.event.created_by === profile.id || data.event.event_organizers.some((o) => o.user_id === profile.id));
  const canScan = can('tickets.scan') || can('events.manage_all') || organizes;
  const ticketsOn = !!data?.event.tickets_enabled;

  const scan = useCallback(async (raw: string) => {
    // La caméra lit le même QR plusieurs fois par seconde : un seul passage pour le même billet d'affilée.
    const now = Date.now();
    if (last.current && last.current.text === raw && now - last.current.at < 3000) return;
    last.current = { text: raw, at: now };
    const ticket = parseScanned(raw);
    if (!ticket) { buzz(false); setVerdict({ result: 'invalid' }); return; }
    setBusy(true);
    try {
      const result = await checkInTicket(eventId, ticket);
      buzz(result.result === 'ok');
      setVerdict(result);
      setError(null);
      void reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(false);
    }
  }, [eventId, reload]);

  const opened = useRef(false);
  useEffect(() => {
    if (initialToken && !opened.current) { opened.current = true; void scan(initialToken); }
  }, [initialToken, scan]);

  async function act(p: Promise<TicketPerson>) {
    try {
      const person = await p;
      setVerdict((v) => (v && 'person' in v && v.person.user_id === person.user_id ? { ...v, person } : v));
      setError(null);
      setNotice(person.notice ?? null);  // billet retiré avec le paiement annulé
      void reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    }
  }

  if (loadError) return <Screen><Title size={24}>Entrée</Title><ErrorText error={loadError} /></Screen>;
  const people = data?.people ?? [];
  const present = people.filter((p) => !p.waitlisted);
  const arrived = present.filter((p) => p.checked_in_at);
  const heads = (list: TicketPerson[]) => list.reduce((n, p) => n + 1 + p.plus_ones, 0);
  const priced = !!data?.event.price_chf;
  const paidCount = present.filter((p) => p.paid).length;

  return (
    <>
      <Stack.Screen options={{ title: 'Entrée' }} />
      <Screen>
        <View style={{ gap: 4 }}>
          <Title size={26}>{canScan ? 'Scanner les billets' : 'Paiements à l’entrée'}</Title>
          {data ? <T muted size={14}>{data.event.title}</T> : null}
        </View>

        {canScan ? <ScanControls paused={!!verdict || busy} onScanned={scan} /> : null}
        {verdict ? <ScanVerdict verdict={verdict} onPaid={(p, paid) => act(setPaid(eventId, p.user_id, paid, p))}
          onConfirm={(p, received) => act(confirmPayment(eventId, p.user_id, received, p))}
          onIssue={(p) => act(issueTicket(eventId, p.user_id, true)).then(() => {
            // Billet remis sur place : le même QR repasse et l'arrivée est notée.
            const again = last.current?.text;
            last.current = null;
            if (again) void scan(again);
          })}
          onNext={() => { setVerdict(null); last.current = null; }} /> : null}
        <ErrorText error={error} />
        {notice ? <T size={14} weight="semibold" color={colors.coral}>{notice}</T> : null}

        {data ? (
          <TicketsManager eventId={eventId} enabled={ticketsOn} canToggle={organizes || can('events.manage_all')}
            onToggled={() => { void reload(); }} onIssued={() => { void reload(); }} list={false} />
        ) : null}

        <Section
          title="Arrivées"
          right={<T size={13} weight="bold" color={colors.mint}>{heads(arrived)} / {heads(present)} personnes</T>}
        >
          {priced ? <T muted size={13}>{paidCount} / {present.length} ont payé</T> : null}
          {present.length === 0 ? <T muted size={14}>Personne n’est encore noté présent.</T> : null}
          {people.map((p) => (
            // Nom et état sur une ligne, gestes dessous : sur un téléphone, trois boutons écrasaient le nom (« Z… »).
            <View key={p.user_id} style={[st.row, p.checked_in_at && st.rowIn]}>
              <View style={st.who}>
                <Avatar id={p.user_id} name={p.display_name} photo={p.avatar_url} size={36} />
                <View style={{ flex: 1, minWidth: 0 }}>
                  {/* « +1 » à part : un long nom se coupe (« … ») sans jamais cacher les accompagnants. */}
                  <View style={st.nameLine}>
                    <T weight="semibold" numberOfLines={1} style={{ flexShrink: 1 }}><PersonName id={p.user_id} pseudo={p.display_name} weight="semibold" /></T>
                    {p.plus_ones ? <T muted size={13}>+{p.plus_ones}</T> : null}
                  </View>
                  <T size={12} color={p.checked_in_at ? colors.mint : colors.muted}>
                    {p.waitlisted ? 'Liste d’attente' : p.checked_in_at ? `✓ Arrivé·e à ${formatTime(p.checked_in_at)}` : 'Attendu·e'}
                    {ticketsOn && !p.waitlisted ? <T size={12} color={p.issued ? colors.mint : colors.muted}>{p.issued ? '  ·  billet remis' : '  ·  billet à remettre'}</T> : null}
                    {priced && !p.waitlisted ? <T size={12} color={p.paid ? colors.mint : p.pay_pending ? colors.coral : colors.coralSoft}>{p.paid ? '  ·  payé' : p.pay_pending ? '  ·  payé, à confirmer' : '  ·  pas payé'}</T> : null}
                  </T>
                </View>
              </View>
              {p.waitlisted ? null : <View style={st.actions}>
                {priced && !p.waitlisted && p.pay_pending ? (
                  <Button small label="Reçu ✓" onPress={() => act(confirmPayment(eventId, p.user_id, true))} />
                ) : priced && !p.waitlisted ? (
                  <Button small variant="secondary" label={p.paid ? 'Payé ✓' : 'Payé ?'} onPress={() => act(setPaid(eventId, p.user_id, !p.paid, p))} />
                ) : null}
                {ticketsOn && !p.waitlisted ? <IssueButton person={p} onPress={(issued) => act(issueTicket(eventId, p.user_id, issued))} /> : null}
                {!p.waitlisted ? (
                  <Button small variant={p.checked_in_at ? 'ghost' : 'secondary'} label={p.checked_in_at ? 'Annuler' : 'Arrivé'}
                    onPress={() => act(setArrival(eventId, p.user_id, !p.checked_in_at))} />
                ) : null}
              </View>}
            </View>
          ))}
        </Section>
      </Screen>
    </>
  );
}

const st = StyleSheet.create({
  row: { gap: 8, paddingVertical: 8, paddingHorizontal: 8, borderRadius: radius.md },
  who: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  nameLine: { flexDirection: 'row', alignItems: 'baseline', gap: 6, minWidth: 0 },
  // Sous le nom, alignés après la photo (36 px + 10 px d'écart).
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingLeft: 46 },
  rowIn: { backgroundColor: 'rgba(91,227,166,0.08)' },
});
