import { answersClosed } from './eventTime';
import { refreshPending } from './pending';
import { friendlyError } from './errors';
import { dbMessage } from './moderation';
import { supabase } from './supabase';
import { plural } from './format';
import { colors } from './theme';
import type { RsvpNote } from './rsvpNote';
import type { EventRow, Rsvp, RsvpStatus } from './types';

type MinimalRsvp = Pick<Rsvp, 'status' | 'plus_ones' | 'plus_ones_waitlisted'> | undefined;
/** `note` : '' efface le mot, un texte le remplace ; absent = mot inchangé (jamais renvoyé). */
type RsvpPatch = Partial<Pick<Rsvp, 'status' | 'plus_ones'>> & { note?: string };

/** Petits mots d'un événement que la base nous laisse lire (le mien ; tous pour l'organisation et les admins). */
export async function fetchRsvpNotes(eventId: string): Promise<RsvpNote[]> {
  const { data, error } = await supabase.from('rsvp_notes').select('id, user_id, note').eq('event_id', eventId);
  // Base plus ancienne (table absente) ou réseau : pas de mot affiché, la réponse reste possible.
  if (error) return [];
  return (data as RsvpNote[] | null) ?? [];
}

/** Les réponses sont closes une fois la date limite passée, ou l'événement terminé (6 h après sa fin). */
export function rsvpClosed(event: Pick<EventRow, 'rsvp_deadline'> & Partial<Pick<EventRow, 'starts_at' | 'ends_at' | 'date_mode'>>, now = Date.now()): boolean {
  return answersClosed(event, now);
}

/**
 * En liste d’attente = Présent ET en attente. La base peut laisser « waitlisted » à vrai sur une réponse
 * Absent / Peut-être (passée par Présent en attente) : ce n’est jamais une attente.
 */
export function onWaitlist(r: Pick<Rsvp, 'status' | 'waitlisted'> | null | undefined): boolean {
  return !!r && r.status === 'yes' && r.waitlisted;
}

/** Accompagnants en liste d’attente (la personne, elle, a sa place). */
export function waitingPlusOnes(r: Pick<Rsvp, 'plus_ones_waitlisted'> | null | undefined): number {
  return r?.plus_ones_waitlisted ?? 0;
}

/** Accompagnants voulus : confirmés + en attente (c’est ce total que l’app enregistre). */
export function totalPlusOnes(r: Pick<Rsvp, 'plus_ones' | 'plus_ones_waitlisted'> | null | undefined): number {
  return (r?.plus_ones ?? 0) + waitingPlusOnes(r);
}

/** « Toi + 1 accompagnant confirmé · 1 en liste d’attente ». */
export function guestsLine(confirmed: number, waiting: number): string {
  const head = confirmed ? `Toi + ${plural(confirmed, 'accompagnant confirmé', 'accompagnants confirmés')}` : 'Toi';
  if (!waiting) return head;
  return `${head} · ${confirmed ? waiting : plural(waiting, 'accompagnant')} en liste d’attente`;
}

/**
 * Crée ou met à jour la réponse de l’utilisateur en conservant les champs non modifiés.
 * La base n’autorise la mise à jour que de status, plus_ones(_waitlisted) et note : pas d’upsert
 * (il réécrirait event_id et user_id), mais une insertion puis, si elle existe déjà, une mise à jour.
 * Le mot n’est envoyé que s’il change (la base le range dans rsvp_notes, filtre et CGU compris).
 */
export async function saveRsvp(eventId: string, me: string, current: MinimalRsvp, patch: RsvpPatch) {
  const status = patch.status ?? current?.status ?? 'yes';
  const fields = {
    status,
    // Un absent ne vient pas accompagné. plus_ones = TOTAL voulu (confirmés + en attente) : la base le répartit ;
    // complet, les accompagnants de plus passent en liste d’attente sans faire perdre sa place à la personne.
    plus_ones: status === 'yes' ? (patch.plus_ones ?? totalPlusOnes(current)) : 0,
    ...(patch.note !== undefined ? { note: patch.note } : {}),
    // Seulement si la base connaît la colonne (la réponse lue la contient) : sinon la mise à jour serait refusée.
    ...(current?.plus_ones_waitlisted !== undefined ? { plus_ones_waitlisted: 0 } : {}),
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

/**
 * L’organisateur (ou un admin) note quelqu’un Présent / Peut-être / Absent, ou retire sa réponse (null).
 * La base vérifie le droit, prévient la personne et l’inscrit au journal ; valable même après la date limite.
 */
export async function setRsvpFor(eventId: string, member: string, answer: RsvpStatus | null) {
  const { error } = await supabase.rpc('set_rsvp_for', { event: eventId, member, answer });
  if (error) throw new Error(friendlyRsvpError(error.message));
}

function friendlyRsvpError(message: string): string {
  // « content_refused: Mot non enregistré… », « terms_required: accepte… » : la phrase, sans la clé technique.
  return friendlyError(dbMessage(message, message));
}

export const rsvpChoices: Record<RsvpStatus, { label: string; icon: string; fg: string; bg: string; dim: string; mine: string }> = {
  yes: { label: 'Présent', icon: '✓', fg: colors.onMint, bg: colors.mint, dim: colors.mintDim, mine: 'Présent' },
  maybe: { label: 'Peut-être', icon: '?', fg: colors.onCoral, bg: colors.coral, dim: colors.coralDim, mine: 'Peut-être' },
  no: { label: 'Absent', icon: '✕', fg: colors.onRed, bg: colors.red, dim: colors.redDim, mine: 'Absent' },
};

export function rsvpOptions(allowMaybe: boolean): RsvpStatus[] {
  return allowMaybe ? ['yes', 'maybe', 'no'] : ['yes', 'no'];
}
