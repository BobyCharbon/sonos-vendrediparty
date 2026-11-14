import { useCallback, useEffect, useSyncExternalStore } from 'react';
import { Platform } from 'react-native';

import { IMPORTANT_KINDS } from './activityBadge';
import { fetchEventList, needsAnswer, useRealtime } from './data';
import { supabase } from './supabase';

/** Les notifications ne passent pas par le temps réel : relecture régulière tant que le module est ouvert. */
const UNREAD_REFRESH_MS = 60_000;

/**
 * Pastille de l'onglet Événements (avis a1d340ff00dd) : les événements qui attendent ta réponse, plus les nouveautés
 * importantes pas encore ouvertes (celles de la cloche) qui ne parlent pas d'un événement déjà compté. Un événement ne
 * compte qu'une fois ; une nouveauté sans événement (groupe…) compte pour elle-même.
 */
export function tabBadgeCount(pending: ReadonlySet<string>, unreadEventIds: readonly (string | null)[]): number {
  const others = new Set(unreadEventIds.filter((id): id is string => !!id && !pending.has(id)));
  return pending.size + others.size + unreadEventIds.filter((id) => !id).length;
}

async function fetchImportantUnreadEventIds(): Promise<(string | null)[]> {
  const { data, error } = await supabase
    .from('notifications')
    .select('event_id')
    .is('read_at', null)
    .in('kind', [...IMPORTANT_KINDS])
    .limit(200);
  if (error) throw error;
  return (data ?? []).map((row: { event_id: string | null }) => row.event_id);
}

const listeners = new Set<() => void>();
// Compteur partagé : calculé une seule fois à la racine du module (usePendingSync), lu par les écrans (usePendingCount).
let shared = 0;
const readers = new Set<() => void>();
function setShared(n: number) {
  shared = n;
  for (const fn of readers) fn();
}

/** À appeler après une réponse, un vote ou une notification lue : le compteur se recalcule aussitôt. */
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
      const [events, unread] = await Promise.all([fetchEventList(), fetchImportantUnreadEventIds().catch(() => [])]);
      const now = Date.now();
      const pending = new Set(events.filter((e) => needsAnswer(e, me, now)).map((e) => e.id));
      setShared(pending.size);
      publish(tabBadgeCount(pending, unread));
    } catch {
      /* Hors ligne : on garde la dernière valeur. */
    }
  }, [me]);

  useEffect(() => {
    // Premier calcul hors du rendu (la règle react-hooks interdit un setState synchrone ici).
    const first = setTimeout(() => void load(), 0);
    const timer = setInterval(() => void load(), UNREAD_REFRESH_MS);
    listeners.add(load);
    const onVisible = () => { if (document.visibilityState === 'visible') void load(); };
    if (Platform.OS === 'web' && typeof document !== 'undefined') document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
      listeners.delete(load);
      if (Platform.OS === 'web' && typeof document !== 'undefined') document.removeEventListener('visibilitychange', onVisible);
      setShared(0);
      publish(0); // Déconnexion ou accès retiré : la pastille disparaît.
    };
  }, [load]);

  useRealtime('pending', [{ table: 'rsvps' }, { table: 'date_votes' }, { table: 'events' }], load);
}
