import { useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from './SheetGesture';
import { Button, ErrorText, Input, T } from './ui';
import { SUPPORT_EMAIL } from '@/lib/contact';
import { REPORT_REASONS, reportContent, type ReportReason, type ReportTarget } from '@/lib/moderation';
import { colors, radius } from '@/lib/theme';

type Props = {
  target: ReportTarget | null;
  onClose: (sent: boolean) => void;
  /** Envoi propre à un contenu hors de report_content (demande de rendez-vous : agenda_booking_report). */
  send?: (reason: ReportReason, comment: string) => Promise<void>;
  /** Message d'une discussion : case « Joindre les 10 messages précédents » (décochée par défaut, conformité 🟠 8). */
  allowContext?: boolean;
  /** Motifs propres à un contenu (photo Souvenirs : « Je suis sur la photo… ») ; sinon les motifs communs. */
  reasons?: readonly { key: ReportReason; label: string; hint?: string }[];
  /** Phrase après l'envoi (photo Souvenirs : masquée aussitôt, organisation et modération prévenues). */
  thanks?: string;
};

/** « Signaler » (Apple 1.2, Google UGC) : une raison, un commentaire facultatif ; la file des modérateurs le reçoit.
 * La personne signalée n'est pas prévenue ; la base garde une copie du contenu au moment du signalement. */
export function ReportSheet({ target, onClose, send: sendOwn, allowContext = false, reasons = REPORT_REASONS, thanks }: Props) {
  const [reason, setReason] = useState<ReportReason | null>(null);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const [context, setContext] = useState(false);
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const sheetTop = useSheetTop();

  function close() {
    const done = sent;
    setReason(null);
    setComment('');
    setError(null);
    setSent(false);
    setContext(false);
    onClose(done);
  }

  useSheetDrag(!!target, close, card, overlay);

  async function send() {
    if (!target || !reason) return;
    setBusy(true);
    setError(null);
    try {
      if (sendOwn) await sendOwn(reason, comment);
      else await reportContent(target, reason, comment, allowContext && context);
      setSent(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Le signalement n’a pas pu être envoyé. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal visible={!!target} transparent animationType="fade" onRequestClose={close}>
      <View ref={overlay} style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={close} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Signaler">
          <SheetTop onClose={close} />
          {sent ? (
            <>
              <T weight="bold" size={18}>Merci, c’est envoyé</T>
              <T muted size={14}>{thanks ?? (target?.kind === 'group'
                ? 'Un modérateur va regarder. Ni le groupe ni ses membres ne sont prévenus que c’est toi.'
                : 'Un modérateur va regarder. La personne n’est pas prévenue que c’est toi.')}</T>
              <T muted size={13}>Urgent ou grave (menace, contenu illégal) : écris aussi à {SUPPORT_EMAIL}.</T>
              <Button label="Fermer" onPress={close} />
            </>
          ) : (
            <>
              <T weight="bold" size={18}>Signaler {target?.label ?? ''}</T>
              <T muted size={13}>Pourquoi ? Un modérateur reçoit ton signalement et une copie du contenu.</T>
              {reasons.map((r) => (
                <Pressable key={r.key} accessibilityRole="radio" accessibilityState={{ checked: reason === r.key }}
                  accessibilityLabel={r.label} onPress={() => setReason(r.key)}
                  style={[st.reason, reason === r.key && st.chosen]}>
                  <T weight="semibold">{r.label}</T>
                  {r.hint ? <T muted size={12}>{r.hint}</T> : null}
                </Pressable>
              ))}
              {allowContext ? (
                <Pressable accessibilityRole="checkbox" aria-checked={context} accessibilityState={{ checked: context }} accessibilityLabel="Joindre les 10 messages précédents"
                  onPress={() => setContext((v) => !v)} style={[st.reason, { flexDirection: 'row', alignItems: 'center', gap: 12 }, context && st.chosen]}>
                  <View style={[st.box, context && st.boxOn]}>{context ? <T size={14} weight="bold" color={colors.onAccent}>✓</T> : null}</View>
                  <View style={{ flex: 1, gap: 2 }}>
                    <T weight="semibold">Joindre les 10 messages précédents</T>
                    <T muted size={12}>Le modérateur reçoit aussi leur texte, leur auteur et leur heure, pour comprendre le contexte.</T>
                  </View>
                </Pressable>
              ) : null}
              <Input accessibilityLabel="Commentaire" placeholder="Commentaire (facultatif)" value={comment}
                onChangeText={setComment} maxLength={500} multiline style={{ minHeight: 70 }} />
              <ErrorText error={error} />
              <T muted size={12}>Traité sous 24 h · {SUPPORT_EMAIL}</T>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Button variant="secondary" label="Annuler" style={{ flex: 1 }} onPress={close} />
                <Button label="Envoyer" style={{ flex: 1 }} disabled={!reason} loading={busy} onPress={() => void send()} />
              </View>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  sheet: { width: '100%', maxWidth: 420, marginVertical: 'auto', gap: 10, padding: 18, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  reason: { padding: 12, borderRadius: radius.md, backgroundColor: colors.fill, borderWidth: 1, borderColor: 'transparent', gap: 2 },
  chosen: { borderColor: colors.accent, backgroundColor: colors.accentDim },
  box: { width: 24, height: 24, borderRadius: 7, borderWidth: 2, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: colors.accent, borderColor: colors.accent },
});
