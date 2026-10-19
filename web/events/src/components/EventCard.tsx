import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { rsvpCounts, type EventListItem } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { colors, fonts, radius } from '@/lib/theme';
import type { Tag } from '@/lib/types';

import { Badge, T } from './ui';

const statusBadges = {
  draft: { label: 'Brouillon', fg: colors.textSoft, bg: colors.surface2 },
  pending: { label: 'En attente de validation', fg: colors.lavender, bg: colors.lavenderDim },
  rejected: { label: 'Refusé', fg: colors.coralSoft, bg: colors.coralDim },
  cancelled: { label: 'Annulé', fg: colors.coralSoft, bg: colors.coralDim },
} as const;

export function EventCard({ event, me, tagsById }: { event: EventListItem; me: string; tagsById: Map<string, Tag> }) {
  const mine = event.rsvps.find((r) => r.user_id === me);
  const counts = rsvpCounts(event.rsvps);
  const isPoll = event.date_mode === 'poll';
  const voters = new Set(event.date_options.flatMap((o) => o.date_votes.map((v) => v.user_id)));
  const status = event.status !== 'published' ? statusBadges[event.status] : null;
  const tags = event.event_tags.map((t) => tagsById.get(t.tag_id)).filter((t): t is Tag => !!t);

  return (
    <Pressable
      accessibilityRole="link"
      onPress={() => router.push(`/event/${event.id}`)}
      style={({ pressed }) => [st.card, pressed && { opacity: 0.85 }]}
    >
      <View style={st.top}>
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap', flex: 1 }}>
          {status ? (
            <Badge {...status} />
          ) : isPoll ? (
            <Badge label="Date à définir" fg={colors.coralSoft} bg={colors.coralDim} />
          ) : (
            <Badge label="Date fixée" fg={colors.accent} bg={colors.accentDim} />
          )}
          {event.category ? <Badge label={event.category.name} fg={colors.onAccent} bg={event.category.color} /> : null}
        </View>
        {mine && !isPoll ? (
          <Badge
            label={mine.waitlisted ? 'Liste d’attente' : mine.status === 'yes' ? 'Tu viens' : mine.status === 'maybe' ? 'Peut-être' : 'Absent'}
            fg={colors.onAccent}
            bg={mine.waitlisted ? colors.lavender : mine.status === 'yes' ? colors.accent : mine.status === 'maybe' ? colors.lavender : colors.coral}
          />
        ) : null}
      </View>

      <T style={{ fontFamily: fonts.display, fontSize: 22 }}>{event.title}</T>
      <T muted size={14}>
        {isPoll
          ? `${event.date_options.length} date(s) proposée(s)${event.poll_deadline ? ` · vote avant ${formatShort(event.poll_deadline)}` : ''}`
          : `${formatShort(event.starts_at)}${event.location_name ? ` · ${event.location_name}` : ''}`}
      </T>

      {tags.length ? (
        <View style={{ flexDirection: 'row', gap: 6, flexWrap: 'wrap' }}>
          {tags.map((t) => (
            <T key={t.id} size={12} color={t.color} weight="semibold">#{t.name}</T>
          ))}
        </View>
      ) : null}

      {event.status === 'published' ? (
        <T muted size={13}>
          {isPoll
            ? `${voters.size} votant(s)${voters.has(me) ? '' : ' · tu n’as pas encore voté'}`
            : `${counts.yes} présent(s) · ${counts.maybe} peut-être${event.max_participants ? ` · ${counts.heads}/${event.max_participants} places` : ''}`}
        </T>
      ) : null}
    </Pressable>
  );
}

const st = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: radius.lg, padding: 16, gap: 10 },
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 },
});
