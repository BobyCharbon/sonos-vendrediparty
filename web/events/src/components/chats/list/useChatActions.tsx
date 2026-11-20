import { useCallback, useEffect, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { chatFont, useNeon, web } from '../neon';
import type { MenuChoice } from './ChatMenu';
import type { RowAction } from './ChatRow';
import { chatKey, markRead, movedPins, PIN_LIMIT, reorderPins, setChatState, setMute, sortChats, type ChatItem } from '@/lib/chatList';
import { useMiniProfile } from '@/lib/miniProfile';
import { setBlocked } from '@/lib/moderation';
import { enter } from '@/lib/motion';

/** Changement d'état gardé à l'écran tout de suite, puis envoyé à la base. */
export type Patch = Partial<Pick<ChatItem, 'unread' | 'marked_unread' | 'pinned_at' | 'archived' | 'notify' | 'muted_until' | 'blocked'>>;

/** Actions partagées par la liste, les Demandes et les Archivées (optimistes ; la liste se relit en cas d'échec). */
export function useChatActions(chats: ChatItem[], setChats: (next: ChatItem[]) => void, reload: () => unknown) {
  const mini = useMiniProfile();
  const [error, setError] = useState<string | null>(null);
  const [snack, setSnack] = useState<{ text: string; undo?: () => void } | null>(null);
  const latest = useRef(chats);
  useEffect(() => { latest.current = chats; }, [chats]);

  const patch = useCallback((chat: ChatItem, change: Patch) => {
    setChats(sortChats(latest.current.map((x) => (chatKey(x) === chatKey(chat) ? { ...x, ...change } : x))));
  }, [setChats]);

  const run = useCallback(async (chat: ChatItem, change: Patch, send: () => Promise<unknown>) => {
    setError(null);
    patch(chat, change);
    try { await send(); } catch (e) {
      setError(e instanceof Error ? e.message : 'Le changement n’a pas été enregistré.');
      void reload();
    }
  }, [patch, reload]);

  const choose = useCallback((chat: ChatItem, choice: MenuChoice) => {
    switch (choice.kind) {
      case 'read': return void run(chat, { unread: 0, marked_unread: false }, () => markRead(chat));
      case 'unread': return void run(chat, { marked_unread: true }, () => setChatState(chat, { unread: true }));
      case 'pin':
        if (latest.current.filter((x) => x.pinned_at && !x.archived).length >= PIN_LIMIT) {
          setError(`Tu peux épingler ${PIN_LIMIT} discussions au plus. Désépingles-en une d’abord.`);
          return undefined;
        }
        return void run(chat, { pinned_at: new Date().toISOString() }, () => setChatState(chat, { pinned: true }));
      case 'unpin': return void run(chat, { pinned_at: null }, () => setChatState(chat, { pinned: false }));
      case 'archive':
        setSnack({ text: 'Discussion archivée', undo: () => void run(chat, { archived: false }, () => setChatState(chat, { archived: false })) });
        return void run(chat, { archived: true }, () => setChatState(chat, { archived: true }));
      case 'unarchive': return void run(chat, { archived: false }, () => setChatState(chat, { archived: false }));
      case 'mute':
        setError(null);
        return void setMute(chat, choice.span).then((r) => patch(chat, r), (e: Error) => setError(e.message));
      case 'profile': if (chat.user_id) mini.open(chat.user_id); return undefined;
      case 'block': if (chat.user_id) void run(chat, { blocked: true }, () => setBlocked(chat.user_id!, true)); return undefined;
      case 'move': {
        const order = movedPins(sortChats(latest.current.filter((x) => x.pinned_at && !x.archived)), chat, choice.step);
        if (!order) return undefined;
        // L'ordre à l'écran tout de suite (la première à gauche = la plus récente), puis la base.
        const now = Date.now();
        const at = new Map(order.map((x, i) => [chatKey(x), new Date(now - i * 1000).toISOString()]));
        setError(null);
        setChats(sortChats(latest.current.map((x) => (at.has(chatKey(x)) ? { ...x, pinned_at: at.get(chatKey(x))! } : x))));
        return void reorderPins(order).catch((e: Error) => { setError(e.message); void reload(); });
      }
    }
  }, [run, patch, mini, setChats, reload]);

  const rowAction = useCallback((chat: ChatItem, a: RowAction, openMute: () => void) => {
    if (a === 'mute') return openMute();
    choose(chat, a === 'unmute' ? { kind: 'mute', span: 'off' } : { kind: a });
  }, [choose]);

  useEffect(() => {
    if (!snack) return undefined;
    const t = setTimeout(() => setSnack(null), 5000);
    return () => clearTimeout(t);
  }, [snack]);

  return { error, setError, snack, setSnack, choose, rowAction };
}

/** Petit bandeau en bas (« Discussion archivée · Annuler »), 5 s. */
export function Snack({ snack, onDone, bottom }: { snack: { text: string; undo?: () => void } | null; onDone: () => void; bottom: number }) {
  const c = useNeon();
  if (!snack) return null;
  return (
    <View role="status" style={[st.snack, { bottom, backgroundColor: c.s1b, borderColor: c.line2 }, web({ boxShadow: c.shadow }), enter('rise')]}>
      <Text style={[chatFont.medium, { flex: 1, color: c.t1, fontSize: 15 }]}>{snack.text}</Text>
      {snack.undo ? (
        <Pressable accessibilityRole="button" accessibilityLabel="Annuler" onPress={() => { snack.undo?.(); onDone(); }} style={st.undo}>
          <Text style={[chatFont.bold, { color: c.lav, fontSize: 15 }]}>Annuler</Text>
        </Pressable>
      ) : null}
    </View>
  );
}


const st = StyleSheet.create({
  snack: { position: 'absolute', left: 16, right: 16, zIndex: 35, minHeight: 50, borderRadius: 16, borderWidth: 1, flexDirection: 'row', alignItems: 'center', paddingLeft: 16, paddingRight: 4 },
  undo: { height: 44, paddingHorizontal: 12, justifyContent: 'center' },
});
