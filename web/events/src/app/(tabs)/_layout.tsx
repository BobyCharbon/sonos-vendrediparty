import { Slot } from 'expo-router';
import { View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/lib/theme';

/**
 * Accueil Événements sans barre d'onglets (maquette A du 08.11) : « Mon profil » vit dans les Réglages, l'Activité
 * s'ouvre depuis la cloche de l'accueil. Les adresses /activity et /profile restent valables (liens des notifications).
 */
export default function EventsLayout() {
  const insets = useSafeAreaInsets();
  return (
    <View style={{ flex: 1, minHeight: 0, backgroundColor: colors.bg, paddingTop: insets.top, paddingLeft: insets.left, paddingRight: insets.right }}>
      <Slot />
    </View>
  );
}
