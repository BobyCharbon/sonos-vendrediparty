import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { Modal, StyleSheet, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from './SheetGesture';
import { Button, ErrorText, T } from './ui';
import { TERMS_PATH, useTerms } from '@/lib/moderation';
import { colors, radius } from '@/lib/theme';

/** Conditions d'utilisation à accepter avant le PREMIER contenu (message, surnom, nom de groupe ; Google UGC) :
 * `await ensure()` vaut true une fois acceptées (tout de suite si c'est déjà fait), false si la personne renonce. */
export function useTermsGate() {
  const terms = useTerms();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const answer = useRef<((ok: boolean) => void) | null>(null);
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const sheetTop = useSheetTop();
  useSheetDrag(open, () => finish(false), card, overlay);   // glisser vers le bas = « Plus tard »

  async function ensure(): Promise<boolean> {
    if (terms.accepted) return true;
    const fresh = await terms.reload();
    // Pas de réponse (serveur plus ancien, réseau) : on laisse passer, la base reste la garde (« Exiger les CGU »).
    if (!fresh || fresh.accepted) return true;
    setOpen(true);
    return new Promise<boolean>((resolve) => { answer.current = resolve; });
  }

  function finish(ok: boolean) {
    setOpen(false);
    setError(null);
    answer.current?.(ok);
    answer.current = null;
  }

  async function accept() {
    setBusy(true);
    setError(null);
    try {
      await terms.accept();
      finish(true);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'L’acceptation n’a pas été enregistrée. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  const sheet = (
    <Modal visible={open} transparent animationType="fade" onRequestClose={() => finish(false)}>
      <View ref={overlay} style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={() => finish(false)} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Conditions d’utilisation">
          <SheetTop onClose={() => finish(false)} />
          <T weight="bold" size={18}>Avant de publier</T>
          <T size={14}>Sur Party, on se respecte : pas de harcèlement, pas de propos haineux ni de contenu sexuel, pas
            d’arnaque ni de vente. Les objets du jeu n’ont aucune valeur en argent. Tout contenu peut être signalé ; un
            modérateur peut le masquer, avertir, suspendre ou bannir un compte.</T>
          <Button small variant="ghost" label="Lire les conditions d’utilisation" onPress={() => { finish(false); router.push(TERMS_PATH); }} />
          <ErrorText error={error} />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button variant="secondary" label="Plus tard" style={{ flex: 1 }} onPress={() => finish(false)} />
            <Button label="J’accepte" style={{ flex: 1 }} loading={busy} onPress={() => void accept()} />
          </View>
        </View>
      </View>
    </Modal>
  );

  return { ensure, sheet, accepted: terms.accepted };
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  sheet: { width: '100%', maxWidth: 420, marginVertical: 'auto', gap: 12, padding: 18, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
});
