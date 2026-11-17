/**
 * Réponse choisie sur une carte d'invitation avant la connexion (10.11) : la personne passe par la page de connexion
 * normale (SMS) puis « Faisons connaissance », et retrouve sa réponse en revenant sur le lien, sans retoucher le bouton.
 * Gardée dans l'onglet (sessionStorage) 10 minutes au plus, pour ce lien seulement ; effacée une fois la réponse partie
 * et à la déconnexion (un autre compte connecté ensuite dans le même onglet ne l'envoie jamais à son nom).
 */
const KEY = 'party-invite-answer';
const MAX_AGE_MS = 10 * 60 * 1000;

export type PendingAnswer = 'yes' | 'maybe' | 'no' | 'poll';
const ANSWERS: readonly PendingAnswer[] = ['yes', 'maybe', 'no', 'poll'];

/** join : état de la case « Rejoindre aussi le groupe » (17.11), gardé avec la réponse ; absent si la case n'était pas montrée. */
export function rememberInviteAnswer(token: string, answer: PendingAnswer, now: number = Date.now(), join?: boolean): void {
  try { sessionStorage.setItem(KEY, JSON.stringify({ token, answer, at: now, join })); } catch { /* Stockage indisponible. */ }
}

/** La case gardée avec la réponse de CE lien (même fraîcheur que la réponse) ; undefined si elle n'était pas montrée. */
export function peekInviteJoin(token: string, now: number = Date.now()): boolean | undefined {
  if (!peekInviteAnswer(token, now)) return undefined;
  try {
    const join = (JSON.parse(sessionStorage.getItem(KEY) ?? '{}') as { join?: unknown }).join;
    return typeof join === 'boolean' ? join : undefined;
  } catch {
    return undefined;
  }
}

/** La réponse gardée pour CE lien (encore fraîche), sans l'effacer : la lire deux fois rend la même chose. */
export function peekInviteAnswer(token: string, now: number = Date.now()): PendingAnswer | null {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw) as { token?: unknown; answer?: unknown; at?: unknown };
    const fresh = typeof saved.at === 'number' && now - saved.at >= 0 && now - saved.at < MAX_AGE_MS;
    return saved.token === token && fresh && ANSWERS.includes(saved.answer as PendingAnswer) ? (saved.answer as PendingAnswer) : null;
  } catch {
    return null;
  }
}

/** Une réponse à une invitation attend la connexion (n'importe quel lien) : la page de connexion le dit (recette UX du 14.11). */
export function hasPendingInviteAnswer(now: number = Date.now()): boolean {
  try {
    const raw = sessionStorage.getItem(KEY);
    if (!raw) return false;
    const saved = JSON.parse(raw) as { token?: unknown; at?: unknown };
    return typeof saved.token === 'string' && typeof saved.at === 'number' && now - saved.at >= 0 && now - saved.at < MAX_AGE_MS;
  } catch {
    return false;
  }
}

export function clearInviteAnswer(): void {
  try { sessionStorage.removeItem(KEY); } catch { /* Stockage indisponible. */ }
}
