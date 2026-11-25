import { storeApp } from '@/lib/features';
import { Card, T } from './ui';

// App App Store : jeux illimités sans compte, onglet Musique caché (décisions de l'admin du 25.11).
const NOTE = storeApp ? 'Les jeux se jouent aussi sans compte, dans l’onglet Jeux.' : 'Les jeux et la musique sont ouverts avec ton compte.';

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
