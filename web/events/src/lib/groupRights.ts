/**
 * Réglages du groupe pour son admin (demande du 23.11) : rôles et « Qui peut… », mêmes textes que l'app iPhone
 * (ios/Party/Chats/Groups/GroupRights.swift). La base décide de tout (migration 20261123110000, group_admin_panel,
 * set_group_right, set_group_role…) ; ces textes ne font que la dire.
 */
import { supabase } from './supabase';
import { colors } from './theme';

export type RightKey = 'invite' | 'events' | 'announce' | 'write' | 'pin' | 'edit' | 'remove';
export type Level = 'admins' | 'staff' | 'members';
export type GroupRole = 'creator' | 'coadmin' | 'organizer' | 'member';

export const RIGHT_KEYS: RightKey[] = ['invite', 'events', 'announce', 'write', 'pin', 'edit', 'remove'];
export const LEVELS: Level[] = ['admins', 'staff', 'members'];

export const RIGHTS: Record<RightKey, { label: string; about: string; members: string; staff?: string }> = {
  invite: { label: 'Inviter des personnes', about: 'Ajouter quelqu’un au groupe et partager le lien du groupe.',
    members: 'Chaque membre peut inviter et partager le lien du groupe.' },
  events: { label: 'Créer un événement pour le groupe', about: 'L’événement est réservé au groupe et apparaît sur sa page.',
    members: 'Chaque membre peut créer un événement du groupe.', staff: 'Les membres proposent en message, pas d’événement.' },
  announce: { label: 'Prévenir tout le groupe (@tout, annonce)',
    about: '@tout prévient chaque membre ; une annonce (@annonce) est épinglée en haut de la discussion.',
    members: 'Chaque membre peut écrire @tout. Les annonces restent aux organisateurs et aux admins.' },
  write: { label: 'Écrire dans la discussion', about: 'Les autres lisent la discussion, réagissent et signalent.',
    members: 'Chaque membre écrit dans la discussion.' },
  pin: { label: 'Épingler un message', about: 'Un message épinglé reste en haut de la discussion.',
    members: 'Chaque membre peut épingler un message.' },
  edit: { label: 'Modifier le nom, l’emoji et la photo', about: 'Le nom, l’emoji, la couleur et la photo du groupe.',
    members: 'Chaque membre peut les changer.' },
  remove: { label: 'Retirer un membre', about: 'Un membre ou un organisateur ne retire jamais un admin, un co-admin ni un organisateur.',
    members: 'Chaque membre peut retirer un simple membre.' },
};

export const LEVEL_TITLE: Record<Level, string> = {
  admins: 'Admins seulement', staff: 'Organisateurs et admins', members: 'Tous les membres',
};
export const LEVEL_COLOR: Record<Level, string> = { admins: colors.accentSoft, staff: colors.lavender, members: colors.mint };

/** Détail d'un choix sur l'écran d'un droit. */
export function levelDetail(k: RightKey, level: Level): string {
  if (level === 'admins') return 'Toi et les co-admins.';
  if (level === 'staff') return RIGHTS[k].staff ?? 'Les organisateurs, toi et les co-admins.';
  return RIGHTS[k].members;
}

/** « Tous les membres », « Membres · à valider par un admin »… (ligne de « Qui peut… »). */
export function whoText(k: RightKey, level: Level, needApproval = false): { text: string; color: string } {
  if (k === 'events' && level === 'members' && needApproval) return { text: 'Membres · à valider par un admin', color: colors.coral };
  return { text: LEVEL_TITLE[level], color: LEVEL_COLOR[level] };
}

export const ROLE_TITLE: Record<GroupRole, string> = {
  creator: 'Admin du groupe', coadmin: 'Co-admin', organizer: 'Organisateur', member: 'Membre',
};
export const ROLE_DETAIL: Record<Exclude<GroupRole, 'creator'>, string> = {
  member: 'Ce que tu permets aux membres dans « Qui peut… ».',
  organizer: 'Crée des événements sans validation et prévient le groupe (@annonce).',
  coadmin: 'Comme toi : réglages, rôles, membres. Sauf supprimer le groupe.',
};

/** « tu es l’admin du groupe », « tu es co-admin »… */
export function myRoleLine(role: GroupRole | null): string {
  if (role === 'creator') return 'tu es l’admin du groupe';
  if (role === 'coadmin') return 'tu es co-admin';
  if (role === 'organizer') return 'tu es organisateur';
  return role === 'member' ? 'tu es membre' : '';
}

export type PanelMember = { id: string; name: string; photo: string | null; role: GroupRole; since: string | null };
export type MyRights = {
  role: GroupRole | null; manage: boolean; rules: boolean; owner: boolean;
} & Record<RightKey, boolean>;
export type GroupPanel = {
  group: { id: string; name: string; emoji: string; color: string; photo: string | null; system: boolean; created_by: string | null };
  me: MyRights;
  rights: Record<RightKey, Level>;
  events_need_approval: boolean;
  announce_mode: 'request' | 'free';
  join_approval: boolean;
  link_active: boolean;
  members: PanelMember[];
  requests: { id: string; name: string; photo: string | null; at: string; via: string }[];
  /** Base sans la migration du 23.11 (lue autrement) : pas de rôles ni de « Qui peut… ». */
  legacy?: boolean;
};

type Row = { id: string; name: string; emoji: string; color: string; photo_path: string | null; created_by: string | null;
  system_key: string | null; events_need_approval: boolean; announce_mode: 'request' | 'free'; members_invite?: boolean;
  member_group_members: { user_id: string }[] };

/**
 * L'écran des réglages en une lecture (group_admin_panel). Base d'avant le 23.11 (fonction absente ou réponse vide) :
 * reconstruit depuis la table du groupe, avec les droits d'avant (créateur ou Admin du site) et l'ancien écran.
 */
export async function loadGroupPanel(id: string, meId: string, siteAdmin: boolean): Promise<GroupPanel | null> {
  const { data, error } = await supabase.rpc('group_admin_panel', { grp: id });
  if (!error && (data as GroupPanel | null)?.group) return data as GroupPanel;
  const { data: row } = await supabase.from('member_groups')
    .select('id, name, emoji, color, photo_path, created_by, system_key, events_need_approval, announce_mode, members_invite, member_group_members(user_id)')
    .eq('id', id).maybeSingle();
  const g = row as Row | null;
  if (!g) return null;
  const ids = g.member_group_members.map((m) => m.user_id);
  const people = ids.length ? await supabase.from('profiles').select('id, display_name, avatar_url').in('id', ids) : { data: [] };
  const system = !!g.system_key;
  const owner = !system && (g.created_by === meId || siteAdmin);
  const member = ids.includes(meId);
  return {
    legacy: true,
    group: { id: g.id, name: g.name, emoji: g.emoji, color: g.color, photo: system ? null : g.photo_path, system, created_by: g.created_by },
    me: { role: g.created_by === meId ? 'creator' : member ? 'member' : null, manage: owner, rules: owner, owner,
      invite: owner || (member && g.members_invite !== false), events: member || siteAdmin, announce: member, write: member,
      pin: owner, edit: owner, remove: owner },
    rights: { invite: g.members_invite === false ? 'staff' : 'members', events: 'members', announce: 'members', write: 'members',
      pin: 'admins', edit: 'admins', remove: 'admins' },
    events_need_approval: g.events_need_approval, announce_mode: g.announce_mode ?? 'request', join_approval: false, link_active: false,
    members: ((people.data ?? []) as { id: string; display_name: string; avatar_url: string | null }[]).map((p) => ({
      id: p.id, name: p.display_name, photo: p.avatar_url, role: p.id === g.created_by ? 'creator' : 'member', since: null })),
    requests: [],
  };
}
