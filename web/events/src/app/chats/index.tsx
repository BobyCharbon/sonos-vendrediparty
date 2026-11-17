import { router, Stack } from 'expo-router';
import { FlatList, Pressable, View } from 'react-native';

import { ChatsOff } from '@/components/ChatsOff';
import { ChatsPause } from '@/components/NotificationPause';
import { GroupTile } from '@/components/GroupBits';
import { usePersonText } from '@/components/PersonName';
import { Avatar, Empty, ErrorText, Loading, s, T } from '@/components/ui';
import type { ChatSummary } from '@/lib/chats';
import { useQuery, useRealtime } from '@/lib/data';
import { discussionsOn } from '@/lib/features';
import { formatMessageTime } from '@/lib/format';
import { duration, enter, transition } from '@/lib/motion';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

/** Discussions (avis n°10) : absentes hors site de test (production, décision du 04.11). */
export default function ChatsRoute() {
  return discussionsOn ? <ChatsList /> : <ChatsOff />;
}

/** Une discussion par groupe, la plus récente en haut, comme WhatsApp ; « Nouveau groupe » (même formulaire que
 * Réglages › Groupes) le crée, son créateur dedans, et ouvre sa discussion. */
function ChatsList() {
  const { data, loading, error, reload } = useQuery(async () => {
    const { data, error } = await supabase.rpc('my_chats');
    if (error) throw new Error('Les discussions n’ont pas pu être chargées.');
    return (data as ChatSummary[]) ?? [];
  }, []);
  useRealtime('chats-list', [{ table: 'group_messages' }, { table: 'direct_messages' }], reload);

  if (loading && !data) return <Loading />;
  return (
    <View style={s.screen}>
      <Stack.Screen options={{ title: 'Discussions' }} />
      {/* En tête de liste, comme « Nouveau groupe » dans WhatsApp : la création en 2 étapes (17.11). */}
      <NewGroupRow />
      <ErrorText error={error} />
      {/* En haut de la liste : sourdine des Discussions des groupes (30 min, 1 h, 2 h, 8 h ; messages sans son). */}
      <ChatsPause scope="chats" compact />
      <FlatList
        data={data ?? []}
        keyExtractor={(c) => c.id}
        ItemSeparatorComponent={() => <View style={{ height: 1, backgroundColor: colors.line, marginLeft: 76 }} />}
        ListEmptyComponent={<Empty>Rejoins ou crée un groupe pour discuter avec ses membres, ou écris à quelqu’un depuis sa fiche.</Empty>}
        renderItem={({ item: c }) => <ChatRow chat={c} />}
      />
    </View>
  );
}

function NewGroupRow() {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel="Nouveau groupe" onPress={() => router.push('/group/new')}
      style={({ pressed }) => [{ flexDirection: 'row', gap: 12, alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 },
        transition('background-color', duration.fast), pressed && { backgroundColor: colors.fill }]}>
      <View style={{ width: 48, height: 48, borderRadius: 24, backgroundColor: colors.accentDim, alignItems: 'center', justifyContent: 'center' }}>
        <T size={22} weight="bold" color={colors.accent}>+</T>
      </View>
      <T weight="semibold" color={colors.accent}>Nouveau groupe</T>
    </Pressable>
  );
}

function ChatRow({ chat }: { chat: ChatSummary }) {
  const personText = usePersonText();
  // Message direct : la personne (« Nom du contact · pseudo » dans l'app iPhone) et sa photo.
  const direct = chat.kind === 'direct' && Boolean(chat.user_id);
  const name = direct ? personText(chat.user_id, chat.name) : chat.name;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${direct ? 'Message direct' : 'Discussion'} ${name}${chat.unread ? `, ${chat.unread} non lus` : ''}`}
      onPress={() => router.push(`/chats/${chat.id}`)}
      style={({ pressed }) => [{ flexDirection: 'row', gap: 12, alignItems: 'center', paddingHorizontal: 16, paddingVertical: 12 },
        transition('background-color', duration.fast), pressed && { backgroundColor: colors.fill }]}>
      {direct ? <Avatar id={chat.user_id!} name={name} photo={chat.avatar_url ?? null} size={48} profile={false} />
        : <GroupTile group={{ emoji: chat.emoji ?? '👯', color: chat.color ?? 'pink' }} size={48} />}
      <View style={{ flex: 1, gap: 3 }}>
        <View style={s.rowBetween}>
          <T weight="semibold" numberOfLines={1} style={{ flex: 1 }}>{name}</T>
          {chat.last_at ? <T muted size={12} color={chat.unread ? colors.accent : undefined}>{formatMessageTime(chat.last_at)}</T> : null}
        </View>
        <View style={s.rowBetween}>
          <T muted size={14} numberOfLines={1} style={{ flex: 1 }}>{chat.last ?? 'Aucun message pour l’instant'}</T>
          {chat.notify === 'none' ? <T muted size={12}>🔕</T> : null}
          {chat.unread ? (
            // Nouveau message non lu : la pastille se pose (sa clé suit le compte).
            <View key={chat.unread} style={[{ minWidth: 22, height: 22, borderRadius: 11, paddingHorizontal: 6, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' }, enter('pop')]}>
              <T size={12} weight="bold" color={colors.onAccent}>{chat.unread > 99 ? '99+' : chat.unread}</T>
            </View>
          ) : null}
        </View>
      </View>
    </Pressable>
  );
}
