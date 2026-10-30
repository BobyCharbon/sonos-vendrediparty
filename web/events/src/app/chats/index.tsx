import { router, Stack } from 'expo-router';
import { FlatList, Pressable, View } from 'react-native';

import { Avatar, Empty, ErrorText, Loading, s, T } from '@/components/ui';
import type { ChatSummary } from '@/lib/chats';
import { useQuery, useRealtime } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

/** Discussions (avis n°10) : une discussion par groupe, la plus récente en haut, comme WhatsApp. */
export default function ChatsRoute() {
  const { data, loading, error, reload } = useQuery(async () => {
    const { data, error } = await supabase.rpc('my_chats');
    if (error) throw new Error('Les discussions n’ont pas pu être chargées.');
    return (data as ChatSummary[]) ?? [];
  }, []);
  useRealtime('chats-list', [{ table: 'group_messages' }], reload);

  if (loading && !data) return <Loading />;
  return (
    <View style={s.screen}>
      <Stack.Screen options={{ title: 'Discussions' }} />
      <ErrorText error={error} />
      <FlatList
        data={data ?? []}
        keyExtractor={(c) => c.id}
        ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: colors.line, marginLeft: 76 }} />}
        ListEmptyComponent={<Empty>Rejoins ou crée un groupe pour discuter avec ses membres.</Empty>}
        renderItem={({ item: c }) => <ChatRow chat={c} />}
      />
    </View>
  );
}

function ChatRow({ chat }: { chat: ChatSummary }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Discussion ${chat.name}${chat.unread ? `, ${chat.unread} non lus` : ''}`}
      onPress={() => router.push(`/chats/${chat.id}`)}
      style={({ pressed }) => [{ flexDirection: 'row', gap: 12, alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 },
        pressed && { backgroundColor: colors.fill }]}>
      <Avatar id={chat.id} name={chat.name} size={48} profile={false} />
      <View style={{ flex: 1, gap: 3 }}>
        <View style={s.rowBetween}>
          <T weight="semibold" numberOfLines={1} style={{ flex: 1 }}>{chat.name}</T>
          {chat.last_at ? <T muted size={12} color={chat.unread ? colors.accent : undefined}>{formatMessageTime(chat.last_at)}</T> : null}
        </View>
        <View style={s.rowBetween}>
          <T muted size={14} numberOfLines={1} style={{ flex: 1 }}>{chat.last ?? 'Aucun message pour l’instant'}</T>
          {chat.notify === 'none' ? <T muted size={12}>🔕</T> : null}
          {chat.unread ? (
            <View style={{ minWidth: 22, height: 22, borderRadius: 11, paddingHorizontal: 6, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' }}>
              <T size={12} weight="bold" color={colors.onAccent}>{chat.unread > 99 ? '99+' : chat.unread}</T>
            </View>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}
