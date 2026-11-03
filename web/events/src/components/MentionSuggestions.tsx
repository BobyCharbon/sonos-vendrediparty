import { Pressable, View } from 'react-native';

import { Avatar, T } from './ui';
import type { MentionSuggestion } from '@/lib/chats';
import { duration, enter, transition } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';

type Props = {
  suggestions: MentionSuggestion[];
  onPick: (s: MentionSuggestion) => void;
};

/** Suggestions de l'@ dans une discussion : membres du groupe filtrés par les lettres tapées, puis @tout et @annonce. */
export function MentionSuggestions({ suggestions, onPick }: Props) {
  if (!suggestions.length) return null;
  return (
    <View accessibilityRole="menu" accessibilityLabel="Suggestions de citation"
      style={[{ marginHorizontal: 12, marginTop: 8, borderRadius: radius.md, backgroundColor: colors.surface2, overflow: 'hidden' }, enter('drop')]}>
      {suggestions.map((sug) => (
        <Pressable key={sug.key} accessibilityRole="menuitem" accessibilityLabel={sug.id ? `Citer ${sug.label}` : `@${sug.label} : ${sug.hint}`}
          onPress={() => onPick(sug)}
          style={({ pressed }) => [{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 12, paddingVertical: 8 },
            transition('background-color', duration.fast), pressed && { backgroundColor: colors.fill }]}>
          {sug.id ? <Avatar id={sug.id} name={sug.label} photo={sug.photo ?? null} size={28} profile={false} />
            : <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: colors.accentDim, alignItems: 'center', justifyContent: 'center' }}>
                <T size={14}>{sug.key === 'tout' ? '👥' : '📣'}</T>
              </View>}
          <T weight="semibold" style={{ flex: 1 }} numberOfLines={1}>@{sug.label}</T>
          {sug.hint ? <T muted size={12} numberOfLines={1}>{sug.hint}</T> : null}
        </Pressable>
      ))}
    </View>
  );
}
