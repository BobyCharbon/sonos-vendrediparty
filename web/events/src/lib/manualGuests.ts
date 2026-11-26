import { friendlyError } from './errors';
import { dbMessage } from './moderation';
import { supabase } from './supabase';
import type { RsvpStatus } from './types';

/**
 * Présences notées à la main pour des personnes SANS compte (« Pote Théo du bar », migration 20261126150000).
 * Table lisible et modifiable par l'organisation seulement ; la base filtre le nom, vérifie Peut-être et les places.
 * Les invités n'en voient que les nombres (event_attendance, event_guest_list…).
 */
export type ManualGuest = { id: string; name: string; status: RsvpStatus; created_at: string };

/** Base d'avant la migration : table inconnue de PostgREST (PGRST205) ou de Postgres (42P01). */
const MISSING = new Set(['PGRST205', '42P01']);

/** null = la base ne connaît pas encore les présences sans compte (l'éditeur garde l'ancien fonctionnement). */
export async function fetchManualGuests(eventId: string): Promise<ManualGuest[] | null> {
  const { data, error } = await supabase.from('event_manual_guests').select('id, name, status, created_at')
    .eq('event_id', eventId).order('created_at', { ascending: true });
  if (error) {
    if (MISSING.has(error.code ?? '')) return null;
    throw new Error(manualError(error.message));
  }
  return (data as ManualGuest[] | null) ?? [];
}

export async function addManualGuest(eventId: string, name: string, status: RsvpStatus = 'yes'): Promise<ManualGuest> {
  const { data, error } = await supabase.from('event_manual_guests').insert({ event_id: eventId, name: name.trim(), status })
    .select('id, name, status, created_at').single();
  if (error) throw new Error(manualError(error.message));
  return data as ManualGuest;
}

export async function setManualGuest(id: string, status: RsvpStatus) {
  const { error } = await supabase.from('event_manual_guests').update({ status }).eq('id', id);
  if (error) throw new Error(manualError(error.message));
}

export async function removeManualGuest(id: string) {
  const { error } = await supabase.from('event_manual_guests').delete().eq('id', id);
  if (error) throw new Error(manualError(error.message));
}

function manualError(message: string): string {
  // « content_refused: Ce nom… » : la phrase seule ; les refus de la garde (complet, Peut-être) sont déjà en français.
  return friendlyError(dbMessage(message, message));
}
