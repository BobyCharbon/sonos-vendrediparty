import { rsvpCounts } from './data';
import { supabase } from './supabase';
import type { Rsvp } from './types';

/** Pastille des présents : totaux anonymes + visages des premiers présents (si l'on a le droit de voir qui vient). */
export type Face = { id: string; name: string; avatar_url: string | null };
export type Attendance = { going: number; maybe: number; waitlist: number; faces: Face[] };

type Row = Attendance & { event_id: string };
type LocalRsvp = Pick<Rsvp, 'user_id' | 'status' | 'waitlisted' | 'plus_ones'>;

const MAX_FACES = 3;

/**
 * Décompte calculé avec les seules réponses lisibles (repli si la fonction de la base manque, par exemple avant
 * la migration en production) : visages sans photo, prénom pris dans `names`.
 */
export function localAttendance(rsvps: readonly LocalRsvp[], names: ReadonlyMap<string, string> = new Map()): Attendance {
  const c = rsvpCounts([...rsvps]);
  const faces = rsvps
    .filter((r) => r.status === 'yes' && !r.waitlisted)
    .slice(0, MAX_FACES)
    .map((r) => ({ id: r.user_id, name: names.get(r.user_id) ?? '?', avatar_url: null }));
  return { going: c.heads, maybe: c.maybe, waitlist: c.waitlist, faces };
}

/** Totaux exacts de plusieurs événements (une seule requête). Événement absent : pas visible, ou base pas à jour. */
export async function fetchAttendance(ids: readonly string[]): Promise<Map<string, Attendance>> {
  if (!ids.length) return new Map();
  const { data, error } = await supabase.rpc('event_attendance', { ids });
  if (error || !Array.isArray(data)) return new Map();
  return new Map((data as Row[]).map(({ event_id, ...a }) => [event_id, { ...a, faces: a.faces ?? [] }]));
}
