import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { pressTransition, transition } from '@/lib/motion';

import { C, label, web } from './model';

/**
 * Onglets segmentés (maquette 1-liste : 44 de haut, rayon 15, segment 11, compteur rose / gris), collés en haut au
 * défilement ; titres de section en capitales ; ligne « pour l'honneur » quand aucune patate n'est en jeu.
 */
export function Tabs<K extends string>({ tabs, value, onChange, sticky = true }: {
  tabs: { key: K; label: string; count?: number; hot?: boolean }[]; value: K; onChange: (k: K) => void; sticky?: boolean;
}) {
  return (
    <View role="tablist" style={[st.seg, sticky && st.sticky]}>
      {tabs.map((t) => {
        const on = t.key === value;
        return (
          <Pressable key={t.key} role="tab" aria-selected={on} accessibilityState={{ selected: on }} testID={`prono-tab-${t.key}`}
            accessibilityLabel={t.count ? `${t.label}, ${t.count}` : t.label} onPress={() => onChange(t.key)}
            style={[st.tab, on && st.tabOn, transition('background-color, box-shadow', 350), pressTransition]}>
            <Text style={[st.tabText, on && { color: C.t1 }]}>{t.label}</Text>
            {t.count ? <View style={[st.count, !t.hot && st.soft]}><Text style={st.countText}>{t.count}</Text></View> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

export function SectionTitle({ children, right }: { children: ReactNode; right?: ReactNode }) {
  return (
    <View style={st.section}>
      <Text role="heading" aria-level={2} style={label}>{children}</Text>
      {right}
    </View>
  );
}

export function HonourLine() {
  return (
    <View style={st.honour}>
      <Text aria-hidden style={{ fontSize: 16 }}>🏅</Text>
      <Text style={{ flex: 1, color: C.t2, fontSize: 13, lineHeight: 18, fontWeight: '500' }}>
        <Text style={{ color: C.t1, fontWeight: '700' }}>Pour l’honneur. </Text>Des points au classement, rien d’autre.
      </Text>
    </View>
  );
}

const st = StyleSheet.create({
  seg: web({ height: 44, padding: 4, borderRadius: 15, flexDirection: 'row', gap: 4, backgroundColor: 'rgba(26,20,51,0.92)',
    borderWidth: 1, borderColor: C.line, backdropFilter: 'blur(20px)' }),
  sticky: web({ position: 'sticky' as 'relative', top: 0, zIndex: 5 }),
  tab: { flex: 1, borderRadius: 11, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  tabOn: web({ backgroundColor: C.s1b, boxShadow: '0 1px 0 rgba(255,255,255,.06) inset, 0 6px 16px -8px rgba(0,0,0,.6)' }),
  tabText: { color: C.t2, fontSize: 14, fontWeight: '600' },
  count: { minWidth: 20, height: 20, paddingHorizontal: 6, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: C.pinkFill },
  soft: { backgroundColor: C.line2 },
  countText: { color: '#fff', fontSize: 12, fontWeight: '800', fontVariant: ['tabular-nums'] },
  section: { paddingTop: 16, paddingBottom: 2, flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between' },
  honour: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', padding: 12, borderRadius: 14, backgroundColor: 'rgba(91,227,166,0.08)',
    borderWidth: 1, borderColor: 'rgba(91,227,166,0.28)' },
});
