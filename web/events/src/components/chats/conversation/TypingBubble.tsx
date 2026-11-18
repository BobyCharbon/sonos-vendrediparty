import { StyleSheet, Text, View } from 'react-native';

import { C, cf, web } from './kit';
import { enter, reducedMotion } from '@/lib/motion';

const breathe = StyleSheet.create({
  dot: web({
    animationKeyframes: [{ '0%': { opacity: 0.35 }, '50%': { opacity: 1 }, '100%': { opacity: 0.35 } }],
    animationDuration: '1200ms', animationIterationCount: 'infinite', animationTimingFunction: 'ease-in-out',
  }),
});

/** « écrit… » dans le fil (maquette : trois points lavande qui respirent, jamais de clignotement ; immobiles avec
 * « Réduire les animations »). Groupe ou soirée : le prénom de qui écrit. */
export function TypingBubble({ names, showName }: { names: string[]; showName: boolean }) {
  if (!names.length) return null;
  const who = names.length === 1 ? `${names[0]} écrit…` : `${names.length} personnes écrivent…`;
  return (
    <View accessibilityRole="text" accessibilityLiveRegion="polite" accessibilityLabel={showName ? who : 'écrit…'}
      style={[{ alignSelf: 'flex-start', flexDirection: 'row', alignItems: 'center', gap: 8, marginTop: 10, marginLeft: showName ? 0 : 2 }, enter('fade')]}>
      <View style={{ flexDirection: 'row', gap: 5, paddingVertical: 13, paddingHorizontal: 16, borderRadius: 22, borderBottomLeftRadius: 8,
        backgroundColor: C.theirs, borderWidth: 1, borderColor: C.theirsLine }}>
        {[0, 1, 2].map((i) => (
          <View key={i} style={[{ width: 8, height: 8, borderRadius: 4, backgroundColor: C.lav, opacity: 0.4 + i * 0.3 },
            reducedMotion ? null : [breathe.dot, web({ animationDelay: `${i * 200}ms` })]]} />
        ))}
      </View>
      {showName ? <Text style={[cf.semibold, { color: C.t2, fontSize: 13 }]}>{who}</Text> : null}
    </View>
  );
}
