import { supabase } from './supabase';
import { colors } from './theme';
import type { EventRow, Rsvp, RsvpStatus } from './types';

type MinimalRsvp = (Pick<Rsvp, 'status' | 'plus_ones'> & { note?: string | null }) | undefined;

/** Les réponses sont closes une fois la date limite passée. */
export function rsvpClosed(event: Pick<EventRow, 'rsvp_deadline'>, now = Date.now()): boolean {
  return !!event.rsvp_deadline && new Date(event.rsvp_deadline).getTime() < now;
}

/** Crée ou met à jour la réponse de l’utilisateur en conservant les champs non modifiés. */
export async function saveRsvp(eventId: string, me: string, current: MinimalRsvp, patch: Partial<Pick<Rsvp, 'status' | 'plus_ones' | 'note'>>) {
  const status = patch.status ?? current?.status ?? 'yes';
  const { error } = await supabase.from('rsvps').upsert({
    event_id: eventId,
    user_id: me,
    status,
    // Un absent ne vient pas accompagné.
    plus_ones: status === 'yes' ? (patch.plus_ones ?? current?.plus_ones ?? 0) : 0,
    note: patch.note !== undefined ? patch.note : (current?.note ?? null),
  });
  if (error) throw new Error(error.message);
}

export const rsvpChoices: Record<RsvpStatus, { label: string; icon: string; fg: string; bg: string; dim: string; mine: string }> = {
  yes: { label: 'Présent', icon: '✓', fg: colors.onAccent, bg: colors.accent, dim: colors.accentDim, mine: 'Tu viens' },
  maybe: { label: 'Peut-être', icon: '?', fg: colors.onAccent, bg: colors.lavender, dim: colors.lavenderDim, mine: 'Peut-être' },
  no: { label: 'Absent', icon: '✕', fg: colors.onAccent, bg: colors.coral, dim: colors.coralDim, mine: 'Absent' },
};

export function rsvpOptions(allowMaybe: boolean): RsvpStatus[] {
  return allowMaybe ? ['yes', 'maybe', 'no'] : ['yes', 'no'];
}
