import { router, type Href } from 'expo-router';
import { Platform } from 'react-native';

// Le module vit d'ordinaire dans le cadre de la page Party (barre d'onglets). Ouvert SEUL (lien d'invitation, de groupe,
// de prono…), une fin de parcours ne doit jamais laisser la personne dans le module sans Party autour : elle n'aurait
// aucun moyen de voir les autres événements (retour de l'admin du 19.11, invité du paintball).
export const insidePartyFrame = () => Platform.OS !== 'web' || typeof window === 'undefined' || window.parent !== window;

const ID = /^\/event\/([0-9a-f-]{36})$/i;

/** Adresse de la page Party qui ouvre ce chemin du module (lu par PartyEvents.target, app/static/events-shell.js). */
export function partyUrl(path: string) {
  const event = ID.exec(path);
  if (event) return `/?tab=events&event=${event[1].toLowerCase()}`;
  if (path === '/' || path === '') return '/?tab=events';
  return `/?tab=events&path=${encodeURIComponent(path)}`;
}

// Pages qui restent seules (la personne n'a pas encore de compte, ou lien public) : carte d'invitation, partage,
// invitation de groupe / de prono / dans Party, connexion, accueil, CGU, confidentialité (URL de l'App Store), admin
// (dans le cadre d'admin.html). Toute autre page du module ouverte seule repart dans Party.
const ALONE = /^\/(invite|share|group-invite|join|prono-invite|sign-in|welcome|terms|privacy|admin)(\/|$)/;

/** Module ouvert seul sur une page « de l'app » : la page Party autour (même page du module). true : on part. */
export function leaveIfAlone(routerPath?: string): boolean {
  if (insidePartyFrame()) return false;
  try { if (localStorage.getItem('party_module_alone') === '1') return false; } catch { /* stockage bloqué */ }
  // Chemin du routeur : l'adresse du navigateur le suit avec un temps de retard (« /welcome » lu comme « / »).
  const here = location.pathname.replace(/^\/events(?=\/|$)/, '') || '/';
  const path = routerPath ?? here;
  if (ALONE.test(path)) return false;
  location.replace(partyUrl(path + (path === here ? location.search : '')));
  return true;
}

/** Ouvre une page du module : dans le cadre de Party, sur place ; module seul, la page Party autour. */
export function openInParty(path: string) {
  if (insidePartyFrame()) router.replace(path as Href);
  else location.assign(partyUrl(path));
}
