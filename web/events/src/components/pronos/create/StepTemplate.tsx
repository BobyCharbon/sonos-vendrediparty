import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { KindIcon, kindLabel } from '@/components/pronos/Kit';
import { palette } from '@/lib/groups';
import { enter, pressTransition } from '@/lib/motion';

import { FAMILIES, familyOf, KINDS, type Family, type Kind, type Template } from './model';
import { C, Chip, ChipRow, nb, rounded, StepNav, StepScreen, Txt, web } from './ui';

/**
 * Étape 1 « Qu'est-ce qu'on prédit ? » (maquette 2-1) : les modèles prêts de la base (prono_templates), rangés par
 * famille (Soirée, Sport, La bande, Votes) — une carte vedette puis des tuiles —, et « Partir de zéro » avec les 9 types.
 * Aucun modèle d'alcool : la base les écrit, l'écran ne fait que les montrer.
 */
export function StepTemplate({ templates, onPick, onScratch, onClose }: {
  templates: Template[] | null; onPick: (t: Template) => void; onScratch: (k: Kind) => void; onClose: () => void;
}) {
  const [family, setFamily] = useState<Family | 'all'>('all');
  const byFamily = FAMILIES.map((f) => ({ ...f, items: (templates ?? []).filter((t) => familyOf(t) === f.key) })).filter((f) => f.items.length);
  const shown = family === 'all' ? byFamily : byFamily.filter((f) => f.key === family);

  return (
    <StepScreen nav={<StepNav step={1} title="Modèle" icon="✕" onBack={onClose} backLabel="Fermer la création" />}>
      <View style={[{ gap: 8 }, enter('rise')]}>
        <Text role="heading" aria-level={1} style={[rounded, st.h1]}>{'Qu’est-ce qu’on prédit\u00a0?'}</Text>
        <Txt size={16} color={C.t2}>Prends un modèle, tout reste modifiable.</Txt>
      </View>

      {byFamily.length ? (
        <View style={st.sticky}>
          <ChipRow>
            <Chip label="Tout" on={family === 'all'} onPress={() => setFamily('all')} />
            {byFamily.map((f) => (
              <Chip key={f.key} label={f.label} icon={<Text style={{ fontSize: 16 }}>{f.emoji}</Text>} on={family === f.key} onPress={() => setFamily(f.key)}
                testID={`prono-family-${f.key}`} />
            ))}
          </ChipRow>
        </View>
      ) : null}

      {shown.map((f, fi) => {
        const [first, ...rest] = f.items;
        return (
          <View key={f.key} style={[{ gap: 12 }, enter('rise', fi + 1)]}>
            <View style={st.famHead}>
              <Text style={{ fontSize: 22 }}>{f.emoji}</Text>
              <Text style={[rounded, { fontSize: 22, color: C.t1 }]}>{f.label}</Text>
              <Txt size={14} color={C.t2} weight="500">{f.hint}</Txt>
            </View>
            <Featured t={first} color={f.color} onPress={() => onPick(first)} />
            {rest.length ? (
              <View style={st.grid}>
                {rest.map((t) => <Tile key={t.id} t={t} color={f.color} onPress={() => onPick(t)} />)}
              </View>
            ) : null}
          </View>
        );
      })}

      <View style={[{ gap: 12 }, enter('rise', 5)]}>
        <View style={{ gap: 4 }}>
          <Text style={[rounded, { fontSize: 22, color: C.t1 }]}>✏️ Partir de zéro</Text>
          <Txt size={15} color={C.t2}>Choisis la forme de la réponse, tu écris la question.</Txt>
        </View>
        <View style={st.list}>
          {KINDS.map((k, i) => (
            <Pressable key={k.kind} accessibilityRole="button" accessibilityLabel={`Partir de zéro : ${kindLabel(k.kind)}. ${k.phrase}`}
              testID={`prono-kind-${k.kind}`} onPress={() => onScratch(k.kind)}
              style={({ pressed }) => [st.row, pressTransition, pressed && { backgroundColor: 'rgba(255,255,255,0.05)' }]}>
              {i > 0 ? <View style={st.sep} /> : null}
              <View style={[st.kindTile, web({ backgroundImage: `linear-gradient(135deg, ${k.tint[0]}, ${k.tint[1]})` })]}>
                <KindIcon kind={k.kind} />
              </View>
              <View style={{ flex: 1, gap: 2 }}>
                <Txt size={17} weight="600">{kindLabel(k.kind)}</Txt>
                <Txt size={13} color={C.t2}>{k.phrase}</Txt>
              </View>
              <Txt size={22} color={C.t3}>›</Txt>
            </Pressable>
          ))}
        </View>
        <View style={st.note}>
          <Txt size={14} color={C.t3}>ⓘ</Txt>
          <Txt size={14} color={C.t2} style={{ flex: 1 }}>Pour l’honneur, entre amis : jamais d’argent ni de boisson en jeu.</Txt>
        </View>
      </View>
    </StepScreen>
  );
}

function KindTag({ kind }: { kind: Kind }) {
  return (
    <View style={st.kindTag}>
      <KindIcon kind={kind} />
      <Txt size={13} weight="600">{kindLabel(kind)}</Txt>
    </View>
  );
}

function Featured({ t, color, onPress }: { t: Template; color: string; onPress: () => void }) {
  const p = palette(color);
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${t.title}, ${kindLabel(t.kind)}. ${t.hint}`} testID={`prono-template-${t.id}`} onPress={onPress}
      style={({ pressed }) => [st.featured, web({ backgroundImage: `linear-gradient(100deg, ${C.s1} 42%, ${p.from}cc 78%, ${p.to})` }),
        pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
      <View style={[st.halo, web({ backgroundImage: `radial-gradient(160px 160px at 100% 0%, ${p.main}4d, transparent 70%)` })]} />
      <View style={{ flex: 1, gap: 8 }}>
        <KindTag kind={t.kind} />
        <Text style={[rounded, { fontSize: 22, lineHeight: 25, color: C.t1 }]}>{nb(t.question || t.title)}</Text>
        <Txt size={14} color={C.t2} numberOfLines={2}>{t.hint}</Txt>
      </View>
      <View style={st.disc}><Text style={{ fontSize: 56 }}>{t.emoji}</Text></View>
    </Pressable>
  );
}

function Tile({ t, color, onPress }: { t: Template; color: string; onPress: () => void }) {
  const p = palette(color);
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${t.title}, ${kindLabel(t.kind)}`} testID={`prono-template-${t.id}`} onPress={onPress}
      style={({ pressed }) => [st.tile, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
      <View style={[st.halo, web({ backgroundImage: `radial-gradient(140px 140px at 0% 0%, ${p.main}33, transparent 70%)` })]} />
      <View style={[st.tileIcon, web({ backgroundImage: `linear-gradient(135deg, ${p.from}, ${p.to})` })]}><Text style={{ fontSize: 26 }}>{t.emoji}</Text></View>
      <Text style={[rounded, { fontSize: 17, lineHeight: 20, color: C.t1, flex: 1 }]} numberOfLines={3}>{nb(t.question || t.title)}</Text>
      <KindTag kind={t.kind} />
    </Pressable>
  );
}

const st = StyleSheet.create({
  h1: { fontSize: 32, lineHeight: 35, color: C.t1 },
  sticky: web({ position: 'sticky', top: 0, zIndex: 5, marginHorizontal: -20, paddingVertical: 8, paddingHorizontal: 20,
    backgroundColor: 'rgba(14,10,31,0.82)', backdropFilter: 'blur(24px)', WebkitBackdropFilter: 'blur(24px)' }),
  famHead: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  featured: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 128, padding: 18, borderRadius: 24, overflow: 'hidden',
    borderWidth: 1, borderColor: C.line, backgroundColor: C.s1 },
  halo: web({ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, pointerEvents: 'none' }),
  disc: { width: 92, height: 92, borderRadius: 46, alignItems: 'center', justifyContent: 'center' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  tile: { flexBasis: '47%', flexGrow: 1, minHeight: 156, padding: 14, gap: 10, borderRadius: 22, overflow: 'hidden', backgroundColor: C.s1,
    borderWidth: 1, borderColor: C.line },
  tileIcon: { width: 48, height: 48, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  kindTag: { flexDirection: 'row', alignItems: 'center', gap: 6, alignSelf: 'flex-start', height: 28, paddingHorizontal: 10, borderRadius: 14,
    backgroundColor: 'rgba(255,255,255,0.10)' },
  list: web({ borderRadius: 24, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line, overflow: 'hidden', backdropFilter: 'blur(24px)' }),
  row: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 64, paddingHorizontal: 14, paddingVertical: 10 },
  sep: { position: 'absolute', top: 0, left: 72, right: 0, height: 1, backgroundColor: C.line },
  kindTile: { width: 44, height: 44, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  note: { flexDirection: 'row', gap: 8, alignItems: 'flex-start', paddingHorizontal: 4 },
});
