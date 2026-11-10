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

export function rememberInviteAnswer(token: string, answer: PendingAnswer, now: number = Date.now()): void {
  try { sessionStorage.setItem(KEY, JSON.stringify({ token, answer, at: now })); } catch { /* Stockage indisponible. */ }
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

export function clearInviteAnswer(): void {
  try { sessionStorage.removeItem(KEY); } catch { /* Stockage indisponible. */ }
}
