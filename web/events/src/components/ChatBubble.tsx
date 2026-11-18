import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Animated, Image, PanResponder, Pressable, Text, View, type ViewStyle } from 'react-native';

import { C, cf, Icon, lavButton, mineBubble, neonName, web } from './chats/conversation/kit';
import type { PrivateQuote } from './chats/conversation/data';
import { LinkedText } from './LinkedText';
import { Avatar } from './ui';
import { deletedLabel, voiceClock, withoutAnnounceTag, type GroupMessage, type Reaction } from '@/lib/chats';
import { formatClock } from '@/lib/format';
import { duration, enter, pressTransition, transition, useChangedSinceMount } from '@/lib/motion';

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
  onReply: () => void;
  onReact: (emoji: string) => void;
  /** Menu du message (appui long, clic droit, Entrée) ; absent : aucune action possible. */
  onMenu?: () => void;
  /** Toucher le nom ou la photo de l'auteur : son mini-profil. */
  onAuthor?: () => void;
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
  /** Mon dernier message lu par l'autre personne (message direct, confirmations de lecture des deux côtés). */
  seen?: boolean;
  /** Carte de la soirée jointe au message. */
  card?: ReactNode;
  /** « Répondre en privé » : le message de groupe / de soirée cité. */
  privateQuote?: PrivateQuote | null;
  /** Message pas parti (réseau absent) : un toucher le renvoie. */
  onRetry?: () => void;
};

/** Distance à glisser vers la droite pour répondre (comme WhatsApp). */
const REPLY_SWIPE = 64;
const AVATAR = 28;
/** Coins : 22 px, 8 px du côté de l'auteur entre deux bulles d'une même série (kit.css .msg.first/.mid/.last). */
const R = 22;
const TIGHT = 8;

/** Texte d'un message : liens touchables (comme partout) et @citations en gras et en couleur. */
export function MentionText({ body, names, color, mentionColor, size = 17 }: { body: string; names: string[]; color: string; mentionColor: string; size?: number }) {
  return <LinkedText text={body} size={size} color={color} linkColor={mentionColor} mentions={{ names, color: mentionColor }} style={{ lineHeight: Math.round(size * 1.35) }} />;
}

/** Heure (« modifié », « Envoi… », ✓ reçu, « Vu ») : en bas à droite, DANS la bulle, jamais par-dessus le texte. */
function Meta({ m, mine, deleted, light, seen }: { m: GroupMessage; mine: boolean; deleted: boolean; light?: boolean; seen?: boolean }) {
  const color = light ? 'rgba(255,255,255,0.9)' : mine && !deleted ? 'rgba(255,255,255,0.9)' : C.t3;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 3 }}>
      <Text style={[cf.num, { color, fontSize: 12, lineHeight: 14 }]}>
        {m.edited_at && !deleted ? 'modifié · ' : ''}{m.pending ? 'Envoi…' : formatClock(m.created_at)}{mine && seen && !m.pending ? ' · Vu' : ''}
      </Text>
      {mine && m.failed ? null : mine && !deleted ? (m.pending
        ? <Text style={{ fontSize: 10, color }}>🕓</Text>
        : <View accessibilityLabel={seen ? 'Lu' : 'Envoyé'}><Icon name={seen ? 'check2' : 'check'} size={13} stroke={2.4} color={light ? '#fff' : '#DCD5FF'} /></View>) : null}
    </View>
  );
}

/** Une bulle façon WhatsApp, graphisme « Néon club » : glisser vers la droite pour répondre ; appui long, clic droit ou
 * Entrée pour le menu (réactions, répondre, modifier, épingler, supprimer, signaler). Dans un groupe, le nom (couleur de
 * la palette) en tête de la série et la photo à côté de la dernière bulle (toucher : mini-profil) ; l'heure dans la bulle. */
export function ChatBubble({ message: m, mine, me, author, quoted, photoUrl, audioUrl, reactions, canWrite,
  onReply, onReact, onMenu, onAuthor, fresh = false, first = true, last = true, showAuthor = true, names = [], onQuote, flash = false,
  seen = false, card, privateQuote, onRetry }: Props) {
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
  const menu = onMenu && !deleted && !m.pending ? onMenu : undefined;
  // Clic droit (souris) et Entrée / touche Menu (clavier, lecteur d'écran) ouvrent le même menu que l'appui long.
  const webMenu = menu ? ({
    onContextMenu: (e: { preventDefault: () => void }) => { e.preventDefault(); menu(); },
    onKeyDown: (e: { key: string; shiftKey?: boolean; target?: unknown; currentTarget?: unknown; preventDefault: () => void }) => {
      // La bulle elle-même (pas un lien du texte, qui garde Entrée pour s'ouvrir).
      if (e.target !== e.currentTarget) return;
      if (e.key === 'Enter' || e.key === ' ' || e.key === 'ContextMenu' || (e.key === 'F10' && e.shiftKey)) { e.preventDefault(); menu(); }
    },
    focusable: true,
  } as object) : {};
  const announced = Boolean(m.announcement && m.pinned) && !deleted;
  const showName = showAuthor && first && !mine;
  const photoOnly = Boolean(photoUrl) && !m.body && !deleted;
  const corners: ViewStyle = mine
    ? { borderTopRightRadius: first ? R : TIGHT, borderBottomRightRadius: last && !first ? R : TIGHT }
    : { borderTopLeftRadius: first ? R : TIGHT, borderBottomLeftRadius: last && !first ? R : TIGHT };
  const textColor = deleted ? C.t3 : mine ? '#FFFFFF' : C.t1;
  const authorButton = (child: ReactNode, label: string) => (onAuthor
    ? <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onAuthor} hitSlop={8}>{child}</Pressable>
    : child);

  if (announced) {
    return (
      <View style={[arrive, { gap: 6, paddingVertical: 4 }]}>
        <Pressable onLongPress={menu} delayLongPress={380} {...webMenu} accessibilityRole="summary"
          accessibilityLabel={`Annonce de ${mine ? 'toi' : author.name} : ${withoutAnnounceTag(m.body) || 'Photo'}`}
          accessibilityHint={menu ? 'Appui long pour les actions' : undefined}
          style={[{ padding: 14, borderRadius: R, gap: 8, borderWidth: 1.5, borderColor: 'rgba(255,79,154,0.65)' },
            web({ backgroundColor: '#24112F', backgroundImage: 'radial-gradient(120% 90% at 0% 0%, rgba(255,79,154,0.22), transparent 62%)',
              boxShadow: '0 14px 30px -18px rgba(255,79,154,0.6)' }),
            flash && { backgroundColor: '#5A1F45' }, transition('background-color', duration.base), m.pending && { opacity: 0.72 }]}>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <Text style={[cf.label, { color: C.pinkInk, fontSize: 12 }]}>📣 ANNONCE</Text>
            <Text numberOfLines={1} style={[cf.semibold, { color: C.t2, fontSize: 12, flex: 1 }]}>· {mine ? 'toi' : author.name}</Text>
            <Meta m={m} mine={false} deleted={false} />
          </View>
          {photoUrl ? <Image accessibilityLabel={`Photo de ${author.name}`} source={{ uri: photoUrl }} resizeMode="cover"
            style={{ width: '100%', height: 220, borderRadius: 16, backgroundColor: C.s2 }} /> : null}
          {m.audio_seconds != null ? <VoicePlayer id={m.id} url={audioUrl ?? null} seconds={m.audio_seconds} mine={false} /> : null}
          {withoutAnnounceTag(m.body) ? <MentionText body={withoutAnnounceTag(m.body)} names={names} color={C.t1} mentionColor={C.pinkInk} size={17} /> : null}
        </Pressable>
        <Reactions counts={counts} reacted={reacted} canWrite={canWrite} onReact={onReact} align="flex-start" />
      </View>
    );
  }

  return (
    <View {...pan.panHandlers} style={arrive}>
    <Animated.View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ position: 'absolute', left: 4, top: '35%',
      opacity: swipe.interpolate({ inputRange: [0, REPLY_SWIPE], outputRange: [0, 1], extrapolate: 'clamp' }) }}>
      <Icon name="reply" size={20} color={C.lav} />
    </Animated.View>
    <Animated.View style={{ transform: [{ translateX: swipe }], flexDirection: 'row', gap: 6, alignItems: 'flex-end', justifyContent: mine ? 'flex-end' : 'flex-start' }}>
      {!mine && showAuthor ? (last
        ? authorButton(<Avatar id={m.user_id} name={author.name} photo={author.photo} size={AVATAR} profile={false} />, `Profil de ${author.name}`)
        : <View style={{ width: AVATAR }} />) : null}
      <View style={{ maxWidth: card ? '86%' : '78%', alignItems: mine ? 'flex-end' : 'flex-start' }}>
        {card && !deleted ? <View style={{ marginBottom: m.body ? 3 : 0, maxWidth: '100%' }}>{card}</View> : null}
        {card && !deleted && !m.body && !photoUrl && m.audio_seconds == null ? (
          <View style={{ marginTop: 2, paddingHorizontal: 4 }}><Meta m={m} mine={mine} deleted={false} seen={seen} /></View>
        ) : (
        <Pressable onLongPress={menu} delayLongPress={380} {...webMenu} onPress={m.failed ? onRetry : undefined}
          accessibilityHint={m.failed ? 'Pas envoyé : touche pour réessayer' : menu ? 'Appui long ou clic droit pour réagir, répondre ou signaler' : undefined}
          style={({ pressed }) => [{ paddingHorizontal: photoUrl ? 4 : 13, paddingTop: photoUrl ? 4 : 9, paddingBottom: photoUrl ? 4 : 8, borderRadius: R, gap: 5 },
            deleted ? { backgroundColor: 'rgba(255,255,255,0.05)', borderWidth: 1, borderColor: C.line }
              : mine ? mineBubble : { backgroundColor: C.theirs, borderWidth: 1, borderColor: C.theirsLine },
            corners, flash && (mine ? { backgroundColor: C.lavB, backgroundImage: 'none' } as ViewStyle : { backgroundColor: C.s2 }),
            transition('transform, opacity, background-color', duration.base), m.pending && { opacity: 0.72 }, pressed && menu && { transform: [{ scale: 0.98 }] }]}>
          {showName ? authorButton(
            <Text numberOfLines={1} style={[cf.bold, { color: neonName(m.user_id), fontSize: 13 }, photoUrl ? { paddingHorizontal: 9, paddingTop: 4 } : null]}>{author.name}</Text>,
            `Profil de ${author.name}`) : null}
          {m.pinned && !deleted ? (
            <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 4 }, photoUrl ? { paddingHorizontal: 9 } : null]}>
              <Icon name="pin" size={12} color={mine ? '#E6DFFF' : C.lav} stroke={2.2} />
              <Text style={[cf.bold, { fontSize: 11, color: mine ? '#E6DFFF' : C.lav }]}>Épinglé</Text>
            </View>
          ) : null}
          {privateQuote && !deleted ? (
            <View accessibilityLabel={`Réponse privée à un message de ${privateQuote.author} dans ${privateQuote.title} : ${privateQuote.excerpt}`}
              style={[quoteBox(mine), { marginHorizontal: -5 }]}>
              <View style={quoteBar(mine)} />
              <Text numberOfLines={1} style={[cf.bold, { fontSize: 13, color: mine ? '#E6DFFF' : C.lav }]}>
                {privateQuote.author} · {privateQuote.from === 'event' ? '🎉 ' : ''}{privateQuote.title}
              </Text>
              <Text numberOfLines={2} style={[cf.text, { fontSize: 14, lineHeight: 19, color: mine ? 'rgba(255,255,255,0.82)' : C.t2 }]}>{privateQuote.excerpt}</Text>
            </View>
          ) : null}
          {quoted && !deleted ? (
            <Pressable accessibilityRole="button" accessibilityLabel={`Réponse à ${quoted.name} : ${quoted.text}`} accessibilityHint="Montre le message d’origine"
              onPress={onQuote} disabled={!onQuote} style={[quoteBox(mine), photoUrl ? { marginHorizontal: 0 } : { marginHorizontal: -5 }]}>
              <View style={[quoteBar(mine), !mine && { backgroundColor: neonName(quoted.author ?? quoted.name) }]} />
              <Text numberOfLines={1} style={[cf.bold, { fontSize: 13, color: mine ? '#E6DFFF' : neonName(quoted.author ?? quoted.name) }]}>{quoted.name}</Text>
              <Text numberOfLines={2} style={[cf.text, { fontSize: 14, lineHeight: 19, color: mine ? 'rgba(255,255,255,0.82)' : C.t2 }]}>{quoted.text}</Text>
            </Pressable>
          ) : null}
          {photoUrl && !deleted ? (
            <View>
              <Image accessibilityLabel={`Photo de ${author.name}`} source={{ uri: photoUrl }} resizeMode="cover"
                style={{ width: 244, height: 244, borderRadius: 18, backgroundColor: C.s2 }} />
              {photoOnly ? (
                <View style={[{ position: 'absolute', left: 0, right: 0, bottom: 0, paddingTop: 26, paddingBottom: 8, paddingHorizontal: 10,
                  borderBottomLeftRadius: 18, borderBottomRightRadius: 18, alignItems: 'flex-end' },
                  web({ backgroundImage: 'linear-gradient(180deg, transparent, rgba(10,6,20,0.72))' })]}>
                  <Meta m={m} mine={mine} deleted={false} light seen={seen} />
                </View>
              ) : null}
            </View>
          ) : null}
          {m.audio_seconds != null && !deleted ? <VoicePlayer id={m.id} url={audioUrl ?? null} seconds={m.audio_seconds} mine={mine} /> : null}
          {deleted ? (
            <View style={{ flexDirection: 'row', alignItems: 'flex-end', gap: 8 }}>
              <Text style={[cf.text, { fontSize: 15, color: textColor, fontStyle: 'italic', flexShrink: 1 }]}>🚫 {deletedLabel(m)}</Text>
              <Meta m={m} mine={mine} deleted />
            </View>
          ) : m.body ? (
            // Le texte puis l'heure, à droite, sur la dernière ligne quand elle a la place, sinon dessous : rien ne se chevauche.
            <View style={[{ flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-end', columnGap: 10 },
              photoUrl ? { paddingHorizontal: 9, paddingBottom: 4 } : null]}>
              <View style={{ flexShrink: 1 }}>
                <MentionText body={m.body} names={names} color={textColor} mentionColor={mine ? '#FFFFFF' : C.lav} />
              </View>
              <View style={{ marginLeft: 'auto', paddingBottom: 1 }}><Meta m={m} mine={mine} deleted={false} seen={seen} /></View>
            </View>
          ) : !photoUrl ? <View style={{ alignSelf: 'flex-end' }}><Meta m={m} mine={mine} deleted={false} seen={seen} /></View> : null}
        </Pressable>
        )}
        {m.failed ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Pas envoyé. Toucher pour réessayer" onPress={onRetry} hitSlop={8}
            style={[{ flexDirection: 'row', alignItems: 'center', gap: 4, marginTop: 4, paddingHorizontal: 4 }, enter('fade')]}>
            <Text style={[cf.semibold, { fontSize: 12, color: C.danger }]}>⚠︎ Pas envoyé · Toucher pour réessayer</Text>
          </Pressable>
        ) : null}
        <Reactions counts={counts} reacted={reacted} canWrite={canWrite} onReact={onReact} align={mine ? 'flex-end' : 'flex-start'} />
      </View>
    </Animated.View>
    </View>
  );
}

const quoteBox = (mine: boolean): ViewStyle => ({ position: 'relative', overflow: 'hidden', borderRadius: 12, paddingVertical: 6, paddingRight: 10, paddingLeft: 12,
  marginBottom: 2, backgroundColor: mine ? 'rgba(14,10,31,0.28)' : 'rgba(185,167,255,0.08)' });
const quoteBar = (mine: boolean): ViewStyle => ({ position: 'absolute', left: 0, top: 0, bottom: 0, width: 4, backgroundColor: mine ? C.lavA : C.lav });

/** Réactions posées sur le bas de la bulle (kit.css .reacts) : un toucher ajoute ou retire la mienne. */
function Reactions({ counts, reacted, canWrite, onReact, align }: { counts: Map<string, { n: number; mine: boolean }>; reacted: boolean;
  canWrite: boolean; onReact: (emoji: string) => void; align: 'flex-start' | 'flex-end' }) {
  if (!counts.size) return null;
  return (
    <View style={{ flexDirection: 'row', gap: 4, flexWrap: 'wrap', marginTop: -7, marginHorizontal: 10, alignSelf: align, zIndex: 2 }}>
      {[...counts].map(([emoji, c]) => (
        <Pressable key={`${emoji}-${c.n}-${c.mine}`} accessibilityRole="button" accessibilityLabel={`${emoji} ${c.n}${c.mine ? ', retirer ma réaction' : ''}`}
          disabled={!canWrite} onPress={() => onReact(emoji)}
          style={({ pressed }) => [{ height: 28, minWidth: 36, paddingHorizontal: 8, borderRadius: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 4,
            backgroundColor: c.mine ? '#2E2560' : C.s1b, borderWidth: 2, borderColor: C.bg },
            web({ boxShadow: c.mine ? '0 0 0 1px rgba(185,167,255,0.5)' : `0 0 0 1px ${C.line2}` }),
            reacted ? enter('pop') : null, pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
          <Text style={{ fontSize: 15 }}>{emoji}</Text>
          {c.n > 1 ? <Text style={[cf.bold, { fontSize: 12, color: c.mine ? C.lavA : C.t2 }]}>{c.n}</Text> : null}
        </Pressable>
      ))}
    </View>
  );
}

/** Lecture d'un vocal dans le navigateur (un seul à la fois) : lecture / pause, onde qui avance, durée, vitesse
 * 1× / 1,5× / 2× / 3× gardée pour les vocaux suivants (la hauteur de la voix est conservée par le navigateur). */
let playingNow: HTMLAudioElement | null = null;
const SPEEDS = [1, 1.5, 2, 3];
const SPEED_KEY = 'party-chat-voice-speed';
const BARS = 22;

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

/** Onde décorative propre à chaque vocal (tirée de son identifiant) : la même à chaque affichage. */
function waveOf(id: string): number[] {
  let h = 7;
  return Array.from({ length: BARS }, (_, i) => {
    h = (h * 31 + id.charCodeAt(i % id.length)) % 9973;
    return 0.25 + (h % 75) / 100;
  });
}

function VoicePlayer({ id, url, seconds, mine }: { id: string; url: string | null; seconds: number; mine: boolean }) {
  const audio = useRef<HTMLAudioElement | null>(null);
  const [playing, setPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [speed, setSpeed] = useState(savedSpeed);
  const bars = useMemo(() => waveOf(id), [id]);
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

  const done = mine ? '#FFFFFF' : C.lavA;
  const rest = mine ? 'rgba(255,255,255,0.4)' : 'rgba(185,167,255,0.38)';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, width: 236, paddingVertical: 2, marginLeft: -5 }}>
      <Pressable accessibilityRole="button" accessibilityLabel={playing ? 'Pause' : `Écouter le message vocal, ${voiceClock(seconds)}`} disabled={!url} onPress={toggle}
        style={({ pressed }) => [{ width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center' }, lavButton,
          !url && { opacity: 0.5 }, pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
        <View style={{ marginLeft: playing ? 0 : 2 }}><Icon name={playing ? 'pause' : 'play'} size={16} color={C.onLav} /></View>
      </Pressable>
      <View accessibilityElementsHidden importantForAccessibility="no-hide-descendants" style={{ flex: 1, height: 30, flexDirection: 'row', alignItems: 'center', gap: 2 }}>
        {bars.map((b, i) => (
          <View key={i} style={[{ flex: 1, height: `${Math.round(b * 100)}%`, borderRadius: 2, backgroundColor: (i + 0.5) / BARS <= progress ? done : rest },
            transition('background-color', 200, 'linear')]} />
        ))}
      </View>
      <View style={{ alignItems: 'flex-end', gap: 3 }}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Vitesse de lecture ${speedLabel(speed)}`} onPress={changeSpeed} hitSlop={10}
          style={{ paddingHorizontal: 6, paddingVertical: 2, borderRadius: 8, backgroundColor: mine ? 'rgba(255,255,255,0.18)' : 'rgba(185,167,255,0.16)' }}>
          <Text style={[cf.bold, { fontSize: 11, color: mine ? '#FFFFFF' : C.lav }]}>{speedLabel(speed)}</Text>
        </Pressable>
        <Text style={[cf.num, { fontSize: 12, color: mine ? 'rgba(255,255,255,0.9)' : C.t3 }]}>{voiceClock(seconds)}</Text>
      </View>
    </View>
  );
}
