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
  // Haut seulement : chaque écran (Screen, SafeAreaView de l'accueil) garde déjà la marge gauche / droite. La reprendre
  // ici la comptait deux fois : sur l'iPhone Duo plié (colonne de la barre d'état à droite), l'accueil n'occupait que
  // ~64 % de la largeur, « Événements » se coupait en trois lignes (retour de l'admin du 19.11).
  return (
    <View style={{ flex: 1, minHeight: 0, backgroundColor: colors.bg, paddingTop: insets.top }}>
      <Slot />
    </View>
  );
}
