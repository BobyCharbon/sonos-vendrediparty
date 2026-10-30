import { router, Stack } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { ChatBubble } from './ChatBubble';
import { GroupChatSettings } from './GroupChatSettings';
import { Button, ErrorText, HeaderBack, Input, Loading, s, T } from './ui';
import { useMe } from '@/lib/auth';
import { mentionsIn, newMessageId, pickPhoto, shrinkPhoto, signedPhotos, startVoice, uploadChatAudio, uploadChatPhoto, voiceClock,
  type ChatSummary, type GroupMessage, type Reaction, type VoiceRecording } from '@/lib/chats';
import { useQuery, useRealtime } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import { roleRank } from '@/lib/types';

const PAGE = 150;

type Profile = { id: string; display_name: string; avatar_url: string | null; member?: boolean };

/** Discussion d'un groupe (avis n°10) : texte, photos, réactions, réponses, @citations ; les admins épinglent
 * et suppriment. Un membre écrit ; un compte qui voit le groupe sans en faire partie ne fait que lire. */
export function GroupChat({ id }: { id: string }) {
  const me = useMe();
  const [text, setText] = useState('');
  const [replyTo, setReplyTo] = useState<GroupMessage | null>(null);
  const [sending, setSending] = useState(false);
  // Messages envoyés pas encore revenus de la base : affichés tout de suite (« Envoi… »), comme Snapchat.
  const [pending, setPending] = useState<GroupMessage[]>([]);
  const [voice, setVoice] = useState<{ rec: VoiceRecording; started: number } | null>(null);
  const [voiceNow, setVoiceNow] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const [photos, setPhotos] = useState<Map<string, string>>(new Map());
  const list = useRef<FlatList<GroupMessage>>(null);

  const { data, loading, error: loadError, reload } = useQuery(async () => {
    const [group, msgs, people, admins, chats, phones] = await Promise.all([
      supabase.from('member_groups').select('id, name, created_by, member_group_members(user_id)').eq('id', id).single(),
      supabase.from('group_messages').select('*').eq('group_id', id).order('created_at', { ascending: false }).limit(PAGE),
      supabase.rpc('group_chat_people', { grp: id }),  // un Guest ne lit pas le profil d'un admin dans profiles
      supabase.from('group_admins').select('user_id').eq('group_id', id),
      supabase.rpc('my_chats'),
      supabase.rpc('group_chat_phones', { grp: id }),
    ]);
    const messages = (must(msgs) as GroupMessage[]).reverse();
    const reactions = messages.length
      ? must(await supabase.from('group_message_reactions').select('message_id, user_id, emoji').in('message_id', messages.map((m) => m.id))) as Reaction[]
      : [];
    const chat = ((chats.data as ChatSummary[] | null) ?? []).find((c) => c.id === id) ?? null;
    return {
      group: must(group) as { id: string; name: string; created_by: string | null; member_group_members: { user_id: string }[] },
      messages, reactions, chat,
      people: must(people) as Profile[],
      admins: new Set((must(admins) as { user_id: string }[]).map((a) => a.user_id)),
      phones: new Map(((phones.data as { id: string; phone: string }[] | null) ?? []).map((p) => [p.id, p.phone])),
    };
  }, [id]);

  useRealtime(`group-chat-${id}`, [
    { table: 'group_messages', filter: `group_id=eq.${id}` },
    { table: 'group_message_reactions' },
  ], reload);

  const member = Boolean(data?.chat?.member);
  const isAdmin = Boolean(data?.chat?.admin);
  useEffect(() => { if (member && data?.messages.length) void supabase.rpc('mark_group_read', { grp: id }); }, [member, id, data?.messages]);

  const paths = useMemo(() => (data?.messages ?? []).flatMap((m) => (m.deleted_at ? []
    : [m.photo_path, m.audio_path].filter((p): p is string => Boolean(p)))), [data?.messages]);
  useEffect(() => {
    if (!voice) return;
    const timer = setInterval(() => setVoiceNow(Date.now()), 200);
    return () => clearInterval(timer);
  }, [voice]);
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
  const pinned = (data?.messages ?? []).filter((m) => m.pinned && !m.deleted_at);
  const nameOf = (uid: string) => people.get(uid)?.display_name ?? '?';

  /** Texte, photo ou vocal : la bulle apparaît tout de suite, le champ se vide ; en cas d'échec, le texte revient. */
  async function send(photoPath: string | null = null, audio: { blob: Blob; seconds: number; ext: 'm4a' | 'webm' } | null = null) {
    const body = audio ? '' : text.trim();
    if (!body && !photoPath && !audio) return;
    const quoted = replyTo;
    const messageId = newMessageId();
    const draft: GroupMessage = { id: messageId, group_id: id, user_id: me.id, body, photo_path: photoPath, reply_to: quoted?.id ?? null,
      mentions: [], mention_all: false, pinned: false, created_at: new Date().toISOString(), edited_at: null, deleted_at: null,
      deleted_by_admin: false, audio_path: null, audio_seconds: audio ? Math.round(audio.seconds * 10) / 10 : null, pending: true };
    const known = new Set((data?.messages ?? []).map((m) => m.id));
    setPending((list) => [...list.filter((m) => !known.has(m.id)), draft]);
    if (!audio) setText('');
    setReplyTo(null);
    setError(null);
    const tagged = mentionsIn(body, inside.filter((u) => u !== me.id).map((u) => ({ id: u, display_name: nameOf(u) })));
    try {
      const audioPath = audio ? await uploadChatAudio(id, audio) : null;
      const { error } = await supabase.from('group_messages').insert({
        id: messageId, group_id: id, body, photo_path: photoPath, reply_to: quoted?.id ?? null, mentions: tagged.mentions,
        mention_all: tagged.all && isAdmin, audio_path: audioPath, audio_seconds: draft.audio_seconds,
      });
      if (error) throw new Error('Le message n’a pas pu être envoyé. Réessaie.');
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
    const { error } = mineAlready
      ? await supabase.from('group_message_reactions').delete().eq('message_id', m.id).eq('user_id', me.id).eq('emoji', emoji)
      : await supabase.from('group_message_reactions').insert({ message_id: m.id, emoji });
    if (error) setError('La réaction n’a pas pu être enregistrée.');
    reload();
  }

  async function rpc(name: 'pin_group_message' | 'delete_group_message', args: Record<string, unknown>) {
    const { error } = await supabase.rpc(name, args);
    if (error) setError(error.message.replace(/^\w+: /, ''));
    reload();
  }

  if (loading && !data) return <Loading />;
  const title = data?.group.name ?? 'Discussion';
  const header = (
    <Stack.Screen options={{
      title,
      // « ‹ » seul, comme WhatsApp : le nom du groupe garde toute la place (ouvert depuis une notification : la liste).
      headerLeft: () => <HeaderBack label="" onPress={() => (router.canGoBack() ? router.back() : router.replace('/chats'))} />,
      headerRight: () => (
        <Pressable accessibilityRole="button" accessibilityLabel="Infos du groupe" hitSlop={8} onPress={() => setShowInfo((v) => !v)} style={{ paddingHorizontal: 12 }}>
          <T weight="semibold" color={colors.accent}>{showInfo ? 'Fermer' : 'Infos'}</T>
        </Pressable>
      ),
    }} />
  );

  if (showInfo && data) {
    return (
      <View style={s.screen}>
        {header}
        <GroupChatSettings groupId={id} notify={data.chat?.notify ?? 'mentions'} member={member}
          canNameAdmins={data.group.created_by === me.id || roleRank(me.role) >= 3}
          members={inside.map((u) => ({ id: u, name: nameOf(u), photo: people.get(u)?.avatar_url ?? null,
            admin: data.admins.has(u), creator: u === data.group.created_by, phone: data.phones.get(u) ?? null }))}
          onChanged={reload} />
      </View>
    );
  }

  return (
    <SafeAreaView style={s.screen} edges={['bottom']}>
      {header}
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        {pinned.length ? (
          <Pressable accessibilityRole="button" onPress={() => list.current?.scrollToIndex({ index: data!.messages.indexOf(pinned[pinned.length - 1]), viewPosition: 0.3 })}
            style={{ margin: 12, marginBottom: 0, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface }}>
            <T size={13} color={colors.textSoft} numberOfLines={2}>
              <T size={13} weight="bold" color={colors.accent}>📌 Épinglé · </T>
              {nameOf(pinned[pinned.length - 1].user_id)} : {pinned[pinned.length - 1].body || '📷 Photo'}
            </T>
          </Pressable>
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
                author={{ name: nameOf(m.user_id), photo: people.get(m.user_id)?.avatar_url ?? null }}
                quoted={quoted ? { name: nameOf(quoted.user_id), text: quoted.deleted_at ? 'Message supprimé' : quoted.body || '📷 Photo' } : null}
                photoUrl={m.photo_path ? photos.get(m.photo_path) ?? null : null}
                audioUrl={m.audio_path ? photos.get(m.audio_path) ?? null : null}
                reactions={reactionsOf.get(m.id) ?? []} canWrite={member} isAdmin={isAdmin}
                onReply={() => setReplyTo(m)} onReact={(e) => void react(m, e)}
                onPin={() => void rpc('pin_group_message', { msg: m.id, pin: !m.pinned })}
                onDelete={() => void rpc('delete_group_message', { msg: m.id })} />
            );
          }}
          ListEmptyComponent={<T muted style={{ textAlign: 'center', marginTop: 40 }}>{loadError ? 'La discussion n’a pas pu être chargée.' : 'Aucun message pour l’instant. Lance la discussion !'}</T>}
        />
        <ErrorText error={error ?? loadError} />
        {member ? (
          <>
            {replyTo ? (
              <View style={[s.rowBetween, { paddingHorizontal: 12, paddingTop: 8 }]}>
                <T muted size={12} numberOfLines={1} style={{ flex: 1 }}>↪ Réponse à {nameOf(replyTo.user_id)} : {replyTo.body || '📷 Photo'}</T>
                <Button small variant="ghost" label="✕" onPress={() => setReplyTo(null)} />
              </View>
            ) : null}
            {voice ? (
              <View style={[s.row, { padding: 12, borderTopWidth: 1, borderTopColor: colors.line }]}>
                <View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: colors.red }} />
                <T style={{ flex: 1 }}>🎙 Enregistrement… {voiceClock((voiceNow - voice.started) / 1000)}</T>
                <Button small variant="ghost" label="Annuler" onPress={() => void stopRecording(false)} />
                <Button small label="Envoyer" onPress={() => void stopRecording(true)} />
              </View>
            ) : (
              <View style={[s.row, { padding: 12, borderTopWidth: 1, borderTopColor: colors.line }]}>
                {Platform.OS === 'web' ? <Button small variant="secondary" label="📷" onPress={() => void sendPhoto()} disabled={sending} /> : null}
                <Input accessibilityLabel="Message" placeholder={isAdmin ? 'Message… (@surnom, @tout)' : 'Message… (@surnom pour citer)'}
                  value={text} onChangeText={setText} multiline editable={!sending} maxLength={2000}
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
    </SafeAreaView>
  );
}
