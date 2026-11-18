import { Pressable, StyleSheet, Text, View } from 'react-native';

import { loop } from '@/components/GroupBits';
import { kindLabel, PrimaryButton } from '@/components/pronos/Kit';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { palette } from '@/lib/groups';
import { enter, pressTransition } from '@/lib/motion';
import { rpc } from '@/lib/pronos';

import { C, label, round, web, type ListCard } from './model';

/**
 * États vides (maquette 1-vides) : « Tu as tout joué » (onglet À jouer), page d'un groupe sans prono (carte fantôme,
 * 3 modèles « en un toucher », « Partir de zéro »), et « Mes pronos » vide.
 */

/** Trois sceaux qui flottent (illustration). */
function Seals({ color, mark }: { color: string; mark: string }) {
  const p = palette(color);
  const seal = (size: number, rotate: number, delay: number, z = 0) => (
    <View style={[{ zIndex: z, marginHorizontal: -4 }, loop('floaty', delay)]}>
      <View style={[st.seal, { width: size, height: size, borderRadius: size / 2 },
        web({ backgroundImage: `radial-gradient(circle at 35% 30%, ${p.from}, ${p.to})`, transform: `rotate(${rotate}deg)`,
          boxShadow: `0 0 0 3px ${p.to}55, 0 10px 24px -10px ${p.to}` })]}>
        <Text style={[round(size * 0.36), { color: '#1D1530' }]}>{mark}</Text>
      </View>
    </View>
  );
  return (
    <View aria-hidden style={st.seals}>
      {seal(46, -12, 0)}{seal(62, 0, 400, 1)}{seal(46, 10, 800)}
    </View>
  );
}

export function AllPlayed({ next, onWait }: { next: ListCard | null; onWait: () => void }) {
  return (
    <View style={[st.ghost, st.solid, enter('rise')]} testID="prono-all-played">
      <Seals color="pink" mark="✓" />
      <Text style={[round(22, 26), { textAlign: 'center' }]}>Tu as tout joué</Text>
      <Text style={st.text}>
        Tes réponses sont scellées.
        {next ? <>{'\n'}Prochaine fin : <Text style={{ color: C.t1, fontWeight: '700' }}>{formatShort(next.closes_at)}</Text>{'\n'}{next.question}</> : null}
      </Text>
      <Pressable accessibilityRole="button" onPress={onWait} style={({ pressed }) => [st.glass, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
        <Text style={{ color: C.t1, fontSize: 17, fontWeight: '700' }}>Voir mes pronos en attente</Text>
      </Pressable>
    </View>
  );
}

type Template = { id: string; kind: string; emoji: string; title: string; question?: string };
const FALLBACK: Template[] = [
  { id: 'last', kind: 'person', emoji: '🐢', title: 'Qui arrive en dernier ?' },
  { id: 'pizzas', kind: 'number', emoji: '🍕', title: 'Combien de pizzas ?' },
  { id: 'match', kind: 'choice', emoji: '⚽', title: 'Le score du match ?' },
];

/** Page d'un groupe sans prono : carte fantôme, trois modèles prêts, « Partir de zéro ». */
export function GroupEmpty({ color, onTemplate, onBlank }: { color: string; onTemplate: (id: string) => void; onBlank: () => void }) {
  const p = palette(color);
  const { data } = useQuery(() => rpc<Template[]>('prono_templates').catch((): Template[] => []), []);
  const templates = (data?.length ? data : FALLBACK).slice(0, 3);
  return (
    <View style={[st.ghost, { borderColor: `${p.main}99` }, web({ backgroundColor: `${p.main}0f` }), enter('rise')]}>
      <Seals color={color} mark="?" />
      <Text style={[round(22, 26), { textAlign: 'center' }]}>Lance le premier prono</Text>
      <Text style={st.text}>Aucun prono dans ce groupe pour l’instant. Une question, des réponses scellées, puis le grand dévoilement.</Text>
      <View style={{ alignSelf: 'stretch', gap: 8, marginTop: 6 }}>
        <Text style={label}>En un toucher</Text>
        {templates.map((t, i) => (
          <Pressable key={t.id} accessibilityRole="button" accessibilityLabel={`Modèle : ${t.title}`} testID={`prono-template-${i}`}
            onPress={() => onTemplate(t.id)} style={({ pressed }) => [st.tpl, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
            <View style={[st.tplEm, web({ backgroundImage: `linear-gradient(135deg, ${p.from}, ${p.to})` })]}><Text style={{ fontSize: 18 }}>{t.emoji}</Text></View>
            <Text numberOfLines={1} style={{ flex: 1, color: C.t1, fontSize: 15, fontWeight: '600' }}>{t.title}</Text>
            <Text style={{ color: C.t2, fontSize: 13, fontWeight: '600' }}>{kindLabel(t.kind)}</Text>
          </Pressable>
        ))}
      </View>
      <View style={{ alignSelf: 'stretch', marginTop: 8 }}>
        <PrimaryButton label="＋  Partir de zéro" onPress={onBlank} testID="prono-new-blank" />
      </View>
    </View>
  );
}

export function NoPronos({ onNew }: { onNew: () => void }) {
  return (
    <View style={[st.ghost, { borderColor: 'rgba(185,167,255,0.5)' }, enter('rise')]}>
      <Seals color="lavender" mark="?" />
      <Text style={[round(22, 26), { textAlign: 'center' }]}>Aucun prono pour l’instant</Text>
      <Text style={st.text}>Lance le premier : « Qui arrive en dernier ? », « Le score du match ? »… Les réponses restent scellées jusqu’au dévoilement.</Text>
      <View style={{ alignSelf: 'stretch', marginTop: 8 }}>
        <PrimaryButton label="＋  Nouveau prono" onPress={onNew} />
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  ghost: { borderRadius: 24, borderWidth: 1.5, borderStyle: 'dashed', paddingHorizontal: 20, paddingTop: 24, paddingBottom: 20, alignItems: 'center', gap: 8 },
  solid: web({ borderStyle: 'solid', borderWidth: 1, borderColor: C.line, backgroundColor: C.s1,
    boxShadow: '0 1px 0 rgba(255,255,255,.04) inset, 0 18px 40px -24px rgba(0,0,0,.8)' }),
  seals: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', height: 80, marginBottom: 6 },
  seal: { alignItems: 'center', justifyContent: 'center' },
  text: { color: C.t2, fontSize: 15, lineHeight: 21, fontWeight: '500', textAlign: 'center', maxWidth: 300 },
  glass: { alignSelf: 'stretch', marginTop: 10, height: 52, borderRadius: 16, alignItems: 'center', justifyContent: 'center',
    backgroundColor: C.s3, borderWidth: 1, borderColor: C.line2 },
  tpl: { height: 52, borderRadius: 16, flexDirection: 'row', alignItems: 'center', gap: 12, paddingLeft: 8, paddingRight: 14,
    backgroundColor: C.s1, borderWidth: 1, borderColor: C.line2 },
  tplEm: { width: 34, height: 34, borderRadius: 17, alignItems: 'center', justifyContent: 'center' },
});
