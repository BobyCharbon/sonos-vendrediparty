import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { BagChip, PatateSlider, ShapeMark, useReducedMotion } from '@/components/pronos/Kit';
import { pressTransition } from '@/lib/motion';

import { C, rounded, shapeAt, webView, wide, type PlayKind, type PronoV2 } from './model';

/**
 * Planter des patates (maquettes 3-1 et 3-3) : 0 à 20 🥔 (curseur + puces Sans / 5 / 10 / 20), le sac, ce qu'il y a
 * dans le champ et combien de joueurs ont planté, la règle en deux lignes, puis le rappel « aucune valeur ».
 * Jamais de multiplicateur, de chance ni de « tu peux récolter X » avant la fin (conformité 🔴).
 */
export const PATATES_NOTE = 'Les patates n’ont aucune valeur : elles ne s’achètent pas, ne se vendent pas, ne s’échangent pas.';

/** Ce qu'on peut planter : 20 au plus, et ce que contient le sac (les patates déjà plantées ici reviennent si on change). */
export function plantMax(p: PronoV2): number {
  const cap = Math.min(20, p.bag?.max_stake ?? 20);
  if (!p.bag) return cap;
  return Math.max(0, Math.min(cap, p.bag.balance + (p.my_answer?.stake ?? 0)));
}

export function fieldRule(kind: PlayKind): string {
  if (kind === 'number' || kind === 'when') return 'Le plus proche prend le champ. Égalité : partagé selon ce que chacun a planté.';
  if (kind === 'majority') return 'La réponse la plus choisie l’emporte. Égalité : tout le monde récupère ses patates.';
  return 'Tu vois juste : tu te partages le champ avec ceux qui ont vu juste.';
}

export function Plant({ p, value, onValue, answer, full }: {
  p: PronoV2; value: number; onValue: (n: number) => void; answer: { label: string; index: number | null }; full: boolean;
}) {
  const max = plantMax(p);
  const reduced = useReducedMotion();
  const [drops, setDrops] = useState(0);
  const pick = (n: number) => { onValue(Math.min(n, max)); if (n) setDrops((d) => d + 1); };
  const shape = answer.index != null ? shapeAt(answer.index) : null;
  return (
    <View style={{ gap: 12 }}>
      <View style={st.card} testID="prono-plant">
        <View style={st.head}>
          {full ? (
            <View style={{ flex: 1 }}>
              <Text style={rounded(19, '800')}>Planter des patates</Text>
              <Text style={st.help}>Facultatif, de 0 à 20</Text>
            </View>
          ) : (
            <Text style={[rounded(19, '800'), { flex: 1 }]}>Planter <Text style={{ color: C.patate }}>{value} 🥔</Text></Text>
          )}
          {p.bag ? <BagChip bag={p.bag} /> : null}
        </View>
        {full ? (
          <View style={{ alignItems: 'center', gap: 2 }}>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
              <Text style={wide(68, C.patate)} accessibilityLiveRegion="polite" accessibilityLabel={`${value} patates plantées`}>{value}</Text>
              <Text key={drops} style={[{ fontSize: 44, transform: [{ rotate: '-12deg' }] }, drops && !reduced ? st.drop : null]} accessibilityElementsHidden>🥔</Text>
            </View>
            {answer.label ? (
              <Text style={st.help}>
                {value ? 'plantées sur ' : 'aucune patate sur '}
                {shape ? <Text style={{ color: shape.color }}>{shape.glyph} </Text> : null}
                <Text style={{ color: C.t1, fontWeight: '700' }}>{answer.label}</Text>
              </Text>
            ) : <Text style={st.help}>{value ? 'plantées' : 'Choisis d’abord ta réponse'}</Text>}
          </View>
        ) : null}
        <PatateSlider value={value} max={max} onChange={(n) => onValue(Math.min(n, max))} />
        <View style={st.chips}>
          {[0, 5, 10, 20].map((n) => {
            const on = value === n;
            const off = n > max;
            return (
              <Pressable key={n} accessibilityRole="button" accessibilityLabel={n ? `Planter ${n} patates` : 'Sans patates'}
                accessibilityState={{ selected: on, disabled: off }} disabled={off} onPress={() => pick(n)}
                style={({ pressed }) => [st.chip, n === 0 && { flex: 1.3 }, on && st.chipOn, off && { opacity: 0.35 }, pressTransition,
                  pressed && { transform: [{ scale: 0.95 }] }]}>
                <Text style={[wide(17, on ? C.patateInk : C.t1), n === 0 && { fontFamily: rounded(17).fontFamily, fontStretch: 'normal' } as object]}>
                  {n ? n : 'Sans'}
                </Text>
              </Pressable>
            );
          })}
        </View>
        <View style={st.sep} />
        <View style={st.field}>
          <View style={st.fieldIcon}><Text style={{ fontSize: 26 }} accessibilityElementsHidden>🥔</Text></View>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={rounded(17, '800')}>
              <Text style={wide(17)}>{p.field?.total ?? 0}</Text> 🥔 dans le champ · {p.field?.planters ?? 0} joueur{(p.field?.planters ?? 0) > 1 ? 's' : ''}
            </Text>
            <Text style={st.help}>{full ? 'Les patates de tout le monde, sur toutes les réponses' : fieldRule(p.kind)}</Text>
          </View>
        </View>
        {full ? (
          <View style={{ gap: 10 }}>
            <Rule ok text={<><Text style={st.ruleStrong}>Tu vois juste : </Text>tu te partages le champ avec ceux qui ont vu juste, selon ce que chacun a planté.</>} />
            <Rule text={<><Text style={st.ruleStrong}>Pas cette fois : </Text>tes patates vont au compost. Personne n’a vu juste : tout le monde les récupère.</>} />
          </View>
        ) : null}
      </View>
      <Text style={st.note}>ⓘ {PATATES_NOTE} Ton sac remonte à 100 🥔 chaque lundi.</Text>
    </View>
  );
}

function Rule({ ok, text }: { ok?: boolean; text: ReactNode }) {
  return (
    <View style={{ flexDirection: 'row', gap: 10, alignItems: 'flex-start' }}>
      <View style={{ marginTop: 2 }}>
        {ok ? <View style={[st.ruleMark, { borderRadius: 11, backgroundColor: C.mint }]}><Text style={st.ruleGlyph}>✓</Text></View>
          : <View style={[st.ruleMark, { borderRadius: 5, backgroundColor: C.missed }]}><Text style={st.ruleGlyph}>✕</Text></View>}
      </View>
      <Text style={[st.help, { flex: 1 }]}>{text}</Text>
    </View>
  );
}

/** Forme de la réponse choisie (résumé au-dessus du bouton). */
export function AnswerShape({ index }: { index: number | null }) {
  if (index == null) return null;
  const s = shapeAt(index);
  return <ShapeMark shape={s.key} color={s.color} size={14} filled />;
}

const st = StyleSheet.create({
  card: webView({ gap: 16, padding: 20, borderRadius: 24, backgroundColor: C.s1, borderWidth: 1, borderColor: C.line,
    boxShadow: '0 18px 40px -18px rgba(0,0,0,0.6)' }),
  head: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  help: { color: C.t2, fontSize: 15, lineHeight: 21 },
  drop: webView({
    animationKeyframes: [{ from: { transform: 'translateY(-36px) rotate(-12deg)', opacity: 0 }, to: { transform: 'translateY(0) rotate(-12deg)', opacity: 1 } }],
    animationDuration: '380ms', animationTimingFunction: 'cubic-bezier(.34,1.56,.64,1)',
  }),
  chips: { flexDirection: 'row', gap: 8 },
  chip: { flex: 1, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.07)',
    borderWidth: 1, borderColor: C.glassLine },
  chipOn: { backgroundColor: C.patate, borderColor: C.patate },
  sep: { height: 1, backgroundColor: C.line },
  field: { flexDirection: 'row', gap: 14, alignItems: 'center' },
  fieldIcon: webView({ width: 52, height: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center',
    backgroundImage: 'repeating-linear-gradient(135deg, #3A2A1C 0 6px, #2E2016 6px 12px)' }),
  ruleMark: { width: 22, height: 22, alignItems: 'center', justifyContent: 'center' },
  ruleGlyph: { color: C.bg, fontSize: 12, fontWeight: '900' },
  ruleStrong: { color: C.t1, fontWeight: '700' },
  note: { color: C.t3, fontSize: 12.5, lineHeight: 18, paddingHorizontal: 4 },
});
