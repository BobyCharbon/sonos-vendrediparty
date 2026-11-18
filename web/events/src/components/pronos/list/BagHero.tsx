import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { useQuery } from '@/lib/data';
import { palette } from '@/lib/groups';
import { enter, pressTransition } from '@/lib/motion';

import { C, fetchBag, monthName, NO_VALUE, num, sacPath, web, withPatates, type Bag, type ListCard, type Terrain } from './model';

/**
 * Sac de patates en vedette (maquette 1-liste) : le terrain choisi (groupe ou soirée), solde, jauge jusqu'à 100, plantées
 * en cours, récolte de la saison ; puces des autres sacs dessous ; rappel « aucune valeur » OBLIGATOIRE sous chaque sac.
 * Un sac par terrain (jamais de portefeuille commun) ; toucher le sac ouvre son historique (à soi seul).
 */

/** Terrains à patates de la liste, le plus actif d'abord (pronos ouverts, puis en cours). */
export function terrainsOf(list: ListCard[], of: (p: ListCard) => Terrain | null): Terrain[] {
  const score = new Map<string, { t: Terrain; n: number }>();
  for (const p of list) {
    if (!withPatates(p)) continue;
    const t = of(p);
    if (!t) continue;
    const s = score.get(t.key) ?? { t, n: 0 };
    s.n += p.state === 'open' ? 3 : p.state === 'closed' ? 1 : 0;
    score.set(t.key, s);
  }
  return [...score.values()].sort((a, b) => b.n - a.n).map((s) => s.t).slice(0, 8);
}

/** Les sacs de ces terrains (un appel par terrain ; un sac absent est ignoré). */
export function useBags(terrains: Terrain[]): Record<string, Bag> {
  const key = terrains.map((t) => t.key).join(',');
  const { data } = useQuery(async () => {
    const bags = await Promise.all(terrains.map((t) => fetchBag(t)));
    return Object.fromEntries(terrains.map((t, i) => [t.key, bags[i]]).filter(([, b]) => b && typeof (b as Bag).balance === 'number'));
  }, [key]);
  return (data ?? {}) as Record<string, Bag>;
}

export function NoValue({ style }: { style?: object }) {
  return (
    <View style={[st.noValue, style]} accessibilityRole="text">
      <Text aria-hidden style={st.noValueIcon}>ⓘ</Text>
      <Text style={st.noValueText}>{NO_VALUE}</Text>
    </View>
  );
}

export function BagHero({ terrains, bags, selected, onSelect, list, push }: {
  terrains: Terrain[]; bags: Record<string, Bag>; selected: string; onSelect: (key: string) => void; list: ListCard[];
  push: (path: string) => void;
}) {
  const shown = terrains.filter((t) => bags[t.key]);
  const t = shown.find((x) => x.key === selected) ?? shown[0];
  if (!t) return null;
  const bag = bags[t.key];
  const pal = palette(t.color);
  const pending = list.filter((p) => p.answered && (p.state === 'open' || p.state === 'closed') && (p.my_stake ?? 0) > 0
    && (p.group?.id === t.id || (!p.group && p.event?.id === t.id)));
  const planted = pending.reduce((n, p) => n + (p.my_stake ?? 0), 0);
  const harvest = bag.season?.harvest_net ?? 0;
  return (
    <View style={{ gap: 12 }}>
      <Pressable accessibilityRole="button" accessibilityLabel={`Ton sac de patates, ${t.name} : ${bag.balance} patates. Voir l’historique`}
        testID="prono-bag" onPress={() => push(sacPath(t))}
        style={({ pressed }) => [st.bag, enter('rise'), pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
        <View style={[st.glow, web({ backgroundImage: `radial-gradient(260px 200px at 100% 0%, ${pal.to}8c, transparent 70%)` })]} />
        <Text aria-hidden style={st.fili}>{t.emoji}</Text>
        <View style={st.top}>
          <Text numberOfLines={1} style={st.ctx}>Ton sac · <Text style={{ color: C.t1, fontWeight: '700' }}>{t.name}</Text></Text>
          <Text aria-hidden style={{ color: C.t2, fontSize: 18 }}>›</Text>
        </View>
        <View style={st.amount}>
          <Text style={[num(56), { color: C.t1 }]}>{bag.balance}<Text style={{ fontSize: 34 }}>🥔</Text></Text>
          <Text style={st.under}>{bag.balance >= 100 ? 'Ton sac est plein' : <>remonte à <Text style={{ color: C.t1, fontWeight: '800' }}>100</Text>{'\n'}lundi à 0 h</>}</Text>
        </View>
        <View style={st.gauge} aria-hidden>
          <View style={[st.gaugeFill, { width: `${Math.min(100, bag.balance)}%` }, web({ backgroundImage: `linear-gradient(90deg, ${pal.from}, ${pal.to})` }), enter('grow')]} />
        </View>
        <View style={st.tiles}>
          <View style={st.tile}>
            <Text style={st.tileK}>Plantées · {pending.length} prono{pending.length > 1 ? 's' : ''}</Text>
            <Text style={[num(20), { color: C.t1 }]}>{planted} <Text style={{ fontSize: 16 }}>🥔</Text></Text>
          </View>
          <View style={st.tile}>
            <Text style={st.tileK}>Récolte de {monthName(bag.season?.month)}</Text>
            <Text style={[num(20), { color: harvest > 0 ? C.mint : C.t1 }]}>{harvest > 0 ? `+${harvest}` : harvest} <Text style={{ fontSize: 16 }}>🥔</Text></Text>
          </View>
        </View>
      </Pressable>
      {shown.length > 1 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8 }} accessibilityLabel="Tes autres sacs">
          {shown.map((x) => {
            const on = x.key === t.key;
            const p = palette(x.color);
            return (
              <Pressable key={x.key} accessibilityRole="button" accessibilityState={{ selected: on }} aria-pressed={on}
                accessibilityLabel={`Sac ${x.name} : ${bags[x.key].balance} patates`} onPress={() => onSelect(x.key)}
                style={({ pressed }) => [st.chip, on && { borderColor: p.main, borderWidth: 2 }, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
                <View style={[st.chipEm, web({ backgroundImage: `linear-gradient(135deg, ${p.from}, ${p.to})` })]}><Text style={{ fontSize: 15 }}>{x.emoji}</Text></View>
                <Text numberOfLines={1} style={st.chipText}>{x.name.length > 18 ? `${x.name.slice(0, 17)}…` : x.name}</Text>
                <Text style={[num(15), { color: C.t2 }]}>{bags[x.key].balance}</Text>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}
      <NoValue />
    </View>
  );
}

const st = StyleSheet.create({
  bag: web({ borderRadius: 24, padding: 20, paddingBottom: 18, overflow: 'hidden', backgroundColor: C.s1, borderWidth: 1, borderColor: C.line,
    boxShadow: '0 1px 0 rgba(255,255,255,.04) inset, 0 18px 40px -24px rgba(0,0,0,.8)', gap: 14 }),
  glow: { position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, opacity: 0.55 },
  fili: web({ position: 'absolute', right: -24, top: -30, fontSize: 150, lineHeight: 150, opacity: 0.16, transform: 'rotate(-14deg)' }),
  top: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  ctx: { color: C.t2, fontSize: 15, fontWeight: '500', flexShrink: 1 },
  amount: { flexDirection: 'row', alignItems: 'flex-end', gap: 14 },
  under: { color: C.t2, fontSize: 15, lineHeight: 20, fontWeight: '600', paddingBottom: 4 },
  gauge: { height: 6, borderRadius: 3, backgroundColor: C.line2, overflow: 'hidden' },
  gaugeFill: { height: 6, borderRadius: 3 },
  tiles: { flexDirection: 'row', gap: 10 },
  tile: { flex: 1, borderRadius: 14, padding: 14, gap: 8, backgroundColor: C.s3, borderWidth: 1, borderColor: C.line },
  tileK: { color: C.t2, fontSize: 13, fontWeight: '600' },
  chip: web({ height: 40, paddingLeft: 4, paddingRight: 14, borderRadius: 999, flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: C.s2, borderWidth: 1, borderColor: C.line, backdropFilter: 'blur(20px)', minWidth: 44 }),
  chipEm: { width: 30, height: 30, borderRadius: 15, alignItems: 'center', justifyContent: 'center' },
  chipText: { color: C.t1, fontSize: 15, fontWeight: '600' },
  noValue: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', paddingHorizontal: 4 },
  noValueIcon: { color: C.t2, fontSize: 13, lineHeight: 16 },
  noValueText: { flex: 1, color: C.t2, fontSize: 12, lineHeight: 16, fontWeight: '500' },
});
