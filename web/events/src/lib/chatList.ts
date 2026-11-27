import type { ChatSummary } from './chats';
import { supabase } from './supabase';

/**
 * Liste des Discussions v2 (contrat discussions §3, §4, §8) : groupes, messages directs et discussions de soirée dans
 * une seule liste (`chat_list`), état par personne (épinglée, archivée, non lue : `set_chat_state`), demandes de message,
 * recherche (personnes, discussions, messages), pastille de l'onglet (`chat_badge`).
 */

export type ChatKind = 'direct' | 'group' | 'event';
export type ChatLast = {
  id: string; at: string; from_me: boolean; author: string | null;
  type: 'text' | 'photo' | 'audio' | 'event' | 'deleted'; text: string | null;
};
export type ChatItem = {
  kind: ChatKind; id: string; title: string;
  /** Photo : chemin du stockage (profile-photos pour une personne, group-photos pour un groupe), à signer. */
  photo: string | null; emoji: string | null; color: string | null;
  user_id: string | null; event_start: string | null; event_past: boolean;
  last: ChatLast | null;
  unread: number; mention: boolean; marked_unread: boolean; pinned_at: string | null; archived: boolean;
  notify: 'all' | 'mentions' | 'none'; muted_until: string | null;
  request: 'incoming' | 'outgoing' | null; seen_by_other: boolean | null;
  members: number; is_vp: boolean; blocked: boolean;
  /** Ancienne base (my_chats, avant la migration des Discussions v2) : chemins de photo à signer. */
  avatar_path?: string | null; photo_path?: string | null;
};

export const PIN_LIMIT = 5;

export const chatKey = (c: Pick<ChatItem, 'kind' | 'id'>) => `${c.kind}:${c.id}`;

/** Conditions d'utilisation pas encore acceptées : l'écran les ouvre (useTermsGate) puis réessaie ; jamais « va dans Réglages ». */
export class TermsNeeded extends Error {
  constructor() { super('Accepte d’abord les conditions d’utilisation de Party : touche à nouveau le bouton pour les lire.'); }
}
export const needsTerms = (e: unknown): boolean => e instanceof TermsNeeded;

/** Erreur lisible d'une fonction de la base (le message est déjà en français quand la base l'écrit). */
function fail(error: { message?: string; code?: string } | null, fallback: string): never {
  const msg = error?.message ?? '';
  if (/pin_limit/.test(msg)) throw new Error(`Tu peux épingler ${PIN_LIMIT} discussions au plus. Désépingles-en une d’abord.`);
  if (/terms_required/.test(msg)) throw new TermsNeeded();
  throw new Error(fallback);
}

/** Fonction absente de la base (migration pas encore passée) : PostgREST répond PGRST202 / 404. */
function missing(error: { code?: string; message?: string } | null): boolean {
  return !!error && (error.code === 'PGRST202' || error.code === '42883' || /Could not find the function/i.test(error.message ?? ''));
}

/** Toutes mes discussions (archivées comprises : la liste les sépare), épinglées d'abord puis la plus récente. */
export async function fetchChatList(): Promise<ChatItem[]> {
  const { data, error } = await supabase.rpc('chat_list', { include_archived: true });
  if (missing(error)) return fromOldList();
  if (error) fail(error, 'Les discussions n’ont pas pu être chargées. Vérifie ta connexion.');
  const list = sortChats(((data as ChatItem[] | null) ?? []).map(normalize));
  for (const c of list) knownKinds.set(c.id, c.kind);
  return list;
}

// ───────── Vitesse (demande de l'admin du 18.11) : la liste s'affiche tout de suite, puis se met à jour ─────────

/** Sorte de chaque discussion connue (liste) : /chats/<id> s'ouvre sans demander d'abord si c'est un message direct. */
export const knownKinds = new Map<string, ChatKind>();

const LIST_KEY = 'party-chats-list:';
const memoryList = new Map<string, ChatItem[]>();

/** Dernière liste de CE compte (mémoire, sinon stockage du navigateur) ; rien d'un autre compte. */
export function cachedChatList(me: string): ChatItem[] | null {
  const inMemory = memoryList.get(me);
  if (inMemory) return inMemory;
  try {
    const raw = globalThis.localStorage?.getItem(LIST_KEY + me);
    const list = raw ? (JSON.parse(raw) as ChatItem[]) : null;
    if (!Array.isArray(list)) return null;
    for (const c of list) knownKinds.set(c.id, c.kind);
    memoryList.set(me, list);
    return list;
  } catch {
    return null;
  }
}

/** « Lu » envoyé par une conversation, pas encore enregistré par la base. Revenue à la liste avant la réponse (réseau ou
 * base lents), la liste relue gardait « 1 non lu » (recette réelle du 19.11) : elle se relit une fois ces « lu » enregistrés. */
const readsInFlight = new Set<Promise<void>>();
export function trackRead(request: PromiseLike<unknown>): void {
  const done: Promise<void> = Promise.resolve(request).then(() => {}, () => {}).finally(() => { readsInFlight.delete(done); });
  readsInFlight.add(done);
}
/** Les « lu » en cours, enregistrés (ou null : aucun en cours). */
export function afterReads(): Promise<void> | null {
  return readsInFlight.size ? Promise.all([...readsInFlight]).then(() => {}) : null;
}

export function keepChatList(me: string, list: ChatItem[]): void {
  memoryList.set(me, list);
  try { globalThis.localStorage?.setItem(LIST_KEY + me, JSON.stringify(list)); } catch { /* stockage plein ou bloqué */ }
}

/** Déconnexion : plus rien des discussions sur cet appareil (ordinateur partagé). */
function forgetChatLists(): void {
  memoryList.clear();
  knownKinds.clear();
  try {
    const store = globalThis.localStorage;
    if (!store) return;
    for (const key of Object.keys(store)) if (key.startsWith(LIST_KEY)) store.removeItem(key);
  } catch { /* stockage bloqué */ }
}
supabase.auth.onAuthStateChange((event) => { if (event === 'SIGNED_OUT') forgetChatLists(); });

/** Base d'avant les Discussions v2 : my_chats (groupes + messages directs), sans épingles ni archives. */
async function fromOldList(): Promise<ChatItem[]> {
  const { data, error } = await supabase.rpc('my_chats');
  if (error) fail(error, 'Les discussions n’ont pas pu être chargées. Vérifie ta connexion.');
  return ((data as ChatSummary[] | null) ?? []).map((c) => normalize({
    kind: c.kind === 'direct' ? 'direct' : 'group', id: c.id, title: c.name, photo: null,
    emoji: c.emoji ?? null, color: c.color ?? null, user_id: c.user_id ?? null, event_start: null, event_past: false,
    last: c.last_at ? { id: '', at: c.last_at, from_me: false, author: null, type: 'text', text: c.last } : null,
    unread: c.unread, mention: false, marked_unread: false, pinned_at: null, archived: false, notify: c.notify,
    muted_until: null, request: null, seen_by_other: null, members: c.members, is_vp: c.system, blocked: !!c.blocked,
    avatar_path: c.avatar_url ?? null, photo_path: c.photo_path ?? null,
  }));
}

function normalize(c: Partial<ChatItem> & Pick<ChatItem, 'kind' | 'id'>): ChatItem {
  return {
    title: '', photo: null, emoji: null, color: null, user_id: null, event_start: null, event_past: false, last: null,
    unread: 0, mention: false, marked_unread: false, pinned_at: null, archived: false, notify: 'all', muted_until: null,
    request: null, seen_by_other: null, members: 0, is_vp: false, blocked: false, ...c,
  } as ChatItem;
}

/** Épinglées (la plus récemment épinglée d'abord), puis le dernier message le plus récent. */
export function sortChats(list: ChatItem[]): ChatItem[] {
  return [...list].sort((a, b) => {
    if (!!a.pinned_at !== !!b.pinned_at) return a.pinned_at ? -1 : 1;
    if (a.pinned_at && b.pinned_at) return b.pinned_at.localeCompare(a.pinned_at);
    return (b.last?.at ?? '').localeCompare(a.last?.at ?? '');
  });
}

/** En sourdine : coupée (réglage d'avant, ou muted_until « infinity »), ou jusqu'à une heure pas encore passée. */
export function isMuted(c: Pick<ChatItem, 'notify' | 'muted_until'>, now = Date.now()): boolean {
  if (c.notify === 'none') return true;
  if (!c.muted_until) return false;
  if (/^infinity$/i.test(c.muted_until)) return true;
  return Date.parse(c.muted_until) > now;
}

/** À lire : messages non lus ou « marquée non lue ». */
export const isUnread = (c: Pick<ChatItem, 'unread' | 'marked_unread'>) => c.unread > 0 || c.marked_unread;

/** Épingler, archiver, marquer non lue (null : inchangé). */
export async function setChatState(c: Pick<ChatItem, 'kind' | 'id'>, change: { pinned?: boolean; archived?: boolean; unread?: boolean }): Promise<void> {
  const { error } = await supabase.rpc('set_chat_state', {
    kind: c.kind, chat: c.id, pinned: change.pinned ?? null, archived: change.archived ?? null, unread: change.unread ?? null,
  });
  if (error) fail(error, 'Le changement n’a pas été enregistré. Vérifie ta connexion et réessaie.');
}

/** Ordre des épinglées choisi (avis e75a1d5af3ee, 20.11) : la première à gauche ; la base réécrit leurs pinned_at. */
export async function reorderPins(order: Pick<ChatItem, 'kind' | 'id'>[]): Promise<void> {
  const { error } = await supabase.rpc('reorder_chat_pins', { chats: order.map((c) => ({ kind: c.kind, id: c.id })) });
  if (error) fail(error, 'L’ordre n’a pas été enregistré. Vérifie ta connexion et réessaie.');
}

/** Nouvel ordre des épinglées après « Déplacer à gauche / à droite » ; null si elle ne peut pas aller plus loin. */
export function movedPins(pinned: ChatItem[], chat: ChatItem, step: -1 | 1): ChatItem[] | null {
  const i = pinned.findIndex((x) => chatKey(x) === chatKey(chat));
  const j = i + step;
  if (i < 0 || j < 0 || j >= pinned.length) return null;
  const next = [...pinned];
  [next[i], next[j]] = [next[j], next[i]];
  return next;
}

/** « Lu » : les messages sont lus (groupe, message direct) et la marque « non lue » part. */
export async function markRead(c: ChatItem): Promise<void> {
  if (c.unread > 0 && c.kind === 'direct') await supabase.rpc('mark_direct_read', { chat: c.id });
  if (c.unread > 0 && c.kind === 'group') await supabase.rpc('mark_group_read', { grp: c.id });
  await setChatState(c, { unread: false });
}

export type MuteSpan = '1h' | '8h' | '1w' | 'always' | 'off';
const SPAN_MS: Record<'1h' | '8h' | '1w', number> = { '1h': 3_600_000, '8h': 8 * 3_600_000, '1w': 7 * 86_400_000 };
export const MUTE_LABELS: Record<Exclude<MuteSpan, 'off'>, string> = { '1h': '1 heure', '8h': '8 heures', '1w': '1 semaine', always: 'Toujours' };

/** Sourdine d'une discussion (set_chat_state, muted_until) : 1 h, 8 h, 1 semaine, toujours (« infinity ») ; une date
 * passée la retire (et le réglage d'avant « aucune notification » repasse à « tout »). */
export async function setMute(c: ChatItem, span: MuteSpan): Promise<{ notify: ChatItem['notify']; muted_until: string | null }> {
  const until = span === 'always' ? 'infinity' : span === 'off' ? new Date(0).toISOString()
    : new Date(Date.now() + SPAN_MS[span]).toISOString();
  const { error } = await supabase.rpc('set_chat_state', { kind: c.kind, chat: c.id, muted_until: until });
  if (error) fail(error, 'La sourdine n’a pas été enregistrée. Réessaie.');
  if (span !== 'off') return { notify: c.notify, muted_until: until };
  if (c.notify === 'none') {
    if (c.kind === 'direct') await supabase.rpc('set_direct_chat_notify', { chat: c.id, level: 'all' });
    if (c.kind === 'group') await supabase.rpc('set_group_chat_notify', { grp: c.id, level: 'mentions' });
  }
  return { notify: c.notify === 'none' ? (c.kind === 'group' ? 'mentions' : 'all') : c.notify, muted_until: null };
}

/** Pastille de l'onglet Discussions : non lus hors archivées et hors sourdine, + 1 par demande reçue. */
export async function fetchChatBadge(): Promise<number | null> {
  const { data, error } = await supabase.rpc('chat_badge');
  return error ? null : Number(data) || 0;
}

/** Dit la pastille à la page Party (onglet Discussions) ; sans effet hors de son cadre. */
export function tellBadge(count: number): void {
  if (typeof window === 'undefined' || window.parent === window) return;
  window.parent.postMessage({ type: 'party-events:chats-badge', count }, window.location.origin);
}

// ───────── Demandes de message ─────────
export async function acceptRequest(chat: string): Promise<void> {
  const { error } = await supabase.rpc('accept_message_request', { chat });
  if (error) fail(error, 'La demande n’a pas pu être acceptée. Réessaie.');
}
export async function declineRequest(chat: string): Promise<void> {
  const { error } = await supabase.rpc('decline_message_request', { chat });
  if (error) fail(error, 'La demande n’a pas pu être supprimée. Réessaie.');
}

// ───────── Personnes et recherche ─────────
export type ChatPerson = {
  id: string; name: string; nickname: string | null; photo: string | null; sub: string | null;
  link: 'direct' | 'request'; met_count: number;
};
export type MessageHit = { kind: ChatKind; id: string; title: string; message_id: string; excerpt: string; at: string };

/** Personnes (prénom, nom, surnom ; jamais par numéro), seulement celles à qui je peux écrire. */
export async function searchPeople(q: string): Promise<ChatPerson[]> {
  if (q.trim().length < 2) return [];
  const { data, error } = await supabase.rpc('chat_people_search', { q: q.trim() });
  if (error) return [];
  return (data as ChatPerson[] | null) ?? [];
}

/** Mes événements dont le titre contient ce texte, même sans message (10 au plus) : pour y lancer la discussion. */
export async function searchEvents(q: string): Promise<ChatItem[]> {
  if (q.trim().length < 2) return [];
  const { data, error } = await supabase.rpc('chat_event_search', { q: q.trim() });
  if (error) return [];
  return (data as ChatItem[] | null) ?? [];
}

/** Messages de mes conversations qui contiennent ce texte (30 au plus). */
export async function searchMessages(q: string): Promise<MessageHit[]> {
  if (q.trim().length < 2) return [];
  const { data, error } = await supabase.rpc('chat_search', { q: q.trim() });
  if (error) return [];
  return (data as MessageHit[] | null) ?? [];
}

/** Personnes croisées récemment (soirées en commun) : l'état vide propose de leur écrire. */
export async function fetchCrossed(): Promise<ChatPerson[]> {
  const { data, error } = await supabase.rpc('chat_people_suggestions');
  if (error) return [];
  return ((data as { crossed?: ChatPerson[] } | null)?.crossed ?? []).slice(0, 3);
}

/** Sans accents ni casse (recherche dans les titres). */
export function fold(text: string): string {
  return text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
}

// ───────── Ouvrir ─────────
type NativeChats = {
  openEvent?: (id: string) => void; openGroup?: (id: string) => void;
  openDirect?: (userId: string) => void; newMessage?: (options: { event_id?: string }) => void;
};
function native(): NativeChats | null {
  return (globalThis as { PartyNative?: { chat?: NativeChats } }).PartyNative?.chat ?? null;
}

/** Ouvre une discussion : écran natif dans l'app iPhone quand le pont existe, sinon la page web. */
export function openChat(c: Pick<ChatItem, 'kind' | 'id' | 'user_id'>, push: (path: string) => void, message?: string): void {
  const n = native();
  if (c.kind === 'event') {
    if (typeof n?.openEvent === 'function') return n.openEvent(c.id);
    // from=chats : « ‹ » ramène à la liste (sinon, ouverte depuis la fiche, il y ramène : libellé du retour).
    return push(`/event/${c.id}/chat?from=chats${message ? `&message=${message}` : ''}`);
  }
  if (c.kind === 'group' && typeof n?.openGroup === 'function') return n.openGroup(c.id);
  if (c.kind === 'direct' && c.user_id && typeof n?.openDirect === 'function') return n.openDirect(c.user_id);
  push(`/chats/${c.id}${message ? `?message=${message}` : ''}`);
}

/** « Nouveau message » : écran natif dans l'app iPhone, sinon /chats/new. */
export function newMessage(push: (path: string) => void, group = false): void {
  const n = native();
  if (!group && typeof n?.newMessage === 'function') return n.newMessage({});
  push(group ? '/chats/new?group=1' : '/chats/new');
}

const REASONS: Record<string, string> = {
  blocked: 'Tu ne peux pas écrire à cette personne.',
  inactive: 'Ce compte n’est plus actif.',
  profile_required: 'Complète d’abord ton profil (prénom, nom, surnom).',
  terms_required: 'Accepte d’abord les conditions d’utilisation de Party : touche à nouveau le bouton pour les lire.',
  closed: 'Cette personne ne reçoit pas de demandes de message.',
  limit: 'Tu as envoyé beaucoup de demandes : réessaie plus tard.',
};

/** « Écrire » à une personne : ouvre (ou crée) la conversation à deux, puis l'affiche. */
export async function writeTo(userId: string, push: (path: string) => void): Promise<void> {
  const n = native();
  if (typeof n?.openDirect === 'function') return n.openDirect(userId);
  const { data, error } = await supabase.rpc('open_direct_chat', { target: userId });
  if (error) fail(error, 'La conversation n’a pas pu s’ouvrir. Réessaie.');
  const r = data as { chat: string | null; status: string; reason: string | null };
  if (!r?.chat && r?.reason === 'terms_required') throw new TermsNeeded();
  if (!r?.chat) throw new Error(REASONS[r?.reason ?? ''] ?? 'Tu ne peux pas écrire à cette personne pour l’instant.');
  push(`/chats/${r.chat}`);
}
