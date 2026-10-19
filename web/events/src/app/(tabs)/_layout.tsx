import { Link, Slot, usePathname } from 'expo-router';
import { View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { colors, fonts } from '@/lib/theme';

export default function EventsLayout() {
  const { isAdmin } = useAuth();
  const path = usePathname();
  const links = [
    { href: '/', label: 'Sorties' },
    { href: '/activity', label: 'Activité' },
    { href: '/profile', label: 'Mon profil' },
    ...(isAdmin ? [{ href: '/admin', label: 'Administration' }] : []),
  ];
  return (
    <View style={{ flex: 1, backgroundColor: colors.bg }}>
      <View role="navigation" style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 4, padding: 8, borderBottomWidth: 1, borderBottomColor: colors.line }}>
        {links.map((item) => (
          <Link key={item.href} href={item.href} aria-current={path === item.href ? 'page' : undefined}
            style={{ paddingHorizontal: 10, paddingVertical: 12, minHeight: 44, borderRadius: 10,
              color: path === item.href ? colors.onAccent : colors.textSoft,
              backgroundColor: path === item.href ? colors.accent : 'transparent',
              fontFamily: fonts.semibold, fontSize: 13 }}>
            {item.label}
          </Link>
        ))}
      </View>
      <Slot />
    </View>
  );
}
