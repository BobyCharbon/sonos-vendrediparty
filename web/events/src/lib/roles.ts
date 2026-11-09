/**
 * Rôles du groupe (table public.roles, migration 20261103140000_custom_roles) : rôles de base et rôles personnalisés,
 * du plus bas au plus haut. Le rang = la place dans la liste ; l'admin peut réordonner, créer, renommer, supprimer.
 * Le carnet est chargé avec le profil (lib/auth) ; avant cela, ou sur une base sans la table, ce sont les anciens
 * rôles figés et leurs anciens rangs (ceux que renvoie alors my_rank).
 */
export type Role = { key: string; label: string; color: string | null; icon: string | null; rank: number; builtin: boolean };

const LEGACY: Role[] = [
  ['guest', 'Guest', 0], ['guestplus', 'Guest+', 0], ['basic', 'Membre', 0], ['member', 'Membre VIP', 1],
  ['organizer', 'Organisateur', 2], ['coadmin', 'Co-admin', 3], ['admin', 'Admin', 4],
].map(([key, label, rank]) => ({ key: key as string, label: label as string, color: null, icon: null, rank: rank as number, builtin: true }));

let book: Role[] = LEGACY;

/** Remplace le carnet (lignes de public.roles triées par rang) ; vide ou invalide : on garde les anciens rôles. */
export function setRoleBook(rows: Role[] | null | undefined) {
  book = rows && rows.length ? [...rows].sort((a, b) => a.rank - b.rank) : LEGACY;
}

/** Du plus bas au plus haut. */
export const roleBook = (): Role[] => book;
export const isLegacyBook = () => book === LEGACY;
export const findRole = (key: string | null | undefined) => book.find((r) => r.key === key);
/** Rang d'un rôle (-1 : inconnu). */
export const roleRank = (key: string | null | undefined) => findRole(key)?.rank ?? -1;
/** Nom affiché d'un rôle (sa clé s'il est inconnu, par ex. supprimé depuis). */
export const roleName = (key: string | null | undefined) =>
  findRole(key)?.label ?? LEGACY.find((r) => r.key === key)?.label ?? String(key ?? '?');
/** Sous Membre VIP (Guest, Guest+, Membre, rôles placés dessous) : hors de Vendredi Party. */
export const belowVip = (key: string | null | undefined) => roleRank(key) < roleRank('member');
/** Organisateurs, co-admins, admins et tout rôle placé au-dessus de Membre VIP. */
export const aboveVip = (key: string | null | undefined) => roleRank(key) > roleRank('member');
/** Co-admin et au-dessus (admins d'office des groupes). */
export const siteAdminRank = () => roleRank('coadmin');

/** Couleurs proposées pour un rôle (celles des rôles de base). */
export const ROLE_COLORS = ['#8E8E93', '#A2845E', '#5AC8FA', '#34C759', '#FF9500', '#AF52DE', '#FF3B30', '#FF2D55', '#007AFF', '#FFCC00'];

/**
 * Monter (+1) ou descendre (-1) un rôle d'une place. `ascending` : clés du plus bas au plus haut.
 * Guest reste en bas, Admin en haut, et on ne range que les rôles en dessous de son propre rang (comme reorder_roles).
 * Renvoie le nouvel ordre, ou null si le déplacement n'est pas permis.
 */
export function moveRole(ascending: string[], key: string, step: 1 | -1, myRank: number): string[] | null {
  const from = ascending.indexOf(key);
  const to = from + step;
  const fixed = (k: string | undefined, i: number) => !k || k === 'guest' || k === 'admin' || i >= myRank;
  if (from < 0 || to < 0 || to >= ascending.length || fixed(key, from) || fixed(ascending[to], to)) return null;
  const next = [...ascending];
  [next[from], next[to]] = [next[to]!, next[from]!];
  return next;
}

const ROLE_ERRORS: [string, string][] = [
  ['role_duplicate', 'Ce nom de rôle existe déjà.'],
  ['role_not_empty', 'Ce rôle a encore des comptes : choisis le rôle qui les reprend.'],
  ['role_builtin', 'Ce rôle de base ne se supprime pas (tu peux le renommer).'],
  ['role_order', 'Guest reste en bas et Admin en haut. Recharge l’écran si la liste a changé.'],
  ['role_unknown', 'Ce rôle n’existe plus. Recharge l’écran.'],
  ['role_label', 'Donne un nom de 1 à 30 caractères.'],
  ['role_color', 'Cette couleur n’est pas valable.'],
  ['role_icon', 'Une seule icône (emoji).'],
  ['role_limit', '40 rôles au maximum.'],
  ['profile_incomplete', 'Un de ces comptes doit d’abord renseigner son nom, son prénom et son surnom.'],
];

/** Message de la base → phrase pour l'écran. */
export function roleError(message: string): string {
  return ROLE_ERRORS.find(([code]) => message.includes(code))?.[1] ?? message.replace(/^forbidden: /, '');
}
