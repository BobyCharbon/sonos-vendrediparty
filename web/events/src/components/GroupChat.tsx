import { router, Stack } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, View, type TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatBubble } from './ChatBubble';
import { DirectChatSettings } from './DirectChatSettings';
import { EventChatSettings, type EventPerson } from './EventChatSettings';
import { GroupChatSettings } from './GroupChatSettings';
import { GroupJoinNote } from './GuestGroup';
import { MentionSuggestions } from './MentionSuggestions';
import { ReportSheet } from './ReportSheet';
import { useTermsGate } from './TermsSheet';
import { usePersonText } from './PersonName';
import { Button, ErrorText, HeaderBack, Input, Loading, s, T } from './ui';
import { useMe } from '@/lib/auth';
import { useContactNames } from '@/lib/contactNames';
import { chatTimeline, directAsGroupMessage, EVENT_TAGS, eventTag, insertMention, isAnnouncement, mentionQuery, mentionsIn, mentionSuggestions, newMessageId,
  pickPhoto, shrinkPhoto, signedPhotos, startVoice, uploadChatAudio, uploadChatPhoto, voiceClock, withoutAnnounceTag,
  type ChatSummary, type DirectMessageRow, type EveryoneBy, type GroupMessage, type NotifyLevel, type Reaction, type TimelineRow, type VoiceRecording } from '@/lib/chats';
import { useLivePing, useQuery, useRealtime } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import { roleRank, siteAdminRank } from '@/lib/roles';
import { enter, pressTransition } from '@/lib/motion';
import { dbMessage, type ReportTarget } from '@/lib/moderation';

const PAGE = 150;
/** Annonces et messages épinglés lus à part : le bandeau du haut les garde même au-delà des derniers messages. */
const HIGHLIGHTS = 20;
/** Distance au bas du fil sous laquelle on suit les nouveaux messages (sinon le bouton ↓ les compte). */
const NEAR_BOTTOM = 120;
/** Hauteur du champ : une ligne au repos, puis il suit le texte (bordure comprise) jusqu'à 7 lignes environ. */
const COMPOSER_MIN = 46;
const COMPOSER_MAX = 190;
const composerHeightFor = (content: number) => Math.min(COMPOSER_MAX, Math.max(COMPOSER_MIN, Math.ceil(content) + 3));

export type ChatKind = 'group' | 'direct' | 'event';
type Profile = { id: string; display_name: string; avatar_url: string | null; member?: boolean; rsvp?: string | null; organizer?: boolean; invited?: boolean };
type ChatGroup = { id: string; name: string; created_by: string | null; everyone_tag?: EveryoneBy; member_group_members: { user_id: string }[] };

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
  };
}

type EventMessageRow = Omit<GroupMessage, 'group_id' | 'deleted_by_admin' | 'mention_all'> & { event_id: string; mention_all?: boolean };
const eventAsGroupMessage = (m: EventMessageRow): GroupMessage =>
  ({ ...m, group_id: m.event_id, mention_all: Boolean(m.mention_all), deleted_by_admin: false, photo_path: m.photo_path ?? null });

/** Discussion d'un événement (16.11.2026, migration 20261116180000) : mêmes bulles, messages de la table messages.
 * Droits lus dans event_chat_state, personnes à citer dans event_chat_people ; base d'avant cette migration : la
 * fiche de l'événement et les membres actifs, comme l'ancienne page. */
async function loadEvent(id: string, me: string) {
  const [state, msgs, people, blocks, pins] = await Promise.all([
    supabase.rpc('event_chat_state', { e: id }),
    supabase.from('messages').select('*').eq('event_id', id).order('created_at', { ascending: false }).order('id', { ascending: false }).limit(PAGE),
    supabase.rpc('event_chat_people', { e: id }),
    supabase.from('direct_blocks').select('blocked_id'),
    supabase.from('messages').select('*').eq('event_id', id).eq('pinned', true).is('deleted_at', null)
      .order('created_at', { ascending: false }).limit(HIGHLIGHTS),
  ]);
  let st = state.data as { title: string; write: boolean; staff: boolean; muted: boolean } | null;
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
  return {
    group: { id, name: st.title, created_by: null, everyone_tag: 'staff', member_group_members: [] } as ChatGroup,
    messages, reactions, other: null as string | null, blocked: false, hidden,
    chat: { id, name: st.title, kind: 'event', member: st.write, admin: st.staff, notify: st.muted ? 'none' : 'all' } as unknown as ChatSummary,
    highlights: ((pins.data as EventMessageRow[] | null) ?? []).map(eventAsGroupMessage).filter((m) => m.pinned && !m.deleted_at && !hidden.has(m.user_id)),
    people: profiles.map((p) => ({ ...p, member: true })),
    admins: new Set<string>(),
    organizers: new Set(profiles.filter((p) => p.organizer).map((p) => p.id)),
    phones: new Map<string, string>(),
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
  };
}

/** Discussion façon WhatsApp (groupe, message direct, discussion d'un événement) : séparateurs de jours, messages d'une
 * même personne regroupés, heure dans la bulle, @citations en couleur, citation qui remonte au message, bouton ↓ avec
 * les nouveaux messages, bandeau des annonces et épinglés qui passe de l'un à l'autre, annonces en carte.
 * Groupe : @tout (selon le groupe) et @annonce (admins et organisateurs). Événement : @toutlemonde, @present et
 * annonces (📣) pour l'organisation et les admins ; la base décide de toute façon. */
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
  const [showInfo, setShowInfo] = useState(false);
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

  const paths = useMemo(() => (data?.messages ?? []).flatMap((m) => (m.deleted_at ? []
    : [m.photo_path, m.audio_path].filter((p): p is string => Boolean(p)))), [data?.messages]);
  useEffect(() => {
    if (!voice) return;
    const timer = setInterval(() => setVoiceNow(Date.now()), 200);
    return () => clearInterval(timer);
  }, [voice]);
  // Messages déjà là à l'ouverture : ils s'affichent tels quels ; seuls les suivants (envoyés ou reçus) montent.
  const [initialIds, setInitialIds] = useState<Set<string> | null>(null);
  if (data && !initialIds) setInitialIds(new Set(data.messages.map((m) => m.id)));
  const shown = useMemo(() => {
    const known = new Set((data?.messages ?? []).map((m) => m.id));
    return [...(data?.messages ?? []), ...pending.filter((m) => !known.has(m.id))];
  }, [data?.messages, pending]);
  const rows = useMemo(() => chatTimeline(shown), [shown]);
  useEffect(() => {
    let alive = true;
    void signedPhotos(paths.filter((p) => !photos.has(p))).then((more) => {
      if (alive && more.size) setPhotos((prev) => new Map([...prev, ...more]));
    }).catch(() => {});
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seuls les nouveaux chemins comptent
  }, [paths]);

  // Nouveau message : on descend s'il est à moi ou si l'on était en bas ; sinon le bouton ↓ le compte.
  const lastId = shown[shown.length - 1]?.id;
  const lastMine = shown[shown.length - 1]?.user_id === me.id;
  const seenLast = useRef<string | undefined>(undefined);
  useEffect(() => {
    if (!lastId || seenLast.current === lastId) return;
    const first = seenLast.current === undefined;
    seenLast.current = lastId;
    if (first || lastMine || nearBottom.current) {
      requestAnimationFrame(() => list.current?.scrollToEnd({ animated: !first }));
    } else setUnseen((n) => n + 1);
  }, [lastId, lastMine]);

  const people = useMemo(() => new Map((data?.people ?? []).map((p) => [p.id, p])), [data?.people]);
  const contacts = useContactNames();
  const personText = usePersonText();
  // Membres d'après group_chat_people : un Guest ne voit pas les autres appartenances dans member_group_members.
  const inside = useMemo(() => {
    const fromPeople = (data?.people ?? []).filter((p) => p.member).map((p) => p.id);
    return fromPeople.length ? fromPeople : (data?.group.member_group_members ?? []).map((m) => m.user_id);
  }, [data?.people, data?.group]);
  const names = useMemo(() => (data?.people ?? []).map((p) => p.display_name).filter(Boolean), [data?.people]);
  const byId = useMemo(() => new Map((data?.messages ?? []).map((m) => [m.id, m])), [data?.messages]);
  const reactionsOf = useMemo(() => {
    const out = new Map<string, Reaction[]>();
    for (const r of data?.reactions ?? []) out.set(r.message_id, [...(out.get(r.message_id) ?? []), r]);
    return out;
  }, [data?.reactions]);
  // Bandeau du haut, façon WhatsApp : annonces puis épinglés, les plus récents d'abord ; un toucher montre le message
  // et passe au suivant.
  const pins = useMemo(() => {
    const all = data?.highlights ?? [];
    return [...all.filter((m) => m.announcement), ...all.filter((m) => !m.announcement)];
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

  /** Montre un message (citation, bandeau) au milieu de l'écran puis le fait clignoter. */
  const showMessage = useCallback((messageId: string) => {
    const index = rows.findIndex((r) => r.key === messageId);
    if (index < 0) return setError('Ce message est plus ancien que ceux affichés.');
    list.current?.scrollToIndex({ index, viewPosition: 0.4, animated: true });
    setFlashId(messageId);
    setTimeout(() => setFlashId((f) => (f === messageId ? null : f)), 1200);
  }, [rows]);

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

  async function sendPhoto() {
    setError(null);
    try {
      const file = await pickPhoto();
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
    const table = kind === 'direct' ? 'direct_message_reactions' : kind === 'event' ? 'message_reactions' : 'group_message_reactions';
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

  if (loading && !data) return <Loading />;
  // Message direct : « Nom du contact · pseudo » (app iPhone), sinon le pseudo de l'autre personne.
  const title = direct && data?.other ? shownName(data.other) : data?.group.name ?? 'Discussion';
  const subtitle = direct ? null : event ? `Discussion · ${data?.people.length ?? 0} personnes` : `${inside.length} membres`;
  const header = (
    <Stack.Screen options={{
      title,
      headerTitle: () => (
        <Pressable accessibilityRole="button" accessibilityLabel={`${title}, infos`} onPress={() => setShowInfo((v) => !v)} style={{ alignItems: 'center' }}>
          <T weight="bold" numberOfLines={1}>{title}</T>
          {subtitle ? <T muted size={11} numberOfLines={1}>{subtitle}</T> : null}
        </Pressable>
      ),
      // « ‹ » seul, comme WhatsApp : le titre garde toute la place. Événement : sa fiche ; ouvert d'une notification : la liste.
      headerLeft: () => <HeaderBack label="" onPress={() => (router.canGoBack() ? router.back() : router.replace(event ? `/event/${id}` : '/chats'))} />,
      headerRight: () => (
        <Pressable accessibilityRole="button" accessibilityLabel={direct ? 'Infos de la conversation' : event ? 'Participants et notifications' : 'Infos du groupe'}
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

  if (showInfo && data && event) {
    return (
      <View style={s.screen}>
        {header}
        <EventChatSettings eventId={id} me={me.id} muted={data.chat?.notify === 'none'} staff={isStaff}
          people={(data.people as Profile[]).map((p): EventPerson => ({ id: p.id, name: shownName(p.id), photo: p.avatar_url,
            rsvp: p.rsvp ?? null, organizer: Boolean(p.organizer), invited: Boolean(p.invited) }))}
          onChanged={reload} />
      </View>
    );
  }

  if (showInfo && data) {
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

  return (
    <SafeAreaView style={s.screen} edges={['bottom']}>
      {header}
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        {/* Entré par sa réponse à un événement (17.11) : d'où il vient et « Quitter », à la première ouverture. */}
        {direct || event ? null : <GroupJoinNote groupId={id} me={me.id} onLeft={reload} />}
        {banner ? (
          <View style={enter('drop')}>
            <Pressable accessibilityRole="button"
              accessibilityLabel={`${banner.announcement ? 'Annonce' : 'Épinglé'}${pins.length > 1 ? ` ${(pinIndex % pins.length) + 1} sur ${pins.length}` : ''} : ${shownName(banner.user_id)}, ${withoutAnnounceTag(banner.body) || 'Photo'}`}
              accessibilityHint={canUnpinBanner ? 'Touche pour voir le message ; appui long pour le retirer' : 'Touche pour voir le message'}
              onPress={() => { showMessage(banner.id); if (pins.length > 1) setPinIndex((i) => i + 1); }}
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
          <FlatList
            ref={list}
            data={rows}
            keyExtractor={(r) => r.key}
            contentContainerStyle={{ paddingHorizontal: 10, paddingVertical: 12 }}
            onScroll={(e) => {
              const { contentOffset, contentSize, layoutMeasurement } = e.nativeEvent;
              const near = contentSize.height - contentOffset.y - layoutMeasurement.height < NEAR_BOTTOM;
              nearBottom.current = near;
              if (near !== atBottom) setAtBottom(near);
              if (near && unseen) setUnseen(0);
            }}
            scrollEventThrottle={100}
            onScrollToIndexFailed={() => list.current?.scrollToEnd({ animated: true })}
            renderItem={({ item: row }) => {
              if ('day' in row) {
                return (
                  <View accessibilityRole="header" style={{ alignItems: 'center', marginVertical: 10 }}>
                    <T size={12} weight="semibold" muted style={{ paddingHorizontal: 12, paddingVertical: 4, borderRadius: 12, backgroundColor: colors.surface, overflow: 'hidden' }}>{row.day}</T>
                  </View>
                );
              }
              const m = row.message;
              const quoted = m.reply_to ? byId.get(m.reply_to) : null;
              return (
                <View style={{ marginTop: row.first ? 8 : 2 }}>
                  <ChatBubble message={m} mine={m.user_id === me.id} me={me.id}
                    author={{ name: shownName(m.user_id), photo: people.get(m.user_id)?.avatar_url ?? null }}
                    quoted={quoted ? { name: shownName(quoted.user_id), author: quoted.user_id,
                      text: quoted.deleted_at ? 'Message supprimé' : quoted.body || (quoted.audio_seconds != null ? '🎤 Message vocal' : '📷 Photo') } : null}
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
              <View style={{ alignItems: 'center', gap: 12, marginTop: 60 }}>
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
              style={({ pressed }) => [{ position: 'absolute', right: 12, bottom: 12, width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center',
                backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.line }, enter('pop'), pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
              <T size={18} weight="bold">⌄</T>
              {unseen ? (
                <View style={{ position: 'absolute', top: -6, right: -6, minWidth: 18, height: 18, paddingHorizontal: 4, borderRadius: 9, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' }}>
                  <T size={11} weight="bold" color={colors.onAccent}>{Math.min(unseen, 99)}</T>
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
          <View style={{ borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 6 }}>
            {announcing ? <T size={12} weight="semibold" color={colors.accent} style={{ paddingHorizontal: 12, paddingTop: 4 }}>📣 Annonce : épinglée en haut et envoyée à tous les invités</T> : null}
            {replyTo ? (
              <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 8, marginHorizontal: 12, marginTop: 6, padding: 8, borderRadius: 10, backgroundColor: colors.fill }, enter('drop')]}>
                <View style={{ width: 3, alignSelf: 'stretch', borderRadius: 2, backgroundColor: colors.accent }} />
                <View style={{ flex: 1 }}>
                  <T size={12} weight="bold" color={colors.accent} numberOfLines={1}>Réponse à {replyTo.user_id === me.id ? 'toi' : shownName(replyTo.user_id)}</T>
                  <T muted size={12} numberOfLines={1}>{replyTo.body || (replyTo.audio_seconds != null ? '🎤 Message vocal' : '📷 Photo')}</T>
                </View>
                <Button small variant="ghost" label="✕" accessibilityLabel="Ne plus répondre à ce message" onPress={() => setReplyTo(null)} />
              </View>
            ) : null}
            <MentionSuggestions suggestions={suggestions} onPick={(sug) => pickMention(sug.label)} />
            {tagNote ? <T muted size={12} style={{ paddingHorizontal: 12, paddingTop: 6 }}>ℹ️ {tagNote}</T> : null}
            {voice ? (
              <View style={[s.row, { padding: 12 }, enter('fade')]}>
                <View style={[{ width: 10, height: 10, borderRadius: 5, backgroundColor: colors.red }, enter('recording')]} />
                <T style={{ flex: 1 }}>🎙 Enregistrement… {voiceClock((voiceNow - voice.started) / 1000)}</T>
                <Button small variant="ghost" label="Annuler" onPress={() => void stopRecording(false)} />
                <Button small label="Envoyer" onPress={() => void stopRecording(true)} />
              </View>
            ) : (
              <View style={[s.row, { padding: 10, alignItems: 'flex-end' }]}>
                {event && isStaff ? (
                  <Button small variant={announcing ? 'primary' : 'secondary'} label="📣" accessibilityLabel={announcing ? 'Annonce activée' : 'Faire une annonce'}
                    onPress={() => setAnnouncing((v) => !v)} />
                ) : null}
                {Platform.OS === 'web' ? <Button small variant="secondary" label="📷" accessibilityLabel="Envoyer une photo" onPress={() => void sendPhoto()} disabled={sending} /> : null}
                <Input inputRef={input} accessibilityLabel="Message"
                  placeholder={announcing ? 'Ton annonce…' : 'Message…'}
                  value={text} onChangeText={(v) => { setText(v); setCursor(v.length); }}
                  onSelectionChange={(e) => setCursor(e.nativeEvent.selection.end)} multiline editable={!sending} maxLength={event ? 4000 : 2000}
                  // Le champ grandit avec le texte : à hauteur fixe, la 2e ligne rognait le haut du texte.
                  onContentSizeChange={onComposerSize}
                  style={[{ flex: 1, height: text ? composerHeight : COMPOSER_MIN, paddingTop: 12, paddingBottom: 12 }, announcing && { borderColor: colors.accent }]} />
                {text.trim() ? (
                  // Bouton rond de la même largeur que le micro : le champ ne rétrécit pas en écrivant (sa hauteur reste juste).
                  <Button small label="➤" accessibilityLabel={announcing ? 'Publier l’annonce' : 'Envoyer'} onPress={() => void send()} loading={sending}
                    style={{ minWidth: 48 }} />
                ) : (
                  <Button small variant="secondary" label="🎤" accessibilityLabel="Enregistrer un message vocal" onPress={() => void startRecording()} disabled={sending}
                    style={{ minWidth: 48 }} />
                )}
              </View>
            )}
          </View>
        ) : event ? (
          <T muted size={13} style={{ padding: 12, textAlign: 'center' }}>Tu peux lire la discussion ; tu pourras écrire une fois l’événement publié et ta place confirmée.</T>
        ) : null}
      </KeyboardAvoidingView>
      <ReportSheet target={reportTarget} onClose={() => setReportTarget(null)} />
      {terms.sheet}
    </SafeAreaView>
  );
}
