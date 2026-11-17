import { router } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Animated, Image, PanResponder, Pressable, View } from 'react-native';

import { LinkedText } from './LinkedText';
import { Avatar, T } from './ui';
import { deletedLabel, nameColor, REACTIONS, voiceClock, withoutAnnounceTag, type GroupMessage, type Reaction } from '@/lib/chats';
import { formatClock } from '@/lib/format';
import { duration, enter, pressTransition, transition, useChangedSinceMount } from '@/lib/motion';
import { colors } from '@/lib/theme';

type Person = { name: string; photo: string | null };

type Props = {
  message: GroupMessage;
  mine: boolean;
  me: string;
  author: Person;
  quoted: { name: string; text: string; author?: string } | null;
  photoUrl: string | null;
  audioUrl?: string | null;
  reactions: Reaction[];
  canWrite: boolean;
  isAdmin: boolean;
  /** Admin ou organisateur du groupe : retire les annonces. */
  isStaff?: boolean;
  /** Peut épingler (admins d'un groupe ; les deux personnes d'un message direct). Par défaut : isAdmin. */
  canPin?: boolean;
  onReply: () => void;
  onReact: (emoji: string) => void;
  onPin: () => void;
  onDelete: () => void;
  /** « Signaler » (modération commune) : sur le message d'un autre, jamais sur le sien. */
  onReport?: () => void;
  /** Message arrivé pendant que la discussion est ouverte : la bulle monte (pas à l'ouverture ni au défilement). */
  fresh?: boolean;
  /** Série d'une même personne (fil façon WhatsApp) : nom en tête de la première bulle, photo à côté de la dernière. */
  first?: boolean;
  last?: boolean;
  /** Groupe ou événement : nom et photo des autres (pas dans un message direct). */
  showAuthor?: boolean;
  /** Surnoms des membres : leurs « @surnom » en gras et en couleur. */
  names?: string[];
  /** Toucher la citation : remonter au message d'origine. */
  onQuote?: () => void;
  /** Message montré par un toucher (citation, bandeau) : il clignote. */
  flash?: boolean;
};

/** Distance à glisser vers la droite pour répondre (comme WhatsApp). */
const REPLY_SWIPE = 64;
const AVATAR = 28;
/** Mes bulles : le rose de Party en profondeur (comme le vert sombre de WhatsApp), texte blanc lisible (AA). */
export const MINE_BUBBLE = '#7E1F5C';
const MINE_FLASH = '#A3317A';
const MINE_META = 'rgba(255,255,255,0.68)';
const MINE_MENTION = '#FFC6E3';

/** Queue de la bulle (en tête de série), du côté de l'auteur : un petit triangle collé au coin du haut. */
function Tail({ mine, color }: { mine: boolean; color: string }) {
  return (
    <View pointerEvents="none" style={[{ position: 'absolute', top: 0, width: 0, height: 0, borderTopWidth: 10, borderTopColor: color },
      mine ? { right: -7, borderRightWidth: 8, borderRightColor: 'transparent' } : { left: -7, borderLeftWidth: 8, borderLeftColor: 'transparent' },
      transition('border-color', duration.base)]} />
  );
}

/** Texte d'un message : liens touchables (comme partout) et @citations en gras et en couleur. */
export function MentionText({ body, names, color, mentionColor, size = 15 }: { body: string; names: string[]; color: string; mentionColor: string; size?: number }) {
  return <LinkedText text={body} size={size} color={color} linkColor={mentionColor} mentions={{ names, color: mentionColor }} />;
}

/** Heure (« modifié », « Envoi… », coche une fois reçu) : en bas à droite, DANS la bulle, jamais par-dessus le texte. */
function Meta({ m, mine, deleted, light }: { m: GroupMessage; mine: boolean; deleted: boolean; light?: boolean }) {
  const color = light ? '#fff' : mine && !deleted ? MINE_META : colors.muted;
  return (
    <T size={11} color={color} style={{ fontVariant: ['tabular-nums'] }}>
      {m.edited_at && !deleted ? 'modifié ' : ''}{m.pending ? 'Envoi…' : formatClock(m.created_at)}{mine && !deleted ? (m.pending ? ' 🕓' : ' ✓') : ''}
    </T>
  );
}

/** Une bulle façon WhatsApp : glisser vers la droite pour répondre ; appui long (ou ⋯ à côté) pour réagir, répondre,
 * épingler ou retirer une annonce, supprimer, signaler. Dans un groupe, le nom (en couleur) en tête de la série et la
 * photo à côté de la dernière bulle ; l'heure dans la bulle. Un message en cours d'envoi s'affiche déjà (« Envoi… »). */
export function ChatBubble({ message: m, mine, me, author, quoted, photoUrl, audioUrl, reactions, canWrite, isAdmin, isStaff = isAdmin, canPin = isAdmin,
  onReply, onReact, onPin, onDelete, onReport, fresh = false, first = true, last = true, showAuthor = true, names = [], onQuote, flash = false }: Props) {
  const [open, setOpen] = useState(false);
  // Fixé à l'apparition : la bulle ne remonte pas quand un autre message arrive.
  const [arrive] = useState(() => (fresh ? enter(mine ? 'bubbleMine' : 'bubbleTheirs') : undefined));
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
  // Une réaction ajoutée ici (ou par un autre) se pose ; à l'ouverture, les réactions sont déjà là.
  const reacted = useChangedSinceMount([...counts].map(([e, c]) => `${e}${c.n}${c.mine}`).join());
  const baseColor = deleted ? colors.surface : mine ? MINE_BUBBLE : colors.surface;
  const bubbleColor = flash ? (mine ? MINE_FLASH : colors.surface2) : baseColor;
  const textColor = deleted ? colors.muted : colors.text;
  const actions = (canWrite || (!mine && !!onReport)) && !deleted && !m.pending;
  const announced = Boolean(m.announcement && m.pinned) && !deleted;
  const showName = showAuthor && first && !mine;
  const photoOnly = Boolean(photoUrl) && !m.body && !deleted;
  // Tête de série : la queue au coin du haut, côté auteur (comme WhatsApp) ; les suivantes, des coins ronds.
  const corners = mine ? { borderTopRightRadius: first ? 0 : 16 } : { borderTopLeftRadius: first ? 0 : 16 };

  if (announced) {
    return (
      <View style={[arrive, { gap: 6, paddingVertical: 4 }]}>
        <Pressable onLongPress={() => actions && setOpen((v) => !v)} accessibilityRole="summary"
          accessibilityLabel={`Annonce de ${mine ? 'toi' : author.name} : ${withoutAnnounceTag(m.body) || 'Photo'}`}
          style={[{ padding: 14, borderRadius: 18, gap: 8, backgroundColor: colors.accentDim, borderWidth: 1.5, borderColor: colors.accent },
            flash && { backgroundColor: '#5A1F45' }, transition('background-color', duration.base), m.pending && { opacity: 0.72 }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <T size={12} weight="bold" color={colors.accent}>📣 ANNONCE</T>
            <T size={12} weight="semibold" muted numberOfLines={1} style={{ flex: 1 }}>· {mine ? 'toi' : author.name}</T>
            <Meta m={m} mine={false} deleted={false} />
            {actions ? <MoreButton onPress={() => setOpen((v) => !v)} style={{ marginBottom: 0 }} /> : null}
          </View>
          {photoUrl ? <Image accessibilityLabel={`Photo de ${author.name}`} source={{ uri: photoUrl }} resizeMode="cover"
            style={{ width: '100%', height: 220, borderRadius: 12, backgroundColor: colors.surface2 }} /> : null}
          {m.audio_seconds != null ? <VoicePlayer url={audioUrl ?? null} seconds={m.audio_seconds} color={colors.text} /> : null}
          {withoutAnnounceTag(m.body) ? <MentionText body={withoutAnnounceTag(m.body)} names={names} color={colors.text} mentionColor={colors.accent} size={16} /> : null}
        </Pressable>
        <Reactions counts={counts} reacted={reacted} canWrite={canWrite} onReact={onReact} align="flex-start" />
        {open ? <ActionMenu canWrite={canWrite} mine={mine} announced isStaff={isStaff} canPin={canPin} isAdmin={isAdmin} pinned={m.pinned}
          copyText={withoutAnnounceTag(m.body)} onClose={() => setOpen(false)} onReact={onReact} onReply={onReply} onPin={onPin} onDelete={onDelete} onReport={onReport} /> : null}
      </View>
    );
  }

  return (
    <View {...pan.panHandlers} style={arrive}>
    <Animated.Text accessibilityElementsHidden style={{ position: 'absolute', left: 0, top: '40%', fontSize: 20, color: colors.accent,
      opacity: swipe.interpolate({ inputRange: [0, REPLY_SWIPE], outputRange: [0, 1], extrapolate: 'clamp' }) }}>↩︎</Animated.Text>
    <Animated.View style={{ transform: [{ translateX: swipe }], flexDirection: 'row', gap: 6, alignItems: 'flex-end', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
      {!mine && showAuthor ? (last ? <Avatar id={m.user_id} name={author.name} photo={author.photo} size={AVATAR} /> : <View style={{ width: AVATAR }} />) : null}
      {mine && actions ? <MoreButton onPress={() => setOpen((v) => !v)} /> : null}
      <View style={{ maxWidth: '78%', alignItems: mine ? 'flex-end' : 'flex-start', marginLeft: mine ? 0 : 4, marginRight: mine ? 4 : 0 }}>
        {first ? <Tail mine={mine} color={bubbleColor} /> : null}
        <Pressable onLongPress={() => actions && setOpen((v) => !v)} accessibilityHint={actions ? 'Appui long pour réagir ou répondre' : undefined}
          style={({ pressed }) => [{ paddingHorizontal: photoUrl ? 4 : 10, paddingVertical: photoUrl ? 4 : 6, borderRadius: 16, backgroundColor: bubbleColor, gap: 4,
            shadowColor: '#000', shadowOpacity: 0.18, shadowRadius: 1.5, shadowOffset: { width: 0, height: 1 } },
            corners,
            transition('transform, opacity, background-color', duration.base), m.pending && { opacity: 0.72 }, pressed && { transform: [{ scale: 0.98 }] }]}>
          {showName ? (
            <Pressable accessibilityRole="button" accessibilityLabel={`Profil de ${author.name}`} onPress={() => router.push(`/member/${m.user_id}`)}
              style={photoUrl ? { paddingHorizontal: 8, paddingTop: 4 } : undefined}>
              <T size={13} weight="bold" color={nameColor(m.user_id)} numberOfLines={1}>{author.name}</T>
            </Pressable>
          ) : null}
          {m.pinned && !deleted ? <T size={11} weight="bold" color={mine ? MINE_MENTION : colors.accent} style={photoUrl ? { paddingHorizontal: 8 } : undefined}>📌 Épinglé</T> : null}
          {quoted && !deleted ? (
            // Citation dans la bulle, façon WhatsApp : barre de la couleur de l'auteur cité, son nom, deux lignes.
            <Pressable accessibilityRole="button" accessibilityLabel={`Réponse à ${quoted.name} : ${quoted.text}`} accessibilityHint="Montre le message d’origine"
              onPress={onQuote} disabled={!onQuote}
              style={({ pressed }) => [{ flexDirection: 'row', gap: 8, paddingVertical: 5, paddingRight: 8, borderRadius: 8, overflow: 'hidden',
                backgroundColor: 'rgba(0,0,0,0.22)', minWidth: 120 }, pressed && { opacity: 0.75 }]}>
              <View style={{ width: 4, backgroundColor: nameColor(quoted.author ?? quoted.name) }} />
              <View style={{ flexShrink: 1 }}>
                <T size={12} weight="bold" color={nameColor(quoted.author ?? quoted.name)} numberOfLines={1}>{quoted.name}</T>
                <T size={12} color={mine ? MINE_META : colors.muted} numberOfLines={2}>{quoted.text}</T>
              </View>
            </Pressable>
          ) : null}
          {photoUrl && !deleted ? (
            <View>
              <Image accessibilityLabel={`Photo de ${author.name}`} source={{ uri: photoUrl }} resizeMode="cover"
                style={{ width: 240, height: 240, borderRadius: 14, backgroundColor: colors.surface2 }} />
              {photoOnly ? (
                <View style={{ position: 'absolute', right: 6, bottom: 6, paddingHorizontal: 6, paddingVertical: 2, borderRadius: 10, backgroundColor: 'rgba(0,0,0,0.5)' }}>
                  <Meta m={m} mine={mine} deleted={false} light />
                </View>
              ) : null}
            </View>
          ) : null}
          {m.audio_seconds != null && !deleted ? <VoicePlayer url={audioUrl ?? null} seconds={m.audio_seconds} color={textColor} /> : null}
          {deleted ? (
            <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
              <T size={14} color={textColor} style={{ fontStyle: 'italic', flexShrink: 1 }}>🚫 {deletedLabel(m)}</T>
              <Meta m={m} mine={mine} deleted />
            </View>
          ) : m.body ? (
            // Le texte puis l'heure, à droite, sur la dernière ligne quand elle a la place, sinon dessous : rien ne se chevauche.
            <View style={[{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-end', columnGap: 8 },
              photoUrl ? { paddingHorizontal: 8, paddingBottom: 4 } : null]}>
              <View style={{ flexShrink: 1 }}>
                <MentionText body={m.body} names={names} color={textColor} mentionColor={mine ? MINE_MENTION : colors.accentSoft} />
              </View>
              <View style={{ marginLeft: 'auto' }}><Meta m={m} mine={mine} deleted={false} /></View>
            </View>
          ) : !photoUrl ? <Meta m={m} mine={mine} deleted={false} /> : null}
        </Pressable>
        <Reactions counts={counts} reacted={reacted} canWrite={canWrite} onReact={onReact} align={mine ? 'flex-end' : 'flex-start'} overlap />
        {open ? <ActionMenu canWrite={canWrite} mine={mine} announced={false} isStaff={isStaff} canPin={canPin} isAdmin={isAdmin} pinned={m.pinned}
          copyText={m.body} onClose={() => setOpen(false)} onReact={onReact} onReply={onReply} onPin={onPin} onDelete={onDelete} onReport={onReport} /> : null}
      </View>
      {!mine && actions ? <MoreButton onPress={() => setOpen((v) => !v)} /> : null}
    </Animated.View>
    </View>
  );
}

/** « ⋯ » à côté de la bulle (pas dessus) : ouvre les actions du message. */
function MoreButton({ onPress, style }: { onPress: () => void; style?: object }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel="Actions du message" hitSlop={8} onPress={onPress}
      style={({ pressed }) => [{ width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center', marginBottom: 4,
        backgroundColor: pressed ? colors.surface2 : 'transparent' }, style]}>
      <T muted size={14}>⋯</T>
    </Pressable>
  );
}

/** Réactions en pastilles, posées à cheval sur le bas de la bulle (WhatsApp) sans cacher l'heure : un toucher ajoute ou
 * retire la mienne. */
function Reactions({ counts, reacted, canWrite, onReact, align, overlap = false }: { counts: Map<string, { n: number; mine: boolean }>; reacted: boolean;
  canWrite: boolean; onReact: (emoji: string) => void; align: 'flex-start' | 'flex-end'; overlap?: boolean }) {
  if (!counts.size) return null;
  return (
    <View style={{ flexDirection: 'row', gap: 4, flexWrap: 'wrap', marginTop: overlap ? -6 : 4, alignSelf: align, paddingHorizontal: overlap ? 8 : 0 }}>
      {[...counts].map(([emoji, c]) => (
        <Pressable key={`${emoji}-${c.n}-${c.mine}`} accessibilityRole="button" accessibilityLabel={`${emoji} ${c.n}${c.mine ? ', retirer ma réaction' : ''}`}
          disabled={!canWrite} onPress={() => onReact(emoji)}
          style={({ pressed }) => [{ flexDirection: 'row', gap: 3, paddingHorizontal: 7, paddingVertical: 2, borderRadius: 12,
            backgroundColor: c.mine ? colors.accentDim : colors.surface2, borderWidth: 2, borderColor: colors.bg },
            reacted ? enter('pop') : null, pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
          <T size={13}>{emoji}</T>
          {c.n > 1 ? <T size={12} muted>{c.n}</T> : null}
        </Pressable>
      ))}
    </View>
  );
}

/** Actions d'un message, façon WhatsApp : la barre des réactions en pastille, puis la liste Répondre, Copier, Épingler,
 * Supprimer, Signaler. */
function ActionMenu({ canWrite, mine, announced, isStaff, canPin, isAdmin, pinned, copyText, onClose, onReact, onReply, onPin, onDelete, onReport }: {
  canWrite: boolean; mine: boolean; announced: boolean; isStaff: boolean; canPin: boolean; isAdmin: boolean; pinned: boolean; copyText?: string;
  onClose: () => void; onReact: (emoji: string) => void; onReply: () => void; onPin: () => void; onDelete: () => void; onReport?: () => void }) {
  const run = (f: () => void) => () => { onClose(); f(); };
  const copy = copyText && typeof navigator !== 'undefined' && navigator.clipboard
    ? () => { void navigator.clipboard.writeText(copyText).catch(() => {}); } : null;
  return (
    <View accessibilityRole="menu" style={[{ gap: 6, marginTop: 8, alignSelf: mine ? 'flex-end' : 'flex-start', alignItems: mine ? 'flex-end' : 'flex-start' }, enter('pop')]}>
      {canWrite ? (
        <View style={{ flexDirection: 'row', gap: 6, paddingHorizontal: 10, paddingVertical: 6, borderRadius: 26, backgroundColor: colors.surface2,
          borderWidth: 1, borderColor: colors.lineStrong }}>
          {REACTIONS.map((emoji) => (
            <Pressable key={emoji} accessibilityRole="button" accessibilityLabel={`Réagir ${emoji}`} hitSlop={4} onPress={run(() => onReact(emoji))}
              style={({ pressed }) => [{ width: 34, height: 34, alignItems: 'center', justifyContent: 'center', borderRadius: 17 }, pressTransition,
                pressed && { transform: [{ scale: 1.3 }], backgroundColor: colors.fill }]}>
              <T size={22}>{emoji}</T>
            </Pressable>
          ))}
        </View>
      ) : null}
      <View style={{ minWidth: 190, borderRadius: 14, backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.lineStrong, overflow: 'hidden' }}>
        {canWrite ? <Action icon="↩︎" label="Répondre" onPress={run(onReply)} /> : null}
        {copy ? <Action icon="⧉" label="Copier" onPress={run(copy)} /> : null}
        {announced ? (isStaff ? <Action icon="📣" label="Retirer l’annonce" onPress={run(onPin)} /> : null)
          : canPin ? <Action icon="📌" label={pinned ? 'Désépingler' : 'Épingler'} onPress={run(onPin)} /> : null}
        {!mine && onReport ? <Action icon="⚑" label="Signaler" danger onPress={run(onReport)} /> : null}
        {mine || isAdmin ? <Action icon="🗑" label="Supprimer" danger onPress={run(onDelete)} /> : null}
      </View>
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
        <View style={{ height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.25)', overflow: 'hidden' }}>
          {/* Avancement en scaleX (pas de largeur recalculée à chaque timeupdate), lissé entre deux mises à jour. */}
          <View style={[{ height: 4, backgroundColor: color, transform: [{ scaleX: progress }] }, voiceFill, transition('transform', 250, 'linear')]} />
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

const voiceFill = { transformOrigin: 'left' } as const;

function Action({ label, icon, onPress, danger }: { label: string; icon: string; onPress: () => void; danger?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
      style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 44, paddingHorizontal: 14 },
        transition('background-color', duration.fast), pressed && { backgroundColor: colors.fill }]}>
      <T size={15} weight="semibold" color={danger ? colors.redSoft : colors.text} style={{ flex: 1 }}>{label}</T>
      <T size={15} color={danger ? colors.redSoft : colors.muted}>{icon}</T>
    </Pressable>
  );
}
