import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { rsvpCounts, type EventListItem } from '@/lib/data';
import { dateTile, formatShort, formatTime, plural, relativeDay } from '@/lib/format';
import { rsvpChoices, rsvpClosed, rsvpOptions, saveRsvp } from '@/lib/rsvp';
import { colors, fonts, radius } from '@/lib/theme';
import type { RsvpStatus, Tag } from '@/lib/types';

import { Badge, ErrorText, T } from './ui';

const statusBadges = {
  draft: { label: 'Brouillon', fg: colors.textSoft, bg: colors.surface2 },
  pending: { label: 'En attente de validation', fg: colors.lavender, bg: colors.lavenderDim },
  rejected: { label: 'Refusé', fg: colors.coralSoft, bg: colors.coralDim },
  cancelled: { label: 'Annulé', fg: colors.coralSoft, bg: colors.coralDim },
} as const;

/** Tuile calendrier à gauche de la carte. Sondage de dates : point d’interrogation. */
function DateTile({ iso, dim }: { iso: string | null; dim?: boolean }) {
  if (!iso) {
    return (
      <View style={[st.tile, { backgroundColor: colors.coralDim }]}>
        <T size={24} color={colors.coral} style={{ fontFamily: fonts.display }}>?</T>
        <T size={10} weight="bold" color={colors.coralSoft}>DATE</T>
      </View>
    );
  }
  const d = dateTile(iso);
  return (
    <View style={[st.tile, { backgroundColor: dim ? colors.surface2 : colors.accentDim }]}>
      <T size={10} weight="bold" color={dim ? colors.muted : colors.accent}>{d.weekday}</T>
      <T size={24} color={colors.text} style={{ fontFamily: fonts.display, lineHeight: 26 }}>{d.day}</T>
      <T size={10} weight="bold" color={dim ? colors.muted : colors.textSoft}>{d.month}</T>
    </View>
  );
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
      : { label: rsvpChoices[mine.status].mine, fg: colors.onAccent, bg: rsvpChoices[mine.status].bg }
    : needsAnswer
      ? { label: isPoll ? 'Vote attendu' : 'Réponse attendue', fg: colors.accent, bg: colors.accentDim }
      : null;

  return (
    <View style={[st.card, needsAnswer && st.cardAttention, (event.status === 'cancelled' || past) && { opacity: 0.75 }]}>
      <Pressable
        accessibilityRole="link"
        accessibilityLabel={`${event.title}, ${isPoll ? 'date à définir' : formatShort(event.starts_at)}`}
        onPress={() => router.push(`/event/${event.id}`)}
        style={({ pressed }) => [st.main, pressed && { opacity: 0.8 }]}
      >
        <DateTile iso={isPoll ? null : event.starts_at} dim={past || event.status === 'cancelled'} />
        <View style={{ flex: 1, minWidth: 0, gap: 6 }}>
          <View style={st.badges}>
            {status ? <Badge {...status} /> : null}
            {event.category ? <Badge label={event.category.name} fg={colors.onAccent} bg={event.category.color} /> : null}
            {myBadge ? <Badge {...myBadge} /> : null}
          </View>
          <T style={{ fontFamily: fonts.display, fontSize: 20, lineHeight: 24 }} numberOfLines={2}>{event.title}</T>
          <T color={colors.textSoft} size={14} numberOfLines={2}>
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
                : `${plural(counts.heads, 'présent')} · ${counts.maybe} peut-être${event.max_participants ? ` · ${full ? 'complet' : `${event.max_participants - counts.heads} place${event.max_participants - counts.heads > 1 ? 's' : ''} libre${event.max_participants - counts.heads > 1 ? 's' : ''}`}` : ''}`}
            </T>
          ) : null}
        </View>
        <T muted size={20} style={{ alignSelf: 'center' }}>›</T>
      </Pressable>

      {quickRsvp && needsAnswer && !isPoll ? (
        <View style={st.quick}>
          <T size={13} weight="semibold" color={colors.textSoft}>Réponds en un clic</T>
          <View style={{ flexDirection: 'row', gap: 6 }}>
            {rsvpOptions(event.allow_maybe).map((k) => {
              const c = rsvpChoices[k];
              return (
                <Pressable
                  key={k}
                  accessibilityRole="button"
                  accessibilityLabel={`${c.label} à ${event.title}`}
                  disabled={!!busy}
                  onPress={() => answer(k)}
                  style={({ pressed }) => [st.quickBtn, k === 'yes' && { backgroundColor: c.bg, borderColor: c.bg }, (pressed || busy === k) && { opacity: 0.7 }]}
                >
                  <T size={13} style={{ fontFamily: fonts.bold }} color={k === 'yes' ? c.fg : colors.text}>{c.icon}  {k === 'yes' && full && event.waitlist_enabled ? 'Liste d’attente' : c.label}</T>
                </Pressable>
              );
            })}
          </View>
          <ErrorText error={error} />
        </View>
      ) : null}
      {quickRsvp && needsAnswer && isPoll ? (
        <Pressable
          accessibilityRole="link"
          onPress={() => router.push(`/event/${event.id}`)}
          style={({ pressed }) => [st.quick, { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }, pressed && { opacity: 0.8 }]}
        >
          <T size={13} weight="semibold" color={colors.textSoft}>Choisis tes dates</T>
          <T size={13} weight="bold" color={colors.accent}>Voter ›</T>
        </Pressable>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: radius.lg, overflow: 'hidden' },
  cardAttention: { borderColor: colors.accent },
  main: { flexDirection: 'row', gap: 14, padding: 14, alignItems: 'flex-start' },
  tile: { width: 56, paddingVertical: 8, borderRadius: radius.md, alignItems: 'center', justifyContent: 'center', minHeight: 64 },
  badges: { flexDirection: 'row', gap: 6, flexWrap: 'wrap' },
  quick: { gap: 8, paddingHorizontal: 14, paddingVertical: 12, borderTopWidth: 1, borderTopColor: colors.line, backgroundColor: colors.bg },
  quickBtn: { flex: 1, minHeight: 44, borderRadius: radius.sm, borderWidth: 1, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 4 },
});
