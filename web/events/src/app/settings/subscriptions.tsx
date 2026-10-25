import { Redirect } from 'expo-router';

// Les abonnements vivent désormais dans Notifications et abonnements ; l'ancienne adresse y renvoie.
export default function Subscriptions() {
  return <Redirect href="/settings/notifications" />;
}
