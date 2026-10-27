import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, Pressable, StyleSheet, View } from 'react-native';

import { rsvpCounts, type EventListItem } from '@/lib/data';
import { dateTile, formatShort, formatTime, plural, relativeDay } from '@/lib/format';
import { rsvpChoices, rsvpClosed, rsvpOptions, saveRsvp } from '@/lib/rsvp';
import { colors, font, radius } from '@/lib/theme';
import type { RsvpStatus, Tag } from '@/lib/types';

import { RsvpButtons } from './RsvpButtons';
import { Badge, ErrorText, T } from './ui';

const statusBadges = {
  draft: { label: 'Brouillon', fg: colors.textSoft, bg: colors.surface2 },
  pending: { label: 'En attente de validation', fg: colors.lavender, bg: colors.lavenderDim },
  rejected: { label: 'Refusé', fg: colors.coralSoft, bg: colors.coralDim },
  cancelled: { label: 'Annulé', fg: colors.coralSoft, bg: colors.coralDim },
} as const;

/** État de la carte : à répondre, ta réponse, ou passé (grisé). */
type Tone = 'todo' | 'past' | RsvpStatus | null;

/** Tuile calendrier à gauche de la carte, teintée selon l’état. Sondage de dates : point d’interrogation. */
function DateTile({ iso, tone }: { iso: string | null; tone: Tone }) {
  if (!iso) {
    return (
      <View style={[st.tile, { backgroundColor: tone === 'todo' ? colors.accent : colors.coralDim }]}>
        <T size={24} color={tone === 'todo' ? colors.onAccent : colors.coral} style={{ ...font.display }}>?</T>
        <T size={10} weight="bold" color={tone === 'todo' ? colors.onAccent : colors.coralSoft}>DATE</T>
      </View>
    );
  }
  const d = dateTile(iso);
  const c = tone === 'todo'
    ? { bg: colors.accent, top: colors.onAccent, day: colors.onAccent, bottom: colors.onAccent }
    : tone === 'past'
      ? { bg: colors.surface2, top: colors.muted, day: colors.muted, bottom: colors.muted }
      : tone
        ? { bg: rsvpChoices[tone].dim, top: rsvpChoices[tone].bg, day: colors.text, bottom: colors.textSoft }
        : { bg: colors.accentDim, top: colors.accent, day: colors.text, bottom: colors.textSoft };
  return (
    <View style={[st.tile, { backgroundColor: c.bg }]}>
      <T size={10} weight="bold" color={c.top}>{d.weekday}</T>
      <T size={24} color={c.day} style={{ ...font.display, lineHeight: 26 }}>{d.day}</T>
      <T size={10} weight="bold" color={c.bottom}>{d.month}</T>
      {tone === 'yes' || tone === 'no' ? (
        <View style={[st.seal, { backgroundColor: rsvpChoices[tone].bg }]}>
          <T size={11} style={{ ...font.bold, lineHeight: 13 }} color={rsvpChoices[tone].fg}>{rsvpChoices[tone].icon}</T>
        </View>
      ) : null}
    </View>
  );
}

/** Halo et point qui pulsent tant qu’on attend ta réponse (immobiles si « réduire les animations »). */
function usePulse(active: boolean) {
  const [v] = useState(() => new Animated.Value(0));
  useEffect(() => {
    if (!active) return;
    let loop: Animated.CompositeAnimation | null = null;
    let cancelled = false;
    AccessibilityInfo.isReduceMotionEnabled().then((reduce) => {
      if (cancelled || reduce) return;
      loop = Animated.loop(Animated.sequence([
        Animated.timing(v, { toValue: 1, duration: 1200, useNativeDriver: false }),
        Animated.timing(v, { toValue: 0, duration: 1200, useNativeDriver: false }),
      ]));
      loop.start();
    }).catch(() => {});
    return () => { cancelled = true; loop?.stop(); };
  }, [active, v]);
  return v;
}

export function EventCard({
  event,
  me,
  tagsById,
  onChanged,
  quickRsvp = false,
  now,
}: {
  event: EventListItem;
  me: string;
  tagsById: Map<string, Tag>;
  onChanged?: () => void;
  /** Affiche les boutons de réponse directement dans la carte. */
  quickRsvp?: boolean;
  /** Horodatage de référence (chargement des données) pour garder le rendu pur. */
  now: number;
}) {
  const [busy, setBusy] = useState<RsvpStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const mine = event.rsvps.find((r) => r.user_id === me);
  const counts = rsvpCounts(event.rsvps);
  const isPoll = event.date_mode === 'poll';
  const voters = new Set(event.date_options.flatMap((o) => o.date_votes.map((v) => v.user_id)));
  const status = event.status !== 'published' ? statusBadges[event.status] : null;
  const tags = event.event_tags.map((t) => tagsById.get(t.tag_id)).filter((t): t is Tag => !!t);
  const published = event.status === 'published';
  const past = !!event.starts_at && new Date(event.starts_at).getTime() < now - 6 * 3600_000;
  const closed = rsvpClosed(event, now);
  const needsAnswer = published && !past && !closed && (isPoll ? !voters.has(me) : !mine);
  const full = !!event.max_participants && counts.heads >= event.max_participants;
  const answered = mine && !isPoll && !mine.waitlisted ? mine.status : null;
  const tone: Tone = past || event.status === 'cancelled' ? 'past' : needsAnswer ? 'todo' : answered;
  const pulse = usePulse(tone === 'todo');

  async function answer(choice: RsvpStatus) {
    setBusy(choice);
    try {
      await saveRsvp(event.id, me, mine, { status: choice });
      setError(null);
      onChanged?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(null);
    }
  }

  const myBadge = mine && !isPoll
    ? mine.waitlisted
      ? { label: 'Liste d’attente', fg: colors.onAccent, bg: colors.lavender }
      : tone === 'past'
        ? mine.status === 'yes' ? { label: 'Tu y étais', fg: colors.muted, bg: colors.surface2 } : null
        : { label: `${rsvpChoices[mine.status].icon} ${rsvpChoices[mine.status].mine}`, fg: rsvpChoices[mine.status].fg, bg: rsvpChoices[mine.status].bg }
    : null;
  const others = answered === 'yes' ? counts.heads - 1 - mine!.plus_ones : counts.heads;

  return (
    <Animated.View
      style={[
        st.card,
        tone === 'todo' && [st.cardTodo, { shadowOpacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [0.25, 0.5] }) }],
        tone === 'yes' && { borderColor: 'rgba(91,227,166,.45)' },
        tone === 'maybe' && { borderColor: colors.coral, borderStyle: 'dashed', borderWidth: 1.5 },
        tone === 'no' && { borderColor: 'rgba(255,99,99,.5)' },
        tone === 'past' && st.cardPast,
      ]}
    >
      {tone === 'todo' ? (
        <View style={st.banner}>
          <Animated.View style={[st.dot, { opacity: pulse.interpolate({ inputRange: [0, 1], outputRange: [1, 0.35] }) }]} />
          <T size={13} weight="semibold" color={colors.accent} style={{ flex: 1 }}>{isPoll ? 'On attend ton vote' : 'On attend ta réponse'}</T>
          {event.rsvp_deadline || (isPoll && event.poll_deadline) ? (
            <T size={12} muted>avant {formatShort((isPoll ? event.poll_deadline : event.rsvp_deadline)!)}</T>
          ) : null}
        </View>
      ) : null}
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={`${event.title}, ${isPoll ? 'date à définir' : formatShort(event.starts_at)}`}
        onPress={() => router.push(`/event/${event.id}`)}
        style={({ pressed }) => [st.main, pressed && { opacity: 0.8 }]}
      >
        <DateTile iso={isPoll ? null : event.starts_at} tone={tone} />
        <View style={{ flex: 1, minWidth: 0, gap: 6 }}>
          <View style={st.badges}>
            {status ? <Badge {...status} /> : null}
            {event.category ? <Badge label={event.category.name} fg={colors.onAccent} bg={event.category.color} /> : null}
            {myBadge ? <Badge {...myBadge} /> : null}
          </View>
          <T style={{ ...font.display, fontSize: 20, lineHeight: 24 }} color={tone === 'past' ? colors.muted : colors.text} numberOfLines={2}>{event.title}</T>
          <T color={tone === 'past' ? colors.muted : colors.textSoft} size={14} numberOfLines={2}>
            {isPoll
              ? `${plural(event.date_options.length, 'date proposée', 'dates proposées')}${event.poll_deadline ? ` · vote avant ${formatShort(event.poll_deadline)}` : ''}`
              : event.starts_at
                ? `${relativeDay(event.starts_at)} · ${formatTime(event.starts_at)}${event.location_name ? ` · ${event.location_name}` : ''}`
                : 'Date à définir'}
          </T>
          {tags.length ? (
            <View style={st.badges}>
              {tags.map((t) => (
                <T key={t.id} size={12} color={t.color} weight="semibold">#{t.name}</T>
              ))}
            </View>
          ) : null}
          {published ? (
            <T muted size={13}>
              {isPoll
                ? `${plural(voters.size, 'votant')}`
                : `${answered === 'yes' ? 'Toi + ' : ''}${plural(others, 'présent')} · ${counts.maybe} peut-être${event.max_participants ? ` · ${full ? 'complet' : `${event.max_participants - counts.heads} place${event.max_participants - counts.heads > 1 ? 's' : ''} libre${event.max_participants - counts.heads > 1 ? 's' : ''}`}` : ''}`}
              {tone === 'no' ? <T size={13} weight="semibold" color={colors.redSoft}>  ·  Changer d’avis ›</T> : null}
            </T>
          ) : null}
        </View>
        <T muted size={20} style={{ alignSelf: 'center' }}>›</T>
      </Pressable>

      {quickRsvp && needsAnswer && !isPoll ? (
        <View style={[st.quick, st.quickTodo]}>
          <T size={13} weight="semibold" muted>Tu seras là ?</T>
          <RsvpButtons
            options={rsvpOptions(event.allow_maybe)}
            busy={busy}
            onSelect={answer}
            accessibilityLabel={(k) => `${rsvpChoices[k].label} à ${event.title}`}
            label={(k) => (k === 'yes' && full && event.waitlist_enabled ? 'Liste d’attente' : rsvpChoices[k].label)}
          />
          <ErrorText error={error} />
        </View>
      ) : null}
      {quickRsvp && needsAnswer && isPoll ? (
        <Pressable
          accessibilityRole="link"
          onPress={() => router.push(`/event/${event.id}`)}
          style={({ pressed }) => [st.quick, { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, pressed && { opacity: 0.8 }]}
        >
          <T size={15} weight="bold">Choisis tes dates</T>
          <T size={13} weight="bold" color={colors.accent}>Voter ›</T>
        </Pressable>
      ) : null}
      {quickRsvp && tone === 'maybe' && !closed ? (
        <View style={[st.quick, st.quickMaybe]}>
          <T size={13} weight="semibold" color={colors.coralSoft} style={{ flex: 1 }}>Tu confirmes ?</T>
          {(['yes', 'no'] as const).map((k) => (
            <Pressable
              key={k}
              accessibilityRole="button"
              accessibilityLabel={`${rsvpChoices[k].label} à ${event.title}`}
              disabled={!!busy}
              onPress={() => answer(k)}
              style={({ pressed }) => [st.quickBtn, { flexGrow: 0, flexShrink: 0, flexBasis: 'auto', minWidth: 88, paddingHorizontal: 14 }, k === 'yes' && { backgroundColor: colors.coral, borderColor: colors.coral }, (pressed || busy === k) && { opacity: 0.7 }]}
            >
              <T size={13} style={{ ...font.bold }} color={k === 'yes' ? colors.onCoral : colors.text}>{rsvpChoices[k].label}</T>
            </Pressable>
          ))}
        </View>
      ) : null}
      {tone === 'maybe' ? <ErrorText error={error} /> : null}
    </Animated.View>
  );
}

const st = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: radius.lg, overflow: 'hidden' },
  cardTodo: { borderColor: 'rgba(255,79,154,0.55)', shadowColor: colors.accent, shadowRadius: 18, shadowOffset: { width: 0, height: 6 } },
  cardPast: { backgroundColor: '#14101D', borderColor: '#241F31' },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, paddingTop: 12, marginBottom: -6 },
  dot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.accent },
  seal: { position: 'absolute', top: -6, right: -6, width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: colors.surface, alignItems: 'center', justifyContent: 'center' },
  main: { flexDirection: 'row', gap: 14, padding: 14, alignItems: 'flex-start' },
  tile: { position: 'relative', width: 56, paddingVertical: 8, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', minHeight: 64 },
  badges: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  quick: { gap: 8, paddingHorizontal: 14, paddingVertical: 12, borderTopWidth: StyleSheet.hairlineWidth, borderTopColor: colors.lineStrong, backgroundColor: 'rgba(0,0,0,0.12)' },
  quickTodo: {},
  quickMaybe: { flexDirection: 'row', alignItems: 'center', gap: 10, backgroundColor: 'rgba(255,179,71,.08)', borderTopColor: 'rgba(255,179,71,.35)' },
  quickBtn: { flex: 1, minHeight: 44, borderRadius: radius.md, borderWidth: 1, borderColor: 'transparent', backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 },
});
