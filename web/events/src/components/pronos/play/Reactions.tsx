import { Pressable, StyleSheet, Text, View } from 'react-native';

import { SectionLabel } from '@/components/pronos/Kit';
import { pressTransition } from '@/lib/motion';

import { C, wide, type Reaction } from './model';

/** Les six réactions permises (base : private.prono_reactions) ; jamais de texte libre ici. */
export const REACTIONS = ['😂', '🔥', '🥔', '👀', '🤯', '👏'] as const;
const NAMES: Record<string, string> = { '😂': 'mort de rire', '🔥': 'le feu', '🥔': 'patate', '👀': 'les yeux', '🤯': 'explosé', '👏': 'bravo' };
/** La base garde la valeur « 🥔 » (et le testID « patate ») ; l'écran montre et dit des confettis. */
const SHOWN: Record<string, string> = { '🥔': '🎊' };
const SAY: Record<string, string> = { ...NAMES, '🥔': 'confettis' };

/** Réactions (maquette 3-2) : grille de 6 capsules, bascule (retoucher l'enlève) ; à moi = lavande. */
export function Reactions({ list, onReact, busy, waiting, patates }: {
  list: Reaction[] | undefined; onReact: (emoji: string) => void; busy: boolean; waiting: boolean; patates: boolean;
}) {
  const emojis = REACTIONS.filter((e) => patates || e !== '🥔');
  return (
    <View style={{ gap: 10 }}>
      <SectionLabel right={waiting ? 'en attendant la fin' : undefined}>Réactions</SectionLabel>
      <View style={st.grid}>
        {emojis.map((e) => {
          const r = list?.find((x) => x.emoji === e);
          const mine = !!r?.mine;
          return (
            <Pressable key={e} accessibilityRole="button" accessibilityState={{ selected: mine, disabled: busy }} disabled={busy}
              accessibilityLabel={`Réaction ${SAY[e]}${r?.count ? `, ${r.count}` : ''}${mine ? ', la tienne' : ''}`}
              onPress={() => onReact(e)} testID={`prono-react-${NAMES[e].replace(/\s/g, '-')}`}
              style={({ pressed }) => [st.pill, mine && st.mine, pressTransition, pressed && { transform: [{ scale: 1.1 }] }]}>
              <Text style={{ fontSize: 21 }}>{SHOWN[e] ?? e}</Text>
              {r?.count ? <Text style={wide(16)}>{r.count}</Text> : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  pill: { flexGrow: 1, flexBasis: 48, minWidth: 48, height: 44, borderRadius: 999, flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    gap: 6, backgroundColor: C.glass, borderWidth: 1, borderColor: C.glassLine },
  mine: { backgroundColor: 'rgba(185,167,255,0.20)', borderColor: C.lav },
});
