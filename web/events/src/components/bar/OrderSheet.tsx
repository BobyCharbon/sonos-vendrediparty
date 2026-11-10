import { useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { barChf, barOrder, errorCode, errorText, itemLabel, linesTotal, orderPayload, round2, type CartLine, type MyBar } from '@/lib/bar';
import { plural } from '@/lib/format';
import { colors, font, radius } from '@/lib/theme';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from '../SheetGesture';
import { Button, ErrorText, T } from '../ui';
import { NETWORK_TEXT } from '@/lib/errors';

type Props = {
  eventId: string;
  bar: MyBar;
  lines: CartLine[];
  open: boolean;
  onClose: () => void;
  /** Commande acceptée : my_bar relu par la base. */
  onDone: (bar: MyBar) => void;
  /** Stock, maximum ou conditions changés : relire my_bar (la commande se réajuste d'elle-même). */
  onStale: () => void;
};

const STALE = new Set(['terms_changed', 'stock', 'max_pending']);

/**
 * Feuille « Valider la commande » : total, solde si tout est servi, et l'engagement à cocher — le texte EXACT de la base
 * (my_bar.pledge_text), renvoyé tel quel. Case décochée d'office si le texte change pendant que la feuille est ouverte.
 */
// Réponse perdue (réseau) : la commande est peut-être passée ; jamais « réessaie » tout court, qui fait commander deux fois
// (test réel du 10.11 dans le simulateur : « La connexion a échoué… réessaie » s'affichait).
const LOST = 'La réponse n’est pas arrivée : vérifie « En attente » avant de renvoyer ta commande.';
const lostAnswer = (text: string) => (text === NETWORK_TEXT ? LOST : text);

export function OrderSheet({ eventId, bar, lines, open, onClose, onDone, onStale }: Props) {
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const sheetTop = useSheetTop();
  const [checkedFor, setCheckedFor] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  // Fermer décoche : l'engagement se coche à CHAQUE commande (exigence de l'admin).
  const close = () => { setError(null); setCheckedFor(null); onClose(); };
  useSheetDrag(open, close, card, overlay);

  const pledgeKey = `${bar.pledge_version}|${bar.pledge_text}`;
  const checked = checkedFor === pledgeKey;
  const { count, total } = linesTotal(lines);
  const after = round2(bar.balance + bar.pending_total + total);

  async function submit() {
    setBusy(true);
    setError(null);
    try {
      const next = await barOrder(eventId, orderPayload(lines), bar.pledge_text, bar.pledge_version);
      setCheckedFor(null);
      onDone(next);
    } catch (e) {
      const code = errorCode(e);
      if (code === 'terms_changed') {
        setCheckedFor(null);
        setError('Les conditions de remboursement ont changé : relis l’engagement ci-dessus puis recoche la case.');
      } else {
        setError(code === 'stock' || code === 'max_pending'
          ? `${errorText(e, 'Plus assez de stock.')} Ta commande a été ajustée : vérifie-la.`
          : lostAnswer(errorText(e, LOST)));
      }
      // Code connu (stock, maximum, conditions) ou réponse perdue : on relit « Mon bar » avant tout nouvel envoi
      // (la commande a peut-être été enregistrée : vérifier « En attente » plutôt que la renvoyer).
      if (!code || STALE.has(code)) onStale();
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={close}>
      <View ref={overlay} style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={close} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Valider la commande">
          <SheetTop onClose={close} />
          <T weight="bold" size={18}>Ta commande</T>
          {lines.map((l) => (
            <View key={l.item.id} style={st.kv}>
              <T size={15} style={{ flex: 1 }}>{itemLabel(l.item)} × {l.qty}</T>
              <T size={15} weight="semibold">{barChf(l.qty * l.item.price_chf)}</T>
            </View>
          ))}
          {lines.length === 0 ? <T muted size={14}>Plus rien à commander : le stock a changé.</T> : null}
          <View style={[st.kv, st.total]}>
            <T size={15}>{plural(count, 'article')}</T>
            <Text style={st.amount}>{barChf(total)}</Text>
          </View>
          <T size={14} color={colors.textSoft}>Ton solde si tout est servi : {barChf(bar.balance)} → {barChf(after)}</T>
          {bar.phase === 'preorder' ? <T size={13} muted>Précommande : servie au bar une fois ouvert.</T> : null}
          <Pressable accessibilityRole="checkbox" accessibilityState={{ checked }} aria-checked={checked}
            onPress={() => setCheckedFor(checked ? null : pledgeKey)}
            style={({ pressed }) => [st.check, checked && st.checkOn, pressed && { opacity: 0.85 }]}>
            <View style={[st.box, checked && st.boxOn]}>{checked ? <Text style={st.tick}>✓</Text> : null}</View>
            <T size={14} style={{ flex: 1, lineHeight: 20 }}>{bar.pledge_text}</T>
          </Pressable>
          <Button label="Valider la commande" disabled={!checked || !count} loading={busy} onPress={() => void submit()} />
          <ErrorText error={error} />
          <T muted size={12}>Rien n’est dû avant le service au bar. Tu peux annuler ce qui n’est pas encore servi.</T>
        </View>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  sheet: { width: '100%', maxWidth: 420, marginVertical: 'auto', gap: 12, padding: 18, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  kv: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  total: { paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.line },
  amount: { ...font.display, color: colors.text, fontSize: 24, lineHeight: 28, marginLeft: 'auto' },
  check: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, minHeight: 44, padding: 12, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.lineStrong, backgroundColor: colors.fill },
  checkOn: { borderColor: colors.mint },
  box: { width: 26, height: 26, borderRadius: 7, borderWidth: 2, borderColor: colors.muted, alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: colors.mint, borderColor: colors.mint },
  tick: { color: colors.onMint, fontSize: 16, ...font.bold },
});
