import { supabase } from '@/lib/supabase';

/** Invitations dans Party (avis 84fab3987f68) : lien personnel de chaque compte, page « X t'invite sur Party ». */

export const INVITE_TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const PENDING_KEY = 'party-app-invite';
const TEST_HOST = 'partytest.bobycharbon.ch';
/** App VendrediParty sur l'App Store (site principal) ; bêta publique TestFlight (site de test). */
export const APP_STORE_URL = 'https://apps.apple.com/app/id6827221948';
export const TESTFLIGHT_URL = 'https://testflight.apple.com/join/eut4j7m9';

export type InvitePreview = { inviter: string; avatar_url: string | null };
export type MyInvite = { token: string; created_at: string; joined: number };

export function isTestSite(): boolean {
  return typeof location !== 'undefined' && location.hostname === TEST_HOST;
}

/** Où télécharger l'app : l'App Store pour le site principal, TestFlight pour le site de test. */
export function appDownload(): { url: string; label: string } {
  return isTestSite()
    ? { url: TESTFLIGHT_URL, label: 'Installer la bêta (TestFlight)' }
    : { url: APP_STORE_URL, label: 'Télécharger sur l’App Store' };
}

export function joinUrl(token: string): string {
  const origin = typeof location !== 'undefined' ? location.origin : 'https://party.bobycharbon.ch';
  return `${origin}/events/join/${token}`;
}

/** « Continuer sur le web » : le lien est gardé pendant l'inscription (SMS, profil), puis réclamé une fois. */
export function rememberInvite(token: string): void {
  if (!INVITE_TOKEN.test(token)) return;
  try { localStorage.setItem(PENDING_KEY, token.toLowerCase()); } catch { /* Stockage indisponible. */ }
}

export function pendingInvite(): string | null {
  try {
    const token = localStorage.getItem(PENDING_KEY);
    return token && INVITE_TOKEN.test(token) ? token : null;
  } catch { return null; }
}

export function forgetInvite(): void {
  try { localStorage.removeItem(PENDING_KEY); } catch { /* Stockage indisponible. */ }
}

/** Texte lisible d'une erreur de la base (« self: C'est ton propre lien… » → « C'est ton propre lien… »). */
export function readable(message: string | undefined, fallback: string): string {
  return message ? message.replace(/^[a-z_]+: /, '') : fallback;
}

export async function previewInvite(token: string): Promise<InvitePreview | null> {
  const { data, error } = await supabase.rpc('app_invite_preview', { token });
  if (error) throw new Error('L’invitation n’a pas pu être lue. Réessaie dans un instant.');
  return (data as InvitePreview | null) ?? null;
}

/** Une seule demande à la fois par lien : la page du lien et la réclamation en arrière-plan partagent la même réponse. */
const claims = new Map<string, Promise<{ new: boolean }>>();

/** Réclame le lien : { new } ; le nom de l'inviteur n'est jamais renvoyé (« qui a invité qui » : admins seulement).
 * Erreur lisible sinon (compte ancien, propre lien, déjà noté…). */
export function claimInvite(token: string): Promise<{ new: boolean }> {
  const key = token.toLowerCase();
  const running = claims.get(key);
  if (running) return running;
  const request = (async () => {
    const { data, error } = await supabase.rpc('claim_app_invite', { token: key });
    if (error) throw new Error(readable(error.message, 'L’invitation n’a pas pu être enregistrée.'));
    return data as { new: boolean };
  })();
  claims.set(key, request);
  request.catch(() => claims.delete(key));  // échec : on pourra réessayer
  return request;
}

/** Erreur définitive : inutile de réessayer plus tard (le lien gardé est oublié). */
export function finalClaimError(message: string): boolean {
  return !/complète ton profil|Connexion requise|réessaie/i.test(message);
}

/** Texte prérempli du partage (WhatsApp, Instagram, Snapchat, Messages…). */
export function shareText(url: string): string {
  return `Rejoins-moi sur Party, pour nos soirées et événements : ${url}`;
}

export type ShareTarget = { key: string; label: string; href: string };

/** Sans feuille de partage (ordinateur, vieux navigateur) : liens directs des applis qui en acceptent un.
 * Instagram et Snapchat n'ont pas d'adresse de partage fiable : « Copier le lien » puis coller dans l'app. */
export function shareTargets(url: string): ShareTarget[] {
  const text = encodeURIComponent(shareText(url));
  return [
    { key: 'whatsapp', label: 'WhatsApp', href: `https://wa.me/?text=${text}` },
    { key: 'telegram', label: 'Telegram', href: `https://t.me/share/url?url=${encodeURIComponent(url)}&text=${encodeURIComponent('Rejoins-moi sur Party')}` },
    { key: 'sms', label: 'SMS', href: `sms:?&body=${text}` },
    { key: 'mail', label: 'E-mail', href: `mailto:?subject=${encodeURIComponent('Rejoins-moi sur Party')}&body=${text}` },
  ];
}
