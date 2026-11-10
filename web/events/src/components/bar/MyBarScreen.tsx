import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import {
  barCancelMine, barChf, barDeclareRefund, canOrder, cartLines, errorText, fetchMyBar, phaseLine, PHASE_LABEL, useBarRefresh,
  type BarPhase, type Cart, type MyBar,
} from '@/lib/bar';
import { useQuery } from '@/lib/data';
import { colors, radius } from '@/lib/theme';

import { Badge, Button, Card, Empty, ErrorText, Loading, Screen, T, Toast } from '../ui';
import { BarBalance } from './BarBalance';
import { BarHeader } from './BarHeader';
import { BarMenu } from './BarMenu';
import { WalletButton } from '../WalletButton';
import { BarQr } from './BarQr';
import { CancelledList, PendingList, PledgesLine, ServedList } from './MyBarLists';
import { OrderSheet } from './OrderSheet';
import { RefundCard } from './RefundCard';

const PHASE_TONE: Record<BarPhase, { fg: string; bg: string }> = {
  waiting: { fg: colors.textSoft, bg: colors.surface2 },
  preorder: { fg: colors.onAccent, bg: colors.lavender },
  open: { fg: colors.onMint, bg: colors.mint },
  closed: { fg: colors.coralSoft, bg: colors.coralDim },
};

const back = (eventId: string) => (router.canGoBack() ? router.back() : router.replace(`/event/${eventId}`));

/** Où en est le bar, et ce que je peux faire maintenant. */
function PhaseCard({ bar }: { bar: MyBar }) {
  const tone = PHASE_TONE[bar.phase];
  const hint = bar.phase === 'open' ? 'Commande ici, puis montre ton QR au barman : il te sert et c’est noté.'
    : bar.phase === 'preorder' ? 'Commande maintenant : ce sera servi une fois le bar ouvert.'
      : bar.phase === 'waiting' ? 'Tu pourras commander dès que l’organisateur ouvre les commandes.'
        : 'Plus de commande possible. Ce qui n’a pas été servi est annulé, rien à payer.';
  return (
    <View style={st.phase}>
      <Badge label={PHASE_LABEL[bar.phase]} fg={tone.fg} bg={tone.bg} />
      <T weight="semibold" size={15}>{phaseLine(bar)}</T>
      <T muted size={13}>{hint}</T>
    </View>
  );
}

/**
 * « Mon bar » (invité) : le solde EN GRAND, mon QR unique, la carte avec − / +, la feuille « Valider la commande »
 * (engagement coché), ce qui attend (« Annuler 1 »), ce qui a été servi, puis rembourser. Relu toutes les 10 s.
 */
export function MyBarScreen({ eventId }: { eventId: string }) {
  const { data: bar, error, loading, reload, setData } = useQuery(() => fetchMyBar(eventId), [eventId]);
  useBarRefresh(reload, !!bar);
  const [cart, setCart] = useState<Cart>({});
  const [sheet, setSheet] = useState(false);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  async function act(key: string, run: () => Promise<MyBar>, done: string) {
    setBusy(key);
    setActionError(null);
    try {
      setData(await run());
      setToast(done);
    } catch (e) {
      setActionError(errorText(e, 'La connexion a échoué. Réessaie.'));
      void reload();
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Loading />;
  // Relecture ratée alors que l'écran a déjà ses données : on les garde (QR, feuille de commande), avec un bandeau.
  if (!bar) {
    return (
      <Screen edges={[]}>
        <BarHeader title="Mon bar" eventId={eventId} />
        {error ? <ErrorText error={error} /> : <Empty>Pas de bar pour cet événement.</Empty>}
        {error ? <Button variant="secondary" label="Réessayer" onPress={() => void reload()} /> : null}
        <Button variant="ghost" label="Retour à l’événement" onPress={() => back(eventId)} />
      </Screen>
    );
  }

  const lines = cartLines(cart, bar.items, bar.phase);
  const payee = bar.payee.name?.trim() || 'l’organisateur';
  return (
    <>
      <BarHeader title="Mon bar" eventId={eventId} />
      <Screen edges={[]}>
        <BarBalance bar={bar} />
        <PhaseCard bar={bar} />
        {!bar.eligible ? (
          <Card>
            <T weight="semibold">Réponds « Présent » à l’événement pour commander au bar.</T>
            <T muted size={13}>Le bar est réservé aux personnes notées présentes, avec un profil complet.</T>
            <Button variant="secondary" label="Retour à l’événement" onPress={() => back(eventId)} />
          </Card>
        ) : null}
        {bar.qr && bar.phase !== 'closed' ? (
          <>
            <BarQr eventId={eventId} qr={bar.qr} />
            {/* Le même QR dans l'app Cartes, avec le solde du bar (test réel du 10.11 : le bouton manquait ici). */}
            <WalletButton eventId={eventId} />
          </>
        ) : null}
        {bar.phase !== 'closed' ? <BarMenu bar={bar} cart={cart} onCart={setCart} onOrder={() => setSheet(true)} /> : null}
        <PendingList bar={bar} busy={busy} onCancel={(item, name) => void act(item, () => barCancelMine(eventId, item, 1),
          `Annulé : 1 × ${name}, de nouveau disponible pour les autres.`)} />
        <ServedList bar={bar} />
        <CancelledList bar={bar} />
        <RefundCard bar={bar} busy={busy === 'refund'} onDeclare={(amount) => void act('refund', () => barDeclareRefund(eventId, amount),
          `Remboursement de ${barChf(amount)} annoncé : ${payee} va confirmer.`)} />
        <PledgesLine pledges={bar.pledges} />
        <ErrorText error={actionError ?? (error ? 'Connexion difficile : les montants peuvent dater de quelques secondes.' : null)} />
      </Screen>
      {canOrder(bar) ? (
        <OrderSheet eventId={eventId} bar={bar} lines={lines} open={sheet} onClose={() => setSheet(false)} onStale={() => void reload()}
          onDone={(next) => {
            setData(next);
            setCart({});
            setSheet(false);
            setToast('Commande envoyée : montre ton QR au bar.');
          }} />
      ) : null}
      {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
    </>
  );
}

const st = StyleSheet.create({
  phase: { gap: 6, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
});
