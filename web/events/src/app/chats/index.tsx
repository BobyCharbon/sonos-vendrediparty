import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View, type NativeScrollEvent, type NativeSyntheticEvent } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ChatsOff } from '@/components/ChatsOff';
import { Dropdown, Fab, FilterChips, IconButton, ListHeader, PauseButton, PausePanel, SearchField, SlimLinks, type Filter } from '@/components/chats/list/Bits';
import { ChatMenu } from '@/components/chats/list/ChatMenu';
import { ChatRow } from '@/components/chats/list/ChatRow';
import { EmptyChats } from '@/components/chats/list/EmptyChats';
import { PinnedTiles } from '@/components/chats/list/PinnedTiles';
import { SearchResults } from '@/components/chats/list/SearchResults';
import { Snack, useChatActions } from '@/components/chats/list/useChatActions';
import { useTyping } from '@/components/chats/list/useTyping';
import { chatFont, glow, NeonTheme, useNeon, web } from '@/components/chats/neon';
import { usePause } from '@/components/NotificationPause';
import { Loading } from '@/components/ui';
import { useMe } from '@/lib/auth';
import {
  chatKey, fetchChatBadge, fetchChatList, fetchCrossed, isUnread, newMessage, openChat, tellBadge, writeTo, type ChatItem, type ChatPerson,
} from '@/lib/chatList';
import { useQuery, useRealtime, useSignal } from '@/lib/data';
import { discussionsOn } from '@/lib/features';
import { useMiniProfile } from '@/lib/miniProfile';
import { enter } from '@/lib/motion';

/** Discussions (drapeau discussions_enabled : éteint, l'écran dit « bientôt »). */
export default function ChatsRoute() {
  // Sombre comme tout Party ; « ?theme=light » / « ?theme=auto » : aperçu des jetons clairs de la maquette 1b.
  const { theme } = useLocalSearchParams<{ theme?: string }>();
  if (!discussionsOn) return <ChatsOff />;
  return <NeonTheme scheme={theme === 'light' || theme === 'auto' ? theme : 'dark'}><ChatsHome /></NeonTheme>;
}

function ChatsHome() {
  const me = useMe();
  const c = useNeon();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ requests?: string }>();
  const push = useCallback((path: string) => router.push(path as never), []);
  const mini = useMiniProfile();
  const { data, error: loadError, loading, reload, setData } = useQuery(fetchChatList, []);
  // Temps réel comme avant (messages des groupes et des messages directs, demandes) + signal de mes groupes / droits.
  useRealtime('chats-list', [{ table: 'group_messages' }, { table: 'direct_messages' }, { table: 'messages' }, { table: 'direct_chats' }], reload);
  useSignal([`user:${me.id}`, 'events'], reload);

  const all = useMemo(() => data ?? [], [data]);
  const setChats = useCallback((next: ChatItem[]) => setData(next), [setData]);
  const actions = useChatActions(all, setChats, reload);

  // Pastille de l'onglet Discussions (page Party) : chat_badge, relue à chaque changement de la liste.
  useEffect(() => {
    if (!data) return;
    void fetchChatBadge().then((n) => { if (n !== null) tellBadge(n); });
  }, [data]);

  useEffect(() => {
    if (params.requests === '1') router.push('/chats/requests');
  }, [params.requests]);

  const live = useMemo(() => all.filter((x) => !x.archived && x.request !== 'incoming'), [all]);
  const requests = all.filter((x) => x.request === 'incoming').length;
  const archivedCount = all.filter((x) => x.archived && x.request !== 'incoming').length;
  const unreadCount = live.filter(isUnread).length;
  const typing = useTyping(live, me.id);

  const [filter, setFilter] = useState<Filter>('all');
  const [q, setQ] = useState('');
  const [searching, setSearching] = useState(false);
  const [open, setOpen] = useState<{ key: string; side: 'left' | 'right' } | null>(null);
  const openSide = useCallback((key: string, side: 'left' | 'right' | null) => setOpen(side ? { key, side } : null), []);
  const [menu, setMenu] = useState<ChatItem | null>(null);
  const [more, setMore] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const lastY = useRef(0);

  const empty = !!data && !live.length;
  const crossed = useQuery(() => (empty ? fetchCrossed() : Promise.resolve([] as ChatPerson[])), [empty]);

  const pinned = filter === 'all' ? live.filter((x) => x.pinned_at) : [];
  const rows = live.filter((x) => (filter === 'all' ? !x.pinned_at
    : filter === 'unread' ? isUnread(x) : x.kind === filter));

  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    const y = e.nativeEvent.contentOffset.y;
    if (Math.abs(y - lastY.current) > 6) setCollapsed(y > 40 && y > lastY.current);
    lastY.current = y;
    if (open) setOpen(null);
  };

  const openOne = (chat: ChatItem) => {
    if (isUnread(chat)) actions.choose(chat, { kind: 'read' });
    openChat(chat, push);
  };

  if (loading && !data) return <Loading />;

  return (
    <View style={[st.screen, { backgroundColor: c.bg }]}>
      <Stack.Screen options={{ headerShown: false, title: 'Discussions' }} />
      <View style={glow(c)} />
      <ScrollView onScroll={onScroll} scrollEventThrottle={32} keyboardShouldPersistTaps="handled"
        contentContainerStyle={{ paddingTop: insets.top + 8, paddingBottom: insets.bottom + 120 }}>
        <ListHeader title="Discussions">
          {!empty ? <PauseButton /> : null}
          <View>
            <IconButton icon="more" expanded={more} onPress={() => setMore((v) => !v)}
              label="Plus : Demandes de message, Archivées, Nouveau groupe, pause des notifications" />
            {more ? <MoreMenu requests={requests} archived={archivedCount} unread={unreadCount} empty={empty} onClose={() => setMore(false)}
              onReadAll={() => live.filter(isUnread).forEach((x) => actions.choose(x, { kind: 'read' }))} push={push} /> : null}
          </View>
        </ListHeader>

        {!empty || searching ? (
          <SearchField value={q} onChange={setQ} active={searching} onFocus={() => setSearching(true)}
            onCancel={() => { setQ(''); setSearching(false); }} />
        ) : null}

        <Message text={actions.error ?? loadError} />

        {searching ? (
          <SearchResults q={q} chats={all.filter((x) => x.request !== 'incoming')}
            onChat={(x) => openChat(x, push)}
            onMessage={(m) => openChat({ kind: m.kind, id: m.id, user_id: null }, push, m.message_id)}
            onPerson={(p) => {
              const existing = live.find((x) => x.kind === 'direct' && x.user_id === p.id);
              if (existing) openChat(existing, push);
              else mini.open(p.id);
            }} />
        ) : empty ? (
          <>
            <SlimLinks requests={requests} archived={archivedCount} onRequests={() => push('/chats/requests')} onArchived={() => push('/chats/archived')} />
            <EmptyChats crossed={crossed.data ?? []} onNew={() => newMessage(push)} onGroup={() => newMessage(push, true)}
              onWrite={(p) => writeTo(p.id, push).catch((e: Error) => actions.setError(e.message))} />
          </>
        ) : (
          <>
            <FilterChips value={filter} onChange={setFilter} unread={unreadCount} />
            <PinnedTiles chats={pinned} onOpen={openOne} onMenu={setMenu} />
            {filter === 'all' ? (
              <SlimLinks requests={requests} archived={archivedCount} onRequests={() => push('/chats/requests')} onArchived={() => push('/chats/archived')} />
            ) : null}
            <View role="list" aria-label="Toutes les discussions" style={{ marginTop: 2 }}>
              {rows.map((chat, i) => (
                <ChatRow key={chatKey(chat)} chat={chat} first={i === 0} index={i} typing={typing[chatKey(chat)]}
                  open={open?.key === chatKey(chat) ? open.side : null}
                  onOpenSide={openSide}
                  onPress={() => openOne(chat)} onMenu={() => setMenu(chat)}
                  onAction={(a) => actions.rowAction(chat, a, () => setMenu(chat))} />
              ))}
            </View>
            {!rows.length && filter !== 'all' ? (
              <Text style={[chatFont.text, st.none, { color: c.t2 }]}>
                {filter === 'unread' ? 'Tout est lu 🎉' : filter === 'direct' ? 'Aucun message direct.' : filter === 'group' ? 'Aucun groupe.' : 'Aucune discussion de soirée en cours.'}
              </Text>
            ) : null}
          </>
        )}
      </ScrollView>

      {!searching && !empty ? <Fab collapsed={collapsed} bottom={insets.bottom + 18} onPress={() => newMessage(push)} /> : null}
      <View pointerEvents="none" style={[st.fade, web({ backgroundImage: `linear-gradient(180deg, transparent, ${c.bg} 85%)` })]} />
      <Snack snack={actions.snack} onDone={() => actions.setSnack(null)} bottom={insets.bottom + 86} />
      <ChatMenu chat={menu} onClose={() => setMenu(null)} onChoose={actions.choose} />
    </View>
  );

}

/** Menu « … » de l'en-tête : Demandes, Archivées, Nouveau groupe, Tout marquer comme lu, pause des Discussions. */
function MoreMenu({ requests, archived, unread, empty, onClose, onReadAll, push }: {
  requests: number; archived: number; unread: number; empty: boolean; onClose: () => void; onReadAll: () => void; push: (p: string) => void;
}) {
  const pause = usePause();
  const [showPause, setShowPause] = useState(empty);
  return (
    <Dropdown onClose={onClose} items={[
      { label: 'Demandes de message', icon: 'inbox', badge: requests, onPress: () => push('/chats/requests') },
      { label: archived ? `Archivées (${archived})` : 'Archivées', icon: 'archive', onPress: () => push('/chats/archived') },
      { label: 'Nouveau groupe', icon: 'users', onPress: () => newMessage(push, true) },
      ...(unread ? [{ label: 'Tout marquer comme lu', icon: 'check2' as const, onPress: onReadAll }] : []),
    ]}>
      {showPause ? <PausePanel pause={pause} /> : (
        <Pressable role="menuitem" accessibilityLabel="Pause des notifications…" onPress={() => setShowPause(true)} style={st.pauseLink}>
          <Text style={[chatFont.medium, { color: '#B9A7FF', fontSize: 16 }]}>🌙 Pause des notifications…</Text>
        </Pressable>
      )}
    </Dropdown>
  );
}

function Message({ text }: { text: string | null }) {
  const c = useNeon();
  if (!text) return null;
  return <Text role="alert" style={[chatFont.medium, st.err, { color: c.danger }, enter('drop')]}>{text}</Text>;
}

const st = StyleSheet.create({
  screen: { flex: 1, position: 'relative', overflow: 'hidden' },
  none: { textAlign: 'center', fontSize: 15, paddingVertical: 32, paddingHorizontal: 24 },
  err: { fontSize: 14, paddingHorizontal: 16, paddingTop: 10 },
  fade: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 48 },
  pauseLink: { minHeight: 46, justifyContent: 'center', paddingHorizontal: 14 },
});
