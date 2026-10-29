// Types alignés sur supabase/migrations. À remplacer par `supabase gen types` une fois le projet lié.

export type MemberRole = 'guest' | 'guestplus' | 'basic' | 'member' | 'organizer' | 'coadmin' | 'admin';
export type MemberStatus = 'pending' | 'active' | 'banned';
export type EventStatus = 'draft' | 'pending' | 'published' | 'rejected' | 'cancelled';
export type DateMode = 'fixed' | 'poll';
export type RsvpStatus = 'yes' | 'maybe' | 'no';
export type DateVote = 'yes' | 'if_needed' | 'no';
export type Visibility = 'all' | 'invited';
export type ChatMode = 'all' | 'mentions' | 'none';
export type NewEventScope = 'all' | 'subscribed' | 'none';
export type Reminder = '7d' | '1d' | '2h' | '0h';

export type Profile = {
  id: string;
  display_name: string;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  avatar_url: string | null;
  role: MemberRole;
  status: MemberStatus;
  created_at: string;
};

export type GroupSettings = {
  name: string;
  timezone: string;
  require_approval: boolean;
  coadmins_skip_approval: boolean;
  organizers_can_edit_published: boolean;
  members_can_create_tags: boolean;
};

export type Category = { id: string; name: string; color: string; icon: string | null; sort: number; archived: boolean };
export type Tag = { id: string; name: string; color: string; archived: boolean };

export type EventRow = {
  id: string;
  title: string;
  description: string;
  cover_url: string | null;
  category_id: string | null;
  created_by: string;
  status: EventStatus;
  rejection_reason: string | null;
  date_mode: DateMode;
  starts_at: string | null;
  ends_at: string | null;
  all_day: boolean;
  poll_deadline: string | null;
  members_can_propose_dates: boolean;
  auto_fix_date: boolean;
  location_name: string | null;
  location_address: string | null;
  location_url: string | null;
  price_chf: number | null;
  payment_info: string | null;
  max_participants: number | null;
  waitlist_enabled: boolean;
  allow_plus_ones: boolean;
  max_plus_ones: number;
  allow_maybe: boolean;
  rsvp_deadline: string | null;
  visibility: Visibility;
  public_link: boolean;
  show_participants: boolean;
  forum_enabled: boolean;
  notify_on_publish: boolean;
  reminders: Reminder[];
  created_at: string;
  updated_at: string;
};

/** Groupe de membres réutilisable pour inviter à un événement privé. */
/** system_key 'vip' : groupe « Vendredi Party » (Membres VIP et au-dessus), tenu à jour par la base selon le statut. */
export type MemberGroup = { id: string; name: string; created_by: string | null; system_key?: string | null; member_group_members: { user_id: string }[] };
export const VIP_GROUP_KEY = 'vip';

export type Rsvp = {
  event_id: string;
  user_id: string;
  status: RsvpStatus;
  plus_ones: number;
  note: string | null;
  waitlisted: boolean;
  /** Réponse posée par l’organisateur (son identifiant) ; vide quand la personne a répondu elle-même. */
  set_by?: string | null;
};

export type DateOption = { id: string; event_id: string; starts_at: string; ends_at: string | null; proposed_by: string | null };
export type DateVoteRow = { option_id: string; user_id: string; vote: DateVote };

export type Poll = {
  id: string;
  event_id: string | null;
  question: string;
  multiple_choice: boolean;
  anonymous: boolean;
  members_can_add_options: boolean;
  results_after_vote: boolean;
  closes_at: string | null;
  created_by: string | null;
  sort: number;
};
export type PollOption = { id: string; poll_id: string; label: string; sort: number };

export type BringItem = { id: string; event_id: string; label: string; claimed_by: string | null; sort: number; added_by: string | null };

export type Message = {
  id: string;
  event_id: string;
  user_id: string;
  body: string;
  reply_to: string | null;
  mentions: string[];
  pinned: boolean;
  created_at: string;
  deleted_at: string | null;
};

export type NotificationPrefs = {
  user_id: string;
  push_enabled: boolean;
  quiet_start: string | null;
  quiet_end: string | null;
  new_event: NewEventScope;
  event_changed: boolean;
  poll_new: boolean;
  poll_nudge: boolean;
  date_fixed: boolean;
  waitlist: boolean;
  proposals: boolean;
  rsvp_mine: boolean;
  chat: ChatMode;
  reminders: Reminder[];
};

/** Droits qui ouvrent l'Administration (dans les Réglages). */
export const ADMIN_PERMS = ['events.approve', 'members.approve', 'members.roles', 'members.ban', 'members.view_identity', 'roles.manage', 'taxonomy.manage', 'group.settings', 'announcements.publish'];
// basic = « Membre » (mêmes droits que Guest), hors du groupe Vendredi Party, réservé aux Membres VIP et plus.
// guestplus = « Guest+ » : droits de Guest, plus « Écrire un avis » (29.10.2026).
export const ROLE_ORDER: MemberRole[] = ['guest', 'guestplus', 'basic', 'member', 'organizer', 'coadmin', 'admin'];
// Mêmes rangs que la base (private.role_rank) : Membre au niveau de Guest. Pas l'ordre de la liste, qui l'a décalé.
const RANKS: Record<MemberRole, number> = { guest: 0, guestplus: 0, basic: 0, member: 1, organizer: 2, coadmin: 3, admin: 4 };
export const roleRank = (r: MemberRole) => RANKS[r];
export const roleLabel: Record<MemberRole, string> = { guest: 'Guest', guestplus: 'Guest+', basic: 'Membre', member: 'Membre VIP', organizer: 'Organisateur', coadmin: 'Co-admin', admin: 'Admin' };
export type Permission = { key: string; grp: string; label: string; hint: string | null; sort: number };

// shortcut: la base plafonne max_plus_ones à 10 ; 10 veut dire « illimité ». Une vraie valeur vide demanderait une migration partagée avec l'app iOS.
export const UNLIMITED_PLUS_ONES = 10;
export const plusOnesLabel = (max: number) => (max >= UNLIMITED_PLUS_ONES ? '∞ Illimité' : `Jusqu’à ${max} par personne`);
