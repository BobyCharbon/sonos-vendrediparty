import { useCallback, useEffect, useState } from 'react';
import { Platform } from 'react-native';

import { fetchEventList, needsAnswer, useRealtime } from './data';

const listeners = new Set<() => void>();

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

/** Nombre de sorties qui attendent ta réponse, tenu à jour en temps réel. */
export function usePendingCount(me: string): number {
  const [count, setCount] = useState(0);

  const load = useCallback(async () => {
    try {
      const events = await fetchEventList();
      const now = Date.now();
      const n = events.filter((e) => needsAnswer(e, me, now)).length;
      setCount(n);
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
      publish(0); // Déconnexion : la pastille disparaît.
    };
  }, [load]);

  useRealtime('pending', [{ table: 'rsvps' }, { table: 'date_votes' }, { table: 'events' }], load);
  return count;
}
