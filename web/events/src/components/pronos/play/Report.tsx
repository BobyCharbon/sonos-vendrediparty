import { useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from '@/components/SheetGesture';
import { Button, ErrorText, Input, T } from '@/components/ui';
import { SUPPORT_EMAIL } from '@/lib/contact';
import { REPORT_REASONS } from '@/lib/moderation';
import { rpc } from '@/lib/pronos';
import { colors, radius } from '@/lib/theme';

/**
 * « Signaler » un prono ou une réponse (Apple 1.2, Google UGC) : les motifs communs, plus « money » (demande d'argent,
 * vente de patates : conformité 🔴), que la base accepte pour report_content (prono) et prono_report_answer.
 * Même feuille que ReportSheet ; la personne signalée n'est pas prévenue.
 */
export type ReportWhat = { label: string; author?: string };

export function PronoReportSheet({ prono, what, patates, onClose }: { prono: string; what: ReportWhat | null; patates: boolean; onClose: () => void }) {
  const reasons = [
    ...REPORT_REASONS.filter((r) => r.key !== 'other'),
    { key: 'money', label: patates ? 'Demande d’argent / vente de confettis' : 'Demande d’argent', hint: 'Argent réel, vente ou échange contre quelque chose' },
    ...REPORT_REASONS.filter((r) => r.key === 'other'),
  ];
  const [reason, setReason] = useState<string | null>(null);
  const [comment, setComment] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState(false);
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const top = useSheetTop();

  function close() {
    setReason(null);
    setComment('');
    setError(null);
    setSent(false);
    onClose();
  }
  useSheetDrag(!!what, close, card, overlay);

  async function send() {
    if (!what || !reason) return;
    setBusy(true);
    setError(null);
    try {
      const note = comment.trim() || null;
      if (what.author) await rpc('prono_report_answer', { id: prono, author: what.author, reason, comment: note });
      else await rpc('report_content', { p_kind: 'prono', p_target: prono, p_reason: reason, p_comment: note });
      setSent(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Le signalement n’a pas pu être envoyé. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal visible={!!what} transparent animationType="fade" onRequestClose={close}>
      <View ref={overlay} style={[st.overlay, { paddingTop: top }]}>
        <SheetBackdrop onPress={close} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Signaler">
          <SheetTop onClose={close} />
          {sent ? (
            <>
              <T weight="bold" size={18}>Merci, c’est envoyé</T>
              <T muted size={14}>Un modérateur va regarder. La personne n’est pas prévenue que c’est toi.</T>
              <T muted size={13}>Urgent ou grave (menace, contenu illégal) : écris aussi à {SUPPORT_EMAIL}.</T>
              <Button label="Fermer" onPress={close} />
            </>
          ) : (
            <>
              <T weight="bold" size={18}>Signaler {what?.label ?? ''}</T>
              <T muted size={13}>Pourquoi ? Un modérateur reçoit ton signalement et une copie du contenu.</T>
              {reasons.map((r) => (
                <Pressable key={r.key} accessibilityRole="radio" accessibilityState={{ checked: reason === r.key }} accessibilityLabel={r.label}
                  onPress={() => setReason(r.key)} style={[st.reason, reason === r.key && st.chosen]}>
                  <T weight="semibold">{r.label}</T>
                  <T muted size={12}>{r.hint}</T>
                </Pressable>
              ))}
              <Input accessibilityLabel="Commentaire" placeholder="Commentaire (facultatif)" value={comment} onChangeText={setComment}
                maxLength={500} multiline style={{ minHeight: 70 }} />
              <ErrorText error={error} />
              <T muted size={12}>Contact : {SUPPORT_EMAIL}</T>
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
  sheet: { width: '100%', maxWidth: 420, marginVertical: 'auto', gap: 10, padding: 18, borderRadius: radius.lg, backgroundColor: colors.surface,
    borderWidth: 1, borderColor: colors.lineStrong },
  reason: { padding: 12, borderRadius: radius.md, backgroundColor: colors.fill, borderWidth: 1, borderColor: 'transparent', gap: 2 },
  chosen: { borderColor: colors.accent, backgroundColor: colors.accentDim },
});
