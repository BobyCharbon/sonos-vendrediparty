/** Refus techniques de la base (anglais, PostgreSQL / PostgREST / Supabase) remplacés par une phrase claire, partout dans le
 * module. Campagne des bots (06.11 puis campagne 2, 07.11) : « new row violates row-level security policy »,
 * « canceling statement due to statement timeout », « Cannot coerce the result to a single JSON object »… s'affichaient tels
 * quels. Les phrases françaises de la base (« La date limite de réponse est passée ») passent sans changement. */
const NOT_ALLOWED = 'Tu n’as pas le droit de faire ça. Si tu penses que c’est une erreur, demande à un admin.';
export const NETWORK_TEXT = 'La connexion a échoué. Vérifie ton réseau puis réessaie.';
export const GONE_TEXT = 'Cet événement n’existe plus ou ne t’est pas ouvert.';
const SLOW = 'Le serveur a mis trop de temps à répondre. Réessaie dans un instant.';
const GENERIC = 'Un souci technique est survenu. Réessaie dans un instant.';

const NETWORK = /Failed to fetch|NetworkError|Load failed|Network request failed|ERR_INTERNET_DISCONNECTED/i;
/** `.single()` sur 0 ligne : supprimé, ou pas visible (RLS) — PostgREST PGRST116. */
const GONE = /Cannot coerce the result to a single JSON object|JSON object requested, multiple \(or no\) rows returned|PGRST116/i;

const TECHNICAL: { test: RegExp; text: string }[] = [
  { test: /row-level security|permission denied|insufficient_privilege/i, text: NOT_ALLOWED },
  { test: NETWORK, text: NETWORK_TEXT },
  { test: GONE, text: GONE_TEXT },
  { test: /statement timeout|canceling statement|upstream request timeout|timed? ?out|HTTP 50[234]|Gateway Time-?out|job startup timeout/i, text: SLOW },
  { test: /numeric field overflow|out of range/i, text: 'Ce nombre est trop grand.' },
  { test: /invalid input syntax for type (integer|bigint|smallint)/i, text: 'Saisis un nombre entier (sans virgule).' },
  { test: /invalid input syntax for type numeric/i, text: 'Saisis un nombre (par exemple 12.50).' },
  { test: /invalid input syntax|invalid input value/i, text: 'Cette valeur n’est pas valable.' },
  { test: /value too long/i, text: 'Ce texte est trop long.' },
  { test: /duplicate key value/i, text: 'Ça existe déjà.' },
  { test: /you can only request this after|rate limit|Too Many Requests|HTTP 429/i, text: 'Attends quelques secondes avant de réessayer.' },
];

/** Message anglais technique non prévu ci-dessus (jamais affiché tel quel). */
const ENGLISH = /\b(the|does not|error|failed|unexpected|violates|relation|column|function|requested|syntax|constraint|cannot|could not|denied|null value|aborted|ignored|transaction|exist)\b|^HTTP \d{3}$/i;

export function friendlyError(message: string): string {
  const known = TECHNICAL.find((t) => t.test.test(message));
  if (known) return known.text;
  return ENGLISH.test(message) ? GENERIC : message;
}

/** L'événement n'existe plus ou n'est pas ouvert à cette personne : « Réessayer » ne servirait à rien. */
export function isGoneError(message: string): boolean {
  // Brut (PostgREST) ou déjà traduit (must / check passent par friendlyError).
  return GONE.test(message) || message === GONE_TEXT || message === 'Introuvable';
}

export function isNetworkError(message: string): boolean {
  return NETWORK.test(message) || message === NETWORK_TEXT;
}
