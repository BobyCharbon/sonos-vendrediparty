/**
 * Contrôles du formulaire d'événement et de la carte « Ta réponse » (campagne 2, 07.11.2026), sans dépendance :
 * testés tels quels par Node (tests/test_event_checks.py). Chaque contrôle rend la phrase à afficher, ou null.
 */

/** Un début « tout juste passé » reste permis (on crée l'événement pendant qu'il commence). */
export const PAST_GRACE_MS = 60 * 60 * 1000;
/** Plafonds du formulaire (la base va plus haut, mais avec une erreur technique). */
export const MAX_PRICE_CHF = 100_000;
export const MAX_PLACES = 10_000;

export type DateChecks = {
  now: number;
  /** ISO (déjà lus) ; null : vide. */
  starts: string | null;
  rsvpDeadline: string | null;
  pollDeadline: string | null;
  /** Créneaux du sondage de dates ; isNew : ajouté ici (un créneau déjà voté peut être passé). */
  slots: { iso: string; isNew: boolean }[];
  /** Le début a été saisi ou changé ici (modifier un événement déjà commencé reste possible). */
  startsChanged: boolean;
};

const time = (iso: string) => new Date(iso).getTime();
const fmt = (iso: string) => {
  const d = new Date(iso);
  const p = (n: number) => String(n).padStart(2, '0');
  return `${p(d.getDate())}.${p(d.getMonth() + 1)}.${d.getFullYear()} ${p(d.getHours())}:${p(d.getMinutes())}`;
};

/** Dates incohérentes : début passé, date limite de réponse après le début, fin du vote après les créneaux. */
export function dateProblem(c: DateChecks): string | null {
  if (c.starts && c.startsChanged && time(c.starts) < c.now - PAST_GRACE_MS) {
    return 'Le début est déjà passé : choisis une date à venir';
  }
  if (c.starts && c.rsvpDeadline && time(c.rsvpDeadline) > time(c.starts)) {
    return 'La date limite de réponse doit être avant le début de l’événement';
  }
  const past = c.slots.find((s) => s.isNew && time(s.iso) < c.now);
  if (past) return `Créneau du ${fmt(past.iso)} : déjà passé`;
  if (c.pollDeadline && c.slots.length) {
    const first = Math.min(...c.slots.map((s) => time(s.iso)));
    if (time(c.pollDeadline) > first) return 'La fin du vote doit être avant le premier créneau proposé';
  }
  if (c.rsvpDeadline && c.slots.length) {
    const first = Math.min(...c.slots.map((s) => time(s.iso)));
    if (time(c.rsvpDeadline) > first) return 'La date limite de réponse doit être avant le premier créneau proposé';
  }
  return null;
}

/** « Accompagnants max » : vide = illimité ; sinon un entier de 1 à max (jamais corrigé en silence). */
export function plusOnesProblem(text: string, max: number): string | null {
  const v = text.trim();
  if (!v) return null;
  if (!/^\d+$/.test(v)) return `Accompagnants max : un nombre entier de 1 à ${max} (vide = illimité)`;
  const n = Number(v);
  if (n < 1) return 'Accompagnants max : 1 au moins. Pour aucun accompagnant, coupe « Accompagnants (+1) »';
  if (n > max) return `Accompagnants max : ${max} au plus (vide = illimité)`;
  return null;
}

/** Prix : positif ou zéro, deux décimales au plus, plafonné (jamais arrondi en silence). */
export function priceProblem(text: string): string | null {
  const v = text.trim().replace(',', '.');
  if (!v) return null;
  const n = Number(v);
  if (!/^\d+(\.\d+)?$/.test(v) || !Number.isFinite(n)) return 'Le prix doit être un montant positif ou zéro';
  if (/\.\d{3,}$/.test(v)) return 'Le prix : deux chiffres après la virgule au plus (ex. 12.50)';
  if (n > MAX_PRICE_CHF) return `Le prix ne peut pas dépasser ${MAX_PRICE_CHF.toLocaleString('fr-CH')} CHF`;
  return null;
}

/** Nombre de places : entier de 1 au plafond. */
export function placesProblem(text: string): string | null {
  const v = text.trim();
  if (!v) return null;
  const n = Number(v.replace(',', '.'));
  if (!Number.isInteger(n) || n < 1) return 'Nombre de places invalide';
  if (n > MAX_PLACES) return `Nombre de places : ${MAX_PLACES.toLocaleString('fr-CH')} au plus`;
  return null;
}

type QueueRsvp = {
  user_id: string;
  status: string;
  waitlisted: boolean;
  updated_at?: string | null;
  plus_ones_waitlisted?: number | null;
  plus_ones_waitlisted_since?: string | null;
};

/** Ordre de la liste d'attente, comme la base (apply_waitlist : moment d'arrivée, la personne avant ses accompagnants). */
export function waitlistQueue<R extends QueueRsvp>(rsvps: readonly R[]): { r: R; extras: number; since: string }[] {
  const people = rsvps.filter((r) => r.status === 'yes' && r.waitlisted).map((r) => ({ r, extras: 0, since: r.updated_at ?? '' }));
  const extras = rsvps.filter((r) => r.status === 'yes' && !r.waitlisted && (r.plus_ones_waitlisted ?? 0) > 0)
    .map((r) => ({ r, extras: r.plus_ones_waitlisted ?? 0, since: r.plus_ones_waitlisted_since ?? '' }));
  return [...people, ...extras].sort((a, b) => (a.since || '￿').localeCompare(b.since || '￿')
    || (a.extras ? 1 : 0) - (b.extras ? 1 : 0) || a.r.user_id.localeCompare(b.r.user_id));
}

/** Rang (1, 2…) de la personne en liste d'attente, ou null (pas en attente, ou file illisible). */
export function waitlistRank(rsvps: readonly QueueRsvp[], me: string): number | null {
  const i = waitlistQueue(rsvps).findIndex((q) => !q.extras && q.r.user_id === me);
  return i < 0 ? null : i + 1;
}
