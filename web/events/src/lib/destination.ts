/** Page demandée à l'ouverture du module, gardée dans l'onglet jusqu'à la connexion (app/_layout.tsx). */
export const DESTINATION_KEY = 'party-events-destination';

/** Lien ouvert avant la connexion (événement public, invitation, groupe, Party) : on y retourne dès la connexion faite. */
export function pendingLinkDestination(): boolean {
  try {
    return /^\/(?:share|invite|group-invite|join)\//.test(sessionStorage.getItem(DESTINATION_KEY) ?? '');
  } catch {
    return false;
  }
}
