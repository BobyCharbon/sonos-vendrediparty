import { useNavigation } from 'expo-router';
import { usePreventRemove, type NavigationAction } from 'expo-router/react-navigation';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Modal, Platform, StyleSheet, View } from 'react-native';

import { colors, radius } from '@/lib/theme';

import { Button, T } from './ui';

/**
 * « Abandonner les changements ? » (campagne 2, 07.11) : formulaire « Proposer » et « Modifier ». Retour (‹, Annuler,
 * geste, bouton retour du navigateur) avec des changements non enregistrés : on demande d'abord. Rechargement ou fermeture
 * de la page : la question du navigateur. abandon : ce qu'il faut défaire en partant (brouillon commencé par un essai raté).
 */
export function useLeaveGuard(active: boolean, abandonNote: string | null, abandon?: () => Promise<void>): ReactNode {
  const navigation = useNavigation();
  const [pending, setPending] = useState<NavigationAction | null>(null);
  const [released, setReleased] = useState(false);
  const leaving = useRef(false);

  usePreventRemove(active && !released, ({ data }) => setPending(data.action));

  // Une fois la garde levée (rendu suivant), on reprend le départ demandé.
  useEffect(() => {
    if (!released || !pending) return;
    navigation.dispatch(pending);
  }, [released, pending, navigation]);

  // Bouton retour du navigateur / geste Android : le routeur remplace l'écran sans passer par la garde (resetRoot).
  // On intercepte le retour AVANT lui (écouteur en capture), on revient sur le formulaire, puis on pose la question ;
  // « Abandonner » repart par un vrai retour.
  useEffect(() => {
    if (!active || released || Platform.OS !== 'web' || typeof window === 'undefined') return;
    // Navigateurs récents (API Navigation) : le retour est annulé avant que React ne démonte l'écran.
    const nav = (window as unknown as { navigation?: EventTarget }).navigation;
    if (nav) {
      const onNavigate = (e: Event) => {
        const n = e as Event & { navigationType?: string };
        if (n.navigationType !== 'traverse' || !n.cancelable) return;
        n.preventDefault();
        setPending({ type: 'GO_BACK' } as NavigationAction);
      };
      nav.addEventListener('navigate', onNavigate);
      return () => nav.removeEventListener('navigate', onNavigate);
    }
    let restoring = false;
    const onPop = (e: PopStateEvent) => {
      e.stopImmediatePropagation();
      if (restoring) { restoring = false; return; }
      restoring = true;
      window.history.go(1);
      setPending({ type: 'GO_BACK' } as NavigationAction);
    };
    window.addEventListener('popstate', onPop, true);
    return () => window.removeEventListener('popstate', onPop, true);
  }, [active, released]);

  useEffect(() => {
    if (!active || Platform.OS !== 'web' || typeof window === 'undefined') return;
    const ask = (e: BeforeUnloadEvent) => { e.preventDefault(); e.returnValue = ''; };
    window.addEventListener('beforeunload', ask);
    return () => window.removeEventListener('beforeunload', ask);
  }, [active]);

  async function confirm() {
    if (leaving.current) return;
    leaving.current = true;
    try {
      await abandon?.();
    } catch {
      // Le brouillon reste dans « Brouillons » : on part quand même, rien n'est perdu.
    }
    setReleased(true);
  }

  return (
    <Modal visible={!!pending && !released} transparent animationType="fade" onRequestClose={() => setPending(null)}
      aria-label="Abandonner les changements ?">
      <View style={st.overlay}>
        <View style={st.card} accessibilityViewIsModal accessibilityRole="alert">
          <T weight="bold" size={18}>Abandonner les changements ?</T>
          <T size={14} color={colors.textSoft}>
            Ce que tu as saisi ici n’est pas enregistré et sera perdu.{abandonNote ? ` ${abandonNote}` : ''}
          </T>
          <Button label="Abandonner" variant="danger" onPress={() => void confirm()} />
          <Button label="Continuer à modifier" variant="secondary" onPress={() => setPending(null)} />
        </View>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(8,5,20,0.6)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  card: { width: '100%', maxWidth: 380, gap: 12, padding: 20, borderRadius: radius.lg, backgroundColor: colors.surface },
});
