import { useMemo, useState } from 'react';
import { PanResponder, Pressable, StyleSheet, Text, View } from 'react-native';

import { chatFont, useNeon, web, type NeonColors } from '../neon';
import { ChatFace } from './Faces';
import { listTime, mentionChunks, previewText } from './format';
import { Icon, type IconName } from './Icons';
import { usePersonText } from '@/components/PersonName';
import { chatKey, isMuted, isUnread, type ChatItem } from '@/lib/chatList';
import { ease, enter, reducedMotion, transition } from '@/lib/motion';

export type RowAction = 'read' | 'unread' | 'pin' | 'unpin' | 'mute' | 'unmute' | 'archive' | 'unarchive';

const ACTION_W = 76;
const OPEN_AT = 56;

type Props = {
  chat: ChatItem; typing?: string; first?: boolean; index?: number;
  open: 'left' | 'right' | null;
  /** Stable (même fonction d'un rendu à l'autre) : le glissé en cours n'est pas recréé. */
  onOpenSide: (key: string, side: 'left' | 'right' | null) => void;
  onPress: () => void; onMenu: () => void; onAction: (a: RowAction) => void;
  /** Entrée en cascade : seulement au premier affichage (liste déjà connue : tout de suite, sans attendre l'animation). */
  animate?: boolean;
  /** Doigt posé ou souris au-dessus : la conversation se précharge (elle s'ouvre ensuite sans attente). */
  onWarm?: () => void;
};

/** Ce que la ligne dit aux lecteurs d'écran (la couleur n'est jamais seule). */
export function rowLabel(c: ChatItem, name: string, typing?: string): string {
  const what = c.kind === 'direct' ? 'Message direct' : c.kind === 'event' ? 'Soirée' : 'Discussion';
  const bits = [`${what} ${name}`];
  if (c.unread) bits.push(`${c.unread} non lu${c.unread > 1 ? 's' : ''}`);
  else if (c.marked_unread) bits.push('marquée non lue');
  if (c.mention) bits.push('on te cite');
  if (typing !== undefined) bits.push(`${typing || name} écrit`);
  if (isMuted(c)) bits.push('en sourdine');
  if (c.pinned_at) bits.push('épinglée');
  return bits.join(', ');
}

/**
 * Ligne de la liste (maquette 1-liste) : visage (rond, carré emoji, calendrier), nom, heure, aperçu, @, sourdine, Vu,
 * non lus. Glisser vers la droite : Lu / Non lu et Épingler ; vers la gauche : Sourdine et Archiver. Appui long ou « … »
 * (au survol, ordinateur) : aperçu et menu complet.
 */
export function ChatRow({ chat, typing, first, index = 0, open, onOpenSide: setSide, onPress, onMenu, onAction, animate = true, onWarm }: Props) {
  const key = chatKey(chat);
  const c = useNeon();
  const personText = usePersonText();
  const name = chat.kind === 'direct' && chat.user_id ? personText(chat.user_id, chat.title) : chat.title;
  const [drag, setDrag] = useState<number | null>(null);
  const [hover, setHover] = useState(false);
  const [focus, setFocus] = useState(false);
  // Un glissé n'est jamais aussi un toucher ni un appui long (le toucher du web suit ses propres événements).
  // (l'appui long du web part d'un minuteur qui ne voit pas toujours la fin d'un glissé : on note l'heure du glissé).
  const [swipedAt, setSwipedAt] = useState(-1e9);
  const justSwiped = (e: { timeStamp: number }) => Math.abs(e.timeStamp - swipedAt) < 900;
  const base = open === 'left' ? ACTION_W * 2 : open === 'right' ? -ACTION_W * 2 : 0;
  const x = drag ?? base;
  const pan = useMemo(() => PanResponder.create({
    onMoveShouldSetPanResponderCapture: (_e, g) => Math.abs(g.dx) > 12 && Math.abs(g.dx) > Math.abs(g.dy) * 1.6,
    onPanResponderGrant: (e) => setSwipedAt(e.timeStamp),
    onPanResponderMove: (_e, g) => setDrag(Math.max(-ACTION_W * 2.4, Math.min(ACTION_W * 2.4, base + g.dx))),
    onPanResponderTerminationRequest: () => false,
    onPanResponderRelease: (e, g) => {
      const end = base + g.dx;
      setDrag(null);
      setSide(key, end > OPEN_AT ? 'left' : end < -OPEN_AT ? 'right' : null);
      setSwipedAt(e.timeStamp);
    },
    onPanResponderTerminate: (e) => { setDrag(null); setSwipedAt(e.timeStamp); },
  }), [base, setSide, key]);
  const onOpenSide = (side: 'left' | 'right' | null) => setSide(key, side);

  const unread = isUnread(chat);
  const muted = isMuted(chat);
  const act = (a: RowAction) => { onOpenSide(null); onAction(a); };
  const left: SwipeAct[] = [
    unread ? { key: 'read', label: 'Lu', icon: 'check', bg: `linear-gradient(135deg, ${c.lavHi}, ${c.lavB})`, ink: '#120B26' }
      : { key: 'unread', label: 'Non lu', icon: 'chat', bg: `linear-gradient(135deg, ${c.lavHi}, ${c.lavB})`, ink: '#120B26' },
    chat.pinned_at ? { key: 'unpin', label: 'Désépingler', icon: 'pin', bg: 'linear-gradient(135deg, #FFEA9C, #FFB347)', ink: '#2A1E04' }
      : { key: 'pin', label: 'Épingler', icon: 'pin', bg: 'linear-gradient(135deg, #FFEA9C, #FFB347)', ink: '#2A1E04' },
  ];
  const right: SwipeAct[] = [
    muted ? { key: 'unmute', label: 'Son', icon: 'bell', bg: c.s2, ink: c.t1 } : { key: 'mute', label: 'Sourdine', icon: 'bellslash', bg: c.s2, ink: c.t1 },
    chat.archived ? { key: 'unarchive', label: 'Sortir', icon: 'archive', bg: 'linear-gradient(150deg, #FFC977, #FF7A59)', ink: '#2A1406' }
      : { key: 'archive', label: 'Archiver', icon: 'archive', bg: 'linear-gradient(150deg, #FFC977, #FF7A59)', ink: '#2A1406' },
  ];

  return (
    <View style={[st.wrap, animate ? enter('rise', index) : null]} onPointerEnter={() => { setHover(true); onWarm?.(); }} onPointerLeave={() => setHover(false)}>
      {x > 0 ? <SwipeSide acts={left} side="left" width={x} onAct={act} /> : null}
      {x < 0 ? <SwipeSide acts={right} side="right" width={-x} onAct={act} /> : null}
      <View {...pan.panHandlers}
        style={[{ transform: [{ translateX: x }], backgroundColor: c.bg }, web({ touchAction: 'pan-y pinch-zoom', userSelect: 'none', WebkitTouchCallout: 'none' }),
          drag === null ? transition('transform', 280, ease.out) : null]}>
        <Pressable accessibilityRole="button" accessibilityLabel={rowLabel(chat, name, typing)}
          testID={`chat-row-${chat.id}`}
          onPressIn={onWarm}
          onPress={(e) => { if (justSwiped(e)) return; if (open) onOpenSide(null); else onPress(); }}
          onLongPress={(e) => { if (!justSwiped(e) && drag === null) onMenu(); }} delayLongPress={450}
          style={({ pressed }) => [st.row, pressed && { backgroundColor: c.glass }, transition('background-color', 140)]}>
          {!first ? <View style={[st.sep, { backgroundColor: c.line }]} /> : null}
          <ChatFace chat={chat} size={54} />
          <View style={st.body}>
            <View style={st.line}>
              <Text numberOfLines={1} style={[unread ? chatFont.bold : chatFont.semibold, st.name, { color: c.t1 }]}>{name}</Text>
              {chat.last ? (
                <Text style={[chatFont.num, unread && !muted ? chatFont.semibold : chatFont.text,
                  { fontSize: 14, color: unread && !muted ? c.pinkInk : c.t3 }]}>{listTime(chat.last.at)}</Text>
              ) : null}
            </View>
            <View style={st.line}>
              <Preview chat={chat} typing={typing} unread={unread} c={c} />
              <Trailing chat={chat} unread={unread} muted={muted} c={c} />
            </View>
          </View>
        </Pressable>
        {/* Ordinateur : « … » au survol (ou au clavier) ouvre le même menu que l'appui long. */}
        <Pressable accessibilityRole="button" accessibilityLabel={`Plus d’options : ${name}`} onPress={(e) => { if (!justSwiped(e)) onMenu(); }}
          onFocus={() => setFocus(true)} onBlur={() => setFocus(false)}
          style={[st.more, { backgroundColor: c.s1b, borderColor: c.glassLine }, web({ boxShadow: c.shadow }),
            { opacity: (hover || focus) && x === 0 ? 1 : 0 }, web({ pointerEvents: (hover || focus) && x === 0 ? 'auto' : 'none' }), transition('opacity', 140)]}>
          <Icon name="more" size={20} color={c.t1} stroke={2.6} />
        </Pressable>
      </View>
    </View>
  );
}

type SwipeAct = { key: RowAction; label: string; icon: IconName; bg: string; ink: string };

function SwipeSide({ acts, side, width, onAct }: { acts: SwipeAct[]; side: 'left' | 'right'; width: number; onAct: (a: RowAction) => void }) {
  return (
    <View style={[st.side, side === 'left' ? { left: 0 } : { right: 0 }, { width: Math.max(width, 0) }]}>
      {acts.map((a) => (
        <Pressable key={a.key} accessibilityRole="button" accessibilityLabel={a.label} onPress={() => onAct(a.key)}
          style={[st.act, web({ background: a.bg })]}>
          <Icon name={a.icon} size={20} color={a.ink} />
          <Text numberOfLines={1} style={[chatFont.bold, { fontSize: 12, color: a.ink }]}>{a.label}</Text>
        </Pressable>
      ))}
    </View>
  );
}

/** « écrit » + trois points qui respirent (opacité, 1,2 s ; fixes avec « Réduire les animations »). */
export function TypingDots({ color }: { color: string }) {
  return (
    <View style={{ flexDirection: 'row', gap: 3, alignItems: 'center' }} aria-hidden>
      {[0, 1, 2].map((i) => (
        <View key={i} style={[{ width: 5, height: 5, borderRadius: 3, backgroundColor: color, opacity: [0.45, 0.75, 1][i] },
          i === 2 ? web({ boxShadow: `0 0 6px ${color}` }) : null,
          reducedMotion ? null : web({ animationKeyframes: [{ '0%': { opacity: 0.3 }, '50%': { opacity: 1 }, '100%': { opacity: 0.3 } }],
            animationDuration: '1200ms', animationIterationCount: 'infinite', animationTimingFunction: ease.inOut, animationDelay: `${i * 200}ms` })]} />
      ))}
    </View>
  );
}

function Preview({ chat, typing, unread, c }: { chat: ChatItem; typing?: string; unread: boolean; c: NeonColors }) {
  const base = [chatFont.text, st.pv, { color: unread ? c.t1 : c.t2 }];
  if (typing !== undefined) {
    return (
      <View style={st.pvRow}>
        <Text numberOfLines={1} style={[chatFont.semibold, { color: c.lav, fontSize: 15, lineHeight: 20, flexShrink: 1 }]}>{chat.kind === 'direct' || !typing ? 'écrit' : `${typing} écrit`}</Text>
        <TypingDots color={c.lav} />
      </View>
    );
  }
  if (chat.kind === 'direct' && chat.blocked) return <Text numberOfLines={1} style={[...base, { color: c.t3 }]}>Personne bloquée</Text>;
  const last = chat.last;
  if (!last) return <Text numberOfLines={1} style={[...base, { color: c.t3 }]}>{chat.kind === 'event' ? 'Discussion de la soirée' : 'Aucun message pour l’instant'}</Text>;
  const text = previewText(last);
  const who = last.from_me ? 'Toi' : chat.kind !== 'direct' ? last.author : null;
  const deleted = last.type === 'deleted';
  return (
    <View style={st.pvRow}>
      {last.from_me && chat.seen_by_other !== null && chat.request !== 'outgoing' ? (
        <View accessibilityLabel={chat.seen_by_other ? 'Vu' : 'Envoyé'} style={{ marginRight: 4 }}>
          <Icon name={chat.seen_by_other ? 'check2' : 'check'} size={16} color={chat.seen_by_other ? c.lav : c.t3} />
        </View>
      ) : null}
      {last.type === 'audio' && !who ? <View style={{ marginRight: 4 }}><Icon name="mic" size={13} color={c.lav} /></View> : null}
      <Text numberOfLines={1} style={base}>
        {chat.request === 'outgoing' ? <Text style={[chatFont.semibold, { color: c.t3 }]}>Demande envoyée · </Text> : null}
        {who ? <Text style={[chatFont.medium, { color: c.t1 }]}>{who} : </Text> : null}
        {deleted ? <Text style={{ fontStyle: 'italic', color: c.t3 }}>{text}</Text>
          : mentionChunks(text).map((p, i) => (p.at
            ? <Text key={i} style={[chatFont.semibold, { color: c.pinkInk }]}>{p.text}</Text>
            : <Text key={i}>{p.text}</Text>))}
      </Text>
    </View>
  );
}

function Trailing({ chat, unread, muted, c }: { chat: ChatItem; unread: boolean; muted: boolean; c: NeonColors }) {
  return (
    <View style={st.trail}>
      {chat.pinned_at ? <View accessibilityLabel="Épinglée" style={{ transform: [{ rotate: '45deg' }] }}><Icon name="pin" size={16} color={c.t3} /></View> : null}
      {chat.mention && unread ? (
        <View accessibilityLabel="On te cite" style={[st.at, { borderColor: c.pink }]}>
          <Text style={[chatFont.heavy, { color: c.pinkInk, fontSize: 14, lineHeight: 16 }]}>@</Text>
        </View>
      ) : null}
      {muted ? <View accessibilityLabel="Sourdine"><Icon name="bellslash" size={16} color={c.t3} /></View> : null}
      {chat.unread ? (
        <View key={chat.unread} style={[st.badge, muted ? { backgroundColor: c.muteBg } : [{ backgroundColor: c.pink }, web({ boxShadow: '0 0 14px -2px rgba(255,79,154,.7)' })], enter('pop')]}>
          <Text style={[chatFont.heavy, chatFont.num, { fontSize: 13, color: muted ? c.muteInk : c.onPink }]}>{chat.unread > 99 ? '99+' : chat.unread}</Text>
        </View>
      ) : chat.marked_unread ? <View accessibilityLabel="Marquée non lue" style={[st.dot, { backgroundColor: muted ? c.muteInk : c.pink }]} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { position: 'relative', overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, height: 78, paddingHorizontal: 16 },
  sep: { position: 'absolute', top: 0, left: 82, right: 0, height: 1 },
  body: { flex: 1, minWidth: 0, gap: 3 },
  line: { flexDirection: 'row', alignItems: 'center', gap: 8, minWidth: 0 },
  name: { flex: 1, minWidth: 0, fontSize: 17, lineHeight: 22 },
  pvRow: { flex: 1, minWidth: 0, flexDirection: 'row', alignItems: 'center', gap: 6 },
  pv: { flex: 1, minWidth: 0, fontSize: 15, lineHeight: 20 },
  trail: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  at: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  badge: { minWidth: 22, height: 22, paddingHorizontal: 7, borderRadius: 11, alignItems: 'center', justifyContent: 'center' },
  dot: { width: 12, height: 12, borderRadius: 6 },
  more: { position: 'absolute', right: 12, top: 17, width: 44, height: 44, borderRadius: 22, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  side: { position: 'absolute', top: 0, bottom: 0, flexDirection: 'row', overflow: 'hidden' },
  act: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 4, paddingHorizontal: 4 },
});
