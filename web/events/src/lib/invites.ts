import { Linking, Platform } from 'react-native';

import { friendlyError } from './errors';
import { formatShort } from './format';
import { supabase } from './supabase';
import type { RsvpStatus } from './types';

const shortDate = (iso: string | null) => formatShort(iso).toLowerCase();

/**
 * Invitations v2 (bêta, migration 20261105200000) : carte « Invités » de l'organisateur, feuille « Inviter », carte
 * d'invitation lisible sans compte. La base vérifie chaque droit (organisateurs seulement, une relance par jour…).
 */

export type GuestSource = 'vip' | 'group' | 'person' | 'link' | 'public';
export type Guest = {
  id: string; name: string; avatar_url: string | null; status: RsvpStatus | null; waitlisted: boolean; plus_ones: number;
  source: GuestSource; group: string | null; invited_by: string | null; invited_by_id: string | null; link_label: string | null; link_token: string | null;
  has_app: boolean; light: boolean; nudged_today: boolean; removable: boolean;
  /** Sondage de dates : a voté pour au moins une date ; poll : la liste est celle d'un sondage (08.11). */
  voted?: boolean; poll?: boolean;
};
export type LinkState = 'pending' | 'opened' | 'full' | 'expired' | 'revoked';
export type SentLink = {
  token: string; label: string | null; max_uses: number; uses: number; created_at: string; expires_at: string;
  opened_at: string | null; state: LinkState; version: number; created_by: string | null; created_by_id: string | null;
  nudged_today: boolean; arrivals: { id: string; name: string; status: RsvpStatus | null }[];
};
export type GuestList = {
  vip: boolean; public: boolean; vip_name: string | null; poll?: boolean;
  groups: { id: string; name: string; members: number }[];
  people: Guest[]; links: SentLink[];
};

/** Filtres de la carte : réponses, pas encore répondu, lien pas encore ouvert. */
export type GuestFilter = 'all' | RsvpStatus | 'none' | 'unopened';

/** Lien « pour une personne » sans réponse : compte comme une personne (ouvert → pas répondu, sinon pas ouvert). */
function waitingLinks(list: GuestList) {
  return list.links.filter((l) => l.max_uses === 1 && (l.state === 'pending' || l.state === 'opened') && !l.arrivals.length);
}

export function guestCounts(list: GuestList): Record<Exclude<GuestFilter, 'all'>, number> & { total: number } {
  const count = (s: RsvpStatus) => list.people.filter((p) => p.status === s).length;
  const waiting = waitingLinks(list);
  const unopened = waiting.filter((l) => l.state === 'pending').length;
  const none = list.people.filter((p) => !p.status).length + waiting.length - unopened;
  return { yes: count('yes'), maybe: count('maybe'), no: count('no'), none, unopened, total: list.people.length + waiting.length };
}

export function filterGuests(list: GuestList, filter: GuestFilter): Guest[] {
  if (filter === 'all') return list.people;
  if (filter === 'unopened') return [];
  return list.people.filter((p) => (filter === 'none' ? !p.status : p.status === filter));
}

/** Liens à montrer pour un filtre : tous (« Tous »), ceux sans réponse (« Pas répondu », « Lien pas ouvert »). */
export function filterLinks(list: GuestList, filter: GuestFilter): SentLink[] {
  if (filter === 'all') return list.links;
  const waiting = waitingLinks(list);
  if (filter === 'unopened') return waiting.filter((l) => l.state === 'pending');
  if (filter === 'none') return waiting.filter((l) => l.state === 'opened');
  return [];
}

/** « Vendredi Party + 3 invités », la règle en une phrase. */
export function ruleSentence(list: Pick<GuestList, 'vip' | 'public' | 'vip_name' | 'groups' | 'people'>): string {
  const groups = [...(list.vip ? [list.vip_name || 'Vendredi Party'] : []), ...list.groups.map((g) => g.name)];
  const extra = list.people.filter((p) => p.source === 'person' || p.source === 'link').length;
  const head = list.public ? 'Tout Party et le lien public' : groups.length ? groups.join(' + ') : 'Sur invitation';
  return extra ? `${head} + ${extra} ${extra > 1 ? 'invités' : 'invité'}` : head;
}

/** D'où vient la personne, en mots simples : « Ajoutée par toi », « Par le lien « Léa » · invitée par Ludo »… */
export function guestOrigin(p: Guest, me: string): string {
  const by = p.invited_by_id === me ? 'toi' : p.invited_by?.trim() || null;
  if (p.source === 'vip' || p.source === 'group') return `Avec le groupe ${p.group ?? ''}`.trim();
  if (p.source === 'public') return 'A répondu au lien public';
  if (p.source === 'link') {
    const link = p.link_label ? `Par le lien « ${p.link_label} »` : 'Par le lien';
    return by ? `${link} · de ${by}` : link;
  }
  return by ? `Ajouté par ${by}` : 'Ajouté un par un';
}

export const statusWords: Record<RsvpStatus, string> = { yes: 'Vient', maybe: 'Peut-être', no: 'Absent' };

/** Suivi d'un lien en une ligne : « Pas encore ouvert », « Ouvert · pas de réponse », « 2 sur 10 places »… */
export function linkLine(l: SentLink): string {
  if (l.state === 'revoked') return 'Arrêté';
  if (l.max_uses > 1) {
    const places = `${l.uses} sur ${l.max_uses} places`;
    return l.state === 'expired' ? `${places} · terminé` : `${places} · jusqu’au ${shortDate(l.expires_at)}`;
  }
  if (l.arrivals.length) return `${l.arrivals[0]!.name} a répondu${l.arrivals[0]!.status ? ` « ${statusWords[l.arrivals[0]!.status]} »` : ''}`;
  if (l.state === 'expired') return 'Plus valable · jamais utilisé';
  if (l.state === 'opened') return `Ouvert ${shortDate(l.opened_at)} · pas encore de réponse`;
  return `Envoyé ${shortDate(l.created_at)} · pas encore ouvert`;
}

/** Titre d'un lien de la carte « Invités ». */
export function linkTitle(l: SentLink): string {
  if (l.label) return `Lien pour ${l.label}`;
  return l.max_uses > 1 ? 'Lien pour plusieurs' : 'Lien pour une personne';
}

/** Nom lu par VoiceOver pour chaque lien : distinct même quand plusieurs liens ont le même titre (« Relancer Lien pour
 * plusieurs » ×3 ne disait pas lequel). Les homonymes sont numérotés, du plus ancien au plus récent, avec leurs places. */
export function linkSpokenNames(links: SentLink[]): Map<string, string> {
  const byTitle = new Map<string, SentLink[]>();
  for (const l of links) byTitle.set(linkTitle(l), [...(byTitle.get(linkTitle(l)) ?? []), l]);
  const names = new Map<string, string>();
  for (const [title, same] of byTitle) {
    const ordered = [...same].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.token.localeCompare(b.token));
    ordered.forEach((l, i) => {
      if (ordered.length === 1) return names.set(l.token, title);
      const places = l.max_uses > 1 ? `, ${l.max_uses} places` : '';
      names.set(l.token, `${title} n° ${i + 1}${places}, envoyé ${shortDate(l.created_at)}`);
    });
  }
  return names;
}

export function inviteLinkUrl(token: string): string {
  const origin = typeof location !== 'undefined' ? location.origin : 'https://party.bobycharbon.ch';
  return `${origin}/events/invite/${token}`;
}

/** Le message prêt à envoyer (le lien seul suffit : l'aperçu montre l'événement). */
export function inviteMessage(opts: { name?: string | null; host: string; title: string; when: string | null; url: string; nudge?: boolean }): string {
  const hello = opts.name?.trim() ? `Hello ${opts.name.trim()} !` : 'Hello !';
  const what = `« ${opts.title} »${opts.when ? `, ${opts.when}` : ''}`;
  const body = opts.nudge ? `Petit rappel : tu viens à ${what} ?` : `${opts.host} t’invite à ${what}.`;
  return `${hello} ${body} Réponds ici, sans app : ${opts.url}`;
}

/** Feuille de partage du téléphone (iOS, Android) ; ailleurs, copie. Renvoie ce qui s'est passé. */
export async function shareInvite(text: string, url: string, title: string): Promise<'shared' | 'copied' | 'cancelled' | 'failed'> {
  if (Platform.OS === 'web' && typeof navigator !== 'undefined' && 'share' in navigator) {
    try {
      await navigator.share({ title, text: text.replace(url, '').trim(), url });
      return 'shared';
    } catch (e) {
      if (e instanceof Error && e.name === 'AbortError') return 'cancelled';
    }
  }
  return (await copyText(text)) ? 'copied' : 'failed';
}

export async function copyText(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    return false;
  }
}

export function openWhatsApp(text: string) {
  void Linking.openURL(`https://wa.me/?text=${encodeURIComponent(text)}`);
}

export function openMessages(text: string) {
  // iOS lit « sms:&body= », Android « sms:?body= » : la forme « sms:?&body= » marche sur les deux.
  void Linking.openURL(`sms:?&body=${encodeURIComponent(text)}`);
}

const readable = (message: string | undefined, fallback: string) => (message ? friendlyError(message.replace(/^[a-z_]+: /, '')) : fallback);

async function call<T>(name: string, args: Record<string, unknown>, fallback: string): Promise<T> {
  const { data, error } = await supabase.rpc(name, args);
  if (error) throw new Error(readable(error.message, fallback));
  return data as T;
}

export const fetchGuestList = (e: string) =>
  call<GuestList>('event_guest_list', { e }, 'La liste des invités n’a pas pu être lue.').then(pollGuestList);

/**
 * Sondage de dates (08.11) : répondre, c'est voter les dates. « A voté » tient la place de « vient » (mêmes comptes, mêmes
 * filtres, même relance) ; une ancienne réponse « je viens » donnée par un lien ne compte pas tant que la date n'est pas fixée.
 */
export function pollGuestList(list: GuestList): GuestList {
  if (!list.poll) return list;
  return { ...list, people: list.people.map((p) => ({ ...p, poll: true, status: p.voted ? 'yes' : null, waitlisted: false, plus_ones: 0 })) };
}
export const createInvite = (e: string, places: number, until: string | null, label: string | null) =>
  call<{ token: string; expires_at: string; max_uses: number; label: string | null }>(
    'create_event_invite', { e, places, until, label }, 'Le lien n’a pas pu être créé. Réessaie.');
/** announce : « Prévenir le groupe » pour les groupes ajoutés ICI seulement (event_groups.announce, migration 20261107100000). */
export const invitePeople = (e: string, people: string[], groups: string[], announce = false) =>
  call<{ people: number; groups: number }>('invite_people', { e, people, groups, ...(announce ? { announce } : {}) }, 'L’invitation n’a pas pu être envoyée.');
export const removeInvitee = (e: string, member: string) => call<null>('remove_invitee', { e, member }, 'La personne n’a pas pu être retirée.');
export const nudgeInvitees = (e: string, people: string[]) =>
  call<{ notified: number; skipped: number; share: string[] }>('nudge_invitees', { e, people }, 'La relance n’a pas pu partir.');
export const nudgeLink = (tok: string) => call<null>('nudge_invite_link', { tok }, 'La relance n’a pas pu partir.');
export const stopLink = (tok: string) => call<null>('revoke_invite_link', { tok }, 'Le lien n’a pas pu être arrêté.');

/** Carte d'invitation (lisible sans compte). */
export type InviteCard = {
  state: LinkState | 'mine'; version: number; label: string | null; places_left: number | null; inviter: string | null;
  title: string; status: 'published' | 'cancelled'; date_mode: 'fixed' | 'poll'; starts_at: string | null; ends_at: string | null;
  all_day: boolean; location_name: string | null; cover_url: string | null; description: string | null; allow_maybe: boolean;
  closed: boolean; going: number; going_names: string[]; mine: RsvpStatus | null; event_id: string | null;
  location_address: string | null; location_url: string | null; me_named: boolean;
};
export type Accepted = {
  event_id: string; status: RsvpStatus | null; title: string; starts_at: string | null; ends_at: string | null; all_day: boolean;
  date_mode: string; location_name: string | null; location_address: string | null; location_url: string | null;
  description: string | null; waitlisted: boolean | null;
};

export const fetchInviteCard = (token: string, opened: boolean) =>
  call<InviteCard | null>('invite_preview', { token, opened }, 'L’invitation n’a pas pu être lue. Réessaie dans un instant.');
/** « poll » : sondage de dates, on rejoint l'événement sans « je viens » puis on vote les dates (08.11). */
export const acceptInvite = (token: string, answer: RsvpStatus | 'poll', firstName: string | null) =>
  call<Accepted>('accept_invite', { token, answer, first_name: firstName }, 'Ta réponse n’a pas pu être enregistrée. Réessaie.');
