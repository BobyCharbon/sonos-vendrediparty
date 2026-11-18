import { router } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ChatsOff } from '@/components/ChatsOff';
import { ChatMenu } from '@/components/chats/list/ChatMenu';
import { ChatRow } from '@/components/chats/list/ChatRow';
import { ListPage, Nothing } from '@/components/chats/list/ListPage';
import { Snack, useChatActions } from '@/components/chats/list/useChatActions';
import { chatFont, useNeon } from '@/components/chats/neon';
import { Loading } from '@/components/ui';
import { useMe } from '@/lib/auth';
import { chatKey, fetchChatList, isUnread, openChat, type ChatItem } from '@/lib/chatList';
import { useQuery, useRealtime, useSignal } from '@/lib/data';
import { discussionsOn } from '@/lib/features';

/** Discussions archivées : mêmes lignes, mêmes glissés et même menu ; « Sortir » les remet dans la liste. */
export default function ArchivedRoute() {
  return discussionsOn ? <Archived /> : <ChatsOff />;
}

function Archived() {
  const me = useMe();
  const c = useNeon();
  const insets = useSafeAreaInsets();
  const { data, error, loading, reload, setData } = useQuery(fetchChatList, []);
  useRealtime('chats-archived', [{ table: 'group_messages' }, { table: 'direct_messages' }, { table: 'messages' }], reload);
  useSignal([`user:${me.id}`], reload);
  const all = useMemo(() => data ?? [], [data]);
  const actions = useChatActions(all, useCallback((next: ChatItem[]) => setData(next), [setData]), reload);
  const list = all.filter((x) => x.archived && x.request !== 'incoming');
  const [open, setOpen] = useState<{ key: string; side: 'left' | 'right' } | null>(null);
  const openSide = useCallback((key: string, side: 'left' | 'right' | null) => setOpen(side ? { key, side } : null), []);
  const [menu, setMenu] = useState<ChatItem | null>(null);
  const push = useCallback((path: string) => router.push(path as never), []);

  if (loading && !data) return <Loading />;
  return (
    <ListPage title="Archivées"
      intro="Rangées hors de la liste. Glisse une discussion vers la gauche, ou garde le doigt appuyé, pour la sortir des archives."
      overlay={(
        <>
          <Snack snack={actions.snack} onDone={() => actions.setSnack(null)} bottom={insets.bottom + 24} />
          <ChatMenu chat={menu} onClose={() => setMenu(null)} onChoose={actions.choose} />
        </>
      )}>
      {actions.error || error ? <Text role="alert" style={[chatFont.medium, { color: c.danger, fontSize: 14, paddingHorizontal: 16, paddingTop: 8 }]}>{actions.error ?? error}</Text> : null}
      {!list.length ? <Nothing icon="archive" title="Rien d’archivé" text="Archive une discussion pour la ranger sans la quitter : glisse-la vers la gauche dans la liste." /> : null}
      <View role="list" aria-label="Discussions archivées" style={{ marginTop: 8 }}>
        {list.map((chat, i) => (
          <ChatRow key={chatKey(chat)} chat={chat} first={i === 0} index={i}
            open={open?.key === chatKey(chat) ? open.side : null}
            onOpenSide={openSide}
            onPress={() => { if (isUnread(chat)) actions.choose(chat, { kind: 'read' }); openChat(chat, push); }}
            onMenu={() => setMenu(chat)}
            onAction={(a) => actions.rowAction(chat, a, () => setMenu(chat))} />
        ))}
      </View>
    </ListPage>
  );
}
