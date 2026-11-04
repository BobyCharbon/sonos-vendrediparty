import { router, Stack } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, View, type TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatBubble } from './ChatBubble';
import { DirectChatSettings } from './DirectChatSettings';
import { GroupChatSettings } from './GroupChatSettings';
import { MentionSuggestions } from './MentionSuggestions';
import { ReportSheet } from './ReportSheet';
import { useTermsGate } from './TermsSheet';
import { usePersonText } from './PersonName';
import { Button, ErrorText, HeaderBack, Input, Loading, s, T } from './ui';
import { useMe } from '@/lib/auth';
import { useContactNames } from '@/lib/contactNames';
import { directAsGroupMessage, insertMention, isAnnouncement, mentionQuery, mentionsIn, mentionSuggestions, newMessageId, pickPhoto, shrinkPhoto, signedPhotos, startVoice, uploadChatAudio, uploadChatPhoto, voiceClock,
  type ChatSummary, type DirectMessageRow, type EveryoneBy, type GroupMessage, type NotifyLevel, type Reaction, type VoiceRecording } from '@/lib/chats';
import { useQuery, useRealtime } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import { roleRank, siteAdminRank } from '@/lib/roles';
import { enter } from '@/lib/motion';
import { dbMessage, type ReportTarget } from '@/lib/moderation';

const PAGE = 150;
/** Annonces et messages épinglés lus à part : le bandeau du haut les garde même au-delà des derniers messages. */
const HIGHLIGHTS = 20;

type Profile = { id: string; display_name: string; avatar_url: string | null; member?: boolean };
type ChatGroup = { id: string; name: string; created_by: string | null; everyone_tag?: EveryoneBy; member_group_members: { user_id: string }[] };

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
    blocked: ((blocks.data as { blocked_id: string }[] | null) ?? []).some((b) => b.blocked_id === other),
    chat: { id, name: group.name, kind: 'direct', member: true, admin: false, notify } as ChatSummary,
    highlights: ((pins.data as DirectMessageRow[] | null) ?? []).map(directAsGroupMessage).filter((m) => m.pinned && !m.deleted_at),
    people: profiles,
    admins: new Set<string>(), organizers: new Set<string>(), phones: new Map<string, string>(),
  };
}

/** Discussion d'un groupe (avis n°10) : texte, photos, réactions, réponses, @citations (suggestions des membres en
 * tapant @, @tout pour tout le groupe), @annonce (épinglée en surbrillance en haut) ; les admins épinglent, retirent
 * les annonces et suppriment. Un membre écrit ; un compte qui voit le groupe sans en faire partie ne fait que lire. */
export function GroupChat({ id, direct = false }: { id: string; direct?: boolean }) {
  const me = useMe();
  const [text, setText] = useState('');
  // Place du curseur (suggestions de l'@ en cours de frappe) et champ, pour y revenir après un choix.
  const [cursor, setCursor] = useState(0);
  const input = useRef<TextInput>(null);
  const [bannerMenu, setBannerMenu] = useState(false);
  const [replyTo, setReplyTo] = useState<GroupMessage | null>(null);
  const [sending, setSending] = useState(false);
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
  const list = useRef<FlatList<GroupMessage>>(null);

  const { data, loading, error: loadError, reload } = useQuery(async () => {
    if (direct) return loadDirect(id, me.id);
    const [group, msgs, people, admins, chats, phones, pins, organizers] = await Promise.all([
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
    ]);
    const messages = (must(msgs) as GroupMessage[]).reverse();
    const reactions = messages.length
      ? must(await supabase.from('group_message_reactions').select('message_id, user_id, emoji').in('message_id', messages.map((m) => m.id))) as Reaction[]
      : [];
    const chat = ((chats.data as ChatSummary[] | null) ?? []).find((c) => c.id === id) ?? null;
    return {
      group: must(group) as ChatGroup,
      messages, reactions, chat, other: null as string | null, blocked: false,
      highlights: ((pins.data as GroupMessage[] | null) ?? []).filter((m) => m.pinned && !m.deleted_at),
      people: must(people) as Profile[],
      admins: new Set((must(admins) as { user_id: string }[]).map((a) => a.user_id)),
      organizers: new Set(((organizers.data as { user_id: string }[] | null) ?? []).map((o) => o.user_id)),
      phones: new Map(((phones.data as { id: string; phone: string }[] | null) ?? []).map((p) => [p.id, p.phone])),
    };
  }, [id, direct]);

  useRealtime(`${direct ? 'direct' : 'group'}-chat-${id}`, direct ? [
    { table: 'direct_messages', filter: `chat_id=eq.${id}` },
    { table: 'direct_message_reactions' },
  ] : [
    { table: 'group_messages', filter: `group_id=eq.${id}` },
    { table: 'group_message_reactions' },
  ], reload);

  const member = Boolean(data?.chat?.member);
  const isAdmin = Boolean(data?.chat?.admin);
  // Admins et organisateurs du groupe : annonces (@annonce) et leur retrait ; @tout selon le choix du groupe.
  const isStaff = isAdmin || (member && Boolean(data?.organizers.has(me.id)));
  const everyone = data?.group.everyone_tag ?? 'all';
  const canEveryone = !direct && (everyone === 'all' || isStaff);
  useEffect(() => {
    if (!member || !data?.messages.length) return;
    void (direct ? supabase.rpc('mark_direct_read', { chat: id }) : supabase.rpc('mark_group_read', { grp: id }));
  }, [member, id, direct, data?.messages]);

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
  useEffect(() => {
    let alive = true;
    void signedPhotos(paths.filter((p) => !photos.has(p))).then((more) => {
      if (alive && more.size) setPhotos((prev) => new Map([...prev, ...more]));
    }).catch(() => {});
    return () => { alive = false; };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seuls les nouveaux chemins comptent
  }, [paths]);

  const people = useMemo(() => new Map((data?.people ?? []).map((p) => [p.id, p])), [data?.people]);
  const contacts = useContactNames();
  const personText = usePersonText();
  // Membres d'après group_chat_people : un Guest ne voit pas les autres appartenances dans member_group_members.
  const inside = useMemo(() => {
    const fromPeople = (data?.people ?? []).filter((p) => p.member).map((p) => p.id);
    return fromPeople.length ? fromPeople : (data?.group.member_group_members ?? []).map((m) => m.user_id);
  }, [data?.people, data?.group]);
  const byId = useMemo(() => new Map((data?.messages ?? []).map((m) => [m.id, m])), [data?.messages]);
  const reactionsOf = useMemo(() => {
    const out = new Map<string, Reaction[]>();
    for (const r of data?.reactions ?? []) out.set(r.message_id, [...(out.get(r.message_id) ?? []), r]);
    return out;
  }, [data?.reactions]);
  // Bandeau du haut : la dernière annonce (surbrillance), sinon le dernier message épinglé.
  const highlights = data?.highlights ?? [];
  const announcements = highlights.filter((m) => m.announcement);
  const banner = announcements[0] ?? highlights[0] ?? null;
  const bannerMore = (banner?.announcement ? announcements.length : highlights.length) - 1;
  const canUnpinBanner = Boolean(banner) && (isAdmin || (isStaff && Boolean(banner?.announcement)));
  const nameOf = (uid: string) => people.get(uid)?.display_name ?? '?';
  // Affichage (pas les @) : app iPhone, « Nom du contact · pseudo » ; ailleurs le pseudo.
  const shownName = (uid: string) => personText(uid, nameOf(uid));
  // Suggestions de l'@ : membres du groupe (moi exclu) filtrés par les lettres tapées, puis @tout et @annonce.
  const typing = mentionQuery(text, cursor);
  const suggestions = useMemo(() => (typing === null || direct ? [] : mentionSuggestions(typing,
    inside.filter((u) => u !== me.id).map((u) => ({ id: u, display_name: nameOf(u), avatar_url: people.get(u)?.avatar_url ?? null })),
    { everyone: canEveryone, announce: isStaff }, contacts)),
  // eslint-disable-next-line react-hooks/exhaustive-deps -- nameOf lit people
  [typing, inside, people, me.id, canEveryone, isStaff, contacts, direct]);
  // Prévenu avant l'envoi : un simple membre n'annonce pas (message normal), @tout peut être réservé par le groupe.
  const tagNote = direct ? null : isAnnouncement(text) && !isStaff
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

  /** Texte, photo ou vocal : la bulle apparaît tout de suite, le champ se vide ; en cas d'échec, le texte revient. */
  async function send(photoPath: string | null = null, audio: { blob: Blob; seconds: number; ext: 'm4a' | 'webm' } | null = null) {
    const body = audio ? '' : text.trim();
    if (!body && !photoPath && !audio) return;
    if (!terms.accepted && !(await terms.ensure())) return;
    const quoted = replyTo;
    const messageId = newMessageId();
    const announced = isStaff && isAnnouncement(body);
    const draft: GroupMessage = { id: messageId, group_id: id, user_id: me.id, body, photo_path: photoPath, reply_to: quoted?.id ?? null,
      mentions: [], mention_all: false, pinned: announced, announcement: announced, created_at: new Date().toISOString(), edited_at: null, deleted_at: null,
      deleted_by_admin: false, audio_path: null, audio_seconds: audio ? Math.round(audio.seconds * 10) / 10 : null, pending: true };
    const known = new Set((data?.messages ?? []).map((m) => m.id));
    setPending((list) => [...list.filter((m) => !known.has(m.id)), draft]);
    if (!audio) { setText(''); setCursor(0); }
    setReplyTo(null);
    setError(null);
    const tagged = mentionsIn(body, inside.filter((u) => u !== me.id).map((u) => ({ id: u, display_name: nameOf(u) })));
    try {
      const audioPath = audio ? await uploadChatAudio(id, audio) : null;
      const { error } = direct
        ? await supabase.from('direct_messages').insert({
          id: messageId, chat_id: id, body, photo_path: photoPath, reply_to: quoted?.id ?? null, audio_path: audioPath, audio_seconds: draft.audio_seconds,
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
    const table = direct ? 'direct_message_reactions' : 'group_message_reactions';
    const { error } = mineAlready
      ? await supabase.from(table).delete().eq('message_id', m.id).eq('user_id', me.id).eq('emoji', emoji)
      : await supabase.from(table).insert({ message_id: m.id, emoji });
    if (error) setError('La réaction n’a pas pu être enregistrée.');
    reload();
  }

  async function rpc(name: 'pin_group_message' | 'delete_group_message', args: Record<string, unknown>) {
    const fn = direct ? (name === 'pin_group_message' ? 'pin_direct_message' : 'delete_direct_message') : name;
    const { error } = await supabase.rpc(fn, args);
    if (error) setError(error.message.replace(/^\w+: /, ''));
    reload();
  }

  if (loading && !data) return <Loading />;
  // Message direct : « Nom du contact · pseudo » (app iPhone), sinon le pseudo de l'autre personne.
  const title = direct && data?.other ? shownName(data.other) : data?.group.name ?? 'Discussion';
  const header = (
    <Stack.Screen options={{
      title,
      // « ‹ » seul, comme WhatsApp : le nom du groupe garde toute la place (ouvert depuis une notification : la liste).
      headerLeft: () => <HeaderBack label="" onPress={() => (router.canGoBack() ? router.back() : router.replace('/chats'))} />,
      headerRight: () => (
        <Pressable accessibilityRole="button" accessibilityLabel={direct ? 'Infos de la conversation' : 'Infos du groupe'} hitSlop={8} onPress={() => setShowInfo((v) => !v)} style={{ paddingHorizontal: 12 }}>
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
        {banner ? (
          <View style={enter('drop')}>
            <Pressable accessibilityRole="button" accessibilityLabel={`${banner.announcement ? 'Annonce' : 'Épinglé'} : ${shownName(banner.user_id)}, ${banner.body || 'Photo'}`}
              accessibilityHint={canUnpinBanner ? 'Appui long pour la retirer' : undefined}
              onPress={() => {
                const index = data!.messages.findIndex((m) => m.id === banner.id);
                if (index >= 0) list.current?.scrollToIndex({ index, viewPosition: 0.3 });
              }}
              onLongPress={() => canUnpinBanner && setBannerMenu((v) => !v)}
              style={{ margin: 12, marginBottom: 0, padding: 12, borderRadius: radius.md, gap: 4,
                backgroundColor: banner.announcement ? colors.accentDim : colors.surface,
                borderWidth: banner.announcement ? 1 : 0, borderColor: colors.accent }}>
              <T size={13} weight="bold" color={colors.accent}>
                {banner.announcement ? '📣 Annonce' : '📌 Épinglé'}{bannerMore > 0 ? ` · +${bannerMore}` : ''}
              </T>
              <T size={banner.announcement ? 15 : 13} color={banner.announcement ? colors.text : colors.textSoft} numberOfLines={3}>
                <T size={banner.announcement ? 15 : 13} weight="semibold" color={banner.announcement ? colors.text : colors.textSoft}>{shownName(banner.user_id)} : </T>
                {banner.body || '📷 Photo'}
              </T>
            </Pressable>
            {bannerMenu && canUnpinBanner ? (
              <View style={[s.row, { marginHorizontal: 12, marginTop: 6 }, enter('drop')]}>
                <Button small variant="secondary" label={banner.announcement ? 'Retirer l’annonce' : 'Désépingler'}
                  onPress={() => { setBannerMenu(false); void rpc('pin_group_message', { msg: banner.id, pin: false }); }} />
                <Button small variant="ghost" label="Annuler" onPress={() => setBannerMenu(false)} />
              </View>
            ) : null}
          </View>
        ) : null}
        <FlatList
          ref={list}
          data={shown}
          keyExtractor={(m) => m.id}
          contentContainerStyle={{ padding: 16, gap: 14 }}
          onContentSizeChange={() => list.current?.scrollToEnd({ animated: false })}
          onScrollToIndexFailed={() => list.current?.scrollToEnd({ animated: true })}
          renderItem={({ item: m }) => {
            const quoted = m.reply_to ? byId.get(m.reply_to) : null;
            return (
              <ChatBubble message={m} mine={m.user_id === me.id} me={me.id}
                author={{ name: shownName(m.user_id), photo: people.get(m.user_id)?.avatar_url ?? null }}
                quoted={quoted ? { name: shownName(quoted.user_id), text: quoted.deleted_at ? 'Message supprimé' : quoted.body || '📷 Photo' } : null}
                photoUrl={m.photo_path ? photos.get(m.photo_path) ?? null : null}
                audioUrl={m.audio_path ? photos.get(m.audio_path) ?? null : null}
                reactions={reactionsOf.get(m.id) ?? []} canWrite={member} isAdmin={isAdmin} isStaff={isStaff} canPin={direct || isAdmin}
                onReply={() => setReplyTo(m)} onReact={(e) => void react(m, e)}
                onPin={() => void rpc('pin_group_message', { msg: m.id, pin: !m.pinned })}
                onDelete={() => void rpc('delete_group_message', { msg: m.id })}
                onReport={() => setReportTarget({ kind: direct ? 'direct_message' : 'group_message', id: m.id, label: `le message de ${shownName(m.user_id)}` })}
                fresh={!!initialIds && !initialIds.has(m.id)} />
            );
          }}
          ListEmptyComponent={
            <View style={{ alignItems: 'center', gap: 12, marginTop: 40 }}>
              <T muted style={{ textAlign: 'center' }}>{loadError ? 'La discussion n’a pas pu être chargée.' : 'Aucun message pour l’instant. Lance la discussion !'}</T>
              {/* Groupe tout neuf (créé depuis Discussions) : y ajouter du monde, dans Réglages › Groupes. */}
              {!loadError && member && inside.length <= 1 && data?.group.created_by === me.id ? (
                <Button small label="Ajouter des membres" onPress={() => router.push(`/groups?open=${id}`)} />
              ) : null}
            </View>
          }
        />
        <ErrorText error={error ?? loadError} />
        {data?.blocked ? (
          // Message direct : j'ai bloqué cette personne ; l'historique reste, l'écriture revient en la débloquant.
          <T muted size={13} style={{ padding: 12, textAlign: 'center' }}>Tu as bloqué {title}. Débloque-le dans Infos pour lui écrire.</T>
        ) : member ? (
          <>
            {replyTo ? (
              <View style={[s.rowBetween, { paddingHorizontal: 12, paddingTop: 8 }, enter('drop')]}>
                <T muted size={12} numberOfLines={1} style={{ flex: 1 }}>↪ Réponse à {shownName(replyTo.user_id)} : {replyTo.body || '📷 Photo'}</T>
                <Button small variant="ghost" label="✕" onPress={() => setReplyTo(null)} />
              </View>
            ) : null}
            <MentionSuggestions suggestions={suggestions} onPick={(sug) => pickMention(sug.label)} />
            {tagNote ? <T muted size={12} style={{ paddingHorizontal: 12, paddingTop: 6 }}>ℹ️ {tagNote}</T> : null}
            {voice ? (
              <View style={[s.row, { padding: 12, borderTopWidth: 1, borderTopColor: colors.line }, enter('fade')]}>
                <View style={[{ width: 10, height: 10, borderRadius: 5, backgroundColor: colors.red }, enter('recording')]} />
                <T style={{ flex: 1 }}>🎙 Enregistrement… {voiceClock((voiceNow - voice.started) / 1000)}</T>
                <Button small variant="ghost" label="Annuler" onPress={() => void stopRecording(false)} />
                <Button small label="Envoyer" onPress={() => void stopRecording(true)} />
              </View>
            ) : (
              <View style={[s.row, { padding: 12, borderTopWidth: 1, borderTopColor: colors.line }]}>
                {Platform.OS === 'web' ? <Button small variant="secondary" label="📷" onPress={() => void sendPhoto()} disabled={sending} /> : null}
                <Input inputRef={input} accessibilityLabel="Message" placeholder={direct ? 'Message…' : 'Message… (@ pour citer, @tout, @annonce)'}
                  value={text} onChangeText={(v) => { setText(v); setCursor(v.length); }}
                  onSelectionChange={(e) => setCursor(e.nativeEvent.selection.end)} multiline editable={!sending} maxLength={2000}
                  style={{ flex: 1, height: undefined, minHeight: 46, maxHeight: 120, paddingTop: 12 }} />
                {text.trim() ? (
                  <Button small label="Envoyer" onPress={() => void send()} loading={sending} />
                ) : (
                  <Button small variant="secondary" label="🎤" onPress={() => void startRecording()} disabled={sending} />
                )}
              </View>
            )}
          </>
        ) : null}
      </KeyboardAvoidingView>
      <ReportSheet target={reportTarget} onClose={() => setReportTarget(null)} />
      {terms.sheet}
    </SafeAreaView>
  );
}
