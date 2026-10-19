import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';

import { must, supabase } from './supabase';
import type { Category, EventRow, Rsvp, Tag } from './types';

let realtimeSubscriptionSequence = 0;

/** Charge des données, recharge au retour sur l'écran, expose `reload`. */
export function useQuery<T>(fn: () => Promise<T>, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fnRef = useRef(fn);
  useEffect(() => { fnRef.current = fn; }, [fn]);

  const reload = useCallback(async () => {
    try {
      setData(await fnRef.current());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
    // This wrapper deliberately forwards the caller's dependency list.
    // eslint-disable-next-line react-hooks/exhaustive-deps, react-hooks/use-memo
  }, deps);

  useFocusEffect(
    useCallback(() => {
      reload();
    }, [reload]),
  );

  return { data, error, loading, reload, setData };
}

/** Recharge quand une des tables change pour cet événement (temps réel Supabase). */
export function useRealtime(channel: string, tables: { table: string; filter?: string }[], onChange: () => void) {
  const cb = useRef(onChange);
  useEffect(() => { cb.current = onChange; }, [onChange]);
  const key = JSON.stringify(tables);
  useFocusEffect(useCallback(() => {
    // Une fiche et son éditeur peuvent coexister dans la pile de navigation.
    // Un sujet unique évite de réutiliser un canal déjà abonné pendant sa fermeture.
    let ch = supabase.channel(`${channel}-${++realtimeSubscriptionSequence}`);
    const descriptors = JSON.parse(key) as { table: string; filter?: string }[];
    for (const t of descriptors) {
      ch = ch.on('postgres_changes', { event: '*', schema: 'public', table: t.table, filter: t.filter }, () => cb.current());
    }
    ch.subscribe();
    return () => {
      void supabase.removeChannel(ch);
    };
  }, [channel, key]));
}

export type Taxonomy = { categories: Category[]; tags: Tag[] };

export async function fetchTaxonomy(includeArchived = false): Promise<Taxonomy> {
  let cq = supabase.from('categories').select('*').order('sort');
  let tq = supabase.from('tags').select('*').order('name');
  if (!includeArchived) {
    cq = cq.eq('archived', false);
    tq = tq.eq('archived', false);
  }
  const [categories, tags] = await Promise.all([cq, tq]);
  return { categories: must(categories) as Category[], tags: must(tags) as Tag[] };
}

export type EventListItem = EventRow & {
  category: Category | null;
  event_tags: { tag_id: string }[];
  rsvps: Pick<Rsvp, 'user_id' | 'status' | 'waitlisted' | 'plus_ones'>[];
  date_options: { id: string; date_votes: { user_id: string }[] }[];
};

export async function fetchEventList(): Promise<EventListItem[]> {
  const res = await supabase
    .from('events')
    .select(
      '*, category:categories(*), event_tags(tag_id), rsvps(user_id, status, waitlisted, plus_ones), date_options(id, date_votes(user_id))',
    )
    .order('starts_at', { ascending: true, nullsFirst: false })
    .order('created_at', { ascending: false });
  return must(res) as unknown as EventListItem[];
}

export function rsvpCounts(rsvps: Pick<Rsvp, 'status' | 'waitlisted' | 'plus_ones'>[]) {
  const c = { yes: 0, maybe: 0, no: 0, waitlist: 0, heads: 0 };
  for (const r of rsvps) {
    if (r.status === 'yes' && r.waitlisted) c.waitlist++;
    else {
      c[r.status]++;
      if (r.status === 'yes') c.heads += 1 + r.plus_ones;
    }
  }
  return c;
}

/** Sortie publiée où l’on attend encore ta réponse (présence ou vote de date). */
export function needsAnswer(e: EventListItem, me: string, now: number): boolean {
  if (e.status !== 'published') return false;
  if (e.rsvp_deadline && new Date(e.rsvp_deadline).getTime() < now) return false;
  if (e.date_mode === 'poll') {
    if (e.poll_deadline && new Date(e.poll_deadline).getTime() < now) return false;
    return e.date_options.length > 0 && !e.date_options.some((o) => o.date_votes.some((v) => v.user_id === me));
  }
  // Une sortie reste « à venir » 6 h après son début.
  if (!e.starts_at || new Date(e.starts_at).getTime() < now - 6 * 3600_000) return false;
  return !e.rsvps.some((r) => r.user_id === me);
}
