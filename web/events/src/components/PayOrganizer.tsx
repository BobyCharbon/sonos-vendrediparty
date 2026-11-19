import { useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import { chf, declarePayment, fetchPayInfo, formatIban, payLinkLabel, type MyTicket, type PayInfo, type TicketPayment } from '@/lib/tickets';
import type { PaymentMode } from '@/lib/types';

import { LinkedText } from './LinkedText';
import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from './SheetGesture';
import { Button, ErrorText, T } from './ui';

const LINK_LABELS: Record<string, string> = {
  revolut: 'Payer avec Revolut', paypal: 'Payer avec PayPal', lydia: 'Payer avec Lydia', other: 'Ouvrir le lien de paiement',
};

/** Lien de paiement sûr (https seulement) ; le profil de paiement est déjà nettoyé côté serveur, on revérifie. */
export function safeLink(url: string): string | null {
  try { return new URL(url).protocol === 'https:' ? url : null; } catch { return null; }
}

/** Copie avec retour visible (« Copié ✓ ») ; sans presse-papiers, le texte reste affiché pour une copie à la main. */
export function CopyRow({ label, value, shown = value }: { label: string; value: string; shown?: string }) {
  const [done, setDone] = useState<'ok' | 'fail' | null>(null);
  async function copy() {
    try { await navigator.clipboard.writeText(value); setDone('ok'); } catch { setDone('fail'); }
  }
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Copier ${label} : ${shown}`} onPress={copy}
      style={({ pressed }) => [st.row, pressTransition, pressed && { opacity: 0.75 }]}>
      <View style={{ flex: 1, minWidth: 0 }}>
        <T muted size={12}>{label}</T>
        <T weight="semibold" size={15} style={done === 'fail' ? ({ userSelect: 'all' } as object) : undefined}>{shown}</T>
      </View>
      <T size={13} weight="bold" color={done === 'ok' ? colors.mint : colors.accent}>{done === 'ok' ? 'Copié ✓' : done === 'fail' ? 'Copie à la main' : 'Copier'}</T>
    </Pressable>
  );
}

/** Moyens de paiement de l'organisateur, montant et référence, puis « J'ai payé ». */
function PaySheet({ info, onDeclare, onClose, busy, error }: { info: PayInfo; onDeclare: () => void; onClose: () => void; busy: boolean; error: string | null }) {
  const twint = info.links.twint;
  const eventLink = info.payment_url ? safeLink(info.payment_url) : null;  // le lien choisi pour CET événement d'abord
  // Le lien de l'événement remplace celui du même service dans le profil (deux « Payer avec Revolut » : lequel ?).
  const links = Object.entries(info.links).filter(([k, v]) => k !== 'twint' && safeLink(v)
    && !(eventLink && (v === eventLink || (LINK_LABELS[k] ?? LINK_LABELS.other) === payLinkLabel(eventLink))));
  const nothing = !twint && !eventLink && !links.length && !info.iban && !info.payment_info;
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
        {eventLink ? <Button variant="secondary" label={payLinkLabel(eventLink)} href={eventLink} /> : null}
        {twint ? <CopyRow label="Twint : numéro à copier dans l’app Twint" value={twint} /> : null}
        {links.map(([kind, url]) => (
          <Button key={kind} variant="secondary" label={LINK_LABELS[kind] ?? 'Ouvrir le lien de paiement'} href={url} />
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

/** Comment payer cet événement (réglage de l'organisateur, maquette du 15.11.2026). */
export type PaySetup = { mode: PaymentMode; url: string | null; organizer: string | null; info: string | null; open?: boolean };

/**
 * Paiement « entre amis » sur le billet (avec ou sans QR : option « Billets QR » éteinte ou billet pas encore remis) : à payer → « Payer l'organisateur » ; payé, en attente de confirmation ;
 * ou ✓ payé (confirmé par l'organisateur).
 */
export function PayOrganizer({ eventId, ticket, onTicket, pay }: { eventId: string; ticket: TicketPayment; onTicket: (t: MyTicket) => void; pay: PaySetup }) {
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
  const online = pay.mode === 'online' && pay.url ? safeLink(pay.url) : null;
  if (ticket.paid) {
    return <View style={[st.status, st.paid]}><T size={14} weight="bold" color={colors.mint}>✓ Place payée · {chf(price)}</T></View>;
  }
  if (ticket.pay_pending) {
    // En ligne (19.11) : rien à confirmer par l'organisateur, c'est noté.
    const done = pay.mode === 'online';
    return (
      <View style={[st.status, done ? st.paid : st.pending]}>
        <View style={{ flex: 1 }}>
          <T size={14} weight="bold" color={done ? colors.mint : colors.coral}>{done ? `✓ Payé en ligne · ${chf(price)}` : 'Payé · en attente de confirmation'}</T>
          <T size={12} muted>{done ? 'C’est noté : l’organisateur le voit.' : `L’organisateur confirme dès qu’il a reçu tes ${chf(price)}.`}</T>
        </View>
        <Button small variant="ghost" label="Annuler" loading={busy} onPress={() => declare(false)} />
        <ErrorText error={error} />
      </View>
    );
  }
  // Sur place : rien à payer ni à noter dans Party (l'organisateur peut cocher « payé » à l'entrée).
  if (pay.mode === 'on_site') {
    return (
      <View style={[st.status, st.onSite]}>
        <View style={{ flex: 1, gap: 2 }}>
          <T size={14} weight="bold" color={colors.coralSoft}>📍 {chf(price)} · à payer sur place</T>
          {pay.info ? <LinkedText size={12} color={colors.muted} text={pay.info} /> : null}
        </View>
      </View>
    );
  }
  // Paiement préparé mais pas encore ouvert par l'organisateur (avis du 16.11) : ni bouton ni lien.
  if (pay.open === false) {
    return (
      <View style={[st.status, st.onSite]} accessibilityRole="text">
        <View style={{ flex: 1, gap: 2 }}>
          <T size={14} weight="bold" color={colors.coralSoft}>⏳ {chf(price)} · paiement bientôt possible</T>
          <T size={12} muted>L’organisateur ouvre le paiement ici dès que c’est prêt. Rien à faire pour l’instant.</T>
        </View>
      </View>
    );
  }
  // En ligne : le bouton ouvre la billetterie (ou le lien), puis « J'ai payé » le note ; l'organisateur n'a rien à accepter
  // (demande de l'admin du 19.11) : il voit qui a payé. Pas de billet QR sur cette seule déclaration.
  if (pay.mode === 'online') {
    return (
      <View style={{ gap: 6 }}>
        {online ? <Button label={`Payer en ligne · ${chf(price)} ↗`} href={online} /> : null}
        <T size={12} muted>{online ? (() => { try { return new URL(online).hostname.replace(/^www\./, ''); } catch { return ''; } })() : `${chf(price)} · à payer en ligne`}{pay.info ? ` · ${pay.info}` : ''}</T>
        <Button variant="secondary" label="J’ai payé" loading={busy} onPress={() => declare(true)} />
        <ErrorText error={error} />
      </View>
    );
  }
  return (
    <View style={{ gap: 6 }}>
      <Button label={`Payer ${pay.organizer?.trim() || 'l’organisateur'} · ${chf(price)}`} loading={busy && !info} onPress={open} />
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
  onSite: { borderColor: 'rgba(255,179,71,.30)', backgroundColor: colors.fill },
  pending: { borderColor: 'rgba(255,179,71,.45)', backgroundColor: colors.coralDim },
});
