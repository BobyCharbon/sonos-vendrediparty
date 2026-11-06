import { StyleSheet, View } from 'react-native';

import { T } from './ui';
import { colors, radius } from '@/lib/theme';

/** Les trois étapes de « Créer avec l'IA » (mêmes mots que l'écran natif, ios/Party/Assistant/AIEventSteps.swift). */
export const AI_STEPS = ['La soirée', 'Les invités', 'C’est en ligne'] as const;

/** Indicateur d'étapes : « 1 La soirée · 2 Les invités · 3 C'est en ligne », l'étape en cours en couleur, les faites cochées. */
export function AIEventSteps({ current }: { current: 1 | 2 | 3 }) {
  return (
    <View style={st.row} accessibilityRole="progressbar" accessibilityLabel={`Étape ${current} sur 3 : ${AI_STEPS[current - 1]}`}>
      {AI_STEPS.map((label, i) => {
        const n = i + 1;
        const done = n < current;
        const on = n === current;
        return (
          <View key={label} style={[st.step, on && st.stepOn]}>
            <View style={[st.dot, (on || done) && st.dotOn]}>
              <T size={11} weight="bold" color={on || done ? colors.onAction : colors.muted}>{done ? '✓' : n}</T>
            </View>
            <T size={11.5} weight={on ? 'bold' : 'semibold'} color={on ? colors.text : colors.muted} numberOfLines={1}>{label}</T>
          </View>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', gap: 4 },
  step: { flexGrow: 1, flexShrink: 1, flexDirection: 'row', alignItems: 'center', gap: 5, paddingHorizontal: 6, paddingVertical: 6, borderRadius: radius.pill, backgroundColor: colors.fill, minWidth: 0 },
  stepOn: { backgroundColor: colors.accentDim },
  dot: { width: 18, height: 18, borderRadius: 9, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.fillStrong },
  dotOn: { backgroundColor: colors.action },
});
