import { refreshPending } from './pending';
import { supabase } from './supabase';
import { colors } from './theme';
import type { EventRow, Rsvp, RsvpStatus } from './types';

type MinimalRsvp = (Pick<Rsvp, 'status' | 'plus_ones'> & { note?: string | null }) | undefined;

/** Les réponses sont closes une fois la date limite passée. */
export function rsvpClosed(event: Pick<EventRow, 'rsvp_deadline'>, now = Date.now()): boolean {
  return !!event.rsvp_deadline && new Date(event.rsvp_deadline).getTime() < now;
}

/**
 * Crée ou met à jour la réponse de l’utilisateur en conservant les champs non modifiés.
 * La base n’autorise la mise à jour que de status, plus_ones et note : pas d’upsert
 * (il réécrirait event_id et user_id), mais une insertion puis, si elle existe déjà, une mise à jour.
 */
export async function saveRsvp(eventId: string, me: string, current: MinimalRsvp, patch: Partial<Pick<Rsvp, 'status' | 'plus_ones' | 'note'>>) {
  const status = patch.status ?? current?.status ?? 'yes';
  const fields = {
    status,
    // Un absent ne vient pas accompagné.
    plus_ones: status === 'yes' ? (patch.plus_ones ?? current?.plus_ones ?? 0) : 0,
    note: patch.note !== undefined ? patch.note : (current?.note ?? null),
  };
  const update = () => supabase.from('rsvps').update(fields).eq('event_id', eventId).eq('user_id', me);
  let { error } = current
    ? await update()
    : await supabase.from('rsvps').insert({ event_id: eventId, user_id: me, ...fields });
  // Réponse déjà enregistrée ailleurs (autre onglet, autre appareil) : on la met à jour.
  if (error?.code === '23505') ({ error } = await update());
  if (error) throw new Error(friendlyRsvpError(error.message));
  refreshPending();
}

function friendlyRsvpError(message: string): string {
  if (/permission denied/i.test(message)) return 'Ta réponse n’a pas pu être enregistrée. Recharge la page puis réessaie.';
  return message;
}

export const rsvpChoices: Record<RsvpStatus, { label: string; icon: string; fg: string; bg: string; dim: string; mine: string }> = {
  yes: { label: 'Présent', icon: '✓', fg: colors.onAccent, bg: colors.accent, dim: colors.accentDim, mine: 'Tu viens' },
  maybe: { label: 'Peut-être', icon: '?', fg: colors.onAccent, bg: colors.lavender, dim: colors.lavenderDim, mine: 'Peut-être' },
  no: { label: 'Absent', icon: '✕', fg: colors.onAccent, bg: colors.coral, dim: colors.coralDim, mine: 'Absent' },
};

export function rsvpOptions(allowMaybe: boolean): RsvpStatus[] {
  return allowMaybe ? ['yes', 'maybe', 'no'] : ['yes', 'no'];
}
