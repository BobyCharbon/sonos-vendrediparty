import { friendlyError } from './errors';
import { dbMessage, isTermsError } from './moderation';
import { supabase } from './supabase';

/** Covoiturage d'un événement (avis 34d5c07f2e56, 11.11 ; migration 20261113090000) : tout passe par la base. */
export type CarpoolPerson = { id: string; name: string; avatar_url?: string | null; from_city?: string | null };
export type CarpoolDriver = CarpoolPerson & { seats: number; passengers: { id: string; name: string }[] };
export type CarpoolMe = { id: string; role: 'driver' | 'passenger'; seats: number | null; from_city: string | null; driver_id: string | null };
export type Carpool =
  | { enabled: false }
  | { enabled: true; member: false }
  | { enabled: true; member: true; me: CarpoolMe | null; drivers: CarpoolDriver[]; seekers: CarpoolPerson[] };

export const MAX_SEATS = 8;

export class CarpoolError extends Error {
  readonly terms: boolean;
  constructor(message: string, terms: boolean) {
    super(message);
    this.terms = terms;
  }
}

async function call(fn: string, args: Record<string, unknown>): Promise<Carpool> {
  const { data, error } = await supabase.rpc(fn, args);
  if (error) {
    throw new CarpoolError(friendlyError(dbMessage(error.message, error.message)), isTermsError(error.message));
  }
  return data as Carpool;
}

export const fetchCarpool = (e: string) => call('carpool', { e });
export const drive = (e: string, seats: number, city: string) => call('carpool_drive', { e, seats, from_city: city.trim() || null });
export const seek = (e: string, city: string) => call('carpool_seek', { e, from_city: city.trim() || null });
export const takeSeat = (e: string, driver: string) => call('carpool_take', { e, driver });
export const pick = (e: string, person: string) => call('carpool_pick', { e, person });
export const drop = (e: string, person: string) => call('carpool_drop', { e, person });
export const leave = (e: string) => call('carpool_leave', { e });

export function freeSeats(d: CarpoolDriver): number {
  return Math.max(0, d.seats - d.passengers.length);
}

/** « 2 voitures · 3 places libres · 1 cherche une place » (seulement ce qui compte). */
export function carpoolSummary(drivers: CarpoolDriver[], seekers: CarpoolPerson[]): string {
  const free = drivers.reduce((n, d) => n + freeSeats(d), 0);
  const parts = [
    drivers.length ? `${drivers.length} voiture${drivers.length > 1 ? 's' : ''}` : '',
    drivers.length ? `${free} place${free > 1 ? 's' : ''} libre${free > 1 ? 's' : ''}` : '',
    seekers.length ? `${seekers.length} cherche${seekers.length > 1 ? 'nt' : ''} une place` : '',
  ].filter(Boolean);
  return parts.length ? parts.join(' · ') : 'Personne pour l’instant : propose tes places ou demande-en une';
}
