import { Card, T } from './ui';

const NOTE = 'Les jeux et la musique sont ouverts avec ton compte.';

/** Confirme la connexion d'un compte (sans demande d'adhésion) : hors bêta, ou Guest qui ne voit que les sorties
 * publiques et ses invitations (note adaptée). */
export function SignedIn({ name, note = NOTE }: { name?: string | null; note?: string }) {
  return (
    <Card>
      <T weight="semibold">Tu es connecté à ton compte ✓</T>
      {name ? <T>Salut {name} 👋</T> : null}
      <T muted>{note}</T>
    </Card>
  );
}
