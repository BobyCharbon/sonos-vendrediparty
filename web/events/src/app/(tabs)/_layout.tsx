import { Link, Slot, usePathname } from 'expo-router';
import { Pressable, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

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
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      {/* Barre figée : seul le contenu dessous défile. */}
      <View role="navigation" style={[st.bar, { paddingTop: insets.top, paddingLeft: insets.left, paddingRight: insets.right }]}>
        <View style={st.track}>
          {links.map((item) => {
            const on = path === item.href;
            return (
              <Link key={item.href} href={item.href} asChild>
                <Pressable
                  role="link"
                  aria-current={on ? 'page' : undefined}
                  aria-label={item.badge ? `${item.label}, ${item.badge} en attente de ta réponse` : item.label}
                  style={StyleSheet.flatten([st.link, on && st.linkOn])}
                >
                <Text numberOfLines={1} style={{ color: on ? '#FFFFFF' : colors.textSoft, ...font.semibold, fontSize: 13 }}>{item.label}</Text>
                {item.badge ? (
                  <View style={[st.badge, on && { backgroundColor: colors.onAccent }]}>
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
  link: { flexGrow: 1, flexBasis: 'auto', flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6, paddingHorizontal: 8, minHeight: 38, borderRadius: 10 },
  linkOn: { backgroundColor: colors.accent, shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 10, shadowOffset: { width: 0, height: 3 } },
  badge: { minWidth: 20, height: 20, paddingHorizontal: 6, borderRadius: 10, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
});
