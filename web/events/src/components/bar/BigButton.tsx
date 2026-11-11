import { ActivityIndicator, Pressable, StyleSheet, Text } from 'react-native';

import { pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

const TONES = {
  mint: { bg: colors.mint, fg: colors.onMint },
  action: { bg: colors.action, fg: colors.onAction },
  red: { bg: colors.redDim, fg: colors.redSoft },
} as const;

/** Très gros bouton du barman (« Servir », « Scanner le suivant ») : lisible d'un coup d'œil, au pouce, dans le bruit. */
export function BigButton({ label, onPress, disabled, loading, tone = 'mint', accessibilityLabel }: {
  label: string; onPress: () => void; disabled?: boolean; loading?: boolean; tone?: keyof typeof TONES; accessibilityLabel?: string;
}) {
  const t = TONES[tone];
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }} disabled={disabled || loading} onPress={onPress}
      style={({ pressed }) => [st.button, pressTransition, { backgroundColor: t.bg, opacity: disabled ? 0.4 : pressed ? 0.88 : 1 },
        pressed && !disabled && { transform: [{ scale: 0.98 }] }]}>
      {loading ? <ActivityIndicator color={t.fg} /> : <Text style={[st.label, { color: t.fg }]}>{label}</Text>}
    </Pressable>
  );
}

const st = StyleSheet.create({
  button: { minHeight: 64, borderRadius: radius.lg, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18, paddingVertical: 14 },
  label: { ...font.bold, fontSize: 19, textAlign: 'center' },
});
