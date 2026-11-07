import { router, Stack } from 'expo-router';
import { View } from 'react-native';

import { Button, Screen, T, Title } from '@/components/ui';

/** Adresse inconnue (/events/n-importe-quoi) : une page en français avec un retour, au lieu de l'écran anglais par défaut
 * d'Expo (campagne 2, rapports 09 et 10). */
export default function NotFound() {
  return (
    <Screen edges={[]}>
      <Stack.Screen options={{ title: 'Page introuvable' }} />
      <View style={{ gap: 12, paddingVertical: 24 }}>
        <Title level={1} size={28}>Page introuvable</Title>
        <T muted>Ce lien ne mène à rien : la page a peut-être été déplacée, ou l’adresse est incomplète.</T>
        <Button label="Retour aux événements" onPress={() => router.replace('/')} />
      </View>
    </Screen>
  );
}
