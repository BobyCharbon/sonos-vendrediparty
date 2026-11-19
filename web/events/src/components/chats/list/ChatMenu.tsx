import { useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { chatFont, useNeon, web } from '../neon';
import { ChatFace } from './Faces';
import { previewText } from './format';
import { Icon, type IconName } from './Icons';
import { usePersonText } from '@/components/PersonName';
import { SheetBackdrop, SheetClose, useSheetDrag, useSheetTop } from '@/components/SheetGesture';
import { isMuted, isUnread, MUTE_LABELS, type ChatItem, type MuteSpan } from '@/lib/chatList';
import { enter } from '@/lib/motion';

export type MenuChoice =
  | { kind: 'read' } | { kind: 'unread' } | { kind: 'pin' } | { kind: 'unpin' } | { kind: 'archive' } | { kind: 'unarchive' }
  | { kind: 'mute'; span: MuteSpan } | { kind: 'profile' } | { kind: 'block' };

/**
 * Appui long (ou « … ») sur une discussion : aperçu du dernier message, puis Lu / Non lu, Épingler, Sourdine (1 h, 8 h,
 * 1 semaine, Toujours), Archiver, Voir le profil, Bloquer (confirmé). Feuille commune (glisser vers le bas, ✕, fond).
 */
export function ChatMenu({ chat, onClose, onChoose }: { chat: ChatItem | null; onClose: () => void; onChoose: (c: ChatItem, choice: MenuChoice) => void }) {
  const c = useNeon();
  const personText = usePersonText();
  const sheet = useRef<View>(null);
  const [muteOpen, setMuteOpen] = useState(false);
  const [confirmBlock, setConfirmBlock] = useState(false);
  const top = useSheetTop();
  const close = () => { setMuteOpen(false); setConfirmBlock(false); onClose(); };
  useSheetDrag(!!chat, close, sheet);
  if (!chat) return null;
  const name = chat.kind === 'direct' && chat.user_id ? personText(chat.user_id, chat.title) : chat.title;
  const pick = (choice: MenuChoice) => { close(); onChoose(chat, choice); };
  const muted = isMuted(chat);
  const direct = chat.kind === 'direct';
  const last = chat.last;

  return (
    <Modal visible transparent animationType="fade" onRequestClose={close}>
      <View style={[st.overlay, { backgroundColor: c.scrim, paddingTop: top }]}>
        <SheetBackdrop onPress={close} />
        <View ref={sheet} accessibilityViewIsModal accessibilityLabel={`Options : ${name}`}
          style={[st.sheet, { backgroundColor: c.sheet }, web({ boxShadow: '0 -1px 0 rgba(255,255,255,.08) inset, 0 -30px 60px -20px rgba(0,0,0,.7)' }), enter('rise')]}>
          <View style={[st.grabber, { backgroundColor: c.line2 }]} />
          <SheetClose onPress={close} label="Fermer" style={{ position: 'absolute', top: 12, right: 12 }} />
          <View style={st.head}>
            <ChatFace chat={chat} size={54} />
            <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
              <Text numberOfLines={1} style={[chatFont.display, { color: c.t1, fontSize: 20, lineHeight: 24 }]}>{name}</Text>
              <Text style={[chatFont.text, { color: c.t2, fontSize: 13 }]}>
                {direct ? 'Message direct' : chat.kind === 'event' ? 'Discussion de l’événement' : chat.is_vp ? 'Toute la communauté' : `Groupe · ${chat.members} membres`}
              </Text>
            </View>
          </View>
          {last && !chat.blocked ? (
            <View style={[st.preview, { backgroundColor: c.theirs, borderColor: c.theirsLine }]} accessibilityLabel={`Dernier message : ${previewText(last)}`}>
              {last.author || last.from_me ? <Text style={[chatFont.bold, { color: c.lav, fontSize: 13 }]}>{last.from_me ? 'Toi' : last.author}</Text> : null}
              <Text numberOfLines={4} style={[chatFont.text, { color: c.t1, fontSize: 16, lineHeight: 22 }]}>{previewText(last)}</Text>
            </View>
          ) : null}

          <View style={[st.group, { backgroundColor: c.glass, borderColor: c.glassLine }]}>
            {isUnread(chat)
              ? <Item icon="check" label="Marquer comme lu" onPress={() => pick({ kind: 'read' })} />
              : <Item icon="chat" label="Marquer comme non lu" onPress={() => pick({ kind: 'unread' })} />}
            <Item icon="pin" label={chat.pinned_at ? 'Désépingler' : 'Épingler'} onPress={() => pick({ kind: chat.pinned_at ? 'unpin' : 'pin' })} />
            {muted
              ? <Item icon="bell" label="Réactiver les notifications" onPress={() => pick({ kind: 'mute', span: 'off' })} />
              : <Item icon="bellslash" label="Sourdine…" expanded={muteOpen} onPress={() => setMuteOpen((v) => !v)} />}
            {muteOpen && !muted ? (
              <View style={st.spans} role="menu" aria-label="Durée de la sourdine">
                {(Object.keys(MUTE_LABELS) as Exclude<MuteSpan, 'off'>[]).map((s) => (
                  <Pressable key={s} role="menuitem" accessibilityLabel={`Sourdine : ${MUTE_LABELS[s]}`} onPress={() => pick({ kind: 'mute', span: s })}
                    style={({ pressed }) => [st.span, { backgroundColor: c.glass, borderColor: c.glassLine }, pressed && { transform: [{ scale: 0.95 }] }]}>
                    <Text style={[chatFont.semibold, { color: c.t1, fontSize: 14 }]}>{MUTE_LABELS[s]}</Text>
                  </Pressable>
                ))}
              </View>
            ) : null}
            <Item icon="archive" label={chat.archived ? 'Sortir des archives' : 'Archiver'} onPress={() => pick({ kind: chat.archived ? 'unarchive' : 'archive' })} />
          </View>

          {direct && chat.user_id ? (
            <View style={[st.group, { backgroundColor: c.glass, borderColor: c.glassLine }]}>
              <Item icon="person" label="Voir le profil" onPress={() => pick({ kind: 'profile' })} />
              {!chat.blocked ? (confirmBlock ? (
                <View style={{ padding: 14, gap: 10 }}>
                  <Text style={[chatFont.text, { color: c.t2, fontSize: 14, lineHeight: 19 }]}>
                    {name} ne pourra plus t’écrire ni te voir dans les suggestions. Les modérateurs sont prévenus. Tu peux débloquer dans Réglages › Confidentialité.
                  </Text>
                  <Pressable accessibilityRole="button" accessibilityLabel={`Confirmer : bloquer ${name}`} onPress={() => pick({ kind: 'block' })}
                    style={({ pressed }) => [st.danger, { borderColor: c.danger }, pressed && { opacity: 0.7 }]}>
                    <Text style={[chatFont.bold, { color: c.danger, fontSize: 16 }]}>Bloquer {name}</Text>
                  </Pressable>
                </View>
              ) : <Item icon="block" danger label={`Bloquer ${name}`} onPress={() => setConfirmBlock(true)} />) : null}
            </View>
          ) : null}
        </View>
      </View>
    </Modal>
  );
}

function Item({ icon, label, onPress, danger, expanded }: { icon: IconName; label: string; onPress: () => void; danger?: boolean; expanded?: boolean }) {
  const c = useNeon();
  return (
    <Pressable role="menuitem" accessibilityLabel={label} accessibilityState={expanded === undefined ? undefined : { expanded }} onPress={onPress}
      style={({ pressed }) => [st.item, pressed && { backgroundColor: c.glass2 }]}>
      <Icon name={icon} size={20} color={danger ? c.danger : c.lav} />
      <Text style={[chatFont.medium, { flex: 1, color: danger ? c.danger : c.t1, fontSize: 17 }]}>{label}</Text>
      {expanded !== undefined ? <View style={{ transform: [{ rotate: expanded ? '90deg' : '0deg' }] }}><Icon name="chevr" size={16} color={c.t3} /></View> : null}
    </Pressable>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end' },
  sheet: { width: '100%', maxWidth: 520, alignSelf: 'center', borderTopLeftRadius: 34, borderTopRightRadius: 34, paddingHorizontal: 16, paddingBottom: 28, gap: 12 },
  grabber: { alignSelf: 'center', width: 40, height: 5, borderRadius: 3, marginTop: 8 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingTop: 10, paddingRight: 48 },
  preview: { borderRadius: 22, borderBottomLeftRadius: 8, borderWidth: 1, paddingHorizontal: 14, paddingVertical: 10, gap: 2, alignSelf: 'flex-start', maxWidth: '90%' },
  group: { borderRadius: 18, borderWidth: 1, overflow: 'hidden' },
  item: { minHeight: 50, flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 16 },
  spans: { flexDirection: 'row', flexWrap: 'wrap', gap: 8, paddingHorizontal: 16, paddingBottom: 12, paddingLeft: 50 },
  span: { height: 40, paddingHorizontal: 14, borderRadius: 20, borderWidth: 1, justifyContent: 'center' },
  danger: { height: 48, borderRadius: 16, borderWidth: 1.5, alignItems: 'center', justifyContent: 'center' },
});
