/** Refus techniques de la base (anglais, PostgreSQL / PostgREST) remplacés par une phrase claire, partout dans le module
 * (campagne des bots, 06.11 : « new row violates row-level security policy for table "events" » s'affichait tel quel). */
const NOT_ALLOWED = 'Tu n’as pas le droit de faire ça. Si tu penses que c’est une erreur, demande à un admin.';
const TECHNICAL: { test: RegExp; text: string }[] = [
  { test: /row-level security|permission denied|insufficient_privilege/i, text: NOT_ALLOWED },
  { test: /Failed to fetch|NetworkError|Load failed/i, text: 'La connexion a échoué. Vérifie ton réseau puis réessaie.' },
];

export function friendlyError(message: string): string {
  return TECHNICAL.find((t) => t.test.test(message))?.text ?? message;
}
