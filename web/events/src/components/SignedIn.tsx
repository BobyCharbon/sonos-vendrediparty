import { Card, T } from './ui';

const BETA_NOTE = 'Les jeux et la musique sont ouverts avec ton compte. Les événements sont pour l’instant réservés aux bêta-testeurs.';

/** Confirme la connexion d'un compte (sans demande d'adhésion) : hors bêta, ou Guest qui ne voit que les sorties
 * publiques et ses invitations (note adaptée). */
export function SignedIn({ name, note = BETA_NOTE }: { name?: string | null; note?: string }) {
  return (
    <Card>
      <T weight="semibold">Tu es connecté à ton compte ✓</T>
      {name ? <T>Salut {name} 👋</T> : null}
      <T muted>{note}</T>
    </Card>
  );
}
