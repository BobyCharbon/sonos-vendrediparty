import { router } from 'expo-router';

import { newMessageId } from '@/lib/chats';
import { dbMessage } from '@/lib/moderation';
import { supabase } from '@/lib/supabase';

/**
 * Personnes des Discussions v2 (contrat §4-5, fonctions de la base) : suggestions et recherche de « Nouveau message »,
 * mini-profil, ouvrir un message direct, groupe à plusieurs. La base décide de tout (qui peut écrire à qui : `link`).
 */
export type Link = 'direct' | 'request' | 'none';

/** Une personne proposée (Nouveau message). `sub` : soirée croisée ou groupe ; vide : « Déjà vu N fois ». */
export type Person = { id: string; name: string; nickname?: string | null; photo: string | null; sub?: string | null; link: Link; met_count?: number };

export type Suggestions = { recent: Person[]; crossed: Person[]; groups: Person[] };

export type Answer = 'yes' | 'maybe' | 'no' | 'invited' | 'organizer' | null;
export type MiniEvent = { id: string; title: string; start: string | null; mine?: Answer; theirs?: Answer };
export type MiniGroup = { id: string; name: string; emoji: string; color: string; photo: string | null };
export type Mini = {
  id: string; name: string; nickname: string | null; photo: string | null; since: string | null; link: Link;
  blocked: boolean; blocked_me: boolean; chat: string | null; met_count: number; met: MiniEvent[];
  events: MiniEvent[]; groups: MiniGroup[]; events_count: number; groups_count: number;
};

export type OpenResult = { chat: string | null; status: 'active' | 'request' | 'none';
  reason: null | 'blocked' | 'inactive' | 'profile_required' | 'terms_required' | 'closed' | 'limit' };

export type EventCard = { id: string; title: string; start: string | null; place: string | null; cover: string | null; going: number; mine: Answer };

const list = <T,>(v: unknown): T[] => (Array.isArray(v) ? (v as T[]) : []);

/** Fiche courte d'un membre ; null si la base ne répond pas comme prévu (ancienne base : la fiche complète prend le relais). */
export async function fetchMini(target: string): Promise<Mini | null> {
  const { data, error } = await supabase.rpc('member_mini', { target });
  if (error) throw new Error(error.message);
  const m = data as Partial<Mini> | null;
  if (!m || typeof m !== 'object' || Array.isArray(m) || typeof m.id !== 'string') return null;
  return { ...m, name: m.name || m.nickname || 'Membre', nickname: m.nickname ?? null, photo: m.photo ?? null, since: m.since ?? null,
    link: m.link ?? 'none', blocked: !!m.blocked, blocked_me: !!m.blocked_me, chat: m.chat ?? null, met_count: m.met_count ?? 0,
    met: list<MiniEvent>(m.met), events: list<MiniEvent>(m.events), groups: list<MiniGroup>(m.groups),
    events_count: m.events_count ?? 0, groups_count: m.groups_count ?? 0 } as Mini;
}

export async function fetchSuggestions(): Promise<Suggestions> {
  const { data, error } = await supabase.rpc('chat_people_suggestions');
  if (error) throw new Error('Les suggestions n’ont pas pu être lues.');
  const d = (data ?? {}) as Partial<Suggestions>;
  return { recent: list(d.recent), crossed: list(d.crossed), groups: list(d.groups) };
}

export async function searchPeople(q: string): Promise<Person[]> {
  if (q.trim().length < 2) return [];
  const { data, error } = await supabase.rpc('chat_people_search', { q: q.trim() });
  if (error) throw new Error('La recherche n’a pas abouti. Réessaie.');
  return list<Person>(data);
}

export async function openDirect(target: string): Promise<OpenResult> {
  const { data, error } = await supabase.rpc('open_direct_chat', { target });
  if (error) {
    if ((error.message ?? '').startsWith('terms_required')) return { chat: null, status: 'none', reason: 'terms_required' };
    throw new Error(dbMessage(error.message, 'La discussion n’a pas pu s’ouvrir. Réessaie.'));
  }
  const r = (data ?? {}) as Partial<OpenResult>;
  return { chat: r.chat ?? null, status: r.status ?? 'none', reason: r.reason ?? null };
}

/** Phrase d'un refus d'open_direct_chat (jamais qui a bloqué qui). */
export function refusal(reason: OpenResult['reason']): string {
  switch (reason) {
    case 'profile_required': return 'Complète ton profil (prénom, nom, surnom) pour écrire.';
    case 'limit': return 'Tu as envoyé beaucoup de demandes de message. Réessaie demain.';
    default: return 'Tu ne peux pas écrire à cette personne.';
  }
}

/** Dans l'app iPhone : la conversation NATIVE (pont PartyNative.chat.openDirect) ; false ailleurs. */
export function nativeOpenDirect(userId: string): boolean {
  const chat = (globalThis as { PartyNative?: { chat?: { openDirect?: (id: string) => void } } }).PartyNative?.chat;
  if (typeof chat?.openDirect !== 'function') return false;
  chat.openDirect(userId);
  return true;
}

/** Discussion de groupe : écran natif dans l'app iPhone (pont existant openGroup), sinon la page web. */
export function goToGroupChat(id: string): void {
  const chat = (globalThis as { PartyNative?: { chat?: { openGroup?: (id: string) => void } } }).PartyNative?.chat;
  if (typeof chat?.openGroup === 'function') chat.openGroup(id);
  else router.replace(`/chats/${id}`);
}

export async function groupWith(members: string[]): Promise<string | null> {
  const { data, error } = await supabase.rpc('chat_group_with', { members });
  if (error) return null;
  return typeof data === 'string' ? data : null;
}

export async function createChatGroup(name: string, emoji: string, color: string, members: string[]):
  Promise<{ group: string; invited: number; refused: string[] }> {
  const { data, error } = await supabase.rpc('create_chat_group', { name, emoji, color, members });
  if (error) throw Object.assign(new Error(dbMessage(error.message, 'Le groupe n’a pas été créé. Réessaie.')), { raw: error.message });
  const r = (data ?? {}) as { group?: string; invited?: number; refused?: string[] };
  if (typeof r.group !== 'string') throw new Error('Le groupe n’a pas été créé. Réessaie.');
  return { group: r.group, invited: r.invited ?? 0, refused: list<string>(r.refused) };
}

export async function fetchEventCard(id: string): Promise<EventCard | null> {
  const { data } = await supabase.rpc('chat_event_cards', { ids: [id] });
  return list<EventCard>(data)[0] ?? null;
}

/** Joint la carte d'une soirée au premier message (colonne event_id, contrat §6). */
export async function sendEventCard(kind: 'direct' | 'group', chat: string, event: string, body: string): Promise<void> {
  const id = newMessageId();
  const row: Record<string, unknown> = kind === 'direct' ? { id, chat_id: chat, body, event_id: event } : { id, group_id: chat, body, event_id: event, mentions: [] };
  const { error } = await supabase.from(kind === 'direct' ? 'direct_messages' : 'group_messages').insert(row);
  if (error) throw new Error(dbMessage(error.message, 'La carte de la soirée n’a pas pu être envoyée.'));
}

/** « Déjà vu 3 fois », « Jamais rencontré ». */
export function metLabel(n: number | null | undefined): string {
  return !n ? 'Jamais rencontré' : n === 1 ? 'Déjà vu 1 fois' : `Déjà vu ${n} fois`;
}

/** Prénom pour les boutons (« Écrire à Léa ») : le surnom, sinon le premier mot du nom. */
export function shortName(p: { name: string; nickname?: string | null }): string {
  return (p.nickname || p.name || '').trim().split(/\s+/)[0] || 'cette personne';
}

/** « Léa », « Léa et Noé », « Léa, Noé et Tom », « Léa, Noé et 2 autres ». */
export function namesList(names: string[]): string {
  if (names.length <= 1) return names[0] ?? '';
  if (names.length <= 3) return `${names.slice(0, -1).join(', ')} et ${names[names.length - 1]}`;
  return `${names.slice(0, 2).join(', ')} et ${names.length - 2} autres`;
}
