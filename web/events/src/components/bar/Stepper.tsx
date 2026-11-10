import { Pressable, StyleSheet, Text, View } from 'react-native';

import { pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/**
 * − quantité + (commande de l'invité, service au bar, stock de l'organisateur). Cibles de 44 px ; chaque bouton dit
 * ce qu'il fait (« Ajouter : Vodka Red Bull »), même éteint (le + bloqué au maximum ou au stock).
 */
export function Stepper({ label, value, onChange, min = 0, max, canAdd = true, tone = 'accent', hideZero = false, disabled = false }: {
  /** Nom de l'article, lu par VoiceOver. */
  label: string;
  value: number;
  onChange: (next: number) => void;
  min?: number;
  max?: number;
  /** + éteint même sous `max` (règle calculée ailleurs : maximum en attente, phase du bar). */
  canAdd?: boolean;
  tone?: 'accent' | 'mint';
  /** À 0 : seulement le « + » (le barman n'a encore rien choisi). */
  hideZero?: boolean;
  /** Enregistrement en cours : rien ne bouge (deux touchers rapides ne partent pas d'une valeur périmée). */
  disabled?: boolean;
}) {
  const plusOn = !disabled && canAdd && (max == null || value < max);
  const minusOn = !disabled && value > min;
  const tint = tone === 'mint' ? colors.mint : colors.accent;
  const compact = hideZero && value === 0;
  return (
    <View style={[st.wrap, value > 0 && { borderColor: tint }]}>
      {compact ? null : (
        <>
          <Pressable accessibilityRole="button" accessibilityLabel={`Retirer : ${label}`} accessibilityState={{ disabled: !minusOn }}
            disabled={!minusOn} onPress={() => onChange(value - 1)}
            style={({ pressed }) => [st.button, pressTransition, pressed && st.pressed, !minusOn && st.off]}>
            <Text style={[st.sign, { color: tint }]}>−</Text>
          </Pressable>
          <View accessible accessibilityLabel={`${value} · ${label}`} style={st.value}>
            <Text style={st.count}>{value}</Text>
          </View>
        </>
      )}
      <Pressable accessibilityRole="button" accessibilityLabel={`Ajouter : ${label}`} accessibilityState={{ disabled: !plusOn }}
        disabled={!plusOn} onPress={() => onChange(value + 1)}
        style={({ pressed }) => [st.button, pressTransition, pressed && st.pressed, !plusOn && st.off]}>
        <Text style={[st.sign, { color: plusOn ? tint : colors.muted }]}>+</Text>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { flexDirection: 'row', alignItems: 'center', borderRadius: radius.pill, borderWidth: 1.5, borderColor: colors.lineStrong, backgroundColor: colors.fill },
  button: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center', borderRadius: 22 },
  pressed: { backgroundColor: colors.fillStrong, transform: [{ scale: 0.92 }] },
  off: { opacity: 0.35 },
  sign: { fontSize: 22, lineHeight: 24, ...font.bold },
  value: { minWidth: 26, alignItems: 'center' },
  count: { color: colors.text, fontSize: 17, ...font.bold, fontVariant: ['tabular-nums'] },
});
