import { check, must, supabase } from './supabase';

/** Modèle d'événement (table event_templates, migration 20261028170000) : perso ou d'équipe (shared). */
export type EventTemplate = { id: string; owner_id: string; name: string; shared: boolean; data: Record<string, unknown>; created_at: string };

// Propre à chaque événement : jamais repris d'un modèle (dates, personnes invitées ou co-organisatrices).
const SKIPPED = ['starts_at', 'ends_at', 'slots', 'poll_deadline', 'rsvp_deadline', 'organizers'];

type WithLabel = { label: string };
type PollLike = { options: WithLabel[] } & Record<string, unknown>;

/** Réglages du formulaire gardés dans un modèle : tout sauf dates et personnes ; sondages et « qui amène quoi »
 *  sans leurs identifiants (ils seront recréés avec le nouvel événement). */
export function templateData(draft: Record<string, unknown>): Record<string, unknown> {
  const data: Record<string, unknown> = {};
  for (const [key, value] of Object.entries(draft)) {
    if (!SKIPPED.includes(key)) data[key] = value;
  }
  if (Array.isArray(draft.polls)) {
    data.polls = (draft.polls as PollLike[]).map(({ id: _id, ...poll }) => ({ ...poll, options: poll.options.map((o) => ({ label: o.label })) }));
  }
  if (Array.isArray(draft.bring)) data.bring = (draft.bring as WithLabel[]).map((b) => ({ label: b.label }));
  if (draft.who && typeof draft.who === 'object') data.who = { ...(draft.who as object), invitees: [], phones: [] };
  return data;
}

/** Applique un modèle à un formulaire : seuls les champs connus, du même type, remplacent ceux du formulaire
 *  (un modèle ancien ou incomplet ne casse rien ; les dates restent celles déjà saisies). */
export function applyTemplate<D extends Record<string, unknown>>(draft: D, data: Record<string, unknown>): D {
  const next: Record<string, unknown> = { ...draft };
  for (const [key, value] of Object.entries(data)) {
    if (SKIPPED.includes(key) || !(key in draft)) continue;
    const current = draft[key];
    const sameKind = Array.isArray(current) ? Array.isArray(value) : current === null || value === null || typeof current === typeof value;
    if (sameKind) next[key] = value;
  }
  return next as D;
}

export async function listTemplates(): Promise<EventTemplate[]> {
  // Équipe d'abord, puis les siens ; par nom.
  return must(await supabase.from('event_templates').select('id, owner_id, name, shared, data, created_at')
    .order('shared', { ascending: false }).order('name')) as EventTemplate[];
}

export async function createTemplate(name: string, shared: boolean, data: Record<string, unknown>): Promise<void> {
  check(await supabase.from('event_templates').insert({ name: name.trim().slice(0, 60), shared, data }));
}

export async function deleteTemplate(id: string): Promise<void> {
  // La base refuse en silence ce qu'on n'a pas le droit de supprimer : on vérifie qu'une ligne est bien partie.
  const removed = must(await supabase.from('event_templates').delete().eq('id', id).select('id')) as { id: string }[];
  if (!removed.length) throw new Error('Tu ne peux supprimer que tes propres modèles.');
}
