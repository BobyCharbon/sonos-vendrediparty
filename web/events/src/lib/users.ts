import { hasCompleteIdentity } from './profile';
import { roleRank, type Profile } from './types';

/** Un inscrit tel que le renvoie admin_member_list (Root, Admin). */
export type UserRow = Profile & {
  first_sign_in_at: string | null;
  last_sign_in_at: string | null;
  beta: boolean;
  sign_in_count: number;
  last_device: string | null;
  groups: string[];
  rsvp_count: number;
  message_count: number;
};

export type UserSort = 'last_sign_in' | 'first_sign_in' | 'signed_up' | 'name' | 'sign_ins' | 'role' | 'activity';
export type UserFilter = 'all' | 'guest' | 'vip' | 'team' | 'beta' | 'incomplete' | 'banned' | 'never';

export const USER_SORTS: { key: UserSort; label: string }[] = [
  { key: 'last_sign_in', label: 'Dernière connexion' },
  { key: 'first_sign_in', label: 'Première connexion' },
  { key: 'signed_up', label: 'Inscription' },
  { key: 'name', label: 'Nom' },
  { key: 'sign_ins', label: 'Nb de connexions' },
  { key: 'activity', label: 'Activité' },
  { key: 'role', label: 'Rôle' },
];

export const USER_FILTERS: { key: UserFilter; label: string }[] = [
  { key: 'all', label: 'Tous' },
  { key: 'guest', label: 'Guest' },
  { key: 'vip', label: 'Membre VIP' },
  { key: 'team', label: 'Orga et admins' },
  { key: 'beta', label: '🧪 Bêta' },
  { key: 'incomplete', label: 'Profil incomplet' },
  { key: 'never', label: 'Pas revenu (30 j)' },
  { key: 'banned', label: 'Accès retiré' },
];

const DAY = 86_400_000;
const time = (iso: string | null) => (iso ? Date.parse(iso) : 0);
const name = (u: UserRow) => (u.display_name || [u.first_name, u.last_name].filter(Boolean).join(' ') || '').toLocaleLowerCase('fr');

const KEYS: Record<UserSort, (u: UserRow) => number | string> = {
  last_sign_in: (u) => time(u.last_sign_in_at),
  first_sign_in: (u) => time(u.first_sign_in_at),
  signed_up: (u) => time(u.created_at),
  name,
  sign_ins: (u) => u.sign_in_count,
  activity: (u) => u.rsvp_count + u.message_count,
  role: (u) => roleRank(u.role),
};

/** Ordre « naturel » de chaque tri : le plus récent / le plus actif d'abord, les noms de A à Z. */
export const defaultDescending = (sort: UserSort) => sort !== 'name';

function matches(u: UserRow, filter: UserFilter, now: number): boolean {
  switch (filter) {
    case 'guest': return u.status === 'active' && u.role === 'guest';
    case 'vip': return u.status === 'active' && u.role === 'member';
    case 'team': return u.status === 'active' && roleRank(u.role) > roleRank('member');
    case 'beta': return u.beta;
    case 'incomplete': return !hasCompleteIdentity(u);
    case 'banned': return u.status === 'banned';
    case 'never': return now - time(u.last_sign_in_at) > 30 * DAY;
    default: return true;
  }
}

/** Recherche (surnom, prénom, nom, numéro), filtre puis tri ; ne modifie pas la liste reçue. */
export function arrangeUsers(users: readonly UserRow[], opts: { search: string; filter: UserFilter; sort: UserSort; descending: boolean; now?: number }): UserRow[] {
  const q = opts.search.trim().toLowerCase();
  const digits = q.replace(/\D/g, '');
  const now = opts.now ?? Date.now();
  const key = KEYS[opts.sort];
  const dir = opts.descending ? -1 : 1;
  return users
    .filter((u) => matches(u, opts.filter, now))
    .filter((u) => !q || [u.display_name, u.first_name, u.last_name].some((v) => v?.toLowerCase().includes(q)) || (digits.length >= 3 && (u.phone ?? '').includes(digits)))
    .slice()
    .sort((a, b) => {
      const ka = key(a), kb = key(b);
      const order = typeof ka === 'string' ? ka.localeCompare(kb as string, 'fr') : (ka as number) - (kb as number);
      return order * dir || name(a).localeCompare(name(b), 'fr');
    });
}
