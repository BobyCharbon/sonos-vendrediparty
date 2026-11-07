/** Un événement reste « à venir » 6 h après son début (ou sa fin) : comme la liste « Passés ». */
export const ENDED_AFTER_MS = 6 * 3600_000;

type Timed = { rsvp_deadline: string | null; starts_at?: string | null; ends_at?: string | null; date_mode?: string };

/** Terminé : sa fin (ou son début) est passée de plus de 6 h. Un sondage de dates sans date n'est jamais terminé. */
export function eventEnded(event: Timed, now = Date.now()): boolean {
  const at = event.ends_at ?? event.starts_at;
  if (!at || event.date_mode === 'poll') return false;
  return new Date(at).getTime() < now - ENDED_AFTER_MS;
}

/** Réponses closes : date limite passée, ou événement terminé (campagne 2 : un événement fini acceptait encore « Présent »). */
export function answersClosed(event: Timed, now = Date.now()): boolean {
  return (!!event.rsvp_deadline && new Date(event.rsvp_deadline).getTime() < now) || eventEnded(event, now);
}

export type ListTab = 'upcoming' | 'polls' | 'pending' | 'drafts' | 'past';

type Listed = { status: string; date_mode: string; created_by: string; starts_at: string | null };

/** Onglet de la liste où paraît un événement. Un événement à venir ANNULÉ reste dans « À venir » (barré, « Annulé ») :
 * l'organisateur le retrouve pour le supprimer, l'admin pour le rouvrir, les invités voient qu'il n'a plus lieu
 * (campagne 2 : il disparaissait de tous les onglets). Ce que chacun voit reste décidé par la base (RLS). */
export function inTab(e: Listed, tab: ListTab, me: string, now: number): boolean {
  const started = e.starts_at ? new Date(e.starts_at).getTime() : null;
  const limit = now - ENDED_AFTER_MS; // un événement reste « à venir » 6 h après son début
  const live = e.status === 'published' || e.status === 'cancelled';
  switch (tab) {
    case 'upcoming':
      return live && e.date_mode === 'fixed' && started !== null && started >= limit;
    case 'polls':
      return e.status === 'published' && e.date_mode === 'poll';
    // Mes propositions envoyées, qui attendent la validation d'un admin.
    case 'pending':
      return e.created_by === me && e.status === 'pending';
    // Mes brouillons, et mes propositions refusées à retravailler.
    case 'drafts':
      return e.created_by === me && (e.status === 'draft' || e.status === 'rejected');
    case 'past':
      return live && started !== null && started < limit;
  }
}
