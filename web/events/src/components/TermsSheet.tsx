import { useRef, useState } from 'react';
import { Modal, ScrollView, StyleSheet, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from './SheetGesture';
import { Button, ErrorText, T, Title } from './ui';
import { useTerms } from '@/lib/moderation';
import { TERMS_SECTIONS, TERMS_UPDATED } from '@/lib/terms';
import { colors, radius } from '@/lib/theme';

/** « Plus tard » touché : dire pourquoi rien ne s'est passé et comment rouvrir les conditions (jamais un bouton muet). */
export function termsLater(what: string, button?: string): string {
  return `Pour ${what}, accepte d’abord les conditions d’utilisation de Party : touche ${button ? `« ${button} »` : 'à nouveau le bouton'} pour les relire.`;
}

/** Conditions d'utilisation à accepter avant le PREMIER contenu (message, surnom, nom de groupe ; Google UGC) :
 * Titre selon le moment (recette UX du 14.11) : « Avant de publier » par défaut, « Avant de commencer » au premier
 * surnom, « Avant de répondre » sur une invitation ; personne ne « publie » en choisissant son surnom.
 * `await ensure()` vaut true une fois acceptées (tout de suite si c'est déjà fait), false si la personne renonce. */
export function useTermsGate(title = 'Avant de publier') {
  const terms = useTerms();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [readAll, setReadAll] = useState(false);
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
    setReadAll(false);
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

  // Conditions en grand (demande de l'admin du 26.11 : « que ce soit clair », sans chercher où elles se trouvent) :
  // l'essentiel en points, le texte complet se déplie ICI (on ne quitte jamais l'écran : le message attend).
  const sheet = (
    <Modal visible={open} transparent animationType="fade" onRequestClose={() => finish(false)}>
      <View ref={overlay} style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={() => finish(false)} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Conditions d’utilisation">
          <SheetTop onClose={() => finish(false)} />
          <ScrollView style={{ flexShrink: 1 }} contentContainerStyle={{ gap: 16, paddingBottom: 4 }}>
            <Title size={28} level={2}>{title}</Title>
            <T size={17} muted>Accepte une seule fois les conditions d’utilisation de Party, puis tu continues tout de suite.</T>
            {POINTS.map(([icon, line]) => (
              <View key={line} style={st.point}>
                <T size={22}>{icon}</T>
                <T size={16} style={{ flex: 1 }}>{line}</T>
              </View>
            ))}
            <View style={st.adult}>
              <T size={16} weight="bold">Party est réservée aux 18 ans et plus : en touchant « J’accepte », tu confirmes avoir 18 ans ou plus.</T>
            </View>
            <Button small variant="ghost" label={readAll ? 'Masquer les conditions complètes' : 'Lire les conditions complètes'}
              onPress={() => setReadAll(!readAll)} />
            {readAll ? (
              <View style={{ gap: 12 }} testID="terms-full">
                <T size={13} muted>Version du {TERMS_UPDATED}</T>
                {TERMS_SECTIONS.map((section) => (
                  <View key={section.title} style={{ gap: 6 }}>
                    <T weight="bold" size={15}>{section.title}</T>
                    {section.paragraphs.map((p) => <T key={p} size={14} muted>{p}</T>)}
                  </View>
                ))}
              </View>
            ) : null}
          </ScrollView>
          <ErrorText error={error} />
          <Button label="J’accepte les conditions" loading={busy} onPress={() => void accept()} />
          <Button variant="secondary" label="Plus tard" onPress={() => finish(false)} />
          <T muted size={12} style={{ textAlign: 'center' }}>Sans elles, tu gardes les jeux. Écrire, publier, choisir ton surnom ou répondre à un événement te les redemanderont.</T>
        </View>
      </View>
    </Modal>
  );

  // needed : la base a répondu et les conditions ne sont pas acceptées (bouton à rendre actif pour les ouvrir).
  return { ensure, sheet, accepted: terms.accepted, needed: Boolean(terms.status && !terms.status.accepted) };
}

const POINTS: [string, string][] = [
  ['🤝', 'On se respecte : ni harcèlement, ni propos haineux, ni contenu sexuel.'],
  ['🚫', 'Pas d’arnaque ni de vente. Les points des jeux n’ont aucune valeur en argent.'],
  ['⛔', 'Tolérance zéro : un contenu choquant est retiré et son auteur peut être banni.'],
  ['🚩', 'Tout contenu peut être signalé ; un modérateur peut le masquer, avertir, suspendre ou bannir un compte.'],
  ['💸', 'Party ne vend rien et ne touche jamais d’argent.'],
];

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  point: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  adult: { padding: 14, borderRadius: radius.md, backgroundColor: 'rgba(255,79,154,0.14)' },
  sheet: { width: '100%', maxWidth: 520, maxHeight: '100%', marginVertical: 'auto', gap: 12, padding: 22, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
});
