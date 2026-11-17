import { Image, Pressable, View } from 'react-native';

import { T } from '../ui';
import { avatarColor, formatShort, plural } from '@/lib/format';
import { colors } from '@/lib/theme';

export type EventChatCard = {
  title: string;
  starts_at: string | null;
  ends_at: string | null;
  place: string | null;
  cover: string | null;
  going: number;
  maybe: number;
  description: string | null;
};

/** Couverture ronde (ou carrée arrondie, en grand) : l'affiche de l'événement, sinon 🎉 sur sa couleur. */
export function EventCover({ id, card, size, round = true }: { id: string; card: EventChatCard; size: number; round?: boolean }) {
  const r = round ? size / 2 : 18;
  if (card.cover?.startsWith('https://')) {
    return <Image accessibilityLabel="Affiche de l’événement" source={{ uri: card.cover }} resizeMode="cover"
      style={{ width: size, height: size, borderRadius: r, backgroundColor: colors.surface2 }} />;
  }
  return (
    <View style={{ width: size, height: size, borderRadius: r, backgroundColor: avatarColor(id), alignItems: 'center', justifyContent: 'center' }}>
      <T size={size * 0.48}>🎉</T>
    </View>
  );
}

/** « Ven. 14 nov. · 19:00 · 12 participants ». */
export function eventChatSubtitle(card: EventChatCard): string {
  const parts = [card.starts_at ? formatShort(card.starts_at) : 'Date à définir', plural(card.going, 'participant')];
  return parts.join(' · ');
}

/** Titre de l'en-tête, façon WhatsApp : couverture ronde, titre, « date · N participants » ; toucher → infos. */
export function EventChatTitle({ id, card, onPress }: { id: string; card: EventChatCard; onPress: () => void }) {
  const subtitle = eventChatSubtitle(card);
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${card.title}, ${subtitle}, infos de la discussion`} onPress={onPress}
      style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: 10, maxWidth: '100%' }, pressed && { opacity: 0.6 }]}>
      <EventCover id={id} card={card} size={36} />
      <View style={{ flexShrink: 1, minWidth: 0 }}>
        <T weight="bold" size={16} numberOfLines={1}>{card.title}</T>
        <T muted size={12} numberOfLines={1}>{subtitle}</T>
      </View>
    </Pressable>
  );
}
