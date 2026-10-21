import { Link, Slot, usePathname } from 'expo-router';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { usePendingCount } from '@/lib/pending';
import { colors, fonts } from '@/lib/theme';

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
        <ScrollView
          horizontal
          showsHorizontalScrollIndicator={false}
          style={{ width: '100%', maxWidth: 640, alignSelf: 'center' }}
          contentContainerStyle={{ gap: 4, paddingHorizontal: 8, paddingVertical: 8 }}
        >
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
                <Text style={{ color: on ? colors.onAccent : colors.textSoft, fontFamily: fonts.semibold, fontSize: 13 }}>{item.label}</Text>
                {item.badge ? (
                  <View style={[st.badge, on && { backgroundColor: colors.onAccent }]}>
                    <Text style={{ color: on ? colors.accent : colors.onAccent, fontFamily: fonts.bold, fontSize: 11 }}>{item.badge}</Text>
                  </View>
                ) : null}
                </Pressable>
              </Link>
            );
          })}
        </ScrollView>
      </View>
      <View style={{ flex: 1, minHeight: 0 }}>
        <Slot />
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  bar: { borderBottomWidth: 1, borderBottomColor: colors.line, backgroundColor: colors.bg, zIndex: 2 },
  link: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 14, paddingVertical: 10, minHeight: 44, borderRadius: 999 },
  linkOn: { backgroundColor: colors.accent },
  badge: { minWidth: 20, height: 20, paddingHorizontal: 6, borderRadius: 10, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
});
