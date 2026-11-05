import { Link, Slot, usePathname } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { duration, ease, enter, transition } from '@/lib/motion';
import { usePendingCount } from '@/lib/pending';
import { colors, font } from '@/lib/theme';

export default function EventsLayout() {
  const pending = usePendingCount();
  const path = usePathname();
  const insets = useSafeAreaInsets();
  const links = [
    { href: '/', label: 'Événements', badge: pending },
    { href: '/activity', label: 'Activité' },
    { href: '/profile', label: 'Mon profil' },
  ];
  // Pastille néon qui glisse vers l’onglet ouvert, une fois les onglets mesurés (comme le contrôle segmenté iOS).
  const [frames, setFrames] = useState<Record<string, { x: number; width: number }>>({});
  const frame = frames[path];
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {/* Barre figée : seul le contenu dessous défile. */}
      <View role="navigation" style={[st.bar, { paddingTop: insets.top, paddingLeft: insets.left, paddingRight: insets.right }]}>
        <View style={st.track}>
          {frame ? (
            <View pointerEvents="none" style={[st.linkOn, st.thumb, { width: frame.width, transform: [{ translateX: frame.x }] },
              transition('transform, width', 320, ease.out)]} />
          ) : null}
          {links.map((item) => {
            const on = path === item.href;
            return (
              <Link key={item.href} href={item.href} asChild>
                <Pressable
                  role="link"
                  aria-current={on ? 'page' : undefined}
                  aria-label={item.badge ? `${item.label}, ${item.badge} en attente de ta réponse` : item.label}
                  onLayout={(e) => {
                    const { x, width } = e.nativeEvent.layout;
                    setFrames((prev) => (prev[item.href]?.x === x && prev[item.href]?.width === width ? prev : { ...prev, [item.href]: { x, width } }));
                  }}
                  style={StyleSheet.flatten([st.link, transition('background-color', duration.fast), on && !frame && st.linkOn])}
                >
                <Text numberOfLines={1} style={[{ color: on ? '#FFFFFF' : colors.textSoft, ...font.semibold, fontSize: 13 }, transition('color', duration.base) as object]}>{item.label}</Text>
                {item.badge ? (
                  <View key={item.badge} style={[st.badge, enter('pop'), transition('background-color', duration.base), on && { backgroundColor: colors.onAccent }]}>
                    <Text style={{ color: on ? colors.accent : colors.onAccent, ...font.bold, fontSize: 11 }}>{item.badge}</Text>
                  </View>
                ) : null}
                </Pressable>
              </Link>
            );
          })}
        </View>
      </View>
      <View style={{ flex: 1, minHeight: 0 }}>
        <Slot />
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  bar: { backgroundColor: colors.bg, zIndex: 2 },
  // Contrôle segmenté iOS, comme dans le reste de Party : piste sombre, choix en pastille néon.
  track: { flexDirection: 'row', gap: 2, padding: 3, marginVertical: 8, marginHorizontal: 12, borderRadius: 13,
    backgroundColor: 'rgba(255,255,255,0.06)' },
  link: { flexGrow: 1, flexShrink: 1, minWidth: 0, flexBasis: 'auto', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingHorizontal: 8, minHeight: 44, borderRadius: 10 },
  linkOn: { backgroundColor: colors.accent, shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 10, shadowOffset: { width: 0, height: 3 } },
  thumb: { position: 'absolute', top: 3, bottom: 3, left: 0, borderRadius: 10 },
  badge: { minWidth: 20, height: 20, paddingHorizontal: 6, borderRadius: 10, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
});
