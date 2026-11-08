import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Platform } from 'react-native';

import { supabase } from './supabase';

/**
 * Nouveautés « importantes » (bulle rouge de la cloche, accueil Événements) : ce qui demande d'agir ou change ta soirée.
 * Le reste (réponses par ton lien, messages, rappels…) reste dans « Tout », sans bulle.
 */
export const IMPORTANT_KINDS = [
  'private_invite', 'new_event', 'group_invite',
  'poll_new', 'poll_nudge', 'date_fixed',
  'event_changed', 'waitlist', 'coorganizer_added',
  'approved', 'rejected', 'group_event_request', 'announce_request',
  // Réponse à une demande de l'organisateur (annonce, événement de groupe) : il l'attend (recette des bots du 08.11).
  'announce_accepted', 'announce_refused', 'group_event_accepted', 'group_event_refused',
  'ticket_issued', 'ticket_pay_confirmed', 'ticket_pay_declared', 'moderation_notice',
] as const;

const IMPORTANT = new Set<string>(IMPORTANT_KINDS);
export const isImportant = (kind: string | null | undefined) => !!kind && IMPORTANT.has(kind);

/** Les annonces de l'admin ont leur propre place (bandeau), jamais dans l'Activité. */
export const HIDDEN_KIND = 'admin_announcement';

/** Relecture régulière tant que l'écran est ouvert (les notifications ne passent pas par le temps réel). */
const REFRESH_MS = 60_000;

export async function fetchImportantUnread(): Promise<number> {
  const { count, error } = await supabase
    .from('notifications')
    .select('id', { count: 'exact', head: true })
    .is('read_at', null)
    .in('kind', [...IMPORTANT_KINDS]);
  if (error) throw error;
  return count ?? 0;
}

/**
 * Compte des nouveautés importantes non lues, relu à chaque retour sur l'écran, quand la page redevient visible,
 * toutes les minutes et à chaque `refreshKey` (la liste des événements a changé en temps réel).
 */
export function useImportantUnread(refreshKey?: unknown): number {
  const [count, setCount] = useState(0);
  const load = useCallback(() => {
    fetchImportantUnread().then(setCount).catch(() => { /* Hors ligne : on garde la dernière valeur. */ });
  }, []);

  useFocusEffect(useCallback(() => {
    load();
    const timer = setInterval(load, REFRESH_MS);
    const onVisible = () => { if (document.visibilityState === 'visible') load(); };
    const web = Platform.OS === 'web' && typeof document !== 'undefined';
    if (web) document.addEventListener('visibilitychange', onVisible);
    return () => {
      clearInterval(timer);
      if (web) document.removeEventListener('visibilitychange', onVisible);
    };
  }, [load]));

  useEffect(() => { if (refreshKey !== undefined) load(); }, [refreshKey, load]);
  return count;
}

/** Rouge des pastilles iOS (cloche de l'accueil et nouveautés importantes). */
export const BADGE_RED = '#FF3B30';
