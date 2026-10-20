import { Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useRef, useState } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { Avatar, Button, ErrorText, Input, s, T } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery, useRealtime } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { check, must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { Message } from '@/lib/types';

export default function ChatRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <Chat key={id} id={id} />;
}

function Chat({ id }: { id: string }) {
  const me = useMe();
  const { can } = useAuth();
  const isAdmin = can('events.manage_all');
  const [text, setText] = useState('');
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const sendingRef = useRef(false);
  const [older, setOlder] = useState<Message[]>([]);
  const [olderMore, setOlderMore] = useState<boolean | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const loadingOlderRef = useRef(false);
  const followLatest = useRef(true);
  const list = useRef<FlatList<Message>>(null);

  const { data, error: loadError, loading, reload } = useQuery(async () => {
    const [ev, msgs, members, pins] = await Promise.all([
      supabase.from('events').select('title, created_by, event_organizers(user_id)').eq('id', id).single(),
      supabase.from('messages').select('*').eq('event_id', id).order('created_at', { ascending: false }).order('id', { ascending: false }).limit(101),
      supabase.from('profiles').select('id, display_name').eq('status', 'active'),
      supabase.from('messages').select('*').eq('event_id', id).eq('pinned', true).is('deleted_at', null).order('created_at'),
    ]);
    const event = must(ev) as { title: string; created_by: string; event_organizers: { user_id: string }[] };
    return {
      event,
      messages: (must(msgs) as Message[]).slice(0, 100),
      hasMore: msgs.data!.length > 100,
      pinned: must(pins) as Message[],
      members: must(members) as { id: string; display_name: string }[],
      canModerate: isAdmin || event.created_by === me.id || event.event_organizers.some((o) => o.user_id === me.id),
    };
  }, [id]);

  useRealtime(`chat-${id}`, [{ table: 'messages', filter: `event_id=eq.${id}` }], reload);

  const names = useMemo(() => new Map((data?.members ?? []).map((m) => [m.id, m.display_name])), [data?.members]);
  const messages = useMemo(() => {
    const unique = new Map([...older, ...(data?.messages ?? [])].map((m) => [m.id, m]));
    return [...unique.values()].filter((m) => !m.deleted_at).sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
  }, [older, data?.messages]);
  const byId = useMemo(() => new Map(messages.map((m) => [m.id, m])), [messages]);
  const pinned = data?.pinned ?? [];

  async function loadOlder() {
    if (loadingOlderRef.current || !data) return;
    const cursor = [...older, ...data.messages].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id))[0];
    if (!cursor) return;
    loadingOlderRef.current = true;
    followLatest.current = false;
    setLoadingOlder(true);
    setError(null);
    try {
      const page = must(await supabase.from('messages').select('*').eq('event_id', id)
        .or(`created_at.lt.${cursor.created_at},and(created_at.eq.${cursor.created_at},id.lt.${cursor.id})`)
        .order('created_at', { ascending: false }).order('id', { ascending: false }).limit(101)) as Message[];
      setOlder((previous) => [...previous, ...data.messages, ...page.slice(0, 100)]);
      setOlderMore(page.length > 100);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      loadingOlderRef.current = false;
      setLoadingOlder(false);
    }
  }

  async function send() {
    const body = text.trim();
    if (!body || sendingRef.current) return;
    sendingRef.current = true;
    setSending(true);
    setError(null);
    // « @Prénom » dans le texte -> mention (notifiée même en mode « Mentions »)
    const mentions = (data?.members ?? [])
      .filter((m) => m.display_name && body.toLowerCase().includes(`@${m.display_name.toLowerCase()}`))
      .map((m) => m.id);
    try {
      check(await supabase.from('messages').insert({ event_id: id, user_id: me.id, body, reply_to: replyTo?.id ?? null, mentions }));
      setText('');
      setReplyTo(null);
      followLatest.current = true;
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  async function togglePin(m: Message) {
    const { error } = await supabase.from('messages').update({ pinned: !m.pinned }).eq('id', m.id);
    setError(error?.message ?? null);
    reload();
  }

  async function remove(m: Message) {
    const { error } = await supabase.from('messages').update({ deleted_at: new Date().toISOString() }).eq('id', m.id);
    setError(error?.message ?? null);
    if (!error) setOlder((previous) => previous.filter((row) => row.id !== m.id));
    reload();
  }

  return (
    <SafeAreaView style={s.screen} edges={['bottom']}>
      <Stack.Screen options={{ title: data?.event.title ?? 'Discussion' }} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        {pinned.map((m) => (
          <View key={m.id} style={{ margin: 12, marginBottom: 0, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface }}>
            <T size={13} color={colors.textSoft}>
              <T size={13} weight="bold" color={colors.accent}>Épinglé · </T>
              {names.get(m.user_id)} : {m.body}
            </T>
          </View>
        ))}
        <FlatList
          ref={list}
          data={messages}
          keyExtractor={(m) => m.id}
          contentContainerStyle={{ padding: 16, gap: 14 }}
          onContentSizeChange={() => { if (followLatest.current) list.current?.scrollToEnd({ animated: false }); }}
          onScroll={(event) => {
            const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
            followLatest.current = contentSize.height - contentOffset.y - layoutMeasurement.height < 100;
          }}
          scrollEventThrottle={100}
          ListHeaderComponent={(olderMore ?? data?.hasMore) ? <Button small variant="secondary" label="Messages précédents" onPress={loadOlder} loading={loadingOlder} /> : null}
          renderItem={({ item: m }) => {
            const mine = m.user_id === me.id;
            const quoted = m.reply_to ? byId.get(m.reply_to) : null;
            return (
              <Pressable
                onLongPress={() => setReplyTo(m)}
                accessibilityHint="Appui long pour répondre"
                style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-end', justifyContent: mine ? 'flex-end' : 'flex-start' }}
              >
                {!mine ? <Avatar id={m.user_id} name={names.get(m.user_id) ?? '?'} /> : null}
                <View style={{ maxWidth: '78%', gap: 4, alignItems: mine ? 'flex-end' : 'flex-start' }}>
                  {!mine ? <T size={12} weight="bold" color={colors.lavender}>{names.get(m.user_id) ?? '?'}</T> : null}
                  <View style={{ padding: 10, borderRadius: 16, backgroundColor: mine ? colors.accent : colors.surface, gap: 6 }}>
                    {quoted ? (
                      <View style={{ padding: 6, borderRadius: 8, backgroundColor: mine ? '#BFD93F' : colors.surface2 }}>
                        <T size={12} color={mine ? colors.onAccent : colors.muted} numberOfLines={2}>
                          ↪ {names.get(quoted.user_id)} : {quoted.body}
                        </T>
                      </View>
                    ) : null}
                    <T size={15} color={mine ? colors.onAccent : colors.text}>{m.body}</T>
                  </View>
                  <View style={s.row}>
                    <T muted size={11}>{formatMessageTime(m.created_at)}</T>
                    {data?.canModerate ? (
                      <Pressable onPress={() => togglePin(m)} accessibilityRole="button">
                        <T muted size={11}>{m.pinned ? 'Désépingler' : 'Épingler'}</T>
                      </Pressable>
                    ) : null}
                    {mine || can('chat.moderate') ? (
                      <Pressable onPress={() => remove(m)} accessibilityRole="button">
                        <T muted size={11}>Supprimer</T>
                      </Pressable>
                    ) : null}
                  </View>
                </View>
              </Pressable>
            );
          }}
          ListEmptyComponent={<T muted style={{ textAlign: 'center', marginTop: 40 }}>{loading ? 'Chargement…' : loadError ? 'La discussion n’a pas pu être chargée.' : 'Aucun message pour l’instant.'}</T>}
        />
        <ErrorText error={error ?? loadError} />
        {loadError ? <Button small label="Réessayer" variant="secondary" onPress={reload} /> : null}
        {replyTo ? (
          <View style={[s.rowBetween, { paddingHorizontal: 12, paddingTop: 8 }]}>
            <T muted size={12} numberOfLines={1} style={{ flex: 1 }}>↪ Réponse à {names.get(replyTo.user_id)} : {replyTo.body}</T>
            <Button small variant="ghost" label="✕" onPress={() => setReplyTo(null)} />
          </View>
        ) : null}
        <View style={[s.row, { padding: 12, borderTopWidth: 1, borderTopColor: colors.line }]}>
          <Input
            accessibilityLabel="Message"
            placeholder="Écrire un message… (@prénom pour mentionner)"
            value={text}
            onChangeText={setText}
            multiline
            editable={!sending}
            maxLength={4000}
            style={{ flex: 1, height: undefined, minHeight: 46, maxHeight: 120, paddingTop: 12 }}
          />
          <Button label="Envoyer" onPress={send} disabled={!text.trim() || !data} loading={sending} small />
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}
