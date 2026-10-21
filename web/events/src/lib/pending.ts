import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { Platform } from 'react-native';

import { fetchEventList, needsAnswer, useRealtime } from './data';

const listeners = new Set<() => void>();
// Compteur partagé : calculé une seule fois à la racine du module (usePendingSync), lu par les écrans (usePendingCount).
let shared = 0;
const readers = new Set<() => void>();
function setShared(n: number) {
  shared = n;
  for (const fn of readers) fn();
}

/** À appeler après une réponse ou un vote : le compteur se recalcule aussitôt. */
export function refreshPending() {
  for (const fn of listeners) fn();
}

/** Prévient Party (page parente, même origine) pour la pastille de l’onglet Événements. */
function publish(count: number) {
  if (Platform.OS !== 'web' || typeof window === 'undefined' || window.parent === window) return;
  try {
    window.parent.postMessage({ type: 'party-events:pending', count }, window.location.origin);
  } catch {
    /* Page parente indisponible. */
  }
}

/** Nombre de sorties qui attendent ta réponse (lecture seule). */
export function usePendingCount(): number {
  return useSyncExternalStore((fn) => { readers.add(fn); return () => readers.delete(fn); }, () => shared, () => shared);
}

/**
 * Tient le compteur à jour en temps réel et l’envoie à Party. Monté à la racine tant que le membre a accès aux sorties :
 * changer d’écran (Réglages, une sortie…) ne remet plus la pastille à zéro ; seule la perte d’accès le fait.
 */
export function usePendingSync(me: string) {
  const load = useCallback(async () => {
    try {
      const events = await fetchEventList();
      const now = Date.now();
      const n = events.filter((e) => needsAnswer(e, me, now)).length;
      setShared(n);
      publish(n);
    } catch {
      /* Hors ligne : on garde la dernière valeur. */
    }
  }, [me]);

  useEffect(() => {
    // Premier calcul hors du rendu (la règle react-hooks interdit un setState synchrone ici).
    const first = setTimeout(() => void load(), 0);
    listeners.add(load);
    const onVisible = () => { if (document.visibilityState === 'visible') void load(); };
    if (Platform.OS === 'web' && typeof document !== 'undefined') document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearTimeout(first);
      listeners.delete(load);
      if (Platform.OS === 'web' && typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVisible);
      setShared(0);
      publish(0); // Déconnexion ou accès retiré : la pastille disparaît.
    };
  }, [load]);

  useRealtime('pending', [{ table: 'rsvps' }, { table: 'date_votes' }, { table: 'events' }], load);
}
