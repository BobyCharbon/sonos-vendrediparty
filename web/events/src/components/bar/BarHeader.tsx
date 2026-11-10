import { router, Stack } from 'expo-router';

import { HeaderBack } from '../ui';

/** En-tête des écrans du bar : « ‹ Retour » court (le titre de l'événement chevauchait « Mon bar » à 390 px) ; ouvert
 * par un lien, sans rien derrière, il ramène à la fiche de l'événement. */
export function BarHeader({ title, eventId }: { title: string; eventId: string }) {
  return (
    <Stack.Screen options={{
      title,
      headerLeft: () => <HeaderBack label="Retour" onPress={() => (router.canGoBack() ? router.back() : router.replace(`/event/${eventId}`))} />,
    }} />
  );
}
