import { router } from 'expo-router';
import { useState } from 'react';
import { Image, Pressable, View } from 'react-native';

import { Avatar, T } from './ui';
import { deletedLabel, REACTIONS, type GroupMessage, type Reaction } from '@/lib/chats';
import { formatMessageTime } from '@/lib/format';
import { colors } from '@/lib/theme';

type Person = { name: string; photo: string | null };

type Props = {
  message: GroupMessage;
  mine: boolean;
  me: string;
  author: Person;
  quoted: { name: string; text: string } | null;
  photoUrl: string | null;
  reactions: Reaction[];
  canWrite: boolean;
  isAdmin: boolean;
  onReply: () => void;
  onReact: (emoji: string) => void;
  onPin: () => void;
  onDelete: () => void;
};

/** Une bulle façon WhatsApp : appui long (ou ⋯) pour réagir, répondre, épingler (admins) ou supprimer. */
export function ChatBubble({ message: m, mine, me, author, quoted, photoUrl, reactions, canWrite, isAdmin, onReply, onReact, onPin, onDelete }: Props) {
  const [open, setOpen] = useState(false);
  const deleted = Boolean(m.deleted_at);
  const counts = new Map<string, { n: number; mine: boolean }>();
  for (const r of reactions) {
    const c = counts.get(r.emoji) ?? { n: 0, mine: false };
    counts.set(r.emoji, { n: c.n + 1, mine: c.mine || r.user_id === me });
  }
  const bubbleColor = deleted ? colors.fill : mine ? colors.accent : colors.surface;
  const textColor = deleted ? colors.muted : mine ? colors.onAccent : colors.text;
  const actions = canWrite && !deleted;

  return (
    <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-end', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
      {!mine ? <Avatar id={m.user_id} name={author.name} photo={author.photo} /> : null}
      <View style={{ maxWidth: '80%', gap: 4, alignItems: mine ? 'flex-end' : 'flex-start' }}>
        {!mine ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Profil de ${author.name}`} onPress={() => router.push(`/member/${m.user_id}`)}>
            <T size={12} weight="bold" color={colors.lavender}>{author.name}</T>
          </Pressable>
        ) : null}
        <Pressable onLongPress={() => actions && setOpen((v) => !v)} accessibilityHint={actions ? 'Appui long pour réagir ou répondre' : undefined}
          style={{ padding: photoUrl ? 4 : 10, borderRadius: 16, backgroundColor: bubbleColor, gap: 6 }}>
          {m.pinned && !deleted ? <T size={11} weight="bold" color={mine ? colors.onAccent : colors.accent}>📌 Épinglé</T> : null}
          {quoted && !deleted ? (
            <View style={{ padding: 6, borderRadius: 8, backgroundColor: mine ? 'rgba(0,0,0,0.12)' : colors.surface2 }}>
              <T size={12} color={mine ? colors.onAccent : colors.muted} numberOfLines={2}>↪ {quoted.name} : {quoted.text}</T>
            </View>
          ) : null}
          {photoUrl && !deleted ? (
            <Image accessibilityLabel={`Photo de ${author.name}`} source={{ uri: photoUrl }} resizeMode="cover"
              style={{ width: 240, height: 240, borderRadius: 12, backgroundColor: colors.surface2 }} />
          ) : null}
          {deleted ? <T size={14} color={textColor} style={{ fontStyle: 'italic' }}>🚫 {deletedLabel(m)}</T>
            : m.body ? <T size={15} color={textColor} style={photoUrl ? { paddingHorizontal: 6, paddingBottom: 4 } : undefined}>{m.body}</T> : null}
        </Pressable>
        {counts.size ? (
          <View style={{ flexDirection: 'row', gap: 4, flexWrap: 'wrap' }}>
            {[...counts].map(([emoji, c]) => (
              <Pressable key={emoji} accessibilityRole="button" accessibilityLabel={`${emoji} ${c.n}${c.mine ? ', retirer ma réaction' : ''}`}
                disabled={!canWrite} onPress={() => onReact(emoji)}
                style={{ flexDirection: 'row', gap: 3, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 12,
                  backgroundColor: c.mine ? colors.accentDim : colors.surface2, borderWidth: 1, borderColor: c.mine ? colors.accent : 'transparent' }}>
                <T size={13}>{emoji}</T>
                <T size={12} muted>{c.n}</T>
              </Pressable>
            ))}
          </View>
        ) : null}
        <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
          <T muted size={11}>{formatMessageTime(m.created_at)}{m.edited_at && !deleted ? ' · modifié' : ''}</T>
          {actions ? (
            <Pressable accessibilityRole="button" accessibilityLabel="Actions du message" hitSlop={8} onPress={() => setOpen((v) => !v)}>
              <T muted size={13}>⋯</T>
            </Pressable>
          ) : null}
        </View>
        {open ? (
          <View style={{ gap: 6, padding: 8, borderRadius: 14, backgroundColor: colors.surface2 }}>
            <View style={{ flexDirection: 'row', gap: 6 }}>
              {REACTIONS.map((emoji) => (
                <Pressable key={emoji} accessibilityRole="button" accessibilityLabel={`Réagir ${emoji}`} hitSlop={4}
                  onPress={() => { setOpen(false); onReact(emoji); }}>
                  <T size={22}>{emoji}</T>
                </Pressable>
              ))}
            </View>
            <View style={{ flexDirection: 'row', gap: 14, flexWrap: 'wrap' }}>
              <Action label="Répondre" onPress={() => { setOpen(false); onReply(); }} />
              {isAdmin ? <Action label={m.pinned ? 'Désépingler' : 'Épingler'} onPress={() => { setOpen(false); onPin(); }} /> : null}
              {mine || isAdmin ? <Action label="Supprimer" danger onPress={() => { setOpen(false); onDelete(); }} /> : null}
            </View>
          </View>
        ) : null}
      </View>
    </View>
  );
}

function Action({ label, onPress, danger }: { label: string; onPress: () => void; danger?: boolean }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} hitSlop={6}>
      <T size={13} weight="semibold" color={danger ? colors.redSoft : colors.textSoft}>{label}</T>
    </Pressable>
  );
}
