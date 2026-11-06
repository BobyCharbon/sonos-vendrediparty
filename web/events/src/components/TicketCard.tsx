import { useCallback, useEffect, useRef, useState } from 'react';
import { Image, Modal, Pressable, StyleSheet, View } from 'react-native';

import { formatLongDay, formatTime, plural } from '@/lib/format';
import { enter, pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import { fetchMyTicket, prettyCode, qrDataUri, renewMyTicket, ticketLink, type MyTicket, chf } from '@/lib/tickets';

import { PayOrganizer } from './PayOrganizer';
import { WalletButton } from './WalletButton';
import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from './SheetGesture';
import { Avatar, Button, ConfirmButton, ErrorText, T } from './ui';

type Props = {
  event: { id: string; title: string; starts_at: string | null; location_name: string | null };
  me: { id: string; display_name: string; avatar_url: string | null };
  /** Change quand ma réponse change (Présent, accompagnants, liste d'attente) : le billet est relu. */
  answerKey: string;
};

/** Pendant que le billet est affiché, l'arrivée scannée par l'organisateur apparaît d'elle-même. */
const ARRIVAL_POLL_MS = 4000;
/** En attente de l'organisateur : le billet remis apparaît de lui-même (la notification le dit aussi). */
const ISSUE_POLL_MS = 15000;

/**
 * « Ton billet » sur la page d'un événement où l'on est noté Présent : QR personnel à montrer à l'entrée.
 * Toucher l'ouvre en grand, plein écran, luminosité de lecture (fond blanc autour du QR).
 * Seulement si l'organisateur a activé « Billets QR » ET remis le billet ; sinon rien (option éteinte : seulement
 * le paiement d'un événement payant) ou l'attente (« Ton billet arrivera quand l'organisateur l'aura validé »).
 */
export function TicketCard({ event, me, answerKey }: Props) {
  const [ticket, setTicket] = useState<MyTicket | null>(null);
  const [open, setOpen] = useState(false);
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const sheetTop = useSheetTop();
  useSheetDrag(open, () => setOpen(false), card, overlay);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => fetchMyTicket(event.id).then(
    (t) => { setTicket(t); setError(null); },
    (e: unknown) => setError(e instanceof Error ? e.message : 'Le billet ne se charge pas. Réessaie.'),
  ), [event.id]);

  // Relu à l'ouverture et quand ma réponse change (answerKey).
  useEffect(() => { void load(); }, [load, answerKey]);

  const waiting = open && ticket?.state === 'ok' && !ticket.checked_in_at;
  useEffect(() => {
    if (!waiting) return;
    const timer = setInterval(() => { void load(); }, ARRIVAL_POLL_MS);
    return () => clearInterval(timer);
  }, [waiting, load]);

  const pending = ticket?.state === 'pending';
  useEffect(() => {
    if (!pending) return;
    const timer = setInterval(() => { void load(); }, ISSUE_POLL_MS);
    return () => clearInterval(timer);
  }, [pending, load]);

  if (error && !ticket) return <ErrorText error={error} />;
  if (!ticket || ticket.state === 'none') return null;
  if (ticket.state === 'waitlist') {
    return (
      <View style={st.card}>
        <T size={22}>🎟️</T>
        <T muted size={14} style={{ flex: 1 }}>Ton billet arrivera dès qu’une place se libère pour toi.</T>
      </View>
    );
  }
  // Option « Billets QR » éteinte : pas de billet, seulement payer sa place si l'événement est payant.
  if (ticket.state === 'off') return <PayOrganizer eventId={event.id} ticket={ticket} onTicket={setTicket} />;
  if (ticket.state === 'pending') {
    return (
      <View style={{ gap: 8 }}>
        <View testID="ticket-pending" accessibilityRole="summary" style={[st.card, st.cardPending]}>
          <T size={22}>🎟️</T>
          <View style={{ flex: 1, gap: 2 }}>
            <T weight="bold" size={16}>Ton billet</T>
            <T muted size={14}>Ton billet arrivera quand l’organisateur l’aura validé.</T>
            {/* Payé ou en attente de confirmation : dit une seule fois, par la carte de paiement juste dessous. */}
            {ticket.price_chf && !ticket.paid && !ticket.pay_pending ? (
              <T size={12} color={colors.coralSoft}>Paie ta place : le billet arrive dès que l’organisateur a reçu ton paiement.</T>
            ) : null}
          </View>
        </View>
        <PayOrganizer eventId={event.id} ticket={ticket} onTicket={setTicket} />
      </View>
    );
  }

  const link = ticketLink(location.origin, event.id, ticket.token);
  const arrived = ticket.checked_in_at ? formatTime(ticket.checked_in_at) : null;
  const priced = ticket.price_chf != null && ticket.price_chf > 0;
  const payLine = ticket.paid ? '✓ Payé' : ticket.pay_pending ? 'Payé · en attente de confirmation' : `À payer : ${chf(ticket.price_chf ?? 0)}`;
  const payColor = ticket.paid ? colors.mint : ticket.pay_pending ? colors.coral : colors.coralSoft;

  return (
    <View style={{ gap: 8 }}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={arrived ? `Ton billet, arrivée enregistrée à ${arrived}` : 'Afficher ton billet à montrer à l’entrée'}
        onPress={() => setOpen(true)}
        style={({ pressed }) => [st.card, st.cardTicket, pressTransition, pressed && { transform: [{ scale: 0.98 }], opacity: 0.9 }]}
      >
        <View style={st.thumb}>
          <Image source={{ uri: qrDataUri(link) }} style={st.thumbQr} accessibilityIgnoresInvertColors />
        </View>
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="bold" size={16}>Ton billet</T>
          <T size={13} color={arrived ? colors.mint : colors.textSoft}>
            {arrived ? `✓ Arrivée enregistrée à ${arrived}` : 'À montrer à l’entrée'}
          </T>
          {/* Payé / en attente : la carte de paiement juste dessous le dit déjà (une seule fois). */}
          {priced && !ticket.paid && !ticket.pay_pending ? <T size={12} color={payColor}>{payLine}</T> : null}
        </View>
        <T size={13} weight="bold" color={colors.accent}>Afficher ›</T>
      </Pressable>
      {/* Nouveau QR : bouton remis à neuf (erreur effacée). */}
      <WalletButton key={ticket.token} eventId={event.id} />
      <PayOrganizer eventId={event.id} ticket={ticket} onTicket={setTicket} />

      {/* Fenêtre au-dessus de toute la page (la page derrière garde sa hauteur). */}
      <Modal visible={open} transparent animationType="fade" onRequestClose={() => setOpen(false)}>
        <View ref={overlay} accessibilityViewIsModal accessibilityLabel="Ton billet" style={[st.overlay, { paddingTop: sheetTop }]}>
          <SheetBackdrop onPress={() => setOpen(false)} />
          <View ref={card} style={[st.ticket, enter('rise')]}>
            <SheetTop onClose={() => setOpen(false)} />
            <View style={st.who}>
              <Avatar id={me.id} name={me.display_name} photo={me.avatar_url} size={44} profile={false} />
              <View style={{ flex: 1 }}>
                <T weight="bold" size={18} numberOfLines={1}>{me.display_name}</T>
                {ticket.plus_ones ? <T muted size={13}>+ {plural(ticket.plus_ones, 'accompagnant')}</T> : null}
              </View>
              {arrived ? <View style={st.stamp}><T size={12} weight="bold" color={colors.onMint}>ARRIVÉ {arrived}</T></View> : null}
            </View>
            <T style={{ ...font.display, fontSize: 22, lineHeight: 26 }} numberOfLines={2}>{event.title}</T>
            {event.starts_at ? <T muted size={14}>{formatLongDay(event.starts_at)} · {formatTime(event.starts_at)}{event.location_name ? ` · ${event.location_name}` : ''}</T> : null}
            <View style={st.qrBox}>
              <Image source={{ uri: qrDataUri(link) }} style={st.qr} accessibilityLabel="QR code de ton billet" />
            </View>
            <T muted size={13} style={{ textAlign: 'center' }}>Sans scanner, donne ce code :</T>
            <View accessible accessibilityLabel={`Code ${ticket.code.split('').join(' ')}`}>
              <T style={st.code}>{prettyCode(ticket.code)}</T>
            </View>
            {priced ? (
              <T size={14} weight="semibold" color={payColor} style={{ textAlign: 'center' }}>
                {ticket.paid ? '✓ Place payée' : ticket.pay_pending ? 'Payé · en attente de confirmation' : `${chf(ticket.price_chf ?? 0)} à payer à l’organisateur`}
              </T>
            ) : null}
            <Button label="Fermer" onPress={() => setOpen(false)} />
            <ConfirmButton
              small
              label="Nouveau QR (l’ancien ne marchera plus)"
              confirmLabel="Oui, changer (Cartes se met à jour)"
              onConfirm={async () => {
                try { setTicket(await renewMyTicket(event.id)); setError(null); } catch (e) { setError(e instanceof Error ? e.message : 'Échec. Réessaie.'); }
              }}
            />
            <ErrorText error={error} />
          </View>
        </View>
      </Modal>
    </View>
  );
}

const st = StyleSheet.create({
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  cardPending: { borderStyle: 'dashed', borderColor: colors.lineStrong },
  cardTicket: { borderColor: 'rgba(91,227,166,.45)', backgroundColor: '#1B2A33' },
  thumb: { width: 52, height: 52, borderRadius: radius.sm, backgroundColor: '#fff', padding: 3 },
  thumbQr: { width: 46, height: 46 },
  // Défile si le billet dépasse un petit écran.
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  ticket: { width: '100%', maxWidth: 380, marginVertical: 'auto', gap: 10, padding: 18, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  who: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  stamp: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: radius.sm, backgroundColor: colors.mint, transform: [{ rotate: '-6deg' }] },
  qrBox: { alignSelf: 'center', width: '100%', maxWidth: 270, aspectRatio: 1, backgroundColor: '#fff', borderRadius: radius.md, padding: 8, marginVertical: 4 },
  qr: { width: '100%', height: '100%' },
  code: { ...font.display, fontSize: 30, lineHeight: 34, letterSpacing: 4, textAlign: 'center', color: colors.text, fontVariant: ['tabular-nums'] },
});
