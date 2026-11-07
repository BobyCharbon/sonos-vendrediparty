import { useRef, useState } from 'react';
import { Linking, Modal, Pressable, StyleSheet, View } from 'react-native';

import { pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import { chf, declarePayment, fetchPayInfo, formatIban, type MyTicket, type PayInfo, type TicketPayment } from '@/lib/tickets';

import { LinkedText } from './LinkedText';
import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from './SheetGesture';
import { Button, ErrorText, T } from './ui';

const LINK_LABELS: Record<string, string> = {
  revolut: 'Payer avec Revolut', paypal: 'Payer avec PayPal', lydia: 'Payer avec Lydia', other: 'Ouvrir le lien de paiement',
};

/** Lien de paiement sûr (https seulement) ; le profil de paiement est déjà nettoyé côté serveur, on revérifie. */
function safeLink(url: string): string | null {
  try { return new URL(url).protocol === 'https:' ? url : null; } catch { return null; }
}

/** Copie avec retour visible (« Copié ✓ ») ; sans presse-papiers, le texte reste affiché pour une copie à la main. */
function CopyRow({ label, value, shown = value }: { label: string; value: string; shown?: string }) {
  const [done, setDone] = useState<'ok' | 'fail' | null>(null);
  async function copy() {
    try { await navigator.clipboard.writeText(value); setDone('ok'); } catch { setDone('fail'); }
  }
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Copier ${label} : ${shown}`} onPress={copy}
      style={({ pressed }) => [st.row, pressTransition, pressed && { opacity: 0.75 }]}>
      <View style={{ flex: 1, minWidth: 0 }}>
        <T muted size={12}>{label}</T>
        <T weight="semibold" size={15}>{shown}</T>
      </View>
      <T size={13} weight="bold" color={done === 'ok' ? colors.mint : colors.accent}>{done === 'ok' ? 'Copié ✓' : done === 'fail' ? 'Copie à la main' : 'Copier'}</T>
    </Pressable>
  );
}

/** Moyens de paiement de l'organisateur, montant et référence, puis « J'ai payé ». */
function PaySheet({ info, onDeclare, onClose, busy, error }: { info: PayInfo; onDeclare: () => void; onClose: () => void; busy: boolean; error: string | null }) {
  const twint = info.links.twint;
  const links = Object.entries(info.links).filter(([k, v]) => k !== 'twint' && safeLink(v));
  const nothing = !twint && !links.length && !info.iban && !info.payment_info;
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const sheetTop = useSheetTop();
  useSheetDrag(true, onClose, card, overlay);   // monté seulement quand la fenêtre est ouverte
  return (
    <View ref={overlay} style={[st.overlay, { paddingTop: sheetTop }]}>
      <SheetBackdrop onPress={onClose} />
      <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Payer l’organisateur">
        <SheetTop onClose={onClose} />
        <T muted size={13}>Payer {info.organizer_name ?? 'l’organisateur'}</T>
        <T style={st.amount}>{chf(info.amount)}</T>
        {info.payment_info ? <LinkedText size={14} color={colors.textSoft} text={info.payment_info} /> : null}
        {info.note ? <T size={13} muted>« {info.note} »</T> : null}
        {twint ? <CopyRow label="Twint : numéro à copier dans l’app Twint" value={twint} /> : null}
        {links.map(([kind, url]) => (
          <Button key={kind} variant="secondary" label={LINK_LABELS[kind] ?? 'Ouvrir le lien de paiement'} onPress={() => Linking.openURL(url)} />
        ))}
        {info.iban ? (
          <>
            <CopyRow label={`Virement · IBAN${info.holder ? ` de ${info.holder}` : ''}`} value={info.iban} shown={formatIban(info.iban)} />
            <CopyRow label="Communication" value={info.reference} />
          </>
        ) : null}
        {nothing ? (
          <T size={14} color={colors.coralSoft}>{info.organizer_name ?? 'L’organisateur'} n’a pas encore rempli son profil de paiement : demande-lui comment payer (Twint, espèces…).</T>
        ) : null}
        <Button label="J’ai payé" loading={busy} onPress={onDeclare} />
        <Button variant="ghost" label="Fermer" onPress={onClose} />
        <ErrorText error={error} />
      </View>
    </View>
  );
}

/**
 * Paiement « entre amis » sur le billet (avec ou sans QR : option « Billets QR » éteinte ou billet pas encore remis) : à payer → « Payer l'organisateur » ; payé, en attente de confirmation ;
 * ou ✓ payé (confirmé par l'organisateur).
 */
export function PayOrganizer({ eventId, ticket, onTicket }: { eventId: string; ticket: TicketPayment; onTicket: (t: MyTicket) => void }) {
  const [info, setInfo] = useState<PayInfo | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const price = ticket.price_chf ?? 0;

  async function open() {
    setBusy(true);
    try {
      const found = await fetchPayInfo(eventId);
      if (!found) setError('Le paiement n’est pas disponible pour cet événement.');
      setInfo(found);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  async function declare(declared: boolean) {
    setBusy(true);
    try {
      onTicket(await declarePayment(eventId, declared));
      setInfo(null);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  if (price <= 0) return null;
  if (ticket.paid) {
    return <View style={[st.status, st.paid]}><T size={14} weight="bold" color={colors.mint}>✓ Place payée · {chf(price)}</T></View>;
  }
  if (ticket.pay_pending) {
    return (
      <View style={[st.status, st.pending]}>
        <View style={{ flex: 1 }}>
          <T size={14} weight="bold" color={colors.coral}>Payé · en attente de confirmation</T>
          <T size={12} muted>L’organisateur confirme dès qu’il a reçu tes {chf(price)}.</T>
        </View>
        <Button small variant="ghost" label="Annuler" loading={busy} onPress={() => declare(false)} />
        <ErrorText error={error} />
      </View>
    );
  }
  return (
    <View style={{ gap: 6 }}>
      <Button label={`Payer l’organisateur · ${chf(price)}`} loading={busy && !info} onPress={open} />
      {!info ? <ErrorText error={error} /> : null}
      <Modal visible={!!info} transparent animationType="fade" onRequestClose={() => setInfo(null)}>
        {info ? <PaySheet info={info} busy={busy} error={error} onDeclare={() => declare(true)} onClose={() => setInfo(null)} /> : null}
      </Modal>
    </View>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  sheet: { width: '100%', maxWidth: 380, marginVertical: 'auto', gap: 10, padding: 18, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  amount: { ...font.display, fontSize: 34, lineHeight: 38, color: colors.text },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: radius.md, backgroundColor: colors.fill },
  status: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: radius.md, borderWidth: 1, flexWrap: 'wrap' },
  paid: { borderColor: 'rgba(91,227,166,.45)', backgroundColor: colors.mintDim },
  pending: { borderColor: 'rgba(255,179,71,.45)', backgroundColor: colors.coralDim },
});
