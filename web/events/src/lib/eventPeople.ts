/** Personnes citées dans une fiche (auteur, organisateurs, réponses, votes, objets, propositions de dates…) : la fiche ne lit
 * plus que leurs profils, au lieu de toute la table `profiles` (campagne 2, 07.11). */
const PERSON_KEYS = new Set(['user_id', 'created_by', 'proposed_by', 'approved_by', 'checked_in_by']);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

function collect(value: unknown, into: Set<string>): void {
  if (Array.isArray(value)) {
    value.forEach((v) => collect(v, into));
    return;
  }
  if (!value || typeof value !== 'object') return;
  for (const [key, v] of Object.entries(value as Record<string, unknown>)) {
    if (PERSON_KEYS.has(key) && typeof v === 'string' && UUID.test(v)) into.add(v);
    else if (v && typeof v === 'object') collect(v, into);
  }
}

export function eventPeopleIds(event: unknown, ...more: unknown[]): string[] {
  const ids = new Set<string>();
  collect(event, ids);
  more.forEach((m) => collect(m, ids));
  return [...ids];
}
