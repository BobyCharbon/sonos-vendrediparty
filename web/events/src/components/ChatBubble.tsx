import { router } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Image, PanResponder, Pressable, View } from 'react-native';

import { Avatar, T } from './ui';
import { deletedLabel, REACTIONS, voiceClock, type GroupMessage, type Reaction } from '@/lib/chats';
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
  audioUrl?: string | null;
  reactions: Reaction[];
  canWrite: boolean;
  isAdmin: boolean;
  onReply: () => void;
  onReact: (emoji: string) => void;
  onPin: () => void;
  onDelete: () => void;
};

/** Distance à glisser vers la droite pour répondre (comme WhatsApp). */
const REPLY_SWIPE = 64;

/** Une bulle façon WhatsApp : glisser vers la droite pour répondre ; appui long (ou ⋯) pour réagir, répondre,
 * épingler (admins) ou supprimer. Un message en cours d'envoi s'affiche déjà, avec « Envoi… ». */
export function ChatBubble({ message: m, mine, me, author, quoted, photoUrl, audioUrl, reactions, canWrite, isAdmin, onReply, onReact, onPin, onDelete }: Props) {
  const [open, setOpen] = useState(false);
  const deleted = Boolean(m.deleted_at);
  const [swipe] = useState(() => new Animated.Value(0));
  const swipeable = canWrite && !deleted && !m.pending;
  const pan = useMemo(() => PanResponder.create({
    // Capture : le glissement horizontal l'emporte sur l'appui long de la bulle (qui garde les touchers simples).
    onMoveShouldSetPanResponderCapture: (_e, g) => swipeable && g.dx > 14 && Math.abs(g.dx) > Math.abs(g.dy) * 1.5,
    onPanResponderMove: (_e, g) => swipe.setValue(g.dx < REPLY_SWIPE ? Math.max(0, g.dx) : REPLY_SWIPE + (g.dx - REPLY_SWIPE) * 0.25),
    onPanResponderRelease: (_e, g) => {
      if (g.dx >= REPLY_SWIPE) onReply();
      Animated.spring(swipe, { toValue: 0, useNativeDriver: false }).start();
    },
    onPanResponderTerminate: () => Animated.spring(swipe, { toValue: 0, useNativeDriver: false }).start(),
  }), [swipe, swipeable, onReply]);
  const counts = new Map<string, { n: number; mine: boolean }>();
  for (const r of reactions) {
    const c = counts.get(r.emoji) ?? { n: 0, mine: false };
    counts.set(r.emoji, { n: c.n + 1, mine: c.mine || r.user_id === me });
  }
  const bubbleColor = deleted ? colors.fill : mine ? colors.accent : colors.surface;
  const textColor = deleted ? colors.muted : mine ? colors.onAccent : colors.text;
  const actions = canWrite && !deleted && !m.pending;

  return (
    <View {...pan.panHandlers}>
    <Animated.Text accessibilityElementsHidden style={{ position: 'absolute', left: 0, top: '40%', fontSize: 20, color: colors.accent,
      opacity: swipe.interpolate({ inputRange: [0, REPLY_SWIPE], outputRange: [0, 1], extrapolate: 'clamp' }) }}>↩︎</Animated.Text>
    <Animated.View style={{ transform: [{ translateX: swipe }], flexDirection: 'row', gap: 8, alignItems: 'flex-end', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
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
          {m.audio_seconds != null && !deleted ? <VoicePlayer url={audioUrl ?? null} seconds={m.audio_seconds} color={textColor} /> : null}
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
          <T muted size={11}>{m.pending ? 'Envoi…' : formatMessageTime(m.created_at)}{m.edited_at && !deleted ? ' · modifié' : ''}</T>
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
    </Animated.View>
    </View>
  );
}

/** Lecture d'un vocal dans le navigateur (un seul à la fois) : lecture / pause, avancement, durée, vitesse
 * 1× / 1,5× / 2× / 3× gardée pour les vocaux suivants (la hauteur de la voix est conservée par le navigateur). */
let playingNow: HTMLAudioElement | null = null;
const SPEEDS = [1, 1.5, 2, 3];
const SPEED_KEY = 'party-chat-voice-speed';

function savedSpeed(): number {
  try {
    const value = Number(localStorage.getItem(SPEED_KEY));
    return SPEEDS.includes(value) ? value : 1;
  } catch {
    return 1;
  }
}

export function nextSpeed(speed: number): number {
  return SPEEDS[(Math.max(0, SPEEDS.indexOf(speed)) + 1) % SPEEDS.length];
}

export function speedLabel(speed: number): string {
  return speed === 1.5 ? '1,5×' : `${speed}×`;
}

function VoicePlayer({ url, seconds, color }: { url: string | null; seconds: number; color: string }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [speed, setSpeed] = useState(savedSpeed);
  useEffect(() => () => { audio.current?.pause(); }, []);

  function changeSpeed() {
    const next = nextSpeed(speed);
    setSpeed(next);
    try { localStorage.setItem(SPEED_KEY, String(next)); } catch { /* stockage indisponible : vitesse pour ce vocal */ }
    if (audio.current) audio.current.playbackRate = next;
  }

  function toggle() {
    if (!url || typeof Audio === 'undefined') return;
    if (!audio.current) {
      const a = new Audio(url);
      a.ontimeupdate = () => setProgress(a.duration ? a.currentTime / a.duration : 0);
      a.onended = () => { setPlaying(false); setProgress(0); };
      a.onpause = () => setPlaying(false);
      a.onplay = () => setPlaying(true);
      audio.current = a;
    }
    if (playing) return audio.current.pause();
    if (playingNow && playingNow !== audio.current) playingNow.pause();
    playingNow = audio.current;
    audio.current.playbackRate = speed;
    void audio.current.play().catch(() => setPlaying(false));
  }

  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, minWidth: 180 }}>
      <Pressable accessibilityRole="button" accessibilityLabel={playing ? 'Pause' : 'Écouter le message vocal'} disabled={!url} onPress={toggle} hitSlop={8}>
        <T size={26} color={color}>{playing ? '⏸' : '▶️'}</T>
      </Pressable>
      <View style={{ flex: 1, gap: 4 }}>
        <View style={{ height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.25)' }}>
          <View style={{ height: 4, borderRadius: 2, width: `${Math.round(progress * 100)}%`, backgroundColor: color }} />
        </View>
        <T size={12} color={color}>{voiceClock(seconds)}</T>
      </View>
      <Pressable accessibilityRole="button" accessibilityLabel={`Vitesse de lecture ${speedLabel(speed)}`} onPress={changeSpeed} hitSlop={8}
        style={{ paddingHorizontal: 8, paddingVertical: 4, borderRadius: 12, backgroundColor: 'rgba(255,255,255,0.18)' }}>
        <T size={12} weight="bold" color={color}>{speedLabel(speed)}</T>
      </Pressable>
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
