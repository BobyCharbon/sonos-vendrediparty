import { router, Stack } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { ActivityIndicator, FlatList, KeyboardAvoidingView, Platform, Pressable, StyleSheet, View, type TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatBubble } from './ChatBubble';
import { ChatWallpaper } from './chat/ChatWallpaper';
import { EventChatTitle, type EventChatCard } from './chat/EventChatTitle';
import { NotifyBell, NotifyMenu } from './chat/NotifyMenu';
import { DirectChatSettings } from './DirectChatSettings';
import { EventChatSettings, type EventPerson } from './EventChatSettings';
import { GroupChatSettings } from './GroupChatSettings';
import { MentionSuggestions } from './MentionSuggestions';
import { ReportSheet } from './ReportSheet';
import { useTermsGate } from './TermsSheet';
import { usePersonText } from './PersonName';
import { Button, ErrorText, HeaderBack, Input, Loading, s, T, Toast } from './ui';
import { useMe } from '@/lib/auth';
import { useContactNames } from '@/lib/contactNames';
import { chatTimeline, directAsGroupMessage, EVENT_TAGS, eventChatPrefs, eventTag, firstUnread, insertMention, isAnnouncement, markEventChatRead,
  mentionQuery, mentionsIn, mentionSuggestions, muteEventChat, muteUntil, NOTIFY_LEVELS, newMessageId, pickPhoto, setEventChatLevel, shrinkPhoto,
  signedPhotos, startVoice, uploadChatAudio, uploadChatPhoto, voiceClock, withoutAnnounceTag,
  type ChatSummary, type ChatWriteMode, type DirectMessageRow, type EveryoneBy, type GroupMessage, type MuteChoice, type NotifyLevel, type Reaction,
  type TimelineRow, type VoiceRecording } from '@/lib/chats';
import { useLivePing, useQuery, useRealtime } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import { roleRank, siteAdminRank } from '@/lib/roles';
import { duration, enter, pressTransition, transition } from '@/lib/motion';
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
const COMPOSER_MIN = 46;
const COMPOSER_MAX = 190;
const composerHeightFor = (content: number) => Math.min(COMPOSER_MAX, Math.max(COMPOSER_MIN, Math.ceil(content) + 3));

export type ChatKind = 'group' | 'direct' | 'event';
type Profile = { id: string; display_name: string; avatar_url: string | null; member?: boolean; rsvp?: string | null; organizer?: boolean; invited?: boolean };
type ChatGroup = { id: string; name: string; created_by: string | null; everyone_tag?: EveryoneBy; member_group_members: { user_id: string }[] };
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
const masked = (m: GroupMessage): GroupMessage => ({ ...m, body: 'Message masqué (personne bloquée)', photo_path: null, audio_path: null });
const blockedOf = (rows: unknown) => new Set(((rows as { blocked_id: string }[] | null) ?? []).map((b) => b.blocked_id));

/** Message direct (conversation privée à deux, 4.11) : mêmes données qu'un groupe, lues dans les tables direct_*
 * (règles : les deux personnes seulement). Pas d'admin, d'organisateur, d'@tout ni d'@annonce. */
async function loadDirect(id: string, me: string) {
  const [pair, msgs, people, settings, blocks, pins] = await Promise.all([
    supabase.from('direct_chats').select('user_a, user_b').eq('id', id).single(),
    supabase.from('direct_messages').select('*').eq('chat_id', id).order('created_at', { ascending: false }).limit(PAGE),
    supabase.rpc('direct_chat_people', { chat: id }),
    supabase.from('direct_chat_settings').select('notify').eq('chat_id', id).maybeSingle(),
    supabase.from('direct_blocks').select('blocked_id'),
    supabase.from('direct_messages').select('*').eq('chat_id', id).eq('pinned', true).is('deleted_at', null)
      .order('created_at', { ascending: false }).limit(HIGHLIGHTS),
  ]);
  const { user_a, user_b } = must(pair) as { user_a: string; user_b: string };
  const other = user_a === me ? user_b : user_a;
  const profiles = must(people) as Profile[];
  const messages = (must(msgs) as DirectMessageRow[]).map(directAsGroupMessage).reverse();
  const reactions = messages.length
    ? must(await supabase.from('direct_message_reactions').select('message_id, user_id, emoji').in('message_id', messages.map((m) => m.id))) as Reaction[]
    : [];
  const notify = ((settings.data as { notify?: NotifyLevel } | null)?.notify ?? 'all') as NotifyLevel;
  const group: ChatGroup = { id, name: profiles.find((p) => p.id === other)?.display_name || 'Profil à compléter', created_by: null,
    everyone_tag: 'staff', member_group_members: [{ user_id: me }, { user_id: other }] };
  return {
    group, messages, reactions, other,
    blocked: blockedOf(blocks.data).has(other), hidden: blockedOf(blocks.data),
    chat: { id, name: group.name, kind: 'direct', member: true, admin: false, notify } as ChatSummary,
    highlights: ((pins.data as DirectMessageRow[] | null) ?? []).map(directAsGroupMessage).filter((m) => m.pinned && !m.deleted_at),
    people: profiles,
    admins: new Set<string>(), organizers: new Set<string>(), phones: new Map<string, string>(),
    event: null as EventExtras | null,
  };
}

type EventMessageRow = Omit<GroupMessage, 'group_id' | 'deleted_by_admin' | 'mention_all'> & { event_id: string; mention_all?: boolean };
const eventAsGroupMessage = (m: EventMessageRow): GroupMessage =>
  ({ ...m, group_id: m.event_id, mention_all: Boolean(m.mention_all), deleted_by_admin: false, photo_path: m.photo_path ?? null });

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
  const [group, msgs, people, admins, chats, phones, pins, organizers, blocks] = await Promise.all([
    // « * » : everyone_tag (qui peut écrire @tout) quand la base le connaît.
    supabase.from('member_groups').select('*, member_group_members(user_id)').eq('id', id).single(),
    supabase.from('group_messages').select('*').eq('group_id', id).order('created_at', { ascending: false }).limit(PAGE),
    supabase.rpc('group_chat_people', { grp: id }),  // un Guest ne lit pas le profil d'un admin dans profiles
    supabase.from('group_admins').select('user_id').eq('group_id', id),
    supabase.rpc('my_chats'),
    supabase.rpc('group_chat_phones', { grp: id }),
    supabase.from('group_messages').select('*').eq('group_id', id).eq('pinned', true).is('deleted_at', null)
      .order('created_at', { ascending: false }).limit(HIGHLIGHTS),
    supabase.from('group_organizers').select('user_id').eq('group_id', id),
    supabase.from('direct_blocks').select('blocked_id'),
  ]);
  // Personnes que j'ai bloquées (App Store 1.2) : leurs messages, photos et vocaux sont masqués aussitôt ; leurs messages
  // épinglés ne s'affichent pas.
  const hidden = blockedOf(blocks.data);
  const messages = (must(msgs) as GroupMessage[]).reverse().map((m) => (hidden.has(m.user_id) ? masked(m) : m));
  const reactions = messages.length
    ? must(await supabase.from('group_message_reactions').select('message_id, user_id, emoji').in('message_id', messages.map((m) => m.id))) as Reaction[]
    : [];
  const chat = ((chats.data as ChatSummary[] | null) ?? []).find((c) => c.id === id) ?? null;
  return {
    group: must(group) as ChatGroup,
    messages, reactions, chat, other: null as string | null, blocked: false, hidden,
    highlights: ((pins.data as GroupMessage[] | null) ?? []).filter((m) => m.pinned && !m.deleted_at && !hidden.has(m.user_id)),
    people: must(people) as Profile[],
    admins: new Set((must(admins) as { user_id: string }[]).map((a) => a.user_id)),
    organizers: new Set(((organizers.data as { user_id: string }[] | null) ?? []).map((o) => o.user_id)),
    phones: new Map(((phones.data as { id: string; phone: string }[] | null) ?? []).map((p) => [p.id, p.phone])),
    event: null as EventExtras | null,
  };
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

/** Discussion façon WhatsApp (groupe, message direct, discussion d'un événement) : fond à motif, bulles avec queue,
 * séparateurs de jours, messages d'une même personne regroupés, heure dans la bulle, @citations en couleur, citation qui
 * remonte au message, « Nouveaux messages », bouton ↓ avec les nouveaux, messages précédents chargés en remontant,
 * bandeau des annonces et épinglés, annonces en carte. Groupe : @tout (selon le groupe) et @annonce (admins et
 * organisateurs). Événement : en-tête (couverture, titre, date, participants), cloche des notifications (Tout /
 * Mentions seulement / Rien, sourdine), @toutlemonde, @present et annonces (📣) pour l'organisation ; « Seule
 * l'organisation peut écrire » selon son réglage. La base décide de toute façon. */
export function GroupChat({ id, direct = false, event = false }: { id: string; direct?: boolean; event?: boolean }) {
  const kind: ChatKind = event ? 'event' : direct ? 'direct' : 'group';
  const me = useMe();
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
  const [announcing, setAnnouncing] = useState(false);
  const [sending, setSending] = useState(false);
  // Envoi en cours (texte ou vocal) : un double toucher, même pendant l'attente des CGU, n'envoie qu'un message.
  const sendingRef = useRef(false);
  // Messages envoyés pas encore revenus de la base : affichés tout de suite (« Envoi… »), comme Snapchat.
  const [pending, setPending] = useState<GroupMessage[]>([]);
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

  const { data, loading, error: loadError, reload } = useQuery(
    () => (event ? loadEvent(id, me.id) : direct ? loadDirect(id, me.id) : loadGroup(id)), [id, direct, event]);

  useRealtime(`${kind}-chat-${id}`, kind === 'direct' ? [
    { table: 'direct_messages', filter: `chat_id=eq.${id}` },
    { table: 'direct_message_reactions' },
  ] : kind === 'group' ? [
    { table: 'group_messages', filter: `group_id=eq.${id}` },
    { table: 'group_message_reactions' },
  ] : [{ table: 'messages', filter: `event_id=eq.${id}` }], reload);
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
  useEffect(() => {
    if (!member || !data?.messages.length || event) return;
    void (direct ? supabase.rpc('mark_direct_read', { chat: id }) : supabase.rpc('mark_group_read', { grp: id }));
  }, [member, id, direct, event, data?.messages]);

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
  // Suggestions de l'@ : membres (moi exclu) filtrés par les lettres tapées, puis les citations spéciales permises.
  const typing = mentionQuery(text, cursor);
  const suggestions = useMemo(() => (typing === null || direct ? [] : mentionSuggestions(typing,
    // Moi et les personnes que j'ai bloquées exceptés.
    inside.filter((u) => u !== me.id && !data?.hidden.has(u)).map((u) => ({ id: u, display_name: nameOf(u), avatar_url: people.get(u)?.avatar_url ?? null })),
    { everyone: canEveryone, announce: isStaff, tags: event ? (isStaff ? EVENT_TAGS : []) : undefined }, contacts)),
  // eslint-disable-next-line react-hooks/exhaustive-deps -- nameOf lit people
  [typing, inside, people, me.id, canEveryone, isStaff, contacts, direct, event, data?.hidden]);
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

  /** Texte, photo ou vocal : la bulle apparaît tout de suite, le champ se vide ; en cas d'échec, le texte revient. */
  async function send(photoPath: string | null = null, audio: { blob: Blob; seconds: number; ext: 'm4a' | 'webm' } | null = null) {
    const body = audio ? '' : text.trim();
    if ((!body && !photoPath && !audio) || sendingRef.current) return;
    sendingRef.current = true;
    try {
      if (!terms.accepted && !(await terms.ensure())) return;
      await deliver(body, photoPath, audio);
    } finally {
      sendingRef.current = false;
    }
  }

  async function deliver(body: string, photoPath: string | null, audio: { blob: Blob; seconds: number; ext: 'm4a' | 'webm' } | null) {
    const quoted = replyTo;
    const announce = announcing;
    const messageId = newMessageId();
    const announced = isStaff && (announce || isAnnouncement(body));
    const draft: GroupMessage = { id: messageId, group_id: id, user_id: me.id, body, photo_path: photoPath, reply_to: quoted?.id ?? null,
      mentions: [], mention_all: false, pinned: announced, announcement: announced, created_at: new Date().toISOString(), edited_at: null, deleted_at: null,
      deleted_by_admin: false, audio_path: null, audio_seconds: audio ? Math.round(audio.seconds * 10) / 10 : null, pending: true };
    const known = new Set((data?.messages ?? []).map((m) => m.id));
    setPending((list) => [...list.filter((m) => !known.has(m.id)), draft]);
    if (!audio) { setText(''); setCursor(0); }
    setReplyTo(null);
    setAnnouncing(false);
    setError(null);
    const tagged = mentionsIn(body, inside.filter((u) => u !== me.id).map((u) => ({ id: u, display_name: nameOf(u) })));
    try {
      const audioPath = audio ? await uploadChatAudio(id, audio) : null;
      const { error } = kind === 'direct'
        ? await supabase.from('direct_messages').insert({
          id: messageId, chat_id: id, body, photo_path: photoPath, reply_to: quoted?.id ?? null, audio_path: audioPath, audio_seconds: draft.audio_seconds,
        })
        : kind === 'event'
          // La base garde seulement les citations et annonces permises (guard_message_change).
          ? await supabase.from('messages').insert({
            id: messageId, event_id: id, user_id: me.id, body, photo_path: photoPath, reply_to: quoted?.id ?? null, mentions: tagged.mentions,
            audio_path: audioPath, audio_seconds: draft.audio_seconds, ...(announce ? { announcement: true } : {}),
          })
          : await supabase.from('group_messages').insert({
            id: messageId, group_id: id, body, photo_path: photoPath, reply_to: quoted?.id ?? null, mentions: tagged.mentions,
            mention_all: tagged.all && canEveryone, audio_path: audioPath, audio_seconds: draft.audio_seconds,
          });
      // Filtre de la base : la phrase dit pourquoi (propos haineux, contenu sexuel…) ; sinon un message général.
      if (error) throw new Error(dbMessage(error.message, 'Le message n’a pas pu être envoyé. Réessaie.'));
    } catch (e) {
      setPending((list) => list.filter((m) => m.id !== messageId));
      if (!audio) setText(body);
      setReplyTo(quoted);
      setAnnouncing(announce);
      return setError(e instanceof Error ? e.message : 'Le message n’a pas pu être envoyé. Réessaie.');
    }
    reload();
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
  const title = direct && data?.other ? shownName(data.other) : data?.group.name ?? 'Discussion';
  const subtitle = direct ? null : `${inside.length} membres`;
  const back = () => (router.canGoBack() ? router.back() : router.replace(event ? `/event/${id}` : '/chats'));
  const header = event && ev ? (
    showInfo ? (
      <Stack.Screen options={{
        title: 'Infos de la discussion', headerTitleAlign: 'center',
        headerTitle: () => <T weight="bold" size={17}>Infos de la discussion</T>,
        headerLeft: () => <HeaderBack label="Discussion" iconOnly onPress={() => setShowInfo(false)} />,
        headerRight: () => null,
      }} />
    ) : (
      <Stack.Screen options={{
        title: ev.card.title, headerTitleAlign: 'left',
        // WhatsApp : ‹, couverture ronde, titre et « date · N participants » (toucher → infos), cloche à droite.
        headerTitle: () => <EventChatTitle id={id} card={ev.card} onPress={() => setShowInfo(true)} />,
        headerLeft: () => <HeaderBack label="Fiche de l’événement" iconOnly onPress={back} />,
        headerRight: () => <NotifyBell level={level} mutedUntil={mutedUntil} onPress={() => setMenuOpen(true)} />,
      }} />
    )
  ) : (
    <Stack.Screen options={{
      title,
      headerTitle: () => (
        <Pressable accessibilityRole="button" accessibilityLabel={`${title}, infos`} onPress={() => setShowInfo((v) => !v)} style={{ alignItems: 'center' }}>
          <T weight="bold" numberOfLines={1}>{title}</T>
          {subtitle ? <T muted size={11} numberOfLines={1}>{subtitle}</T> : null}
        </Pressable>
      ),
      // « ‹ » seul, comme WhatsApp : le titre garde toute la place. Ouvert d'une notification : la liste.
      headerLeft: () => <HeaderBack label="" onPress={back} />,
      headerRight: () => (
        <Pressable accessibilityRole="button" accessibilityLabel={direct ? 'Infos de la conversation' : 'Infos du groupe'}
          hitSlop={8} onPress={() => setShowInfo((v) => !v)} style={{ paddingHorizontal: 12 }}>
          <T weight="semibold" color={colors.accent}>{showInfo ? 'Fermer' : 'Infos'}</T>
        </Pressable>
      ),
    }} />
  );

  if (showInfo && data && direct && data.other) {
    return (
      <View style={s.screen}>
        {header}
        <DirectChatSettings chatId={id} other={{ id: data.other, name: shownName(data.other), photo: people.get(data.other)?.avatar_url ?? null }}
          notify={data.chat?.notify ?? 'all'} blocked={data.blocked} onChanged={reload} />
      </View>
    );
  }

  if (showInfo && data && !event) {
    return (
      <View style={s.screen}>
        {header}
        <GroupChatSettings groupId={id} notify={data.chat?.notify ?? 'mentions'} member={member}
          canNameAdmins={data.group.created_by === me.id || roleRank(me.role) >= siteAdminRank()}
          isAdmin={isAdmin} everyone={everyone}
          members={inside.map((u) => ({ id: u, name: shownName(u), photo: people.get(u)?.avatar_url ?? null,
            admin: data.admins.has(u), organizer: data.organizers.has(u), creator: u === data.group.created_by, phone: data.phones.get(u) ?? null }))}
          onChanged={reload} />
      </View>
    );
  }

  const quoteText = (m: GroupMessage) => (m.deleted_at ? 'Message supprimé'
    : withoutAnnounceTag(m.body) || (m.audio_seconds != null ? '🎤 Message vocal' : '📷 Photo'));
  const staffOnly = Boolean(event && ev && ev.mayWrite && !ev.canWrite && ev.writeMode === 'staff');

  return (
    <SafeAreaView style={s.screen} edges={['bottom']}>
      {header}
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        {banner ? (
          <View style={[{ zIndex: 2 }, enter('drop')]}>
            <Pressable accessibilityRole="button"
              accessibilityLabel={`${banner.announcement ? 'Annonce' : 'Épinglé'}${pins.length > 1 ? ` ${(pinIndex % pins.length) + 1} sur ${pins.length}` : ''} : ${shownName(banner.user_id)}, ${withoutAnnounceTag(banner.body) || 'Photo'}`}
              accessibilityHint={canUnpinBanner ? 'Touche pour voir le message ; appui long pour le retirer' : 'Touche pour voir le message'}
              onPress={() => { showMessage(banner.id, banner.created_at); if (pins.length > 1) setPinIndex((i) => i + 1); }}
              onLongPress={() => canUnpinBanner && setBannerMenu((v) => !v)}
              style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 14, paddingVertical: 10,
                backgroundColor: banner.announcement ? colors.accentDim : colors.surface, borderBottomWidth: 1,
                borderBottomColor: banner.announcement ? colors.accent : colors.line }, pressTransition, pressed && { opacity: 0.85 }]}>
              {pins.length > 1 ? (
                <View style={{ gap: 2, height: 32, justifyContent: 'center' }}>
                  {pins.slice(0, 5).map((p, i) => (
                    <View key={p.id} style={{ width: 3, flex: 1, borderRadius: 2, backgroundColor: i === Math.min(pinIndex % pins.length, 4) ? colors.accent : colors.line }} />
                  ))}
                </View>
              ) : null}
              <T size={18}>{banner.announcement ? '📣' : '📌'}</T>
              <View style={{ flex: 1, gap: 2 }}>
                <T size={12} weight="bold" color={colors.accent}>
                  {banner.announcement ? 'Annonce' : 'Message épinglé'}
                  {pins.length > 1 ? <T size={12} muted>{`  ${(pinIndex % pins.length) + 1}/${pins.length}`}</T> : null}
                </T>
                <T size={14} weight={banner.announcement ? 'semibold' : 'body'} numberOfLines={banner.announcement ? 2 : 1}>
                  {shownName(banner.user_id)} : {withoutAnnounceTag(banner.body) || '📷 Photo'}
                </T>
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
          <ChatWallpaper />
          <FlatList
            ref={list}
            data={rows}
            keyExtractor={(r) => r.key}
            contentContainerStyle={{ paddingHorizontal: 10, paddingVertical: 12 }}
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
              if (!a) return;
              anchor.current = null;
              list.current?.scrollToOffset({ offset: a.y + (h - a.h), animated: false });
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
                <ActivityIndicator color={colors.accent} />
              </View>
            ) : hasMore === false && all.length >= PAGE ? (
              <T muted size={12} style={{ textAlign: 'center', paddingVertical: 8 }}>Début de la discussion</T>
            ) : null}
            renderItem={({ item: row }) => {
              if ('day' in row) {
                return (
                  <View accessibilityRole="header" style={{ alignItems: 'center', marginVertical: 10 }}>
                    <T size={12} weight="semibold" color={colors.textSoft} style={st.dayPill}>{row.day}</T>
                  </View>
                );
              }
              if ('unread' in row) {
                return (
                  <View accessibilityRole="header" style={[st.unread, enter('fade')]}>
                    <T size={12} weight="bold" color={colors.textSoft}>{row.unread > 1 ? `${row.unread} nouveaux messages` : '1 nouveau message'}</T>
                  </View>
                );
              }
              const m = row.message;
              const quoted = m.reply_to ? byId.get(m.reply_to) : null;
              return (
                <View style={{ marginTop: row.first ? 8 : 2 }}>
                  <ChatBubble message={m} mine={m.user_id === me.id} me={me.id}
                    author={{ name: shownName(m.user_id), photo: people.get(m.user_id)?.avatar_url ?? null }}
                    quoted={quoted ? { name: quoted.user_id === me.id ? 'Toi' : shownName(quoted.user_id), author: quoted.user_id, text: quoteText(quoted) } : null}
                    photoUrl={m.photo_path ? photos.get(m.photo_path) ?? null : null}
                    audioUrl={m.audio_path ? photos.get(m.audio_path) ?? null : null}
                    reactions={reactionsOf.get(m.id) ?? []} canWrite={member} isAdmin={isAdmin} isStaff={isStaff} canPin={direct || isAdmin}
                    first={row.first} last={row.last} showAuthor={!direct} names={names} flash={flashId === m.id}
                    onQuote={quoted ? () => showMessage(quoted.id) : undefined}
                    onReply={() => { setReplyTo(m); input.current?.focus(); }} onReact={(e) => void react(m, e)}
                    onPin={() => void pin(m.id, !m.pinned)}
                    onDelete={() => void remove(m.id)}
                    onReport={() => setReportTarget({ kind: event ? 'event_message' : direct ? 'direct_message' : 'group_message', id: m.id, label: `le message de ${shownName(m.user_id)}` })}
                    fresh={!!initialIds && !initialIds.has(m.id)} />
                </View>
              );
            }}
            ListEmptyComponent={
              <View style={{ alignItems: 'center', gap: 12, marginTop: 60, marginHorizontal: 24, padding: 18, borderRadius: 16, backgroundColor: 'rgba(34,26,61,0.85)' }}>
                <T size={34}>💬</T>
                <T muted style={{ textAlign: 'center' }}>{loadError ? 'La discussion n’a pas pu être chargée.'
                  : event ? 'Aucun message pour l’instant. Lance la discussion avec les invités !' : 'Aucun message pour l’instant. Lance la discussion !'}</T>
                {/* Groupe tout neuf (créé depuis Discussions) : y ajouter du monde, dans Réglages › Groupes. */}
                {!loadError && kind === 'group' && member && inside.length <= 1 && data?.group.created_by === me.id ? (
                  <Button small label="Ajouter des membres" onPress={() => router.push(`/groups?open=${id}`)} />
                ) : null}
              </View>
            }
          />
          {!atBottom && rows.length ? (
            <Pressable accessibilityRole="button" accessibilityLabel={unseen ? `${unseen} nouveaux messages, descendre` : 'Descendre au dernier message'}
              onPress={() => { setUnseen(0); list.current?.scrollToEnd({ animated: true }); }}
              style={({ pressed }) => [st.down, enter('pop'), pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
              <T size={20} weight="bold" color={colors.textSoft}>⌄</T>
              {unseen ? (
                <View style={st.downBadge}>
                  <T size={11} weight="bold" color={colors.onAction}>{Math.min(unseen, 99)}</T>
                </View>
              ) : null}
            </Pressable>
          ) : null}
        </View>
        <ErrorText error={error ?? loadError} />
        {data?.blocked ? (
          // Message direct : j'ai bloqué cette personne ; l'historique reste, l'écriture revient en la débloquant.
          <T muted size={13} style={{ padding: 12, textAlign: 'center' }}>Tu as bloqué {title}. Débloque-le dans Infos pour lui écrire.</T>
        ) : member ? (
          <View style={st.composer}>
            {announcing ? <T size={12} weight="semibold" color={colors.accent} style={{ paddingHorizontal: 12, paddingBottom: 4 }}>📣 Annonce : épinglée en haut et envoyée à tous les invités</T> : null}
            {replyTo ? (
              <View style={[st.reply, enter('drop')]}>
                <View style={{ width: 4, alignSelf: 'stretch', borderRadius: 2, backgroundColor: colors.accent }} />
                <View style={{ flex: 1 }}>
                  <T size={12} weight="bold" color={colors.accent} numberOfLines={1}>Réponse à {replyTo.user_id === me.id ? 'toi' : shownName(replyTo.user_id)}</T>
                  <T muted size={12} numberOfLines={1}>{quoteText(replyTo)}</T>
                </View>
                <Button small variant="ghost" label="✕" accessibilityLabel="Ne plus répondre à ce message" onPress={() => setReplyTo(null)} />
              </View>
            ) : null}
            <MentionSuggestions suggestions={suggestions} onPick={(sug) => pickMention(sug.label)} />
            {tagNote ? <T muted size={12} style={{ paddingHorizontal: 12, paddingTop: 6 }}>ℹ️ {tagNote}</T> : null}
            {voice ? (
              <View style={[s.row, { padding: 8 }, enter('fade')]}>
                <View style={[st.field, { alignItems: 'center', paddingHorizontal: 14, gap: 10 }]}>
                  <View style={[{ width: 10, height: 10, borderRadius: 5, backgroundColor: colors.red }, enter('recording')]} />
                  <T style={{ flex: 1 }}>🎙 Enregistrement… {voiceClock((voiceNow - voice.started) / 1000)}</T>
                  <Button small variant="ghost" label="Annuler" onPress={() => void stopRecording(false)} />
                </View>
                <RoundButton label="Envoyer" onPress={() => void stopRecording(true)}><T size={18} color={colors.onAction}>➤</T></RoundButton>
              </View>
            ) : (
              <View style={[s.row, { paddingHorizontal: 8, paddingVertical: 6, alignItems: 'flex-end', gap: 6 }]}>
                <View style={[st.field, announcing && { borderColor: colors.accent }]}>
                  {Platform.OS === 'web' ? (
                    <IconButton label="Joindre une photo" onPress={() => void sendPhoto()} disabled={sending}><T size={22} color={colors.muted}>＋</T></IconButton>
                  ) : null}
                  {event && isStaff ? (
                    <IconButton label={announcing ? 'Annonce activée' : 'Faire une annonce'} onPress={() => setAnnouncing((v) => !v)} active={announcing}>
                      <T size={18}>📣</T>
                    </IconButton>
                  ) : null}
                  <Input inputRef={input} accessibilityLabel="Message"
                    placeholder={announcing ? 'Ton annonce…' : 'Message…'}
                    value={text} onChangeText={(v) => { setText(v); setCursor(v.length); }}
                    onSelectionChange={(e) => setCursor(e.nativeEvent.selection.end)} multiline editable={!sending} maxLength={event ? 4000 : 2000}
                    // Le champ grandit avec le texte : à hauteur fixe, la 2e ligne rognait le haut du texte.
                    onContentSizeChange={onComposerSize}
                    style={{ flex: 1, height: text ? composerHeight : COMPOSER_MIN, paddingTop: 12, paddingBottom: 12, paddingHorizontal: 6,
                      borderWidth: 0, borderRadius: 0, backgroundColor: 'transparent',
                      // Pas de cadre carré du navigateur dans le champ arrondi (la bulle arrondie autour montre le champ).
                      outlineStyle: 'none', outlineWidth: 0 } as object} />
                  {!text.trim() && Platform.OS === 'web' ? (
                    <IconButton label="Prendre une photo" onPress={() => void sendPhoto(true)} disabled={sending}><T size={18}>📷</T></IconButton>
                  ) : null}
                </View>
                {text.trim() ? (
                  // Le micro devient ➤ dès qu'on écrit (WhatsApp) : même place, même taille.
                  <RoundButton label={announcing ? 'Publier l’annonce' : 'Envoyer'} onPress={() => void send()} loading={sending}>
                    <T size={18} color={colors.onAction}>➤</T>
                  </RoundButton>
                ) : (
                  <RoundButton label="Enregistrer un message vocal" onPress={() => void startRecording()} disabled={sending}>
                    <T size={18}>🎤</T>
                  </RoundButton>
                )}
              </View>
            )}
          </View>
        ) : staffOnly ? (
          <View style={st.readOnly}>
            <T muted size={13} style={{ textAlign: 'center' }}>🔒 Seule l’organisation peut écrire dans cette discussion.</T>
          </View>
        ) : event ? (
          <View style={st.readOnly}>
            <T muted size={13} style={{ textAlign: 'center' }}>Tu peux lire la discussion ; tu pourras écrire une fois l’événement publié et ta place confirmée.</T>
          </View>
        ) : null}
      </KeyboardAvoidingView>
      {event && ev && data && showInfo ? (
        // Infos de la discussion : une page poussée par-dessus le fil, qui reste en place derrière (position, brouillon).
        <View style={[StyleSheet.absoluteFill, { backgroundColor: colors.bg }, enter('slideIn')]}>
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
      {event && ev ? (
        <NotifyMenu open={menuOpen} level={level} mutedUntil={mutedUntil} onClose={() => setMenuOpen(false)}
          onLevel={(l) => void changeLevel(l)} onMute={(c) => void changeMute(c)} onSettings={() => setShowInfo(true)} />
      ) : null}
      {notice ? <Toast message={notice} onHide={() => setNotice(null)} /> : null}
      <ReportSheet target={reportTarget} onClose={() => setReportTarget(null)} />
      {terms.sheet}
    </SafeAreaView>
  );
}

/** Bouton dans le champ (＋, 📣, 📷) : 44 px de zone de toucher. */
function IconButton({ label, onPress, disabled, active, children }: { label: string; onPress: () => void; disabled?: boolean; active?: boolean; children: ReactNode }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!disabled, selected: !!active }}
      onPress={onPress} disabled={disabled}
      style={({ pressed }) => [st.icon, active && { backgroundColor: colors.accentDim }, disabled && { opacity: 0.4 }, pressTransition,
        pressed && { transform: [{ scale: 0.9 }] }]}>
      {children}
    </Pressable>
  );
}

/** Bouton rond à droite du champ : micro, ou ➤ dès qu'il y a du texte. */
function RoundButton({ label, onPress, disabled, loading, children }: { label: string; onPress: () => void; disabled?: boolean; loading?: boolean; children: ReactNode }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      onPress={onPress} disabled={disabled || loading}
      style={({ pressed }) => [st.round, (disabled || loading) && { opacity: 0.6 }, enter('pop'), pressTransition,
        pressed && { transform: [{ scale: 0.92 }] }]}>
      {loading ? <ActivityIndicator color={colors.onAction} /> : children}
    </Pressable>
  );
}

const st = StyleSheet.create({
  dayPill: { paddingHorizontal: 12, paddingVertical: 5, borderRadius: 10, backgroundColor: colors.surface2, overflow: 'hidden',
    shadowColor: '#000', shadowOpacity: 0.2, shadowRadius: 2, shadowOffset: { width: 0, height: 1 } },
  unread: { alignItems: 'center', marginVertical: 10, marginHorizontal: -10, paddingVertical: 6, backgroundColor: 'rgba(255,255,255,0.07)' },
  down: { position: 'absolute', right: 12, bottom: 12, width: 42, height: 42, borderRadius: 21, alignItems: 'center', justifyContent: 'center',
    backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.lineStrong,
    shadowColor: '#000', shadowOpacity: 0.35, shadowRadius: 8, shadowOffset: { width: 0, height: 3 } },
  downBadge: { position: 'absolute', top: -7, right: -5, minWidth: 20, height: 20, paddingHorizontal: 5, borderRadius: 10, backgroundColor: colors.action,
    alignItems: 'center', justifyContent: 'center' },
  composer: { paddingTop: 4, backgroundColor: colors.bg },
  reply: { flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 10, marginTop: 4, padding: 8, borderRadius: 12, backgroundColor: colors.surface },
  field: { flex: 1, flexDirection: 'row', alignItems: 'flex-end', minHeight: 48, paddingHorizontal: 2, borderRadius: 24, backgroundColor: colors.surface,
    borderWidth: 1.5, borderColor: 'transparent', ...(transition('border-color', duration.base) as object) },
  icon: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  round: { width: 48, height: 48, borderRadius: 24, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.action },
  readOnly: { paddingVertical: 14, paddingHorizontal: 16, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.line },
});
