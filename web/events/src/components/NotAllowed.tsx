import { router, Stack } from 'expo-router';

import { Button, Screen, T, Title } from './ui';

/** Page ouverte sans le droit (adresse tapée, lien d'un autre) : une phrase claire et un retour, jamais le formulaire. */
export function NotAllowed({ title, text }: { title: string; text: string }) {
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: '' }} />
      <Title size={26}>{title}</Title>
      <T muted>{text}</T>
      <Button label="Retour aux événements" variant="secondary" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
    </Screen>
  );
}
