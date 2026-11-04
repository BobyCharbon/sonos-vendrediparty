// Types alignés sur supabase/migrations. À remplacer par `supabase gen types` une fois le projet lié.

/** Clé d'un rôle (table public.roles) : guest, guestplus, basic, member, organizer, coadmin, admin, ou un rôle personnalisé r_… */
export type MemberRole = string;
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
  pot_enabled?: boolean;
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

export type BringClaim = { user_id: string; quantity: number };
/** quantity : à partager (« 15 bouteilles », chacun dit combien il en amène dans bring_claims) ; null = un seul objet (claimed_by). */
export type BringItem = {
  id: string; event_id: string; label: string; claimed_by: string | null; sort: number; added_by: string | null;
  quantity?: number | null; bring_claims?: BringClaim[];
};

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
  /** Lune des Réglages : tout arrive sans son jusqu'à cette date ; null ou passée = pas de pause. */
  muted_until: string | null;
  /** Pause des Discussions des groupes jusqu'à cette date (messages sans son). */
  chats_muted_until: string | null;
  /** Pause des discussions des événements jusqu'à cette date. */
  event_chats_muted_until: string | null;
  /** Un réglage par type de notification (migration 20261103120000). */
  announcements: boolean;
  rsvp_set: boolean;
  invites: boolean;
  proposal_result: boolean;
  link_join: boolean;
  group_messages: boolean;
  group_invites: boolean;
  group_joins: boolean;
  /** Annonces et @tout des groupes de Discussions (absent avant la migration : reçues). */
  group_broadcasts?: boolean;
  /** Billets payants (migration 20261103130000 ; absent avant : reçues) : quelqu'un dit avoir payé ma place / mon paiement confirmé. */
  ticket_pay_declared?: boolean;
  ticket_pay_confirmed?: boolean;
  /** Mes amis dans Party (migration 20261104090000 ; absents avant : reçues) : quelqu'un rejoint Party grâce à mon lien ;
   * un contact de l'iPhone arrive sur Party (notification calculée par l'app iPhone). */
  referral_joins?: boolean;
  contact_joins?: boolean;
  /** Messages directs (migration 20261104100000 ; absent avant : reçus) : « Nouveau message de X ». */
  direct_messages?: boolean;
  /** Compagnon (migration 20261104130000 ; absents avant : reçus) : rappel doux du jour, alertes avant son envol. */
  pet_daily?: boolean;
  pet_alerts?: boolean;
  /** Compagnon, lot 1 (migration 20261104150000 ; absents avant : reçus) : cadeau d'un ami, paliers de série. */
  pet_gifts?: boolean;
  pet_streaks?: boolean;
  /** Modération (migration 20261104200000 ; absents avant : reçus) : nouveau signalement (modérateurs), message de la modération. */
  moderation_reports?: boolean;
  moderation_notices?: boolean;
};

/** Pause des notifications : 'all' = la lune, 'chats' = Discussions des groupes, 'event_chats' = discussions des événements. */
export type PauseScope = 'all' | 'chats' | 'event_chats';
export type PauseSpan = '30m' | '1h' | '2h' | 'morning' | 'off';

/** Droits qui ouvrent l'Administration (dans les Réglages). */
export const ADMIN_PERMS = ['events.approve', 'members.approve', 'members.roles', 'members.ban', 'members.view_identity', 'roles.manage', 'taxonomy.manage', 'group.settings', 'announcements.publish', 'moderation.reports'];
// Rôles (noms, rangs, ordre) : lib/roles.ts, lus dans la table public.roles (rôles personnalisés, réordonnables).
export type Permission = { key: string; grp: string; label: string; hint: string | null; sort: number };

// shortcut: la base plafonne max_plus_ones à 10 ; 10 veut dire « illimité ». Une vraie valeur vide demanderait une migration partagée avec l'app iOS.
export const UNLIMITED_PLUS_ONES = 10;
export const plusOnesLabel = (max: number) => (max >= UNLIMITED_PLUS_ONES ? '∞ Illimité' : `Jusqu’à ${max} par personne`);
