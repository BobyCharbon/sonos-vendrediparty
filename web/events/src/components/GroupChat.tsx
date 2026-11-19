import { router, Stack } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore, type ReactNode } from 'react';
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, View, type TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatBubble } from './ChatBubble';
import { eventChatSubtitle, type EventChatCard } from './chat/EventChatTitle';
import { NotifyBell, NotifyMenu } from './chat/NotifyMenu';
import { ChatHeader, type HeaderLook } from './chats/conversation/ChatHeader';
import { cannotWrite, excerpt, fetchEventCards, openDirectChat, putDraft, takeDraft, useTyping,
  type ChatEventCard, type DirectState, type PrivateQuote } from './chats/conversation/data';
import { EventCardBubble } from './chats/conversation/EventCardBubble';
import { C, cf, editable, Icon, lavButton, web } from './chats/conversation/kit';
import { MessageMenu, type MenuAction } from './chats/conversation/MessageMenu';
import { enqueue, isNetworkError, outboxVersion, outgoing, retry, retryAll, settle, subscribeOutbox, type SendResult } from './chats/conversation/outbox';
import { RequestBanner } from './chats/conversation/RequestBanner';
import { TypingBubble } from './chats/conversation/TypingBubble';
import { DirectChatSettings } from './DirectChatSettings';
import { EventChatSettings, type EventPerson } from './EventChatSettings';
import { GroupChatSettings } from './GroupChatSettings';
import { GroupJoinNote } from './GuestGroup';
import { MentionSuggestions } from './MentionSuggestions';
import { ReportSheet } from './ReportSheet';
import { useTermsGate } from './TermsSheet';
import { usePersonText } from './PersonName';
import { Button, Input, Loading, s, Toast } from './ui';
import { useMe } from '@/lib/auth';
import { useContactNames } from '@/lib/contactNames';
import { chatTimeline, directAsGroupMessage, EVENT_TAGS, eventChatPrefs, eventTag, firstUnread, insertMention, isAnnouncement, markEventChatRead,
  mentionQuery, mentionsIn, mentionSuggestions, muteEventChat, muteUntil, NOTIFY_LEVELS, newMessageId, pickPhoto, setEventChatLevel, shrinkPhoto,
  signedPhotos, startVoice, uploadChatAudio, uploadChatPhoto, voiceClock, withoutAnnounceTag,
  type ChatSummary, type ChatWriteMode, type DirectMessageRow, type EveryoneBy, type GroupMessage, type MuteChoice, type NotifyLevel, type Reaction,
  type TimelineRow, type VoiceRecording } from '@/lib/chats';
import { useLivePing, useQuery, useRealtime, type RealtimeRow } from '@/lib/data';
import { discussionsOn } from '@/lib/features';
import { groupName } from '@/lib/groups';
import { useMiniProfile } from '@/lib/miniProfile';
import { openNativeDirect } from '@/lib/nativeChat';
import { saveRsvp } from '@/lib/rsvp';
import { must, supabase } from '@/lib/supabase';
import { roleRank, siteAdminRank } from '@/lib/roles';
import { enter, pressTransition } from '@/lib/motion';
import { dbMessage, type ReportTarget } from '@/lib/moderation';

const PAGE = 150;
/** Annonces et messages épinglés lus à part : le bandeau du haut les garde même au-delà des derniers messages. */
const HIGHLIGHTS = 20;
/** Distance au bas du fil sous laquelle on suit les nouveaux messages (sinon le bouton ↓ les compte). */
const NEAR_BOTTOM = 120;
/** Distance au haut du fil sous laquelle les messages précédents se chargent. */
const NEAR_TOP = 80;
/** Message cherché plus ancien que ceux affichés : on lit jusqu'à lui, dans cette limite. */
const JUMP_LIMIT = 1000;
/** Hauteur du champ : une ligne au repos, puis il suit le texte (bordure comprise) jusqu'à 7 lignes environ. */
const COMPOSER_MIN = 44;
const COMPOSER_MAX = 190;
const composerHeightFor = (content: number) => Math.min(COMPOSER_MAX, Math.max(COMPOSER_MIN, Math.ceil(content) + 3));
/** « Vu » relu tant que la conversation est ouverte (les confirmations de lecture ne passent pas par le temps réel). */
const SEEN_EVERY = 15_000;

export type ChatKind = 'group' | 'direct' | 'event';
type Profile = { id: string; display_name: string; avatar_url: string | null; member?: boolean; rsvp?: string | null; organizer?: boolean; invited?: boolean };
type ChatGroup = { id: string; name: string; created_by: string | null; everyone_tag?: EveryoneBy; member_group_members: { user_id: string }[];
  emoji?: string | null; color?: string | null; photo_path?: string | null; system_key?: string | null };
/** Discussion d'un événement : en-tête, notifications, qui écrit (migration 20261117190000). */
type EventExtras = {
  card: EventChatCard; level: NotifyLevel; mutedUntil: string | null; lastReadAt: string | null;
  writeMode: ChatWriteMode; mayWrite: boolean; canWrite: boolean; legacyMuted: boolean;
};

/** Tables de chaque sorte de discussion (messages, colonne de la discussion, réactions). */
const TABLES: Record<ChatKind, { messages: string; column: string; reactions: string }> = {
  direct: { messages: 'direct_messages', column: 'chat_id', reactions: 'direct_message_reactions' },
  event: { messages: 'messages', column: 'event_id', reactions: 'message_reactions' },
  group: { messages: 'group_messages', column: 'group_id', reactions: 'group_message_reactions' },
};

/** Message d'une personne bloquée : ni texte, ni photo, ni vocal (App Store 1.2). */
const masked = (m: GroupMessage): GroupMessage => ({ ...m, body: 'Message masqué (personne bloquée)', photo_path: null, audio_path: null, event_id: null, event_card: null });
const blockedOf = (rows: unknown) => new Set(((rows as { blocked_id: string }[] | null) ?? []).map((b) => b.blocked_id));
const cardsOf = (messages: GroupMessage[]) => fetchEventCards(messages.flatMap((m) => (m.event_id && !m.deleted_at ? [m.event_id] : [])));
// event_card : copie de la soirée gardée par la base quand l'événement est supprimé (event_id passe alors à null).

/** Réactions lues avec les messages (jointure PostgREST, même règle d'accès) : un aller-retour de moins. */
const REACTIONS_OF = {
  direct: 'direct_message_reactions(message_id, user_id, emoji)',
  group: 'group_message_reactions(message_id, user_id, emoji)',
} as const;
async function withReactions<T extends Record<string, unknown> & { id: string }>(rows: T[], embed: string): Promise<{ rows: T[]; reactions: Reaction[] }> {
  const table = embed.slice(0, embed.indexOf('('));
  const reactions: Reaction[] = [];
  let joined = false;
  const clean = rows.map((r) => {
    const { [table]: list, ...rest } = r;
    if (Array.isArray(list)) { joined = true; reactions.push(...(list as Reaction[])); }
    return rest as T;
  });
  // Réponse sans la jointure (ancienne base) : les réactions à part, comme avant.
  if (clean.length && !joined) {
    const r = await supabase.from(table).select('message_id, user_id, emoji').in('message_id', clean.map((m) => m.id));
    reactions.push(...(must(r) as Reaction[]));
  }
  return { rows: clean, reactions };
}

/** Message direct (conversation privée à deux, 4.11) : mêmes données qu'un groupe, lues dans les tables direct_*
 * (règles : les deux personnes seulement). Pas d'admin, d'organisateur, d'@tout ni d'@annonce.
 * Discussions v2 : demande de message (status, requested_by), « Vu » (direct_seen), lien pour « écrit… » (chat_link). */
async function loadDirect(id: string, me: string) {
  // Un seul aller-retour (vitesse, 18.11) : réactions jointes aux messages ; lien (« écrit… ») et cartes des soirées
  // demandés dès que la conversation et les messages répondent, en même temps que le reste.
  const pairP = supabase.from('direct_chats').select('*').eq('id', id).single().then((r) => r);
  const msgsP = supabase.from('direct_messages').select(`*, ${REACTIONS_OF.direct}`).eq('chat_id', id)
    .order('created_at', { ascending: false }).limit(PAGE).then((r) => r);
  const linkP = pairP.then((r) => {
    const row = r.data as { user_a: string; user_b: string } | null;
    if (!row) return null;
    return supabase.rpc('chat_link', { target: row.user_a === me ? row.user_b : row.user_a })
      .then((x) => (typeof x.data === 'string' ? x.data : null), () => null);
  });
  const cardsP = msgsP.then((r) => cardsOf(((r.data as DirectMessageRow[] | null) ?? []).map(directAsGroupMessage)));
  const [pair, msgs, people, settings, blocks, pins, seen, link, cards] = await Promise.all([
    pairP,
    msgsP,
    supabase.rpc('direct_chat_people', { chat: id }),
    supabase.from('direct_chat_settings').select('notify').eq('chat_id', id).maybeSingle(),
    supabase.from('direct_blocks').select('blocked_id'),
    supabase.from('direct_messages').select('*').eq('chat_id', id).eq('pinned', true).is('deleted_at', null)
      .order('created_at', { ascending: false }).limit(HIGHLIGHTS),
    supabase.rpc('direct_seen', { chat: id }),
    linkP,
    cardsP,
  ]);
  const row = must(pair) as { user_a: string; user_b: string; status?: string | null; requested_by?: string | null; declined_at?: string | null };
  const other = row.user_a === me ? row.user_b : row.user_a;
  const profiles = must(people) as Profile[];
  const { rows: directRows, reactions } = await withReactions(must(msgs) as (DirectMessageRow & Record<string, unknown>)[], REACTIONS_OF.direct);
  const messages = directRows.map(directAsGroupMessage).reverse();
  const notify = ((settings.data as { notify?: NotifyLevel } | null)?.notify ?? 'all') as NotifyLevel;
  const group: ChatGroup = { id, name: profiles.find((p) => p.id === other)?.display_name || 'Profil à compléter', created_by: null,
    everyone_tag: 'staff', member_group_members: [{ user_id: me }, { user_id: other }] };
  const directState: DirectState = { status: row.status === 'request' ? 'request' : 'active', requestedBy: row.requested_by ?? null,
    declined: Boolean(row.declined_at) };
  return {
    group, messages, reactions, other, cards, directState, link,
    seenAt: typeof seen.data === 'string' ? seen.data : null,
    eventStart: null as string | null,
    blocked: blockedOf(blocks.data).has(other), hidden: blockedOf(blocks.data),
    chat: { id, name: group.name, kind: 'direct', member: true, admin: false, notify } as ChatSummary,
    highlights: ((pins.data as DirectMessageRow[] | null) ?? []).map(directAsGroupMessage).filter((m) => m.pinned && !m.deleted_at),
    people: profiles,
    admins: new Set<string>(), organizers: new Set<string>(), phones: new Map<string, string>(),
    event: null as EventExtras | null,
  };
}

type EventMessageRow = Omit<GroupMessage, 'group_id' | 'deleted_by_admin' | 'mention_all'> & { event_id: string; mention_all?: boolean };
// La table messages n'a pas de soirée jointe : event_id y est l'événement de la discussion, pas une carte.
const eventAsGroupMessage = (m: EventMessageRow): GroupMessage =>
  ({ ...m, group_id: m.event_id, event_id: null, mention_all: Boolean(m.mention_all), deleted_by_admin: false, photo_path: m.photo_path ?? null });

type EventState = { title: string; write: boolean; staff: boolean; muted: boolean; level?: NotifyLevel; muted_until?: string | null;
  write_mode?: ChatWriteMode; description?: string | null; can_write?: boolean };
type EventInfo = { title?: string; starts_at?: string | null; ends_at?: string | null; date_mode?: string; location_name?: string | null;
  cover_url?: string | null; chat_write?: ChatWriteMode; chat_description?: string | null };

/** Discussion d'un événement (16.11.2026, migration 20261116180000 ; réglages : 20261117190000) : mêmes bulles, messages de
 * la table messages. Droits lus dans event_chat_state, personnes à citer dans event_chat_people, mes notifications dans
 * event_chat_prefs_get ; base d'avant ces migrations : la fiche de l'événement et les membres actifs. */
async function loadEvent(id: string, me: string) {
  const [state, msgs, people, blocks, pins, prefs, info] = await Promise.all([
    supabase.rpc('event_chat_state', { e: id }),
    supabase.from('messages').select('*').eq('event_id', id).order('created_at', { ascending: false }).order('id', { ascending: false }).limit(PAGE),
    supabase.rpc('event_chat_people', { e: id }),
    supabase.from('direct_blocks').select('blocked_id'),
    supabase.from('messages').select('*').eq('event_id', id).eq('pinned', true).is('deleted_at', null)
      .order('created_at', { ascending: false }).limit(HIGHLIGHTS),
    eventChatPrefs(id).catch(() => null),
    supabase.from('events').select('*').eq('id', id).single(),
  ]);
  let st = state.data as EventState | null;
  if (state.error || typeof st?.write !== 'boolean') {
    const ev = must(await supabase.from('events').select('title, created_by, event_organizers(user_id)').eq('id', id).single()) as
      { title: string; created_by: string; event_organizers: { user_id: string }[] };
    const muted = await supabase.from('event_mutes').select('event_id').eq('event_id', id).eq('user_id', me);
    st = { title: ev.title, write: true, staff: ev.created_by === me || ev.event_organizers.some((o) => o.user_id === me),
      muted: Boolean((muted.data as unknown[] | null)?.length) };
  }
  let profiles = (people.data as Profile[] | null) ?? null;
  // Base d'avant la migration (ou réponse vide) : les membres actifs, comme l'ancienne page.
  if (people.error || !Array.isArray(profiles) || !profiles.length) {
    profiles = must(await supabase.from('profiles').select('id, display_name, avatar_url').eq('status', 'active')) as Profile[];
  }
  const hidden = blockedOf(blocks.data);
  const messages = (must(msgs) as EventMessageRow[]).map(eventAsGroupMessage).reverse().map((m) => (hidden.has(m.user_id) ? masked(m) : m));
  const reactions = messages.length
    ? ((await supabase.from('message_reactions').select('message_id, user_id, emoji').in('message_id', messages.map((m) => m.id))).data as Reaction[] | null) ?? []
    : [];
  const ev = (info.error || !info.data || Array.isArray(info.data) ? {} : info.data) as EventInfo;
  const writeMode: ChatWriteMode = (st.write_mode ?? ev.chat_write) === 'staff' ? 'staff' : 'all';
  const canWrite = typeof st.can_write === 'boolean' ? st.can_write : st.write && (writeMode === 'all' || st.staff);
  const extras: EventExtras = {
    card: {
      title: ev.title || st.title, starts_at: ev.date_mode === 'poll' ? null : ev.starts_at ?? null, ends_at: ev.ends_at ?? null,
      place: ev.location_name ?? null, cover: ev.cover_url ?? null, description: (st.description ?? ev.chat_description) || null,
      going: profiles.filter((p) => p.rsvp === 'yes').length, maybe: profiles.filter((p) => p.rsvp === 'maybe').length,
    },
    level: prefs?.level ?? st.level ?? (st.muted ? 'none' : 'mentions'),
    mutedUntil: prefs ? prefs.muted_until : st.muted_until ?? null,
    lastReadAt: prefs?.last_read_at ?? null,
    writeMode, mayWrite: st.write, canWrite, legacyMuted: st.muted,
  };
  return {
    group: { id, name: extras.card.title, created_by: null, everyone_tag: 'staff', member_group_members: [] } as ChatGroup,
    messages, reactions, other: null as string | null, blocked: false, hidden,
    cards: new Map<string, ChatEventCard>(), directState: null as DirectState | null, link: null as string | null, seenAt: null as string | null,
    eventStart: extras.card.starts_at,
    chat: { id, name: extras.card.title, kind: 'event', member: canWrite, admin: st.staff, notify: extras.level } as unknown as ChatSummary,
    highlights: ((pins.data as EventMessageRow[] | null) ?? []).map(eventAsGroupMessage).filter((m) => m.pinned && !m.deleted_at && !hidden.has(m.user_id)),
    people: profiles.map((p) => ({ ...p, member: true })),
    admins: new Set<string>(),
    organizers: new Set(profiles.filter((p) => p.organizer).map((p) => p.id)),
    phones: new Map<string, string>(),
    event: extras as EventExtras | null,
  };
}

async function loadGroup(id: string) {
  // Un seul aller-retour (vitesse, 18.11) : réactions jointes aux messages, cartes des soirées dès que les messages répondent.
  const msgsP = supabase.from('group_messages').select(`*, ${REACTIONS_OF.group}`).eq('group_id', id)
    .order('created_at', { ascending: false }).limit(PAGE).then((r) => r);
  const cardsP = msgsP.then((r) => cardsOf((r.data as GroupMessage[] | null) ?? []));
  const [group, msgs, people, admins, chats, phones, pins, organizers, blocks, cards] = await Promise.all([
    // « * » : everyone_tag (qui peut écrire @tout), emoji, couleur, photo quand la base les connaît.
    supabase.from('member_groups').select('*, member_group_members(user_id)').eq('id', id).single(),
    msgsP,
    supabase.rpc('group_chat_people', { grp: id }),  // un Guest ne lit pas le profil d'un admin dans profiles
    supabase.from('group_admins').select('user_id').eq('group_id', id),
    supabase.rpc('my_chats'),
    supabase.rpc('group_chat_phones', { grp: id }),
    supabase.from('group_messages').select('*').eq('group_id', id).eq('pinned', true).is('deleted_at', null)
      .order('created_at', { ascending: false }).limit(HIGHLIGHTS),
    supabase.from('group_organizers').select('user_id').eq('group_id', id),
    supabase.from('direct_blocks').select('blocked_id'),
    cardsP,
  ]);
  // Personnes que j'ai bloquées (App Store 1.2) : leurs messages, photos et vocaux sont masqués aussitôt ; leurs messages
  // épinglés ne s'affichent pas.
  const hidden = blockedOf(blocks.data);
  const { rows: groupRows, reactions } = await withReactions(must(msgs) as (GroupMessage & Record<string, unknown>)[], REACTIONS_OF.group);
  const messages = groupRows.reverse().map((m) => (hidden.has(m.user_id) ? masked(m) : m));
  const chat = ((chats.data as ChatSummary[] | null) ?? []).find((c) => c.id === id) ?? null;
  return {
    group: must(group) as ChatGroup,
    messages, reactions, chat, other: null as string | null, blocked: false, hidden, cards,
    directState: null as DirectState | null, link: null as string | null, seenAt: null as string | null, eventStart: null as string | null,
    highlights: ((pins.data as GroupMessage[] | null) ?? []).filter((m) => m.pinned && !m.deleted_at && !hidden.has(m.user_id)),
    people: must(people) as Profile[],
    admins: new Set((must(admins) as { user_id: string }[]).map((a) => a.user_id)),
    organizers: new Set(((organizers.data as { user_id: string }[] | null) ?? []).map((o) => o.user_id)),
    phones: new Map(((phones.data as { id: string; phone: string }[] | null) ?? []).map((p) => [p.id, p.phone])),
    event: null as EventExtras | null,
  };
}

type ChatData = Awaited<ReturnType<typeof loadGroup>> | Awaited<ReturnType<typeof loadDirect>> | Awaited<ReturnType<typeof loadEvent>>;

// Vitesse (demande de l'admin du 18.11) : dernière version de chaque conversation gardée en mémoire (par compte) ; elle
// s'affiche tout de suite à l'ouverture, puis la lecture fraîche la remplace. La liste en précharge quelques-unes.
const chatCache = new Map<string, ChatData>();
const preloading = new Map<string, Promise<ChatData | null>>();
const cacheKey = (kind: ChatKind, id: string, me: string) => `${me}:${kind}:${id}`;
const loadChat = (kind: ChatKind, id: string, me: string): Promise<ChatData> =>
  (kind === 'event' ? loadEvent(id, me) : kind === 'direct' ? loadDirect(id, me) : loadGroup(id));

/** Précharge une conversation (lecture seule : rien n'est marqué lu) pour qu'elle s'ouvre sans attendre ; déjà gardée
 * avec ce dernier message (lastId, d'après la liste) : rien à relire. */
export function preloadChat(kind: ChatKind, id: string, me: string, lastId?: string | null): void {
  const key = cacheKey(kind, id, me);
  const kept = chatCache.get(key);
  if (preloading.has(key) || (kept && (lastId === undefined || kept.messages[kept.messages.length - 1]?.id === lastId))) return;
  const job = loadChat(kind, id, me).then((d) => { chatCache.set(key, d); return d; }, () => null)
    .finally(() => { setTimeout(() => preloading.delete(key), 2000); });
  preloading.set(key, job);
}


/** Premier non-lu d'un groupe d'après son compteur (my_chats) : le N-ième dernier message des autres. */
function unreadByCount(messages: GroupMessage[], unread: number, me: string): string | null {
  if (unread <= 0) return null;
  let left = unread;
  for (let i = messages.length - 1; i >= 0; i -= 1) {
    if (messages[i].user_id === me) continue;
    left -= 1;
    if (!left) return messages[i].id;
  }
  return null;
}

/** Discussion façon WhatsApp, graphisme « Néon club » (Discussions v2, maquette 1-neon/4) : en-tête avec photo et nom
 * (toucher : mini-profil), séparateurs de jours, messages d'une même personne regroupés, heure dans la bulle, @citations
 * en couleur, citation qui remonte au message, menu à l'appui long / clic droit (réactions, répondre, répondre en privé,
 * copier, modifier 15 min, épingler, supprimer, signaler), carte de soirée, « Vu », « écrit… », « Nouveaux messages »,
 * bouton ↓ avec les nouveaux messages, messages précédents chargés en remontant, bandeau des annonces et épinglés,
 * annonces en carte, demande de message.
 * Groupe : @tout (selon le groupe) et @annonce (admins et organisateurs). Événement (17.11) : en-tête (date, titre,
 * participants), cloche des notifications (Tout / Mentions seulement / Rien, sourdine), infos de la discussion,
 * @toutlemonde, @present et annonces (📣) pour l'organisation ; « Seule l'organisation peut écrire » selon son réglage.
 * La base décide de toute façon.
 * attachEvent : soirée à joindre au prochain message (« Envoyer à un ami », /chats/<id>?event=<id>). */
export function GroupChat({ id, direct = false, event = false, attachEvent = null }: { id: string; direct?: boolean; event?: boolean; attachEvent?: string | null }) {
  const kind: ChatKind = event ? 'event' : direct ? 'direct' : 'group';
  const me = useMe();
  const mini = useMiniProfile();
  const [text, setText] = useState('');
  // Place du curseur (suggestions de l'@ en cours de frappe) et champ, pour y revenir après un choix.
  const [cursor, setCursor] = useState(0);
  const input = useRef<TextInput>(null);
  const [composerHeight, setComposerHeight] = useState(COMPOSER_MIN);
  // Fonction stable : react-native-web relit la taille du contenu à chaque nouvelle fonction (boucle de rendus sinon).
  const onComposerSize = useCallback((e: { nativeEvent: { contentSize: { height: number } } }) => {
    const next = composerHeightFor(e.nativeEvent.contentSize.height);
    setComposerHeight((h) => (Math.abs(h - next) < 2 ? h : next));
  }, []);
  const [bannerMenu, setBannerMenu] = useState(false);
  const [pinIndex, setPinIndex] = useState(0);
  const [replyTo, setReplyTo] = useState<GroupMessage | null>(null);
  const [editing, setEditing] = useState<GroupMessage | null>(null);
  // Menu d'un message : ses actions sont choisies à l'ouverture (appui long, clic droit).
  const [menu, setMenu] = useState<{ m: GroupMessage; actions: MenuAction[] } | null>(null);
  const menuFor = menu?.m ?? null;
  // Repris une fois : citation de « Répondre en privé », soirée de « Envoyer à un ami ».
  const [draft] = useState(() => (direct ? takeDraft(id) : {}));
  const [privateQuote, setPrivateQuote] = useState<PrivateQuote | null>(draft.quote ?? null);
  const [attached, setAttached] = useState<string | null>(event ? null : attachEvent ?? draft.event ?? null);
  const [extraCards, setExtraCards] = useState<Map<string, ChatEventCard>>(new Map());
  const [announcing, setAnnouncing] = useState(false);
  const [sending, setSending] = useState(false);
  // Envoi en cours (texte ou vocal) : un double toucher, même pendant l'attente des CGU, n'envoie qu'un message.
  const sendingRef = useRef(false);
  // Messages envoyés pas encore revenus de la base : affichés tout de suite (« Envoi… »), file d'envoi commune
  // (outbox.ts) : gardés même si l'écran se ferme, nouvel essai si le réseau manque.
  const box = `${kind}:${id}`;
  const outboxAt = useSyncExternalStore(subscribeOutbox, outboxVersion, outboxVersion);
  // eslint-disable-next-line react-hooks/exhaustive-deps -- outboxAt : nouvelle version de la file, à relire
  const pending = useMemo(() => outgoing(box), [box, outboxAt]);
  const [voice, setVoice] = useState<{ rec: VoiceRecording; started: number } | null>(null);
  const [voiceNow, setVoiceNow] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  // Choix de notifications fait ici (affiché aussitôt, avant la relecture).
  const [prefs, setPrefs] = useState<{ level: NotifyLevel; mutedUntil: string | null } | null>(null);
  // Modération commune : « Signaler » un message, CGU acceptées avant le premier message.
  const [reportTarget, setReportTarget] = useState<ReportTarget | null>(null);
  const terms = useTermsGate();
  const [photos, setPhotos] = useState<Map<string, string>>(new Map());
  const list = useRef<FlatList<TimelineRow<GroupMessage>>>(null);
  // Bas du fil : on y reste quand un message arrive ; plus haut, le bouton ↓ compte les nouveaux.
  const nearBottom = useRef(true);
  const [atBottom, setAtBottom] = useState(true);
  const [unseen, setUnseen] = useState(0);
  const [flashId, setFlashId] = useState<string | null>(null);
  const [unreadElsewhere, setUnreadElsewhere] = useState(0);
  const [polledSeen, setPolledSeen] = useState<string | null>(null);
  // Messages précédents (chargés en remontant ou pour montrer un message ancien) ; la position reste la même.
  const [older, setOlder] = useState<{ messages: GroupMessage[]; reactions: Reaction[] }>({ messages: [], reactions: [] });
  const [hasMore, setHasMore] = useState<boolean | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const loadingOlderRef = useRef(false);
  const scrollY = useRef(0);
  const contentH = useRef(0);
  const anchor = useRef<{ y: number; h: number } | null>(null);
  // Message à montrer dès qu'il est chargé (recherche, épinglé, média plus ancien que le fil).
  const jump = useRef<string | null>(null);
  const jumpTries = useRef(0);

  const key = cacheKey(kind, id, me.id);
  const [initial] = useState(() => chatCache.get(key) ?? null);
  const { data, loading, error: loadError, reload, setData } = useQuery(async () => {
    // Préchargement en cours (liste) : on le reprend au lieu de tout relire une deuxième fois.
    const ready = await preloading.get(key);
    preloading.delete(key);
    const fresh = ready ?? await loadChat(kind, id, me.id);
    chatCache.set(key, fresh);
    return fresh;
  }, [key], initial as ChatData | null);

  // Nouveau message reçu (temps réel) : affiché aussitôt, sans attendre la relecture (qui suit pour les réactions, les
  // noms…). Personne bloquée : masqué comme à la lecture.
  const onRow = useCallback((row: RealtimeRow) => {
    if (row.eventType !== 'INSERT' || !['direct_messages', 'group_messages', 'messages'].includes(row.table)) return;
    const raw = row.new as unknown;
    const m = row.table === 'direct_messages' ? directAsGroupMessage(raw as DirectMessageRow)
      : row.table === 'messages' ? eventAsGroupMessage(raw as EventMessageRow) : raw as GroupMessage;
    if (!m?.id || !m.created_at) return;
    setData((d) => {
      if (!d || d.messages.some((x) => x.id === m.id)) return d;
      const shownMessage = d.hidden.has(m.user_id) ? masked(m) : m;
      return { ...d, messages: [...d.messages, { ...shownMessage, mentions: shownMessage.mentions ?? [] }] } as ChatData;
    });
  }, [setData]);

  useRealtime(`${kind}-chat-${id}`, kind === 'direct' ? [
    { table: 'direct_messages', filter: `chat_id=eq.${id}` },
    // Pas direct_chats (hors de la publication : tout le canal resterait muet) ; une demande acceptée se voit à la
    // première réponse, qui relit la conversation.
    { table: 'direct_message_reactions' },
  ] : kind === 'group' ? [
    { table: 'group_messages', filter: `group_id=eq.${id}` },
    { table: 'group_message_reactions' },
  ] : [{ table: 'messages', filter: `event_id=eq.${id}` }], reload, onRow);
  // Événement : réactions, messages retirés, épingles, réglages : signal de la base (migration 20261116140000).
  useLivePing(event ? id : null, reload);

  const ev = data?.event ?? null;
  const level: NotifyLevel = prefs?.level ?? ev?.level ?? 'mentions';
  const mutedUntil = prefs ? prefs.mutedUntil : ev?.mutedUntil ?? null;
  const member = Boolean(data?.chat?.member);
  const isAdmin = Boolean(data?.chat?.admin);
  // Admins et organisateurs du groupe (organisation d'un événement) : annonces et leur retrait ; @tout selon le groupe.
  const isStaff = event ? isAdmin : isAdmin || (member && Boolean(data?.organizers.has(me.id)));
  const everyone = data?.group.everyone_tag ?? 'all';
  const canEveryone = kind === 'group' && (everyone === 'all' || isStaff);
  const dstate = data?.directState ?? null;
  const requestIn = direct && dstate?.status === 'request' && dstate.requestedBy !== me.id;
  const requestOut = direct && dstate?.status === 'request' && dstate.requestedBy === me.id;

  useEffect(() => {
    // Demande reçue : jamais « lu » tant qu'elle n'est pas acceptée (pas de confirmation de lecture dans une demande).
    if (!data?.messages.length || requestIn) return;
    // Discussion d'une soirée : lue même sans droit d'écrire (son état « lu » vit dans chat_list_state, Discussions v2).
    // .then : une requête Supabase ne part qu'une fois attendue (« void supabase.rpc(…) » seul n'envoyait rien).
    const done = () => {};
    if (event) void supabase.rpc('mark_event_chat_read', { e: id }).then(done, done);
    else if (member) void (direct ? supabase.rpc('mark_direct_read', { chat: id }) : supabase.rpc('mark_group_read', { grp: id })).then(done, done);
  }, [member, id, direct, event, data?.messages, requestIn]);

  // Non lus des autres discussions, à côté de ‹ (une fois, à l'ouverture).
  useEffect(() => {
    let live = true;
    void supabase.rpc('chat_badge').then(({ data: n }) => { if (live && typeof n === 'number') setUnreadElsewhere(n); }, () => {});
    return () => { live = false; };
  }, [id]);

  // « Vu » (message direct, conversation acceptée) : relu régulièrement tant que la conversation est ouverte.
  const readable = direct && dstate?.status === 'active' && !data?.blocked;
  useEffect(() => {
    if (!readable) return undefined;
    const timer = setInterval(() => {
      void supabase.rpc('direct_seen', { chat: id }).then(({ data: at }) => setPolledSeen(typeof at === 'string' ? at : null), () => {});
    }, SEEN_EVERY);
    return () => clearInterval(timer);
  }, [readable, id]);

  // Carte de la soirée à joindre (« Envoyer à un ami ») : lue pour l'aperçu dans la barre de saisie.
  useEffect(() => {
    if (!attached || extraCards.has(attached)) return;
    let live = true;
    void fetchEventCards([attached]).then((cards) => { if (live && cards.size) setExtraCards((prev) => new Map([...prev, ...cards])); });
    return () => { live = false; };
  }, [attached, extraCards]);
  const cards = useMemo(() => new Map([...(data?.cards ?? []), ...extraCards]), [data?.cards, extraCards]);

  useEffect(() => {
    if (!voice) return;
    const timer = setInterval(() => setVoiceNow(Date.now()), 200);
    return () => clearInterval(timer);
  }, [voice]);
  // Messages déjà là à l'ouverture : ils s'affichent tels quels ; seuls les suivants (envoyés ou reçus) montent.
  // Premier non-lu à l'ouverture : « Nouveaux messages » juste avant, et le fil s'y arrête.
  const [initialIds, setInitialIds] = useState<Set<string> | null>(null);
  const [unreadFrom, setUnreadFrom] = useState<string | null>(null);
  if (data && !initialIds) {
    setInitialIds(new Set(data.messages.map((m) => m.id)));
    setUnreadFrom(data.event ? firstUnread(data.messages, data.event.lastReadAt, me.id)
      : kind === 'group' ? unreadByCount(data.messages, data.chat?.unread ?? 0, me.id) : null);
    setHasMore(data.messages.length >= PAGE);
  }
  const all = useMemo(() => {
    const latest = data?.messages ?? [];
    const known = new Set(latest.map((m) => m.id));
    return [...older.messages.filter((m) => !known.has(m.id)), ...latest];
  }, [data?.messages, older.messages]);
  const shown = useMemo(() => {
    const known = new Set(all.map((m) => m.id));
    return [...all, ...pending.filter((m) => !known.has(m.id))];
  }, [all, pending]);
  const rows = useMemo(() => chatTimeline(shown, undefined, unreadFrom), [shown, unreadFrom]);
  const paths = useMemo(() => all.flatMap((m) => (m.deleted_at ? []
    : [m.photo_path, m.audio_path].filter((p): p is string => Boolean(p)))), [all]);
  // Revenus de la base : ils quittent la file d'envoi ; ceux restés « pas envoyés » repartent (le réseau répond).
  useEffect(() => {
    if (!data) return;
    settle(box, new Set(data.messages.map((m) => m.id)));
    retryAll(box);
  }, [data, box]);
  useEffect(() => {
    let alive = true;
    void signedPhotos(paths.filter((p) => !photos.has(p))).then((more) => {
      if (alive && more.size) setPhotos((prev) => new Map([...prev, ...more]));
    }).catch(() => {});
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seuls les nouveaux chemins comptent
  }, [paths]);

  // Nouveau message : on descend s'il est à moi ou si l'on était en bas ; sinon le bouton ↓ le compte.
  // À l'ouverture : le bas du fil, ou « Nouveaux messages » s'il y en a.
  const lastId = shown[shown.length - 1]?.id;
  const lastMine = shown[shown.length - 1]?.user_id === me.id;
  const seenLast = useRef<string | undefined>(undefined);
  const rowsRef = useRef(rows);
  useEffect(() => { rowsRef.current = rows; }, [rows]);
  useEffect(() => {
    if (!lastId || seenLast.current === lastId) return;
    const first = seenLast.current === undefined;
    seenLast.current = lastId;
    if (first || lastMine || nearBottom.current) {
      requestAnimationFrame(() => list.current?.scrollToEnd({ animated: !first }));
      if (first && unreadFrom) {
        setTimeout(() => {
          const index = rowsRef.current.findIndex((r) => r.key === 'unread');
          if (index < 0) return;
          try { list.current?.scrollToIndex({ index, viewPosition: 0.05, animated: false }); } catch { /* le bas du fil suffit */ }
        }, 180);
      }
    } else setUnseen((n) => n + 1);
  }, [lastId, lastMine, unreadFrom]);

  // Événement : lu jusqu'au dernier message tant que le bas du fil est à l'écran (compteurs, pastilles).
  const readUpTo = useRef<string | null>(null);
  useEffect(() => {
    if (!event || !data || !atBottom || !lastId || lastId === readUpTo.current) return;
    if (shown[shown.length - 1]?.pending) return;
    readUpTo.current = lastId;
    void markEventChatRead(id).catch(() => {});
  }, [event, data, atBottom, lastId, shown, id]);

  const people = useMemo(() => new Map((data?.people ?? []).map((p) => [p.id, p])), [data?.people]);
  const contacts = useContactNames();
  const personText = usePersonText();
  // Membres d'après group_chat_people : un Guest ne voit pas les autres appartenances dans member_group_members.
  const inside = useMemo(() => {
    const fromPeople = (data?.people ?? []).filter((p) => p.member).map((p) => p.id);
    return fromPeople.length ? fromPeople : (data?.group.member_group_members ?? []).map((m) => m.user_id);
  }, [data?.people, data?.group]);
  const names = useMemo(() => (data?.people ?? []).map((p) => p.display_name).filter(Boolean), [data?.people]);
  const byId = useMemo(() => new Map(all.map((m) => [m.id, m])), [all]);
  const reactionsOf = useMemo(() => {
    const out = new Map<string, Reaction[]>();
    const fresh = new Set((data?.messages ?? []).map((m) => m.id));
    for (const r of [...older.reactions.filter((x) => !fresh.has(x.message_id)), ...(data?.reactions ?? [])]) {
      out.set(r.message_id, [...(out.get(r.message_id) ?? []), r]);
    }
    return out;
  }, [data?.reactions, data?.messages, older.reactions]);
  // Bandeau du haut, façon WhatsApp : annonces puis épinglés, les plus récents d'abord ; un toucher montre le message
  // et passe au suivant.
  const pins = useMemo(() => {
    const highlights = data?.highlights ?? [];
    return [...highlights.filter((m) => m.announcement), ...highlights.filter((m) => !m.announcement)];
  }, [data?.highlights]);
  const banner = pins.length ? pins[pinIndex % pins.length] : null;
  const canUnpinBanner = Boolean(banner) && (isAdmin || direct || (isStaff && Boolean(banner?.announcement)));
  const nameOf = (uid: string) => people.get(uid)?.display_name ?? '?';
  // Affichage (pas les @) : app iPhone, « Nom du contact · pseudo » ; ailleurs le pseudo.
  const shownName = (uid: string) => personText(uid, nameOf(uid));
  const hidden = useMemo(() => data?.hidden ?? new Set<string>(), [data?.hidden]);

  // Saisie : fermée pour un bloqué, une demande reçue (accepter d'abord) et une demande envoyée (un seul message).
  const mySent = shown.some((m) => m.user_id === me.id);
  const canCompose = member && !data?.blocked && !requestIn && !(requestOut && mySent);
  const requestDraft = Boolean(requestOut && !mySent);

  // « écrit… » : jamais dans une demande, ni envers une personne bloquée (dans un groupe : pas de signal si j'y ai bloqué
  // quelqu'un ; ceux qui m'ont bloqué jettent le mien de leur côté).
  const typingTopic = !data ? null : direct ? (readable ? `typing:direct:${id}` : null) : `typing:${kind}:${id}`;
  const maySendTyping = canCompose && !requestDraft && (direct ? data?.link === 'direct' : !inside.some((u) => hidden.has(u)));
  const typing = useTyping(typingTopic, { id: me.id, name: me.display_name }, hidden);

  // Suggestions de l'@ : membres (moi exclu) filtrés par les lettres tapées, puis les citations spéciales permises.
  const mentionTyping = mentionQuery(text, cursor);
  const suggestions = useMemo(() => (mentionTyping === null || direct ? [] : mentionSuggestions(mentionTyping,
    // Moi et les personnes que j'ai bloquées exceptés.
    inside.filter((u) => u !== me.id && !hidden.has(u)).map((u) => ({ id: u, display_name: nameOf(u), avatar_url: people.get(u)?.avatar_url ?? null })),
    { everyone: canEveryone, announce: isStaff, tags: event ? (isStaff ? EVENT_TAGS : []) : undefined }, contacts)),
  // eslint-disable-next-line react-hooks/exhaustive-deps -- nameOf lit people
  [mentionTyping, inside, people, me.id, canEveryone, isStaff, contacts, direct, event, hidden]);
  // Prévenu avant l'envoi : un simple membre n'annonce pas (message normal), @tout peut être réservé par le groupe.
  const tagNote = direct ? null : event
    ? (!isStaff && eventTag(text) ? '@toutlemonde, @present et les annonces sont réservés à l’organisation de l’événement : ton message partira sans prévenir personne.' : null)
    : isAnnouncement(text) && !isStaff
      ? 'Seuls les admins et organisateurs du groupe font des annonces : ton message partira comme un message normal.'
      : mentionsIn(text, []).all && !canEveryone
        ? 'Dans ce groupe, seuls les admins et organisateurs peuvent écrire @tout : personne ne sera prévenu.'
        : null;

  function pickMention(label: string) {
    const next = insertMention(text, cursor, label);
    setText(next.text);
    setCursor(next.cursor);
    input.current?.focus();
  }

  /** Messages d'avant le plus ancien affiché (une page ; ou jusqu'à `until` pour montrer un message ancien). */
  async function loadOlder(until: string | null = null) {
    const oldest = all[0];
    if (!oldest || loadingOlderRef.current) return;
    loadingOlderRef.current = true;
    setLoadingOlder(true);
    const t = TABLES[kind];
    try {
      let query = supabase.from(t.messages).select('*').eq(t.column, id).lt('created_at', oldest.created_at)
        .order('created_at', { ascending: false }).limit(until ? JUMP_LIMIT : PAGE);
      if (until) query = query.gte('created_at', until);
      const rowsRead = ((await query).data as Record<string, unknown>[] | null) ?? [];
      const known = new Set(all.map((m) => m.id));
      const hidden = data?.hidden ?? new Set<string>();
      const more = rowsRead.map((r) => (kind === 'event' ? eventAsGroupMessage(r as unknown as EventMessageRow)
        : kind === 'direct' ? directAsGroupMessage(r as unknown as DirectMessageRow) : r as unknown as GroupMessage))
        .filter((m) => !known.has(m.id)).reverse().map((m) => (hidden.has(m.user_id) ? masked(m) : m));
      if (!until) setHasMore(rowsRead.length >= PAGE && more.length > 0);
      if (!more.length) return;
      const reactions = ((await supabase.from(t.reactions).select('message_id, user_id, emoji').in('message_id', more.map((m) => m.id))).data as Reaction[] | null) ?? [];
      if (!until) anchor.current = { y: scrollY.current, h: contentH.current };
      setOlder((prev) => ({ messages: [...more, ...prev.messages], reactions: [...reactions, ...prev.reactions] }));
    } finally {
      loadingOlderRef.current = false;
      setLoadingOlder(false);
    }
  }

  /** Montre un message (citation, bandeau, recherche, épinglé, média) au milieu de l'écran puis le fait clignoter ;
   * plus ancien que ceux affichés : on lit jusqu'à lui d'abord (`at`). */
  const showMessage = useCallback((messageId: string, at?: string) => {
    const index = rows.findIndex((r) => r.key === messageId);
    if (index < 0) {
      if (!at) return setError('Ce message est plus ancien que ceux affichés.');
      jump.current = messageId;
      void loadOlder(at);
      return;
    }
    jumpTries.current = 0;
    list.current?.scrollToIndex({ index, viewPosition: 0.4, animated: true });
    setFlashId(messageId);
    setTimeout(() => setFlashId((f) => (f === messageId ? null : f)), 1200);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- loadOlder lit l'état courant
  }, [rows]);
  useEffect(() => {
    const target = jump.current;
    if (!target || !rows.some((r) => r.key === target)) return;
    jump.current = null;
    setTimeout(() => showMessage(target), 60);
  }, [rows, showMessage]);

  /** Texte, photo ou vocal : la bulle apparaît tout de suite, le champ se vide, on peut écrire le suivant aussitôt.
   * Réseau absent : la bulle reste (« Pas envoyé · Toucher pour réessayer ») ; refus de la base : le texte revient. */
  async function send(photoPath: string | null = null, audio: { blob: Blob; seconds: number; ext: 'm4a' | 'webm' } | null = null) {
    const body = audio ? '' : text.trim();
    if (editing && !photoPath && !audio) return void saveEdit(editing, body);
    if ((!body && !photoPath && !audio && !attached) || sendingRef.current) return;
    sendingRef.current = true;
    try {
      if (!terms.accepted && !(await terms.ensure())) return;
      typing.stop();
      deliver(body, photoPath, audio);
    } finally {
      sendingRef.current = false;
    }
  }

  function deliver(body: string, photoPath: string | null, audio: { blob: Blob; seconds: number; ext: 'm4a' | 'webm' } | null) {
    const quoted = replyTo;
    const announce = announcing;
    const eventCard = event ? null : attached;
    const privately = direct ? privateQuote : null;
    const messageId = newMessageId();
    const announced = isStaff && (announce || isAnnouncement(body));
    const draftMessage: GroupMessage = { id: messageId, group_id: id, user_id: me.id, body, photo_path: photoPath, reply_to: quoted?.id ?? null,
      mentions: [], mention_all: false, pinned: announced, announcement: announced, created_at: new Date().toISOString(), edited_at: null, deleted_at: null,
      deleted_by_admin: false, audio_path: null, audio_seconds: audio ? Math.round(audio.seconds * 10) / 10 : null, pending: true,
      event_id: eventCard, quote: privately };
    if (!audio) { setText(''); setCursor(0); }
    setReplyTo(null);
    setAnnouncing(false);
    setAttached(null);
    setPrivateQuote(null);
    setError(null);
    const tagged = mentionsIn(body, inside.filter((u) => u !== me.id).map((u) => ({ id: u, display_name: nameOf(u) })));
    // Colonnes de Discussions v2 envoyées seulement quand elles servent (une base d'avant les refuserait).
    const extra = { ...(eventCard ? { event_id: eventCard } : {}), ...(privately ? { quote: privately } : {}) };
    let audioPath: string | null = null;  // gardé d'un essai à l'autre : le vocal n'est déposé qu'une fois
    const run = async (): Promise<SendResult> => {
      try {
        if (audio && !audioPath) audioPath = await uploadChatAudio(id, audio);
      } catch (e) {
        return { ok: false, network: isNetworkError(e), message: e instanceof Error ? e.message : 'Le vocal n’a pas pu être envoyé.' };
      }
      const { error } = kind === 'direct'
        ? await supabase.from('direct_messages').insert({
          id: messageId, chat_id: id, body, photo_path: photoPath, reply_to: quoted?.id ?? null, audio_path: audioPath, audio_seconds: draftMessage.audio_seconds, ...extra,
        })
        : kind === 'event'
          // La base garde seulement les citations et annonces permises (guard_message_change).
          ? await supabase.from('messages').insert({
            id: messageId, event_id: id, user_id: me.id, body, photo_path: photoPath, reply_to: quoted?.id ?? null, mentions: tagged.mentions,
            audio_path: audioPath, audio_seconds: draftMessage.audio_seconds, ...(announce ? { announcement: true } : {}),
          })
          : await supabase.from('group_messages').insert({
            id: messageId, group_id: id, body, photo_path: photoPath, reply_to: quoted?.id ?? null, mentions: tagged.mentions,
            mention_all: tagged.all && canEveryone, audio_path: audioPath, audio_seconds: draftMessage.audio_seconds, ...extra,
          });
      // Même identifiant déjà enregistré : l'essai d'avant était passé (réponse perdue en route).
      if (!error || error.code === '23505') return { ok: true };
      if (isNetworkError(error)) return { ok: false, network: true, message: error.message };
      // Filtre de la base : la phrase dit pourquoi (propos haineux, contenu sexuel…) ; sinon un message général.
      return { ok: false, network: false, message: /request_pending/.test(error.message)
        ? 'Ta demande est en attente : un seul message texte, sans photo, vocal, lien ni numéro, jusqu’à ce qu’elle soit acceptée.'
        : dbMessage(error.message, 'Le message n’a pas pu être envoyé. Réessaie.') };
    };
    enqueue({
      chat: box, message: draftMessage, run,
      onSent: () => { void reload(); },
      onRefused: (message) => {
        // Le champ a pu être réécrit entre-temps : le texte refusé revient seulement s'il est vide.
        if (!audio) setText((now) => (now.trim() ? now : body));
        setReplyTo((now) => now ?? quoted);
        setAnnouncing(announce);
        setAttached((now) => now ?? eventCard);
        setPrivateQuote((now) => now ?? privately);
        setError(message);
      },
    });
  }

  /** Modifier (15 minutes au plus, la base garde la règle) : le texte revient dans la barre, « modifié » ensuite. */
  async function saveEdit(m: GroupMessage, body: string) {
    if (!body || sendingRef.current) return;
    if (body === m.body.trim()) { setEditing(null); setText(''); return; }
    sendingRef.current = true;
    setError(null);
    setEditing(null);
    setText('');
    setCursor(0);
    try {
      const { error } = kind === 'event'
        ? await supabase.from('messages').update({ body, edited_at: new Date().toISOString() }).eq('id', m.id)
        : await supabase.rpc(direct ? 'edit_direct_message' : 'edit_group_message', { msg: m.id, new_body: body });
      if (error) {
        setEditing(m);
        setText(body);
        setError(/edit_window/.test(error.message)
          ? 'Un message se modifie pendant 15 minutes après son envoi.'
          : dbMessage(error.message, 'Le message n’a pas pu être modifié. Réessaie.'));
      }
    } finally {
      sendingRef.current = false;
    }
    reload();
  }

  function startEdit(m: GroupMessage) {
    setReplyTo(null);
    setAnnouncing(false);
    setEditing(m);
    setText(m.body);
    setCursor(m.body.length);
    requestAnimationFrame(() => input.current?.focus());
  }

  /** « Répondre en privé » (groupe, soirée) : LA conversation directe avec l'auteur, le message cité dans la barre. */
  async function replyPrivately(m: GroupMessage) {
    const who = shownName(m.user_id);
    setError(null);
    if (openNativeDirect(m.user_id)) return;
    const res = await openDirectChat(m.user_id);
    if (!res.chat || res.status === 'none') return setError(cannotWrite(who, res.reason));
    putDraft(res.chat, { quote: { from: event ? 'event' : 'group', title: data ? (event ? data.group.name : groupName(data.group)) : '',
      author: who, excerpt: excerpt(withoutAnnounceTag(m.body) || (m.audio_seconds != null ? 'Message vocal' : 'Photo')) } });
    router.push(`/chats/${res.chat}`);
  }

  async function startRecording() {
    setError(null);
    try {
      setVoice({ rec: await startVoice(), started: Date.now() });
      setVoiceNow(Date.now());
    } catch (e) {
      setError(e instanceof Error && e.name !== 'NotAllowedError' ? e.message : 'Autorise le micro pour envoyer un message vocal.');
    }
  }

  async function stopRecording(sendIt: boolean) {
    const current = voice;
    setVoice(null);
    const done = await current?.rec.stop(sendIt);
    if (done) await send(null, done);
  }

  async function sendPhoto(camera = false) {
    setError(null);
    try {
      const file = await pickPhoto(camera);
      if (!file) return;
      setSending(true);
      const path = await uploadChatPhoto(id, await shrinkPhoto(file));
      setSending(false);
      await send(path);
    } catch (e) {
      setSending(false);
      setError(e instanceof Error ? e.message : 'La photo n’a pas pu être envoyée.');
    }
  }

  async function react(m: GroupMessage, emoji: string) {
    const mineAlready = (reactionsOf.get(m.id) ?? []).some((r) => r.user_id === me.id && r.emoji === emoji);
    const table = TABLES[kind].reactions;
    const { error } = mineAlready
      ? await supabase.from(table).delete().eq('message_id', m.id).eq('user_id', me.id).eq('emoji', emoji)
      : await supabase.from(table).insert(kind === 'event' ? { message_id: m.id, user_id: me.id, emoji } : { message_id: m.id, emoji });
    if (error) setError('La réaction n’a pas pu être enregistrée.');
    reload();
  }

  async function pin(messageId: string, on: boolean) {
    const { error } = kind === 'event'
      ? await supabase.from('messages').update({ pinned: on }).eq('id', messageId)
      : await supabase.rpc(direct ? 'pin_direct_message' : 'pin_group_message', { msg: messageId, pin: on });
    if (error) setError(error.message.replace(/^\w+: /, ''));
    reload();
  }

  async function remove(messageId: string) {
    const { error } = kind === 'event'
      ? await supabase.from('messages').update({ deleted_at: new Date().toISOString() }).eq('id', messageId)
      : await supabase.rpc(direct ? 'delete_direct_message' : 'delete_group_message', { msg: messageId });
    if (error) setError(error.message.replace(/^\w+: /, ''));
    reload();
  }

  const report = (m: GroupMessage) => setReportTarget({ kind: event ? 'event_message' : direct ? 'direct_message' : 'group_message', id: m.id,
    label: `le message de ${shownName(m.user_id)}` });

  /** Actions du menu d'un message (appui long, clic droit) : ce que je peux faire, rien de plus. */
  function actionsFor(m: GroupMessage): MenuAction[] {
    const mine = m.user_id === me.id;
    const announced = Boolean(m.announcement && m.pinned);
    const out: MenuAction[] = [];
    if (canCompose && !requestDraft) out.push({ key: 'reply', label: 'Répondre', icon: 'reply', run: () => { setEditing(null); setReplyTo(m); input.current?.focus(); } });
    if (!direct && !mine && !hidden.has(m.user_id) && discussionsOn) {
      out.push({ key: 'private', label: 'Répondre en privé', icon: 'chat', run: () => void replyPrivately(m) });
    }
    if (m.body && !m.deleted_at) {
      out.push({ key: 'copy', label: 'Copier', icon: 'copy', run: () => { void navigator.clipboard?.writeText(withoutAnnounceTag(m.body)).catch(() => {}); } });
    }
    if (mine && canCompose && editable(m)) out.push({ key: 'edit', label: 'Modifier', icon: 'pencil', run: () => startEdit(m) });
    if (announced) {
      if (isStaff) out.push({ key: 'pin', label: 'Retirer l’annonce', icon: 'pin', run: () => void pin(m.id, false) });
    } else if (direct ? !requestIn && !requestOut : isAdmin) {
      out.push({ key: 'pin', label: m.pinned ? 'Désépingler' : 'Épingler', icon: 'pin', run: () => void pin(m.id, !m.pinned) });
    }
    if (mine || isAdmin) out.push({ key: 'delete', label: 'Supprimer', icon: 'trash', danger: true, run: () => void remove(m.id) });
    if (!mine) out.push({ key: 'report', label: 'Signaler', icon: 'flag', danger: true, run: () => report(m) });
    return out;
  }

  /** Cloche ou réglages : niveau de notifications de cette discussion (Mentions seulement par défaut). */
  async function changeLevel(next: NotifyLevel) {
    const before = { level, mutedUntil };
    setPrefs({ level: next, mutedUntil });
    try {
      await setEventChatLevel(id, next);
      // L'ancien « couper les notifications » de la fiche (event_mutes) ne doit plus tout bloquer après un nouveau choix.
      if (next !== 'none' && ev?.legacyMuted) await supabase.from('event_mutes').delete().eq('event_id', id).eq('user_id', me.id);
      setNotice(`Notifications : ${NOTIFY_LEVELS.find((l) => l.key === next)?.label ?? next}`);
    } catch (e) {
      setPrefs(before);
      setError(e instanceof Error ? e.message : 'Le réglage n’a pas pu être enregistré.');
    }
  }

  async function changeMute(choice: MuteChoice | null) {
    const before = { level, mutedUntil };
    const until = choice ? muteUntil(choice) : null;
    setPrefs({ level, mutedUntil: until });
    try {
      await muteEventChat(id, until);
      setNotice(choice ? 'Discussion en sourdine' : 'Notifications réactivées');
    } catch (e) {
      setPrefs(before);
      setError(e instanceof Error ? e.message : 'La sourdine n’a pas pu être enregistrée.');
    }
  }

  if (loading && !data) return <Loading />;
  // Message direct : « Nom du contact · pseudo » (app iPhone), sinon le pseudo de l'autre personne.
  const title = direct && data?.other ? shownName(data.other) : data ? (event ? data.group.name : groupName(data.group)) : 'Discussion';
  const typers = typing.typers;
  const subtitle = typers.length
    ? (direct ? 'écrit…' : typers.length === 1 ? `${typers[0]} écrit…` : `${typers.length} personnes écrivent…`)
    : direct ? (dstate?.status === 'request' ? 'Demande de message' : null)
      : event ? (ev ? eventChatSubtitle(ev.card) : `Discussion · ${data?.people.length ?? 0} personnes`) : `${inside.length} membres`;
  const look: HeaderLook = direct
    ? { kind: 'direct', userId: data?.other ?? id, photo: data?.other ? people.get(data.other)?.avatar_url ?? null : null }
    : event ? { kind: 'event', start: data?.eventStart ?? null }
      : { kind: 'group', emoji: data?.group.emoji || '🎉', color: data?.group.color ?? null, photo_path: data?.group.photo_path ?? null, system_key: data?.group.system_key ?? null };
  const header = (
    <>
      <Stack.Screen options={{ title, headerShown: false }} />
      <ChatHeader title={title} subtitle={subtitle} typing={typers.length > 0} look={look} unread={unreadElsewhere}
        onBack={() => (router.canGoBack() ? router.back() : router.replace(event ? `/event/${id}` : '/chats'))}
        whoLabel={direct ? `${title}. Ouvrir son profil` : event ? `${title}, ${subtitle ?? ''}, infos de la discussion` : `Groupe ${title} : voir les membres`}
        onWho={() => (direct && data?.other ? mini.open(data.other) : setShowInfo((v) => !v))}
        // Discussion d'un événement : la cloche des notifications (Tout / Mentions seulement / Rien, sourdine), à droite.
        extra={event && ev && !showInfo ? <NotifyBell level={level} mutedUntil={mutedUntil} onPress={() => setMenuOpen(true)} /> : null}
        infoLabel={direct ? 'Infos de la conversation' : event ? 'Infos de la discussion' : 'Infos du groupe'}
        infoOpen={showInfo} onInfo={() => setShowInfo((v) => !v)} />
    </>
  );

  if (showInfo && data && direct && data.other) {
    return (
      <SafeAreaView style={[s.screen, { backgroundColor: C.bg }]} edges={['top', 'bottom']}>
        {header}
        <DirectChatSettings chatId={id} other={{ id: data.other, name: shownName(data.other), photo: people.get(data.other)?.avatar_url ?? null }}
          notify={data.chat?.notify ?? 'all'} blocked={data.blocked} onChanged={reload} onProfile={() => mini.open(data.other!)} />
      </SafeAreaView>
    );
  }

  if (showInfo && data && !event) {
    return (
      <SafeAreaView style={[s.screen, { backgroundColor: C.bg }]} edges={['top', 'bottom']}>
        {header}
        <GroupChatSettings groupId={id} notify={data.chat?.notify ?? 'mentions'} member={member}
          canNameAdmins={data.group.created_by === me.id || roleRank(me.role) >= siteAdminRank()}
          isAdmin={isAdmin} everyone={everyone}
          members={inside.map((u) => ({ id: u, name: shownName(u), photo: people.get(u)?.avatar_url ?? null,
            admin: data.admins.has(u), organizer: data.organizers.has(u), creator: u === data.group.created_by, phone: data.phones.get(u) ?? null }))}
          onChanged={reload} />
      </SafeAreaView>
    );
  }

  const seenAt = [data?.seenAt ?? null, polledSeen].filter((t): t is string => Boolean(t)).sort().pop() ?? null;
  const lastMineShown = [...shown].reverse().find((m) => m.user_id === me.id && !m.pending);
  const seenId = readable && seenAt && lastMineShown && Date.parse(lastMineShown.created_at) <= Date.parse(seenAt) ? lastMineShown.id : null;
  const other = data?.other ?? null;
  const otherName = other ? shownName(other) : title;
  const requestMessage = requestIn ? shown.find((m) => m.user_id === other) ?? null : null;
  const attachedCard = attached ? cards.get(attached) ?? null : null;

  // Soirée visible : sa carte à jour ; soirée supprimée (ou plus visible) : la copie gardée dans le message, sans boutons.
  const cardFor = (m: GroupMessage) => {
    const live = m.event_id ? cards.get(m.event_id) ?? null : null;
    if (live) {
      return <EventCardBubble card={live} onOpen={() => router.push(`/event/${live.id}`)}
        onYes={async () => { await saveRsvp(live.id, me.id, undefined, { status: 'yes' }); setExtraCards(new Map()); reload(); }} />;
    }
    const kept = m.event_card && typeof m.event_card === 'object' && m.event_card.title ? m.event_card as ChatEventCard : null;
    return <EventCardBubble card={kept} gone />;
  };
  const quoteText = (m: GroupMessage) => (m.deleted_at ? 'Message supprimé'
    : withoutAnnounceTag(m.body) || (m.audio_seconds != null ? '🎤 Message vocal' : '📷 Photo'));
  const staffOnly = Boolean(event && ev && ev.mayWrite && !ev.canWrite && ev.writeMode === 'staff');

  return (
    <SafeAreaView style={[s.screen, { backgroundColor: C.bg }]} edges={['top', 'bottom']}>
      {header}
      <View style={{ flex: 1 }}>
        <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
          {/* Entré par sa réponse à un événement (17.11) : d'où il vient et « Quitter », à la première ouverture. */}
          {direct || event ? null : <GroupJoinNote groupId={id} me={me.id} onLeft={reload} />}
          {requestIn && other ? (
            <RequestBanner side="incoming" name={otherName} userId={other} photo={people.get(other)?.avatar_url ?? null}
              onProfile={() => mini.open(other)}
              onAccept={async () => {
                const { error } = await supabase.rpc('accept_message_request', { chat: id });
                if (error) throw new Error(dbMessage(error.message, 'La demande n’a pas pu être acceptée. Réessaie.'));
                reload();
              }}
              onDelete={async () => {
                const { error } = await supabase.rpc('decline_message_request', { chat: id });
                if (error) throw new Error(dbMessage(error.message, 'La demande n’a pas pu être supprimée. Réessaie.'));
                router.replace('/chats');
              }}
              onBlock={async () => {
                const { error } = await supabase.rpc('set_direct_block', { target: other, blocked: true });
                if (error) throw new Error('Le blocage n’a pas pu être enregistré.');
                router.replace('/chats');
              }}
              onReport={() => (requestMessage ? report(requestMessage) : setReportTarget({ kind: 'profile', id: other, label: otherName }))} />
          ) : requestOut ? <RequestBanner side="outgoing" name={otherName} sent={mySent} /> : null}
          {banner ? (
            <View style={[{ zIndex: 2 }, enter('drop')]}>
              <Pressable accessibilityRole="button"
                accessibilityLabel={`${banner.announcement ? 'Annonce' : 'Épinglé'}${pins.length > 1 ? ` ${(pinIndex % pins.length) + 1} sur ${pins.length}` : ''} : ${shownName(banner.user_id)}, ${withoutAnnounceTag(banner.body) || 'Photo'}`}
                accessibilityHint={canUnpinBanner ? 'Touche pour voir le message ; appui long pour le retirer' : 'Touche pour voir le message'}
                onPress={() => { showMessage(banner.id, banner.created_at); if (pins.length > 1) setPinIndex((i) => i + 1); }}
                onLongPress={() => canUnpinBanner && setBannerMenu((v) => !v)}
                style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 10, borderBottomWidth: 1,
                  borderBottomColor: banner.announcement ? 'rgba(255,79,154,0.5)' : C.line },
                  web({ backgroundColor: banner.announcement ? '#22102C' : C.s1,
                    backgroundImage: banner.announcement ? 'linear-gradient(90deg, rgba(255,79,154,0.18), transparent 70%)' : 'none' }),
                  pressTransition, pressed && { opacity: 0.85 }]}>
                {pins.length > 1 ? (
                  <View style={{ gap: 2, height: 32, justifyContent: 'center' }}>
                    {pins.slice(0, 5).map((p, i) => (
                      <View key={p.id} style={{ width: 3, flex: 1, borderRadius: 2, backgroundColor: i === Math.min(pinIndex % pins.length, 4) ? C.pink : C.line2 }} />
                    ))}
                  </View>
                ) : null}
                <View style={{ width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: banner.announcement ? 'rgba(255,79,154,0.18)' : 'rgba(185,167,255,0.14)' }}>
                  {banner.announcement ? <Text style={{ fontSize: 16 }}>📣</Text> : <Icon name="pin" size={16} color={C.lav} stroke={2.2} />}
                </View>
                <View style={{ flex: 1, gap: 1 }}>
                  <Text style={[cf.label, { color: banner.announcement ? C.pinkInk : C.lav }]}>
                    {banner.announcement ? 'Annonce' : 'Message épinglé'}
                    {pins.length > 1 ? <Text style={{ color: C.t3 }}>{`  ${(pinIndex % pins.length) + 1}/${pins.length}`}</Text> : null}
                  </Text>
                  <Text numberOfLines={banner.announcement ? 2 : 1} style={[banner.announcement ? cf.semibold : cf.text, { color: C.t1, fontSize: 14, lineHeight: 19 }]}>
                    {shownName(banner.user_id)} : {withoutAnnounceTag(banner.body) || '📷 Photo'}
                  </Text>
                </View>
              </Pressable>
              {bannerMenu && canUnpinBanner ? (
                <View style={[s.row, { marginHorizontal: 12, marginTop: 6 }, enter('drop')]}>
                  <Button small variant="secondary" label={banner.announcement ? 'Retirer l’annonce' : 'Désépingler'}
                    onPress={() => { setBannerMenu(false); void pin(banner.id, false); }} />
                  <Button small variant="ghost" label="Annuler" onPress={() => setBannerMenu(false)} />
                </View>
              ) : null}
            </View>
          ) : null}
          <View style={{ flex: 1 }}>
            <FlatList
              ref={list}
              data={rows}
              keyExtractor={(r) => r.key}
              // Tout le fil d'un coup (150 messages au plus) : la fin est là dès la première image, sans rendu par paquets
              // qui faisait attendre le dernier message une demi-seconde à l'ouverture.
              initialNumToRender={Math.max(20, rows.length)}
              maxToRenderPerBatch={60}
              windowSize={31}
              contentContainerStyle={{ paddingHorizontal: 12, paddingTop: 10, paddingBottom: 16, flexGrow: 1, justifyContent: rows.length ? 'flex-end' : 'center' }}
              onScroll={(e) => {
                const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
                scrollY.current = contentOffset.y;
                contentH.current = contentSize.height;
                const near = contentSize.height - contentOffset.y - layoutMeasurement.height < NEAR_BOTTOM;
                nearBottom.current = near;
                if (near !== atBottom) setAtBottom(near);
                if (near && unseen) setUnseen(0);
                if (contentOffset.y < NEAR_TOP && hasMore && !loadingOlderRef.current && seenLast.current) void loadOlder();
              }}
              onContentSizeChange={(_w, h) => {
                const a = anchor.current;
                contentH.current = h;
                if (a) {
                  // Messages précédents ajoutés au-dessus : la lecture reste sur le même message.
                  anchor.current = null;
                  list.current?.scrollToOffset({ offset: a.y + (h - a.h), animated: false });
                  return;
                }
                // Fil collé en bas (ouverture, nouveau message) tant qu'on n'est pas remonté lire plus haut.
                if (nearBottom.current) list.current?.scrollToEnd({ animated: false });
              }}
              scrollEventThrottle={100}
              onScrollToIndexFailed={(info) => {
                // Message pas encore dessiné (fil virtualisé) : on s'en approche, puis on réessaie.
                if (jumpTries.current++ > 3) return;
                list.current?.scrollToOffset({ offset: info.averageItemLength * info.index, animated: false });
                setTimeout(() => list.current?.scrollToIndex({ index: info.index, viewPosition: 0.4, animated: true }), 120);
              }}
              ListHeaderComponent={loadingOlder ? (
                <View accessibilityLabel="Chargement des messages précédents" style={{ alignItems: 'center', paddingVertical: 10 }}>
                  <ActivityIndicator color={C.lav} />
                </View>
              ) : hasMore === false && all.length >= PAGE ? (
                <Text style={[cf.text, { color: C.t3, fontSize: 12, textAlign: 'center', paddingVertical: 8 }]}>Début de la discussion</Text>
              ) : null}
              renderItem={({ item: row }) => {
                if ('day' in row) {
                  return (
                    <View accessibilityRole="header" style={{ alignItems: 'center', marginTop: 14, marginBottom: 6 }}>
                      <Text style={[cf.label, { fontSize: 12, color: C.t2, height: 26, lineHeight: 24, paddingHorizontal: 12, borderRadius: 13,
                        overflow: 'hidden', backgroundColor: 'rgba(26,20,51,0.8)', borderWidth: 1, borderColor: C.line }]}>{row.day}</Text>
                    </View>
                  );
                }
                if ('unread' in row) {
                  // « Nouveaux messages » : posée avant le premier non-lu, à l'ouverture.
                  return (
                    <View accessibilityRole="header" style={[{ alignItems: 'center', marginVertical: 10, marginHorizontal: -12, paddingVertical: 6,
                      backgroundColor: C.glass, borderTopWidth: 1, borderBottomWidth: 1, borderColor: C.line }, enter('fade')]}>
                      <Text style={[cf.bold, { fontSize: 12, color: C.lav }]}>{row.unread > 1 ? `${row.unread} nouveaux messages` : '1 nouveau message'}</Text>
                    </View>
                  );
                }
                const m = row.message;
                const quoted = m.reply_to ? byId.get(m.reply_to) : null;
                const mine = m.user_id === me.id;
                const canMenu = !m.deleted_at && !m.pending && !m.failed && (member || !mine);
                return (
                  <View style={{ marginTop: row.first ? 10 : 3 }}>
                    <ChatBubble message={m} mine={mine} me={me.id}
                      author={{ name: shownName(m.user_id), photo: people.get(m.user_id)?.avatar_url ?? null }}
                      quoted={quoted ? { name: quoted.user_id === me.id ? 'Toi' : shownName(quoted.user_id), author: quoted.user_id, text: quoteText(quoted) } : null}
                      photoUrl={m.photo_path ? photos.get(m.photo_path) ?? null : null}
                      audioUrl={m.audio_path ? photos.get(m.audio_path) ?? null : null}
                      reactions={reactionsOf.get(m.id) ?? []} canWrite={canCompose && !requestDraft}
                      first={row.first} last={row.last} showAuthor={!direct} names={names} flash={flashId === m.id}
                      onQuote={quoted ? () => showMessage(quoted.id) : undefined}
                      onReply={() => { setEditing(null); setReplyTo(m); input.current?.focus(); }} onReact={(e) => void react(m, e)}
                      onMenu={canMenu ? () => { const actions = actionsFor(m); if (actions.length) setMenu({ m, actions }); } : undefined}
                      onAuthor={!mine && !direct ? () => mini.open(m.user_id) : undefined}
                      seen={m.id === seenId}
                      card={m.event_id || m.event_card ? cardFor(m) : undefined}
                      privateQuote={direct ? m.quote ?? null : null}
                      fresh={!!initialIds && !initialIds.has(m.id)}
                      onRetry={m.failed ? () => retry(m.id) : undefined} />
                  </View>
                );
              }}
              ListFooterComponent={<TypingBubble names={typers} showName={!direct} />}
              ListEmptyComponent={requestOut ? null : (
                <View style={[{ alignItems: 'center', gap: 12, paddingHorizontal: 24 }, enter('fade')]}>
                  <View style={[{ width: 72, height: 72, borderRadius: 24, alignItems: 'center', justifyContent: 'center' },
                    web({ backgroundImage: `linear-gradient(135deg, ${C.lavA}, ${C.lavB})`, boxShadow: `0 0 28px -6px ${C.lavB}` })]}>
                    <Icon name="chat" size={34} color={C.onLav} stroke={2} />
                  </View>
                  <Text style={[cf.display, { color: C.t1, fontSize: 22, textAlign: 'center' }]}>
                    {loadError ? 'La discussion n’a pas pu être chargée.' : 'Ta discussion commence ici'}
                  </Text>
                  {loadError ? null : (
                    <Text style={[cf.text, { color: C.t2, fontSize: 15, lineHeight: 21, textAlign: 'center' }]}>
                      {event ? 'Aucun message pour l’instant. Lance la discussion avec les invités !' : 'Aucun message pour l’instant. Lance la discussion !'}
                    </Text>
                  )}
                  {/* Groupe tout neuf (créé depuis Discussions) : y ajouter du monde, dans Réglages › Groupes. */}
                  {!loadError && kind === 'group' && member && inside.length <= 1 && data?.group.created_by === me.id ? (
                    <Button small label="Ajouter des membres" onPress={() => router.push(`/group/${id}/invite`)} />
                  ) : null}
                </View>
              )}
            />
            {!atBottom && rows.length ? (
              <Pressable accessibilityRole="button" accessibilityLabel={unseen ? `${unseen} nouveaux messages, descendre` : 'Descendre au dernier message'}
                onPress={() => { setUnseen(0); list.current?.scrollToEnd({ animated: true }); }}
                style={({ pressed }) => [{ position: 'absolute', right: 14, bottom: 12, width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center',
                  backgroundColor: C.s1b, borderWidth: 1, borderColor: C.line2 }, web({ boxShadow: '0 18px 40px -18px rgba(0,0,0,0.7)' }),
                  enter('pop'), pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
                <Icon name="down" size={20} color={C.t1} />
                {unseen ? (
                  <View style={{ position: 'absolute', top: -6, right: -6, minWidth: 20, height: 20, paddingHorizontal: 5, borderRadius: 10, backgroundColor: C.pink, alignItems: 'center', justifyContent: 'center' }}>
                    <Text style={[cf.bold, { fontSize: 11, color: C.onPink }]}>{Math.min(unseen, 99)}</Text>
                  </View>
                ) : null}
              </Pressable>
            ) : null}
          </View>
          {error ?? loadError ? (
            <Text accessibilityRole="alert" style={[cf.semibold, { color: C.danger, fontSize: 14, paddingHorizontal: 16, paddingVertical: 6 }]}>{error ?? loadError}</Text>
          ) : null}
          {data?.blocked ? (
            // Message direct : j'ai bloqué cette personne ; l'historique reste, l'écriture revient en la débloquant.
            <Note text={`Tu as bloqué ${title}. Débloque-le dans Infos pour lui écrire.`} />
          ) : requestIn ? (
            <Note text={`Accepte la demande pour répondre à ${otherName}.`} />
          ) : requestOut && mySent ? (
            <Note icon text="Demande envoyée · tu pourras écrire à nouveau quand elle sera acceptée." />
          ) : canCompose ? (
            <View style={{ paddingTop: 4 }}>
              {announcing ? <Text style={[cf.semibold, { color: C.pinkInk, fontSize: 12, paddingHorizontal: 14, paddingTop: 4 }]}>📣 Annonce : épinglée en haut et envoyée à tous les invités</Text> : null}
              {requestDraft ? (
                <Text style={[cf.text, { color: C.t2, fontSize: 13, paddingHorizontal: 14, paddingTop: 4 }]}>Ce sera une demande de message : un seul message texte, sans photo, vocal, lien ni numéro.</Text>
              ) : null}
              {editing ? (
                <ComposerChip label="Modifier le message" text={editing.body} icon="pencil" onClose={() => { setEditing(null); setText(''); }} closeLabel="Annuler la modification" />
              ) : null}
              {replyTo ? (
                <ComposerChip label={`Réponse à ${replyTo.user_id === me.id ? 'toi' : shownName(replyTo.user_id)}`}
                  text={replyTo.body || (replyTo.audio_seconds != null ? '🎤 Message vocal' : '📷 Photo')} icon="reply"
                  onClose={() => setReplyTo(null)} closeLabel="Ne plus répondre à ce message" />
              ) : null}
              {privateQuote ? (
                <ComposerChip label={`Réponse privée · ${privateQuote.author} dans ${privateQuote.title}`} text={privateQuote.excerpt} icon="lock"
                  onClose={() => setPrivateQuote(null)} closeLabel="Retirer la citation" />
              ) : null}
              {attached ? (
                <View style={[{ marginHorizontal: 12, marginTop: 6 }, enter('drop')]}>
                  <EventCardBubble compact card={attachedCard ?? { id: attached, title: 'Soirée', start: null, place: null, cover: null, going: 0, mine: null }}
                    onOpen={() => router.push(`/event/${attached}`)} onRemove={() => setAttached(null)} />
                </View>
              ) : null}
              <MentionSuggestions suggestions={suggestions} onPick={(sug) => pickMention(sug.label)} />
              {tagNote ? <Text style={[cf.text, { color: C.t2, fontSize: 12, paddingHorizontal: 14, paddingTop: 6 }]}>ℹ️ {tagNote}</Text> : null}
              {voice ? (
                <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingVertical: 10 }, enter('fade')]}>
                  <View style={[{ width: 10, height: 10, borderRadius: 5, backgroundColor: C.danger }, enter('recording')]} />
                  <Text style={[cf.semibold, cf.num, { flex: 1, color: C.t1, fontSize: 16 }]}>Enregistrement… {voiceClock((voiceNow - voice.started) / 1000)}</Text>
                  <Button small variant="ghost" label="Annuler" onPress={() => void stopRecording(false)} />
                  <Button small label="Envoyer" onPress={() => void stopRecording(true)} />
                </View>
              ) : (
                <View style={[{ flexDirection: 'row', alignItems: 'flex-end', gap: 8, paddingHorizontal: 10, paddingTop: 8, paddingBottom: 10 },
                  web({ backgroundImage: 'linear-gradient(180deg, rgba(14,10,31,0), rgba(14,10,31,0.92) 28%)' })]}>
                  {event && isStaff && !editing ? (
                    <RoundButton label={announcing ? 'Annonce activée' : 'Faire une annonce'} onPress={() => setAnnouncing((v) => !v)} active={announcing}>
                      <Text style={{ fontSize: 18 }}>📣</Text>
                    </RoundButton>
                  ) : null}
                  {Platform.OS === 'web' && !requestDraft && !editing ? (
                    <RoundButton label="Envoyer une photo" onPress={() => void sendPhoto()} disabled={sending}>
                      <Icon name="plus" color={C.lav} />
                    </RoundButton>
                  ) : null}
                  <View style={{ flex: 1 }}>
                    <Input inputRef={input} accessibilityLabel="Message"
                      placeholder={announcing ? 'Ton annonce…' : requestDraft ? 'Écris ta demande…' : 'Message…'}
                      placeholderTextColor={C.t3}
                      value={text} onChangeText={(v) => { setText(v); setCursor(v.length); if (v && maySendTyping) typing.ping(); }}
                      onSelectionChange={(e) => setCursor(e.nativeEvent.selection.end)} multiline editable={!sending} maxLength={event ? 4000 : 2000}
                      // Le champ grandit avec le texte : à hauteur fixe, la 2e ligne rognait le haut du texte.
                      onContentSizeChange={onComposerSize}
                      style={[{ height: text ? composerHeight : COMPOSER_MIN, minHeight: COMPOSER_MIN, paddingTop: 11, paddingBottom: 11, paddingLeft: 16,
                        paddingRight: Platform.OS === 'web' && !requestDraft && !editing ? 46 : 16, borderRadius: 22, backgroundColor: C.s1, borderColor: C.line2,
                        color: C.t1, fontSize: 17 }, announcing && { borderColor: C.pink }, editing && { borderColor: C.lav }]} />
                    {Platform.OS === 'web' && !requestDraft && !editing ? (
                      <Pressable accessibilityRole="button" accessibilityLabel="Prendre une photo" onPress={() => void sendPhoto(true)} disabled={sending}
                        style={({ pressed }) => [{ position: 'absolute', right: 4, bottom: 4, width: 36, height: 36, borderRadius: 18, alignItems: 'center', justifyContent: 'center' },
                          pressed && { backgroundColor: C.glass }]}>
                        <Icon name="camera" size={21} color={C.t2} />
                      </Pressable>
                    ) : null}
                  </View>
                  {text.trim() || attached || editing ? (
                    // Bouton rond de la même largeur que le micro : le champ ne rétrécit pas en écrivant (sa hauteur reste juste).
                    <RoundButton label={editing ? 'Enregistrer la modification' : announcing ? 'Publier l’annonce' : 'Envoyer'} onPress={() => void send()} primary busy={sending}>
                      <Icon name={editing ? 'check' : 'send'} color={C.onLav} stroke={2.4} />
                    </RoundButton>
                  ) : requestDraft ? null : (
                    <RoundButton label="Enregistrer un message vocal" onPress={() => void startRecording()} disabled={sending} primary>
                      <Icon name="mic" color={C.onLav} />
                    </RoundButton>
                  )}
                </View>
              )}
            </View>
          ) : staffOnly ? (
            <Note icon text="Seule l’organisation peut écrire dans cette discussion." />
          ) : event ? (
            <Note text="Tu peux lire la discussion ; tu pourras écrire une fois l’événement publié et ta place confirmée." />
          ) : null}
        </KeyboardAvoidingView>
        {event && ev && data && showInfo ? (
          // Infos de la discussion : une page posée par-dessus le fil (sous l'en-tête), qui reste en place derrière
          // (position, brouillon) ; ✕ de l'en-tête la referme.
          <View style={[StyleSheet.absoluteFill, { backgroundColor: C.bg }, enter('slideIn')]}>
            <EventChatSettings eventId={id} me={me.id} staff={isStaff} card={ev.card}
              people={(data.people as Profile[]).map((p): EventPerson => ({ id: p.id, name: shownName(p.id), photo: p.avatar_url,
                rsvp: p.rsvp ?? null, organizer: Boolean(p.organizer), invited: Boolean(p.invited) }))}
              level={level} mutedUntil={mutedUntil} writeMode={ev.writeMode} blocked={data.hidden}
              pins={pins.map((p) => ({ id: p.id, author: shownName(p.user_id), text: quoteText(p), at: p.created_at, announcement: Boolean(p.announcement) }))}
              nameOf={(uid) => people.get(uid)?.display_name ?? null}
              onLevel={(l) => void changeLevel(l)} onMute={(c) => void changeMute(c)}
              onJump={(messageId, at) => { setShowInfo(false); setTimeout(() => showMessage(messageId, at), 80); }}
              onChanged={reload} />
          </View>
        ) : null}
      </View>
      <MessageMenu open={!!menu}
        preview={menuFor ? { author: shownName(menuFor.user_id), mine: menuFor.user_id === me.id,
          text: withoutAnnounceTag(menuFor.body) || (menuFor.audio_seconds != null ? '🎤 Message vocal' : menuFor.photo_path ? '📷 Photo' : menuFor.event_id ? '🎉 Soirée Party' : '') } : null}
        reactions={menuFor && canCompose && !requestDraft
          ? REACTION_STATE(reactionsOf.get(menuFor.id) ?? [], me.id) : null}
        onReact={(e) => menuFor && void react(menuFor, e)}
        actions={menu?.actions ?? []} onClose={() => setMenu(null)} />
      {event && ev ? (
        <NotifyMenu open={menuOpen} level={level} mutedUntil={mutedUntil} onClose={() => setMenuOpen(false)}
          onLevel={(l) => void changeLevel(l)} onMute={(c) => void changeMute(c)} onSettings={() => setShowInfo(true)} />
      ) : null}
      {notice ? <Toast message={notice} onHide={() => setNotice(null)} /> : null}
      <ReportSheet target={reportTarget} allowContext={Boolean(reportTarget && reportTarget.kind !== 'profile')} onClose={() => setReportTarget(null)} />
      {terms.sheet}
    </SafeAreaView>
  );
}

const REACTION_STATE = (rows: Reaction[], me: string) => rows.map((r) => ({ emoji: r.emoji, mine: r.user_id === me }));

function Note({ text, icon = false }: { text: string; icon?: boolean }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 16, paddingVertical: 14, borderTopWidth: 1, borderTopColor: C.line }}>
      {icon ? <Icon name="lock" size={16} color={C.lav} /> : null}
      <Text style={[cf.text, { color: C.t2, fontSize: 14, lineHeight: 19, textAlign: 'center', flexShrink: 1 }]}>{text}</Text>
    </View>
  );
}

function ComposerChip({ label, text, icon, onClose, closeLabel }: { label: string; text: string; icon: 'pencil' | 'reply' | 'lock'; onClose: () => void; closeLabel: string }) {
  return (
    <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 12, marginTop: 6, paddingVertical: 8, paddingLeft: 12, paddingRight: 4,
      borderRadius: 16, backgroundColor: C.s1, borderWidth: 1, borderColor: C.line2 }, enter('drop')]}>
      <View style={{ width: 3, alignSelf: 'stretch', borderRadius: 2, backgroundColor: C.lav }} />
      <Icon name={icon} size={16} color={C.lav} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text numberOfLines={1} style={[cf.bold, { color: C.lav, fontSize: 13 }]}>{label}</Text>
        <Text numberOfLines={1} style={[cf.text, { color: C.t2, fontSize: 13 }]}>{text}</Text>
      </View>
      <Pressable accessibilityRole="button" accessibilityLabel={closeLabel} onPress={onClose}
        style={({ pressed }) => [{ width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' }, pressed && { backgroundColor: C.glass }]}>
        <Icon name="x" size={16} color={C.t2} stroke={2.2} />
      </Pressable>
    </View>
  );
}

function RoundButton({ label, onPress, children, primary = false, active = false, disabled = false, busy = false }: {
  label: string; onPress: () => void; children: ReactNode; primary?: boolean; active?: boolean; disabled?: boolean; busy?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: disabled || busy, busy, selected: active }}
      onPress={onPress} disabled={disabled || busy}
      style={({ pressed }) => [{ width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
        primary ? lavButton : { backgroundColor: active ? 'rgba(255,79,154,0.22)' : C.glass, borderWidth: 1, borderColor: active ? C.pink : C.glassLine },
        (disabled || busy) && { opacity: 0.5 }, pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
      {children}
    </Pressable>
  );
}
