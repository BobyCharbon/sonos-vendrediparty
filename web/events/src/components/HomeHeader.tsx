import { createElement } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { Title } from '@/components/ui';
import { BADGE_RED } from '@/lib/activityBadge';
import { duration, enter, pressTransition, transition } from '@/lib/motion';
import { colors, font } from '@/lib/theme';

/** Icônes au trait (même dessin que les maquettes), en SVG dans la page : le module ne tourne que sur le web. */
function Icon({ paths }: { paths: string[] }) {
  return createElement('svg', {
    width: 20, height: 20, viewBox: '0 0 24 24', fill: 'none', stroke: colors.text, strokeWidth: 2,
    strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true,
  }, paths.map((d) => createElement('path', { key: d, d })));
}
const SEARCH = ['M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14', 'M20 20l-3.5-3.5'];
const BELL = ['M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8', 'M10 20a2 2 0 0 0 4 0'];

type HeaderProps = {
  searchOpen: boolean;
  onToggleSearch: () => void;
  important: number;
  onBell: () => void;
};

/** « Événements » sur une ligne, loupe et cloche à bulle rouge (nouveautés importantes non lues). */
export function HomeHeader({ searchOpen, onToggleSearch, important, onBell }: HeaderProps) {
  const many = important > 1 ? 's' : '';
  const bellLabel = important ? `Activité, ${important} nouveauté${many} importante${many}` : 'Activité';
  return (
    <View style={st.header}>
      <Title level={1} style={st.title}>Événements</Title>
      <Pressable accessibilityRole="button" accessibilityLabel={searchOpen ? 'Fermer la recherche' : 'Rechercher'}
        accessibilityState={{ expanded: searchOpen }} testID="home-search" onPress={onToggleSearch}
        style={({ pressed }) => [st.round, searchOpen && st.roundOn, pressTransition, pressed && st.pressed]}>
        <Icon paths={SEARCH} />
      </Pressable>
      <Pressable accessibilityRole="button" accessibilityLabel={bellLabel} testID="home-bell" onPress={onBell}
        style={({ pressed }) => [st.round, pressTransition, pressed && st.pressed]}>
        <Icon paths={BELL} />
        {important ? (
          <View key={important} testID="home-bell-badge" style={[st.badge, enter('pop')]}>
            <Text style={st.badgeText}>{important > 99 ? '99+' : important}</Text>
          </View>
        ) : null}
      </Pressable>
    </View>
  );
}

export type PillItem<K extends string> = { key: K; label: string; count?: number; selected: boolean; outline?: boolean };

/** Rangée de pastilles (sous-onglets + Filtres) qui tient sur une ligne et défile si besoin. */
export function HomePills<K extends string>({ items, onPress }: { items: PillItem<K>[]; onPress: (k: K) => void }) {
  return (
    <View role="tablist" style={st.pillsScroll}>
    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={st.pills}>
      {items.map((p) => (
        <Pressable key={p.key} accessibilityRole={p.outline ? 'button' : 'tab'} aria-selected={p.outline ? undefined : p.selected}
          accessibilityState={{ selected: p.selected }}
          accessibilityLabel={p.count ? `${p.label}, ${p.count} en attente de ton vote` : p.label}
          testID={`pill-${p.key}`} onPress={() => onPress(p.key)}
          style={({ pressed }) => [st.pill, p.selected ? st.pillOn : p.outline ? st.pillOutline : null,
            transition('background-color', duration.fast), pressed && st.pressed]}>
          <Text numberOfLines={1} style={[st.pillText, p.selected && st.pillTextOn]}>{p.label}</Text>
          {p.count ? (
            <View style={[st.pillBadge, p.selected && st.pillBadgeOn]}>
              <Text style={[st.pillBadgeText, p.selected && { color: colors.action }]}>{p.count}</Text>
            </View>
          ) : null}
        </Pressable>
      ))}
    </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  header: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  title: { flex: 1, minWidth: 0 },
  round: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.surface, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: 'transparent' },
  roundOn: { backgroundColor: colors.surface2, borderColor: colors.accent },
  pressed: { opacity: 0.75, transform: [{ scale: 0.95 }] },
  badge: { position: 'absolute', top: 1, right: -1, minWidth: 20, height: 20, paddingHorizontal: 5, borderRadius: 10,
    backgroundColor: BADGE_RED, borderWidth: 2, borderColor: colors.bg, alignItems: 'center', justifyContent: 'center' },
  badgeText: { color: '#FFFFFF', fontSize: 11, lineHeight: 13, ...font.bold },
  pillsScroll: { marginHorizontal: -16, flexGrow: 0 },
  pills: { gap: 6, paddingHorizontal: 16, alignItems: 'center' },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 40, paddingHorizontal: 11, borderRadius: 20,
    backgroundColor: colors.surface, borderWidth: 1, borderColor: 'transparent' },
  pillOn: { backgroundColor: colors.action },
  pillOutline: { backgroundColor: 'transparent', borderColor: colors.lineStrong },
  pillText: { color: colors.textSoft, fontSize: 13, ...font.semibold },
  pillTextOn: { color: colors.onAction, ...font.bold },
  pillBadge: { minWidth: 18, height: 18, paddingHorizontal: 5, borderRadius: 9, backgroundColor: BADGE_RED, alignItems: 'center', justifyContent: 'center' },
  pillBadgeOn: { backgroundColor: '#FFFFFF' },
  pillBadgeText: { color: '#FFFFFF', fontSize: 11, ...font.bold },
});
