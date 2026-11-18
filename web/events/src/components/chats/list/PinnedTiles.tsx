import { Pressable, ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import { chatFont, useNeon, web } from '../neon';
import { ChatFace } from './Faces';
import { rowLabel } from './ChatRow';
import { usePersonText } from '@/components/PersonName';
import { isMuted, isUnread, type ChatItem } from '@/lib/chatList';
import { enter, pressTransition, reducedMotion } from '@/lib/motion';

/** Épinglées en grandes tuiles (4 par ligne) ; anneau néon rose → lavande = à lire (il tourne une fois à l'arrivée). */
export function PinnedTiles({ chats, onOpen, onMenu }: { chats: ChatItem[]; onOpen: (c: ChatItem) => void; onMenu: (c: ChatItem) => void }) {
  const { width } = useWindowDimensions();
  if (!chats.length) return null;
  // 4 tuiles se partagent la largeur ; la 5e (5 épinglées au plus) se montre en faisant défiler la rangée.
  const tile = (Math.min(width, 560) - 20) / 4;
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} scrollEnabled={chats.length > 4} style={{ flexGrow: 0 }}
      contentContainerStyle={st.row}>
      <View role="list" aria-label="Épinglées" style={{ flexDirection: 'row' }}>
        {chats.map((chat, i) => <Tile key={`${chat.kind}:${chat.id}`} chat={chat} index={i} width={tile} onOpen={() => onOpen(chat)} onMenu={() => onMenu(chat)} />)}
      </View>
    </ScrollView>
  );
}

function Tile({ chat, index, width, onOpen, onMenu }: { chat: ChatItem; index: number; width: number; onOpen: () => void; onMenu: () => void }) {
  const c = useNeon();
  const personText = usePersonText();
  const name = chat.kind === 'direct' && chat.user_id ? personText(chat.user_id, chat.title) : chat.title;
  const unread = isUnread(chat);
  const muted = isMuted(chat);
  const round = chat.kind === 'direct';
  const ring = round ? 999 : 24;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={rowLabel(chat, name)} onPress={onOpen} onLongPress={onMenu} delayLongPress={450}
      style={({ pressed }) => [st.pin, { width }, enter('rise', index), pressTransition, pressed && { transform: [{ scale: 0.95 }] }, web({ userSelect: 'none' })]}>
      <View style={{ position: 'relative' }}>
        <View style={{ padding: 3, borderRadius: ring }}>
          {/* L'anneau est un calque à part : il tourne une fois (rond) ou se pose (carré) à l'arrivée d'un message. */}
          {unread ? (
            <View key={`ring-${chat.last?.id ?? ''}`} testID="pin-ring" style={[StyleSheet.absoluteFill, { borderRadius: ring },
              web({ backgroundImage: `conic-gradient(from 200deg, ${c.pink}, ${c.lavB}, ${c.lavHi}, ${c.pink})`, boxShadow: '0 0 18px -2px rgba(255,79,154,.55)' }),
              reducedMotion ? null : web({ animationKeyframes: [round
                ? { from: { transform: 'rotate(-180deg)' }, to: { transform: 'rotate(0deg)' } }
                : { from: { transform: 'scale(.86)', opacity: 0 }, to: { transform: 'none', opacity: 1 } }],
              animationDuration: '900ms', animationTimingFunction: 'cubic-bezier(.22,1,.36,1)' })]} />
          ) : null}
          <View style={{ padding: 2, borderRadius: ring, backgroundColor: c.bg }}>
            <ChatFace chat={chat} size={64} />
          </View>
        </View>
        {chat.unread ? (
          <View style={[st.badge, muted ? { backgroundColor: c.muteBg } : [{ backgroundColor: c.pink }, web({ boxShadow: '0 0 14px -2px rgba(255,79,154,.7)' })]]}>
            <Text style={[chatFont.heavy, chatFont.num, { fontSize: 13, color: muted ? c.muteInk : c.onPink }]}>{chat.unread > 99 ? '99+' : chat.unread}</Text>
          </View>
        ) : null}
      </View>
      <Text numberOfLines={1} style={[chatFont.semibold, st.nm, { color: unread ? c.t1 : c.t2 }]}>{name}</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  row: { paddingHorizontal: 10, paddingTop: 10, paddingBottom: 4 },
  pin: { alignItems: 'center', gap: 7, paddingVertical: 6, borderRadius: 18 },
  nm: { fontSize: 13, lineHeight: 16, maxWidth: 86, textAlign: 'center' },
  badge: { position: 'absolute', right: -4, top: -4, minWidth: 22, height: 22, paddingHorizontal: 7, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
});
