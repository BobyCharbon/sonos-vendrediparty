import { Card, T } from './ui';

/** Compte connecté sans accès aux sorties : confirme la connexion, sans demande d'adhésion (accès donné par un admin). */
export function SignedIn({ name }: { name?: string | null }) {
  return (
    <Card>
      <T weight="semibold">Tu es connecté à ton compte ✓</T>
      {name ? <T>Salut {name} 👋</T> : null}
      <T muted>Les jeux et la musique sont ouverts avec ton compte. Les sorties sont pour l’instant réservées aux bêta-testeurs.</T>
    </Card>
  );
}
