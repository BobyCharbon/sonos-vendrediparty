import { router, Stack } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Pressable, View } from 'react-native';

import { useAuth, useMe } from '@/lib/auth';
import { fetchTaxonomy, useQuery } from '@/lib/data';
import { dateProblem, placesProblem, plusOnesProblem, priceProblem } from '@/lib/eventChecks';
import { EventCover } from './CoverSheet';
import { useLeaveGuard } from './LeaveGuard';
import { parseLocalDateTime, toLocalInput } from '@/lib/format';
import { NO_REPEAT, REPEAT_CHOICES, repeatLabel, repeatOf, untilDate, type Repeat, type Series } from '@/lib/recurrence';
import { friendlyError } from '@/lib/errors';
import { dbMessage } from '@/lib/moderation';
import { termsLater, useTermsGate } from './TermsSheet';
import { enter, pressTransition, useChangedSinceMount } from '@/lib/motion';
import { check, must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { DateMode, EventRow, MemberGroup, PaymentMode, Poll, PollOption, Reminder } from '@/lib/types';
import { UNLIMITED_PLUS_ONES, VIP_GROUP_KEY } from '@/lib/types';

import { Button, Cascade, Chip, ConfirmButton, ErrorText, Field, HeaderBack, Input, Reveal, Rows, s, Screen, Section, Segmented, T, ToggleRow } from './ui';
import { afterPublish } from './InviteStep';
import { PUBLIC_REVIEW } from './VisibilityChoice';
import { coversOn, invitesV2On, souvenirsOn } from '@/lib/features';
import { AudiencePicker, audienceError, saveAudience, audienceFromEvent, audienceToEvent, DEFAULT_AUDIENCE, mayUseVip, type AudienceValue, type Person } from './AudiencePicker';
import { DateTimeField } from './DateTimeField';
import { PlaceSearch } from './PlaceSearch';
import { SaveAsTemplate, TemplateList } from './TemplatePicker';
import { applyTemplate, templateData } from '@/lib/templates';
import { notifyWallet } from '@/lib/wallet';
import { AnnounceToggle } from './AnnounceToggle';
import { SouvenirsSettings } from './souvenirs/SouvenirsSettings';

type PollDraft = {
  id?: string;
  question: string;
  options: { id?: string; label: string }[];
  multiple_choice: boolean;
  anonymous: boolean;
  members_can_add_options: boolean;
  results_after_vote: boolean;
};


type Draft = {
  title: string;
  description: string;
  category_id: string | null;
  tag_ids: string[];
  date_mode: DateMode;
  starts_at: string;
  ends_at: string;
  slots: { id?: string; text: string }[];
  poll_deadline: string;
  members_can_propose_dates: boolean;
  auto_fix_date: boolean;
  location_name: string;
  location_address: string;
  location_url: string;
  price_chf: string;
  payment_info: string;
  payment_mode: PaymentMode;
  payment_url: string;
  payment_open: boolean;
  /** « Prévenir les participants à l'ouverture » (events.payment_open_notify) ; payment_was_open : état enregistré. */
  payment_notify: boolean;
  payment_was_open: boolean;
  max_participants: string;
  waitlist_enabled: boolean;
  allow_plus_ones: boolean;
  max_plus_ones: string;
  allow_maybe: boolean;
  rsvp_deadline: string;
  who: AudienceValue;  // qui voit la sortie (AudiencePicker)
  organizers: string[];
  show_participants: boolean;
  pot_enabled: boolean;
  carpool_enabled: boolean;
  /** Billets QR : éteints par défaut ; l'organisateur remet ensuite chaque billet (migration 20261104233000). */
  tickets_enabled: boolean;
  /** Souvenirs (24.11) : éteints par défaut, jamais allumés par l'IA ; « Garder les photos après la story » allumé par défaut.
   * souvenirs_was : état enregistré (on n'écrit les colonnes que si l'option est ou était allumée) ; figés dès la 1re photo. */
  souvenirs_enabled: boolean;
  souvenirs_keep: boolean;
  souvenirs_was: boolean;
  souvenirs_locked: boolean;
  forum_enabled: boolean;
  notify_on_publish: boolean;
  /** « Prévenir le groupe » : éteint par défaut ; un simple membre du groupe fait une demande à l'admin du groupe. */
  announce_group: boolean;
  polls: PollDraft[];
  /** quantity : texte du champ « Qté » ; vide ou 1 = un seul objet, pris en entier par une personne. */
  bring: { id?: string; label: string; quantity?: string }[];
  /** Répétition (16.11) : la suivante apparaît une fois celle-ci terminée. */
  repeat: Repeat;
};

const emptyDraft: Draft = {
  title: '',
  description: '',
  category_id: null,
  tag_ids: [],
  date_mode: 'fixed',
  starts_at: '',
  ends_at: '',
  slots: [{ text: '' }, { text: '' }],
  poll_deadline: '',
  members_can_propose_dates: true,
  auto_fix_date: false,
  location_name: '',
  location_address: '',
  location_url: '',
  price_chf: '',
  payment_info: '',
  payment_mode: 'organizer',
  payment_url: '',
  payment_open: true,
  payment_notify: true,
  payment_was_open: true,
  max_participants: '',
  waitlist_enabled: true,
  allow_plus_ones: true,   // nouvel événement : accompagnants autorisés, sans limite (max vide = illimité)
  max_plus_ones: '',
  allow_maybe: true,
  rsvp_deadline: '',
  // Public + lien public par défaut, comme l'assistant IA (décision de l'admin, 06.11) ; un public ne prévient personne.
  who: { ...DEFAULT_AUDIENCE, audience: 'public', vip: false },
  organizers: [],
  show_participants: true,
  pot_enabled: false,
  carpool_enabled: false,
  tickets_enabled: false,
  souvenirs_enabled: false,
  souvenirs_keep: true,
  souvenirs_was: false,
  souvenirs_locked: false,
  forum_enabled: true,
  notify_on_publish: true,
  announce_group: false,
  polls: [],
  bring: [],
  repeat: NO_REPEAT,
};

// Rappels : chacun choisit les siens (Réglages → Notifications) ; l'événement les propose tous.
const ALL_REMINDERS: Reminder[] = ['7d', '1d', '2h', '0h'];

/** Simple : l’essentiel pour lancer l’événement ; avancé : toutes les options. Le dernier choix est retenu. */
type FormMode = 'simple' | 'advanced';
// Au-delà, « Publier » rend la main (la base peut encore finir : le même brouillon est repris, jamais un second).
const PUBLISH_LIMIT_MS = 20000;
const SLOW_PUBLISH = 'La publication prend du temps : ton événement est peut-être déjà enregistré (publié ou en attente de validation), regarde dans tes événements avant de réessayer.';
const modeKey = 'party-event-form-mode';
function readMode(): FormMode {
  try { return localStorage.getItem(modeKey) === 'advanced' ? 'advanced' : 'simple'; } catch { return 'simple'; }
}
function saveMode(mode: FormMode) {
  try { localStorage.setItem(modeKey, mode); } catch { /* Stockage indisponible : le choix vaut pour cette page. */ }
}

/** Réglages avancés qui diffèrent des valeurs par défaut : rappelés en mode simple, rien n’est caché sans le dire. */
function activeAdvanced(d: Draft): string[] {
  return [
    d.tag_ids.length ? 'tags' : '',
    d.location_address || d.location_url ? 'adresse' : '',
    d.price_chf || d.payment_info ? 'prix' : '',
    d.max_participants ? 'places limitées' : '',
    d.tickets_enabled ? 'billets QR' : '',
    d.allow_maybe ? '' : 'sans « Peut-être »',
    d.allow_plus_ones ? '' : 'sans accompagnants',
    d.allow_plus_ones && d.max_plus_ones.trim() ? 'accompagnants limités' : '',
    d.rsvp_deadline ? 'date limite' : '',
    d.show_participants ? '' : 'participants masqués',
    d.organizers.length ? 'co-organisateurs' : '',
    d.polls.length ? 'mini-sondages' : '',
    d.bring.length ? 'qui amène quoi' : '',
    d.forum_enabled ? '' : 'sans discussion',
  ].filter(Boolean);
}

/** Réservé à un groupe (ou aux Membres Vendredi Party) : « Prévenir le groupe » a un sens. Public : jamais. */
export function hasGroupAudience(who: AudienceValue): boolean {
  return who.audience === 'invite' && (who.vip || who.group_ids.length > 0);
}

/** « 15 » → 15 (partagé entre plusieurs personnes) ; vide, 0 ou 1 → null (une personne prend l'objet entier). */
export function bringQuantity(text: string | undefined): number | null {
  const n = parseInt(text ?? '', 10);
  return n >= 2 ? Math.min(n, 999) : null;
}

/** « Bouteilles de vin : déjà 13 promises, la quantité ne peut pas descendre à 5 » ; null si tout va bien. */
async function bringBelowPromised(bring: Draft['bring']): Promise<string | null> {
  const kept = bring.filter((b) => b.id);
  if (!kept.length) return null;
  const { data } = await supabase.from('bring_claims').select('item_id, quantity').in('item_id', kept.map((b) => b.id!));
  const promised = new Map<string, number>();
  for (const c of data ?? []) promised.set(c.item_id, (promised.get(c.item_id) ?? 0) + c.quantity);
  for (const b of kept) {
    const taken = promised.get(b.id!) ?? 0;
    const wanted = bringQuantity(b.quantity);
    if (taken && (wanted === null || wanted < taken)) {
      return `${b.label} : déjà ${taken} promis par les invités, la quantité ne peut pas descendre en dessous.`;
    }
  }
  return null;
}

// Couverture éteinte (prod, app App Store) : ses colonnes n'existent pas encore en prod, jamais lues (sinon « Modifier » plante).
const FORM_EVENT_COLS = (coversOn ? 'status, created_by, cover_url, cover_credit, cover_credit_url' : 'status, created_by') as 'status, created_by, cover_url, cover_credit, cover_credit_url';

async function loadDraft(eventId: string): Promise<Draft> {
  const res = await supabase
    .from('events')
    .select(
      '*, event_tags(tag_id), event_organizers(user_id), event_invites(user_id, via_group), event_groups(group_id), event_phone_invites(phone), date_options(id, starts_at), polls(*, poll_options(*)), bring_items(id, label, sort, quantity), series:event_series(frequency, every, until, stopped_at)',
    )
    .eq('id', eventId)
    .single();
  const e = must(res) as unknown as EventRow & {
    event_tags: { tag_id: string }[];
    event_organizers: { user_id: string }[];
    event_invites: { user_id: string; via_group: boolean }[];
    event_groups: { group_id: string }[];
    event_phone_invites: { phone: string }[];
    date_options: { id: string; starts_at: string }[];
    polls: (Poll & { poll_options: PollOption[] })[];
    bring_items: { id: string; label: string; sort: number; quantity: number | null }[];
    series?: Series | null;
  };
  return {
    title: e.title,
    description: e.description,
    category_id: e.category_id,
    tag_ids: e.event_tags.map((t) => t.tag_id),
    date_mode: e.date_mode,
    starts_at: toLocalInput(e.starts_at),
    ends_at: toLocalInput(e.ends_at),
    slots: e.date_options
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at))
      .map((o) => ({ id: o.id, text: toLocalInput(o.starts_at) })),
    poll_deadline: toLocalInput(e.poll_deadline),
    members_can_propose_dates: e.members_can_propose_dates,
    auto_fix_date: e.auto_fix_date,
    location_name: e.location_name ?? '',
    location_address: e.location_address ?? '',
    location_url: e.location_url ?? '',
    price_chf: e.price_chf?.toString() ?? '',
    payment_info: e.payment_info ?? '',
    payment_mode: e.payment_mode ?? 'organizer',
    payment_url: e.payment_url ?? '',
    payment_open: e.payment_open !== false,
    payment_notify: e.payment_open_notify !== false,
    payment_was_open: e.payment_open !== false,
    max_participants: e.max_participants?.toString() ?? '',
    waitlist_enabled: e.waitlist_enabled,
    allow_plus_ones: e.allow_plus_ones,
    max_plus_ones: e.max_plus_ones >= UNLIMITED_PLUS_ONES ? '' : e.max_plus_ones.toString(),
    allow_maybe: e.allow_maybe,
    rsvp_deadline: toLocalInput(e.rsvp_deadline),
    who: audienceFromEvent(e),
    organizers: e.event_organizers.map((o) => o.user_id),
    show_participants: e.show_participants,
    pot_enabled: e.pot_enabled ?? false,
    carpool_enabled: e.carpool_enabled ?? false,
    tickets_enabled: e.tickets_enabled ?? false,
    souvenirs_enabled: e.souvenirs_enabled ?? false,
    souvenirs_keep: e.souvenirs_keep ?? true,
    souvenirs_was: e.souvenirs_enabled ?? false,
    souvenirs_locked: e.souvenirs_locked ?? false,
    forum_enabled: e.forum_enabled,
    notify_on_publish: e.notify_on_publish,
    announce_group: !!e.announce_group,
    polls: e.polls
      .sort((a, b) => a.sort - b.sort)
      .map((p) => ({
        id: p.id,
        question: p.question,
        options: p.poll_options.sort((a, b) => a.sort - b.sort).map((o) => ({ id: o.id, label: o.label })),
        multiple_choice: p.multiple_choice,
        anonymous: p.anonymous,
        members_can_add_options: p.members_can_add_options,
        results_after_vote: p.results_after_vote,
      })),
    bring: e.bring_items.sort((a, b) => a.sort - b.sort).map((b) => ({ id: b.id, label: b.label, quantity: b.quantity ? String(b.quantity) : '' })),
    repeat: repeatOf(e.series),
  };
}

/** Préremplissage d'un nouvel événement depuis l'Agenda (« Qui est libre ? ») : titre, date fixée, ou dates d'un sondage. */
export type EventPrefill = { title?: string; starts?: string; ends?: string; poll?: string[] };

function prefilled(p?: EventPrefill): Draft {
  if (!p) return emptyDraft;
  const d: Draft = { ...emptyDraft, title: p.title ?? '' };
  if (p.poll) return { ...d, date_mode: 'poll', slots: p.poll.length ? p.poll.map((iso) => ({ text: toLocalInput(iso) })) : emptyDraft.slots };
  return { ...d, starts_at: toLocalInput(p.starts), ends_at: toLocalInput(p.ends) };
}

/** group : « Créer un événement pour le groupe » (page du groupe, 17.11) : ce groupe déjà coché, sans prévenir le groupe.
 * prefill : « Organiser le sam. 28 » / « Faire voter le groupe » de l'Agenda (titre, date ou dates du sondage). */
export function EventForm({ eventId, group, prefill }: { eventId?: string; group?: string; prefill?: EventPrefill }) {
  const me = useMe();
  // CGU exigées en prod (terms_enforced) : un nouvel événement les fait accepter avant d'être enregistré.
  const terms = useTermsGate();
  const { can } = useAuth();
  const isAdmin = can('events.publish_direct');  // publie sans passer par la validation
  const siteAdmin = can('events.manage_all');  // co-organisateurs : choisit parmi tous les comptes qui peuvent modifier
  const canRepeat = can('events.recurring');  // Admin, Co-admin, Organisateur (Rôles et droits)
  const [draft, setDraft] = useState<Draft | null>(() => (eventId ? null : prefilled(prefill)));
  // Ce qui était là à l'ouverture : la base de « changements non enregistrés » et du « début changé ».
  const [initial, setInitial] = useState<Draft | null>(() => (eventId ? null : prefilled(prefill)));
  const savedEventId = useRef(eventId);
  const groupPreset = useRef(!eventId && !!group);
  const saving = useRef(false);
  // Publication en route (base lente) : un nouveau toucher l'attend, jamais une seconde publication.
  const inflight = useRef<Promise<void> | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newTag, setNewTag] = useState('');
  const [mode, setModeState] = useState<FormMode>(readMode);
  const setMode = (next: FormMode) => { setModeState(next); saveMode(next); };
  // Brouillon créé par une publication qui a échoué en route : repris au nouvel essai, supprimé si l'on abandonne.
  const [orphan, setOrphan] = useState<string | null>(null);
  const orphanDraft = useRef<string | null>(null);
  // Enregistré : on part (après le rendu qui lève la garde « Abandonner les changements ? »).
  const [doneAt, setDoneAt] = useState<string | null>(null);
  useEffect(() => { if (doneAt) router.replace(doneAt as never); }, [doneAt]);
  const dirty = !!draft && !!initial && JSON.stringify(draft) !== JSON.stringify(initial);
  const leaveSheet = useLeaveGuard(
    (dirty || !!orphan) && !doneAt,
    orphan ? 'Le brouillon commencé est supprimé.' : null,
    // Seulement s'il est resté brouillon : une publication lente arrivée entre-temps n'est jamais effacée.
    orphan ? async () => { check(await supabase.from('events').delete().eq('id', orphan).eq('status', 'draft')); } : undefined,
  );
  const cancel = () => (router.canGoBack() ? router.back() : router.replace((eventId ? `/event/${eventId}` : '/') as never));

  const { data: ctx, error: contextError, reload: reloadCtx } = useQuery(async () => {
    const [taxonomy, members, groups, settings, current, editorRoles, linked] = await Promise.all([
      fetchTaxonomy(),
      supabase.from('profiles').select('id, display_name, role').eq('status', 'active').order('display_name'),
      supabase.from('member_groups').select('id, name, created_by, system_key, events_need_approval, member_group_members(user_id)').order('name'),
      supabase.from('group_settings').select('require_approval').single(),
      eventId ? supabase.from('events').select(FORM_EVENT_COLS).eq('id', eventId).single() : Promise.resolve(null),
      // Co-organisateurs : seulement des rôles qui peuvent modifier un événement publié (sinon ni Modifier ni Annuler).
      supabase.from('role_permissions').select('role').in('perm', ['events.edit_own_published', 'events.manage_all']),
      // Recette du 27.11 : un Guest tout neuf se voyait proposer les comptes de l'équipe. Seulement les personnes avec qui
      // on a un lien (groupes en commun, événements en commun : migration 20261127100000) ; un admin du site garde tout.
      siteAdmin ? Promise.resolve(null) : supabase.rpc('co_organizer_suggestions'),
    ]);
    if (eventId && !draft) {
      const loaded = await loadDraft(eventId);
      setInitial(loaded);
      setDraft(loaded);
    }
    // Depuis la page d'un groupe : ce groupe coché (Vendredi Party : « Membres Vendredi Party »), « Prévenir » éteint ;
    // une seule fois (un retour sur l'écran ne défait pas ce qu'on a changé depuis).
    const preset = groupPreset.current ? (must(groups) as MemberGroup[]).find((g) => g.id === group) : undefined;
    if (preset) {
      groupPreset.current = false;
      const who: AudienceValue = preset.system_key === VIP_GROUP_KEY
        ? { ...DEFAULT_AUDIENCE, audience: 'invite', vip: true }
        : { ...DEFAULT_AUDIENCE, audience: 'invite', vip: false, group_ids: [preset.id] };
      const withGroup = (d: Draft | null) => (d ? { ...d, who, announce_group: false } : d);
      setDraft(withGroup);
      setInitial(withGroup);
    }
    // Hors du groupe Vendredi Party, on ne peut pas lui réserver un événement (base : 20261106090000) : public par défaut.
    if (!eventId && !mayUseVip(must(groups) as MemberGroup[], me.id, can('events.manage_all'))) {
      setDraft((d) => (d && d.who.audience === 'invite' && d.who.vip ? { ...d, who: { ...d.who, audience: 'public', vip: false } } : d));
    }
    return {
      ...taxonomy,
      members: must(members) as Person[],
      groups: must(groups) as MemberGroup[],
      settings: must(settings) as { require_approval: boolean },
      status: current ? (must(current) as { status: EventRow['status'] }).status : null,
      createdBy: current ? (must(current) as { created_by?: string | null }).created_by ?? null : null,
      cover: current && coversOn ? (must(current) as Pick<EventRow, 'cover_url' | 'cover_credit' | 'cover_credit_url'>) : null,
      editors: new Set((must(editorRoles) as { role: string }[]).map((r) => r.role)),
      // null : tout le monde (admin du site) ; base sans la fonction ou erreur : personne (jamais toute l'équipe).
      linked: linked === null ? null
        : new Set(!linked.error && Array.isArray(linked.data) ? (linked.data as { id: string }[]).map((p) => p.id) : []),
    };
  }, [eventId]);

  // Une ligne ajoutée (créneau, option, sondage, objet) apparaît en douceur ; celles du départ restent posées.
  const slotsGrew = useChangedSinceMount(draft?.slots.length ?? 0);
  const pollsGrew = useChangedSinceMount(draft?.polls.map((p) => p.options.length).join() ?? '');
  const bringGrew = useChangedSinceMount(draft?.bring.length ?? 0);

  if (!draft || !ctx) return (
    <Screen edges={[]}>
      {contextError ? (
        <>
          <ErrorText error={contextError} />
          <Button label="Réessayer" onPress={reloadCtx} />
        </>
      ) : <T muted>Chargement de l’événement…</T>}
    </Screen>
  );

  const d = draft;
  const set = (patch: Partial<Draft>) => setDraft({ ...d, ...patch });
  const toggleIn = <K extends 'tag_ids' | 'organizers'>(key: K, v: Draft[K][number]) => {
    const list = d[key] as string[];
    set({ [key]: list.includes(v) ? list.filter((x) => x !== v) : [...list, v] } as Partial<Draft>);
  };
  const setPoll = (i: number, patch: Partial<PollDraft>) => set({ polls: d.polls.map((p, j) => (j === i ? { ...p, ...patch } : p)) });

  async function createTag() {
    const name = newTag.trim().replace(/^#/, '').toLowerCase();
    if (!name) return;
    const { data, error } = await supabase.from('tags').insert({ name, created_by: me.id }).select('id').single();
    if (error) return setError(error.message.includes('duplicate') ? 'Ce tag existe déjà' : friendlyError(dbMessage(error.message, error.message)));
    setNewTag('');
    await reloadCtx();
    set({ tag_ids: [...d.tag_ids, data.id] });
  }

  function validate(): { row: Record<string, unknown>; slots: { id?: string; iso: string }[] } | string {
    if (!d.title.trim()) return 'Il manque un titre';
    const errors: string[] = [];
    const date = (v: string, label: string, required = false): string | null => {
      if (!v.trim()) {
        if (required) errors.push(`${label} : obligatoire`);
        return null;
      }
      const iso = parseLocalDateTime(v);
      if (!iso) errors.push(`${label} : format attendu JJ.MM.AAAA HH:MM`);
      return iso;
    };
    const starts = d.date_mode === 'fixed' ? date(d.starts_at, 'Début', true) : null;
    const ends = d.date_mode === 'fixed' ? date(d.ends_at, 'Fin') : null;
    const deadline = d.date_mode === 'poll' ? date(d.poll_deadline, 'Fin du vote') : null;
    const rsvpDeadline = date(d.rsvp_deadline, 'Date limite de réponse');
    if (errors.length) return errors[0]!;
    if (starts && ends && ends <= starts) return 'La fin doit être après le début';
    if (starts && ends && ends < starts) return 'La fin est avant le début';
    if (d.date_mode === 'fixed' && d.repeat.frequency !== 'none' && d.repeat.until.trim()) {
      const until = untilDate(d.repeat.until);
      if (!until) return 'Répétition : date de fin attendue JJ.MM.AAAA';
      if (starts && until < starts.slice(0, 10)) return 'La répétition doit finir après la première date';
    }

    const slots: { id?: string; iso: string }[] = [];
    if (d.date_mode === 'poll') {
      for (const sl of d.slots.filter((x) => x.text.trim())) {
        const iso = parseLocalDateTime(sl.text);
        if (!iso) return `Créneau « ${sl.text} » : format attendu JJ.MM.AAAA HH:MM`;
        slots.push({ id: sl.id, iso });
      }
      if (slots.length < 2 && !d.members_can_propose_dates) return 'Propose au moins deux créneaux';
    }
    // Dates incohérentes (brouillon comme publication) : début passé, date limite après le début, vote après les créneaux.
    const datesWrong = dateProblem({
      now: Date.now(), starts, rsvpDeadline, pollDeadline: deadline,
      slots: slots.map((sl) => ({ iso: sl.iso, isNew: !sl.id })),
      startsChanged: !eventId || d.starts_at !== initial?.starts_at,
    });
    if (datesWrong) return datesWrong;
    const num = (v: string) => (v.trim() ? Number(v.replace(',', '.')) : null);
    // Jamais corrigé en silence : la phrase dit ce qui ne va pas (accompagnants, prix, places).
    const amountWrong = placesProblem(d.max_participants) ?? priceProblem(d.price_chf)
      ?? (d.allow_plus_ones ? plusOnesProblem(d.max_plus_ones, UNLIMITED_PLUS_ONES - 1) : null);
    if (amountWrong) return amountWrong;
    const max = num(d.max_participants);
    const price = num(d.price_chf);
    const plusMax = d.max_plus_ones.trim();
    const maxPlusOnes = plusMax && !plusOnesProblem(plusMax, UNLIMITED_PLUS_ONES - 1) ? Number(plusMax) : UNLIMITED_PLUS_ONES;
    if (d.location_url.trim()) {
      try {
        const url = new URL(d.location_url.trim());
        if (!['https:', 'http:'].includes(url.protocol)) return 'Le lien doit commencer par https:// ou http://';
      } catch {
        return 'Le lien doit être une adresse complète (ex. https://…)';
      }
    }
    // Paiement (maquette du 15.11) : « en ligne » exige un lien ; tout lien de paiement est une adresse https complète.
    const paid = (price ?? 0) > 0;
    const payLink = paid && d.payment_mode !== 'on_site' ? d.payment_url.trim() : '';
    if (paid && d.payment_mode === 'online' && !payLink) return 'Paiement en ligne : ajoute le lien (billetterie, Revolut…)';
    if (payLink) {
      try {
        if (new URL(payLink).protocol !== 'https:') return 'Le lien de paiement doit commencer par https://';
        if (/\s/.test(payLink)) return 'Le lien de paiement ne doit pas contenir d’espace';
      } catch {
        return 'Le lien de paiement doit être une adresse complète (ex. https://revolut.me/…)';
      }
    }
    const audienceProblem = audienceError(d.who);
    if (audienceProblem) return audienceProblem;
    for (const p of d.polls) {
      if (!p.question.trim()) return 'Un sondage n’a pas de question';
      if (p.options.filter((o) => o.label.trim()).length < 2 && !p.members_can_add_options) return `« ${p.question} » : au moins deux options`;
    }

    return {
      slots,
      row: {
        title: d.title.trim(),
        description: d.description.trim(),
        category_id: d.category_id,
        date_mode: d.date_mode,
        starts_at: d.date_mode === 'fixed' ? starts : null,
        ends_at: d.date_mode === 'fixed' ? ends : null,
        poll_deadline: deadline,
        members_can_propose_dates: d.members_can_propose_dates,
        auto_fix_date: d.auto_fix_date,
        location_name: d.location_name.trim() || null,
        location_address: d.location_address.trim() || null,
        location_url: d.location_url.trim() || null,
        price_chf: price,
        // Gratuit : la précision du paiement (cachée dans le formulaire) ne reste pas sous « Gratuit » sur la fiche.
        payment_info: paid ? d.payment_info.trim() || null : null,
        payment_mode: paid ? d.payment_mode : 'organizer',
        payment_url: payLink || null,
        payment_open: paid && d.payment_mode !== 'on_site' ? d.payment_open : true,
        payment_open_notify: d.payment_notify,
        max_participants: max,
        waitlist_enabled: d.waitlist_enabled,
        allow_plus_ones: d.allow_plus_ones,
        max_plus_ones: maxPlusOnes,
        allow_maybe: d.allow_maybe,
        rsvp_deadline: rsvpDeadline,
        ...audienceToEvent(d.who),
        show_participants: d.show_participants,
        pot_enabled: d.pot_enabled,
        carpool_enabled: d.carpool_enabled,
        tickets_enabled: d.tickets_enabled,
        // Réglés par l'organisation (garde souvenirs_guard) ; jamais écrits tant qu'on n'y a pas touché (base d'avant).
        ...(souvenirsOn && (d.souvenirs_enabled || d.souvenirs_was) ? { souvenirs_enabled: d.souvenirs_enabled, souvenirs_keep: d.souvenirs_keep } : {}),
        forum_enabled: d.forum_enabled,
        // Public : jamais d'annonce (la base l'impose aussi, migration 20261106200000).
        notify_on_publish: d.who.audience === 'public' ? false : d.notify_on_publish,
        // « Prévenir le groupe » : jamais pour un public ; la base fait valider la demande (migration 20261106220000).
        announce_group: hasGroupAudience(d.who) && d.announce_group,
        reminders: ALL_REMINDERS,
      },
    };
  }

  async function syncChildren(id: string, slots: { id?: string; iso: string }[], snapshot: Draft, prev: Draft | null) {
    const d = snapshot;
    // Tags, organisateurs, invités : on remplace l'ensemble
    const replace = async (table: string, col: string, values: string[]) => {
      check(await supabase.from(table).delete().eq('event_id', id));
      if (values.length) check(await supabase.from(table).insert(values.map((v) => ({ event_id: id, [col]: v }))));
    };
    await replace('event_tags', 'tag_id', d.tag_ids);
    // Co-organisateurs : jamais sa propre ligne. Un co-organisateur (pas le créateur) qui enregistre se retirait
    // lui-même, puis la base (RLS « gérer organisateurs ») refusait de réinscrire les autres : plus personne.
    check(await supabase.from('event_organizers').delete().eq('event_id', id).neq('user_id', me.id));
    const helpers = d.organizers.filter((u) => u !== me.id);
    if (helpers.length) check(await supabase.from('event_organizers').insert(helpers.map((user_id) => ({ event_id: id, user_id }))));
    // Invités : la base recopie les membres des groupes (via_group) ; ici seulement les groupes et les invités cochés un par un.
    await saveAudience(id, d.who);

    // Créneaux : on garde les votes des créneaux existants
    if (d.date_mode === 'poll') {
      const keep = new Set(slots.filter((x) => x.id).map((x) => x.id!));
      const removed = (prev?.slots ?? []).filter((x) => x.id && !keep.has(x.id)).map((x) => x.id!);
      if (removed.length) check(await supabase.from('date_options').delete().in('id', removed));
      for (const sl of slots.filter((x) => x.id)) check(await supabase.from('date_options').update({ starts_at: sl.iso }).eq('id', sl.id!));
      const nonEmptySlots = d.slots.filter((sl) => sl.text.trim());
      for (const [index, sl] of slots.entries()) {
        if (sl.id) continue;
        const created = must(await supabase.from('date_options').insert({ event_id: id, starts_at: sl.iso, proposed_by: me.id }).select('id').single());
        nonEmptySlots[index]!.id = created.id as string;
      }
    }
    // Date fixe : les créneaux du sondage et leurs votes sont GARDÉS (cachés). Les effacer ici a perdu tous les votes du
    // paintball (prod, 13.11.2026 : date fixée par erreur puis événement modifié) ; repasser en « Sondage » les retrouve.

    // Sondages : suppression des retirés, ajout des nouveaux (les existants gardent leurs votes)
    const keptPolls = new Set(d.polls.filter((p) => p.id).map((p) => p.id!));
    const removedPolls = (prev?.polls ?? []).filter((p) => p.id && !keptPolls.has(p.id)).map((p) => p.id!);
    if (removedPolls.length) check(await supabase.from('polls').delete().in('id', removedPolls));
    for (const [i, p] of d.polls.entries()) {
      const row = {
        question: p.question.trim(), multiple_choice: p.multiple_choice, anonymous: p.anonymous,
        members_can_add_options: p.members_can_add_options, results_after_vote: p.results_after_vote, sort: i,
      };
      let pollId = p.id;
      if (pollId) {
        check(await supabase.from('polls').update(row).eq('id', pollId).eq('event_id', id));
        const previous = prev?.polls.find((poll) => poll.id === pollId);
        const keptOptions = new Set(p.options.filter((o) => o.label.trim()).map((o) => o.id));
        const removedOptions = (previous?.options ?? []).filter((o) => o.id && !keptOptions.has(o.id)).map((o) => o.id!);
        if (removedOptions.length) check(await supabase.from('poll_options').delete().eq('poll_id', pollId).in('id', removedOptions));
      } else {
        pollId = must(await supabase.from('polls').insert({ ...row, event_id: id, created_by: me.id }).select('id').single()).id as string;
        p.id = pollId;
      }
      for (const [sort, option] of p.options.filter((o) => o.label.trim()).entries()) {
        if (option.id) {
          check(await supabase.from('poll_options').update({ label: option.label.trim(), sort }).eq('id', option.id).eq('poll_id', pollId));
        } else {
          const created = must(await supabase.from('poll_options').insert({ poll_id: pollId, label: option.label.trim(), created_by: me.id, sort }).select('id').single());
          option.id = created.id as string;
        }
      }
    }

    // Qui amène quoi
    const keptItems = new Set(d.bring.filter((b) => b.id).map((b) => b.id!));
    const removedItems = (prev?.bring ?? []).filter((b) => b.id && !keptItems.has(b.id)).map((b) => b.id!);
    if (removedItems.length) check(await supabase.from('bring_items').delete().in('id', removedItems));
    for (const [sort, item] of d.bring.entries()) {
      if (item.id) check(await supabase.from('bring_items').update({ label: item.label.trim(), sort, quantity: bringQuantity(item.quantity) }).eq('id', item.id).eq('event_id', id));
    }
    for (const [sort, item] of d.bring.entries()) {
      if (item.id || !item.label.trim()) continue;
      const created = must(await supabase.from('bring_items').insert({ event_id: id, label: item.label.trim(), sort, quantity: bringQuantity(item.quantity) }).select('id').single());
      item.id = created.id as string;
    }
  }

  async function submit(asDraft: boolean) {
    // La garde AVANT toute attente (CGU comprises) : un double toucher ne crée jamais deux événements.
    if (saving.current) return;
    saving.current = true;
    setError(null);
    try {
      let run = inflight.current;
      if (!run) {
        const v = validate();
        if (typeof v === 'string') return setError(v);
        if (!savedEventId.current && !terms.accepted && !(await terms.ensure())) return setError(termsLater('publier ton événement'));
        run = save(v, asDraft).finally(() => { inflight.current = null; });
        inflight.current = run;
      }
      setBusy(true);
      // Base lente (recette iPhone du 28.11 : « Publier » tournait sans fin) : au bout de 20 s, on rend la main et on le dit.
      let timer: ReturnType<typeof setTimeout> | undefined;
      const late = await Promise.race([
        run.then(() => false),
        new Promise<boolean>((done) => { timer = setTimeout(() => done(true), PUBLISH_LIMIT_MS); }),
      ]);
      clearTimeout(timer);
      if (late) {
        setOrphan(orphanDraft.current);
        setError(SLOW_PUBLISH);
      }
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  async function save(v: Exclude<ReturnType<typeof validate>, string>, asDraft: boolean) {
    // Travailler sur une copie : conserver les identifiants reçus même en cas d'échec partiel.
    const snapshot = JSON.parse(JSON.stringify(d)) as Draft;
    let createdNow = false;
    try {
      let id = savedEventId.current;
      const previous = id ? await loadDraft(id) : null;
      // Avant toute écriture : une quantité ne descend pas sous ce que les invités ont déjà promis (sinon
      // l'enregistrement s'arrêterait à moitié, l'événement modifié mais pas « qui amène quoi »).
      const short = await bringBelowPromised(snapshot.bring);
      if (short) throw new Error(short);
      if (!id) {
        // Créé en brouillon pour attacher tags/sondages AVANT la publication (et donc les notifications).
        // Un échec plus loin : le nouvel essai reprend CE brouillon (savedEventId), jamais un second.
        id = must(await supabase.from('events').insert({ ...v.row, status: 'draft' }).select('id').single()).id as string;
        savedEventId.current = id;
        createdNow = true;
      } else {
        check(await supabase.from('events').update(v.row).eq('id', id));
      }
      if (createdNow && !asDraft) orphanDraft.current = id;
      await syncChildren(id, v.slots, snapshot, previous);
      // Répétition : seulement si elle change (ou la date de la série) ; elle repart de CET événement.
      const repeat = snapshot.date_mode === 'fixed' ? snapshot.repeat : NO_REPEAT;
      const before = previous?.repeat ?? NO_REPEAT;
      if (canRepeat && (JSON.stringify(repeat) !== JSON.stringify(before) || (repeat.frequency !== 'none' && snapshot.starts_at !== previous?.starts_at))) {
        check(await supabase.rpc('set_event_recurrence', {
          e: id, frequency: repeat.frequency, every: repeat.every, until: untilDate(repeat.until),
        }));
      }
      const status = ctx!.status;
      const needsSubmit = !eventId || status === 'draft' || status === 'rejected';
      let published = status === 'published';
      if (needsSubmit && !asDraft) {
        // La base décide (guard_event) : réservé à ses groupes, il est publié même sans « publier sans validation ».
        const saved = await supabase.from('events').update({ status: isAdmin ? 'published' : 'pending' }).eq('id', id).select('status');
        check(saved);
        published = ((saved.data?.[0] as { status?: string } | undefined)?.status ?? (isAdmin ? 'published' : 'pending')) === 'published';
      }
      if (eventId) notifyWallet(id);  // titre, date, lieu : les billets déjà dans Cartes se mettent à jour
      orphanDraft.current = null;
      setOrphan(null);
      // Nouvel événement « Sur invitation » (sans groupe), invitations v2 : la fiche ouvre aussitôt la feuille « Inviter »,
      // lien prêt, comme l'étape 2 de « Créer avec l'IA » (recette réelle du 10.11.2026).
      const invitedOnly = snapshot.who.audience === 'invite' && !snapshot.who.vip && !snapshot.who.group_ids.length;
      setDoneAt(!eventId && !asDraft && invitedOnly ? afterPublish(id, 'invite', published, [], invitesV2On) : `/event/${id}`);
    } catch (e) {
      // Filtre de la base (titre, description) ou CGU : sa phrase, sans la clé technique (« content_refused: … »).
      const message = e instanceof Error ? e.message : String(e);
      // Toutes les écritures (sondages, choix, objets compris) : clé retirée, puis phrase claire si c'est technique.
      const text = friendlyError(dbMessage(message, message));
      // Brouillon créé puis étape ratée : on le dit (le nouvel essai le reprend ; « Abandonner » le supprime).
      setOrphan(orphanDraft.current);
      setError(orphanDraft.current && !asDraft
        ? `L’événement n’est pas encore publié : ${text.replace(/[.!]?\s*$/, '.')} Touche à nouveau le bouton pour réessayer (le même brouillon est repris).`
        : text);
    } finally {
      setDraft(snapshot);
    }
  }

  const memberChips = (key: 'organizers') => {
    // Co-organisateurs : comptes qui peuvent modifier, parmi les personnes avec qui on a un lien (déjà choisis : gardés
    // visibles pour pouvoir les retirer).
    const people = ctx.members.filter((m) => m.id !== me.id
      && ((ctx.editors.has(m.role ?? '') && (!ctx.linked || ctx.linked.has(m.id))) || d[key].includes(m.id)));
    if (!people.length) {
      return <T muted size={13}>Personne à proposer pour l’instant : les co-organisateurs se choisissent parmi les membres de tes groupes et de tes soirées qui ont le droit d’organiser.</T>;
    }
    return (
      <View style={s.wrap}>
        {people.map((m) => (
          <Chip key={m.id} label={m.display_name} selected={d[key].includes(m.id)} onPress={() => toggleIn(key, m.id)} />
        ))}
      </View>
    );
  };

  // Publier n'a lieu que pour un nouvel événement, un brouillon ou un refusé (needsSubmit) : ailleurs (publié, en
  // attente de validation, annulé), le bouton enregistre seulement et le dit.
  // Groupes libres (22.11) : réservé à ses groupes (sans Membres Vendredi Party), jamais de validation du site.
  const onlyGroups = (w: AudienceValue) => w.audience === 'invite' && !w.vip && w.group_ids.length > 0;
  const siteReview = !isAdmin && ctx.settings.require_approval && !onlyGroups(d.who);
  // Publié sur invitation ou pour ses groupes, puis élargi (public, Membres Vendredi Party) : repasse par la validation.
  const widened = siteReview && !!eventId && ctx.status === 'published' && !!initial
    && initial.who.audience === 'invite' && !initial.who.vip && (d.who.audience === 'public' || d.who.vip);
  // Créateur sans « Modifier ses événements déjà publiés » (22.11) : il modifie, l'événement repasse en validation.
  const revalidate = siteReview && !widened && !!eventId && ctx.status === 'published' && ctx.createdBy === me.id
    && !can('events.edit_own_published');
  // Réservé à ses groupes : un groupe « Événements à valider » qu'il ne gère pas valide la création (prévenu avant,
  // recette iPhone du 22.11) et revalide la modification.
  const groupEdit = !!eventId && ctx.status === 'published';
  const recheckGroups = (groupEdit || !eventId || ['draft', 'rejected'].includes(ctx.status ?? '')) && onlyGroups(d.who)
    ? ctx.groups.filter((g) => d.who.group_ids.includes(g.id) && g.events_need_approval && g.created_by !== me.id) : [];
  const submitLabel = eventId && !['draft', 'rejected'].includes(ctx.status ?? '')
    ? 'Enregistrer'
    : siteReview ? 'Envoyer pour validation' : 'Publier';

  // Un sondage de dates n’existe qu’en avancé : on n’en cache jamais les créneaux.
  const advanced = mode === 'advanced' || d.date_mode === 'poll';
  const hiddenActive = advanced ? [] : activeAdvanced(d);

  return (
    <Screen edges={[]}>
      {/* « Annuler » plutôt que le titre (parfois long) de l'événement, qui chevauchait « Modifier » ; la garde
          « Abandonner les changements ? » s'applique aussi à ce bouton. */}
      {/* Nouvel événement : chevron seul (le titre « Proposer un événement » est long, le libellé le chevauchait). */}
      <Stack.Screen options={{ headerLeft: () => <HeaderBack label="Annuler" iconOnly={!eventId} onPress={cancel} /> }} />
      <View pointerEvents={busy ? 'none' : 'auto'} style={{ gap: 14 }}>
      {/* Ouverture en cascade ; en passant en Avancé, les sections ajoutées montent à leur tour. */}
      <Cascade>
      <View style={{ gap: 6 }}>
        <Segmented<FormMode>
          value={advanced ? 'advanced' : 'simple'}
          onChange={setMode}
          disabled={d.date_mode === 'poll'}
          options={[{ key: 'simple', label: 'Simple' }, { key: 'advanced', label: 'Avancé' }]}
        />
        <T key={advanced ? 'advanced' : 'simple'} muted size={12} style={[{ paddingHorizontal: 4 }, enter('fade')]}>
          {advanced
            ? 'Toutes les options : places, prix, sondages, discussion…'
            : 'L’essentiel pour lancer l’événement. Le reste garde ses réglages habituels.'}
        </T>
      </View>

      {!eventId && isAdmin ? (
        <TemplateList meId={me.id} canDeleteAll={can('events.manage_all')}
          onApply={(t) => setDraft(applyTemplate(d as unknown as Record<string, unknown>, t.data) as unknown as Draft)} />
      ) : null}

      <Section title="L’essentiel">
        {/* Couverture (25.11) : changée tout de suite par le serveur, jamais par l'enregistrement du formulaire. */}
        {eventId && ctx.cover && coversOn ? (
          <EventCover eventId={eventId} url={ctx.cover.cover_url} credit={ctx.cover.cover_credit} creditUrl={ctx.cover.cover_credit_url}
            canEdit onChanged={reloadCtx} />
        ) : null}
        <Field label="Titre" value={d.title} onChangeText={(title) => set({ title })} maxLength={120} placeholder="Karting, soirée raclette…" />
        <Field label="Description" value={d.description} onChangeText={(description) => set({ description })} multiline />
        <T muted size={13} weight="medium">Catégorie</T>
        <View style={s.wrap}>
          {ctx.categories.map((c) => (
            <Chip
              key={c.id}
              label={c.name}
              color={c.color}
              selected={d.category_id === c.id}
              onPress={() => set({ category_id: d.category_id === c.id ? null : c.id })}
            />
          ))}
        </View>
        {advanced ? (
          <>
            <T muted size={13} weight="medium">Tags</T>
            <View style={s.wrap}>
              {ctx.tags.map((t) => (
                <Chip key={t.id} label={`#${t.name}`} color={t.color} selected={d.tag_ids.includes(t.id)} onPress={() => toggleIn('tag_ids', t.id)} />
              ))}
            </View>
            {can('taxonomy.manage') ? (
              <View style={s.row}>
                <Input placeholder="Nouveau tag" value={newTag} onChangeText={setNewTag} style={{ flex: 1 }} onSubmitEditing={createTag} />
                <Button small variant="secondary" label="Créer" onPress={createTag} disabled={!newTag.trim()} />
              </View>
            ) : null}
          </>
        ) : null}
      </Section>

      <Section title="Quand">
        {advanced ? (
          <Segmented<DateMode>
            value={d.date_mode}
            onChange={(date_mode) => set({ date_mode })}
            options={[{ key: 'fixed', label: 'Date fixée' }, { key: 'poll', label: 'Date à définir' }]}
          />
        ) : null}
        {d.date_mode === 'fixed' ? (
          <>
            <DateTimeField label="Début" value={d.starts_at} onChangeText={(starts_at) => set({ starts_at })} />
            <DateTimeField label="Fin (optionnel)" optional min={d.starts_at} value={d.ends_at} onChangeText={(ends_at) => set({ ends_at })} />
            {/* Événements récurrents : droit events.recurring (Admin, Co-admin, Organisateur ; précision du 16.11). */}
            {canRepeat ? (<>
            <T muted size={13} weight="medium">Répéter</T>
            <View style={s.wrap} accessibilityRole="radiogroup" accessibilityLabel="Répéter">
              {REPEAT_CHOICES.map((c) => (
                <Chip key={c.label} label={c.label}
                  selected={d.repeat.frequency === c.frequency && (c.frequency === 'none' || d.repeat.every === c.every)}
                  onPress={() => set({ repeat: { ...d.repeat, frequency: c.frequency, every: c.every } })} />
              ))}
            </View>
            {d.repeat.frequency !== 'none' ? (
              <>
                <T size={13} color={colors.textSoft}>
                  🔁 {repeatLabel({ ...d.repeat, until: untilDate(d.repeat.until) }, parseLocalDateTime(d.starts_at))}. Une seule date à la fois : la suivante
                  s’affiche quand celle-ci est terminée, avec les mêmes réglages et les mêmes invités (sans leurs réponses).
                </T>
                <DateTimeField label="Jusqu’au (facultatif)" optional min={d.starts_at} value={d.repeat.until}
                  onChangeText={(until) => set({ repeat: { ...d.repeat, until } })} />
              </>
            ) : null}
            </>) : d.repeat.frequency !== 'none' ? (
              <T size={13} color={colors.textSoft}>🔁 {repeatLabel({ ...d.repeat, until: untilDate(d.repeat.until) }, parseLocalDateTime(d.starts_at))}</T>
            ) : null}
          </>
        ) : (
          <>
            <T muted size={12}>Chacun vote Oui / Si besoin / Non sur chaque créneau.</T>
            {d.slots.map((sl, i) => (
              <Reveal key={sl.id ?? `new-${i}`} kind={slotsGrew ? 'rise' : null} style={[s.row, { alignItems: 'flex-end', flexWrap: 'wrap' }]}>
                {/* La question « Retirer et ses votes » passe dessous au lieu d'écraser le champ (recette de nuit du 28.11). */}
                <View style={{ flexGrow: 1, flexBasis: 220 }}>
                  <DateTimeField label={`Créneau ${i + 1}`} value={sl.text} onChangeText={(text) => set({ slots: d.slots.map((x, j) => (j === i ? { ...x, text } : x)) })} />
                </View>
                {/* Créneau enregistré : l'enregistrement efface aussi ses votes, on confirme (comme les sondages, contrôle du 27.11). */}
                {sl.id
                  ? <ConfirmButton small label="✕" confirmLabel="Retirer et ses votes" accessibilityLabel={`Retirer le créneau ${i + 1}`}
                      onConfirm={() => set({ slots: d.slots.filter((_, j) => j !== i) })} />
                  : <Button small variant="secondary" label="✕" accessibilityLabel={`Retirer le créneau ${i + 1}`}
                      onPress={() => set({ slots: d.slots.filter((_, j) => j !== i) })} />}
              </Reveal>
            ))}
            <Button small variant="ghost" label="+ Ajouter un créneau" onPress={() => set({ slots: [...d.slots, { text: '' }] })} />
            <DateTimeField label="Fin du vote (optionnel)" optional value={d.poll_deadline} onChangeText={(poll_deadline) => set({ poll_deadline })} />
            <Rows>
              <ToggleRow label="Les membres peuvent proposer des dates" value={d.members_can_propose_dates} onChange={(v) => set({ members_can_propose_dates: v })} />
              <ToggleRow
                label="Fixer la date automatiquement"
                hint="À la fin du vote, la date avec le plus de Oui est retenue"
                value={d.auto_fix_date}
                onChange={(v) => set({ auto_fix_date: v })}
              />
            </Rows>
          </>
        )}
      </Section>

      <Section title={advanced ? 'Lieu et prix' : 'Où'}>
        <PlaceSearch typed={d.location_name} onPick={(p) => set({ location_name: p.name, location_address: p.address, location_url: p.url })} />
        <Field label="Lieu" placeholder="Chez Marco" value={d.location_name} onChangeText={(location_name) => set({ location_name })} />
        {advanced ? (
          <>
            <Field label="Adresse" value={d.location_address} onChangeText={(location_address) => set({ location_address })} />
            <Field label="Lien (site, carte…)" autoCapitalize="none" keyboardType="url" value={d.location_url} onChangeText={(location_url) => set({ location_url })} />
            <Field label="Prix / pers. (CHF)" keyboardType="decimal-pad" value={d.price_chf} onChangeText={(price_chf) => set({ price_chf })} />
            {Number(d.price_chf.replace(',', '.')) > 0 ? <PaymentChoice d={d} set={set} /> : null}
            <ToggleRow
              label="Billets QR"
              hint="Tu remets son billet à chaque présent (ou il arrive avec la place payée) ; il le montre à l’entrée. Modifiable à tout moment."
              value={d.tickets_enabled}
              onChange={(v) => set({ tickets_enabled: v })}
            />
          </>
        ) : null}
      </Section>

      <Section title={advanced ? 'Participants' : 'Qui'}>
        <AudiencePicker value={d.who} onChange={(who) => set({ who })} groups={ctx.groups} people={ctx.members} meId={me.id} allGroups={can('events.manage_all')} />
        {hasGroupAudience(d.who) ? (
          <AnnounceToggle groupIds={d.who.group_ids} vip={d.who.vip} value={d.announce_group} onChange={(announce_group) => set({ announce_group })}
            label={d.who.vip && !d.who.group_ids.length ? 'Prévenir les Membres Vendredi Party' : 'Prévenir le groupe'} />
        ) : null}
        {advanced ? (
          <>
            <Button small variant="ghost" label="Gérer les groupes ›" onPress={() => router.push('/groups')} />
            <Field
              label="Nombre de places (vide = illimité)"
              keyboardType="number-pad"
              value={d.max_participants}
              onChangeText={(max_participants) => set({ max_participants })}
            />
            <Rows>
              {d.max_participants ? (
                <ToggleRow label="Liste d’attente" hint="Les suivants passent automatiquement quand une place se libère" value={d.waitlist_enabled} onChange={(v) => set({ waitlist_enabled: v })} />
              ) : null}
              <ToggleRow label="Réponse « Peut-être » autorisée" value={d.allow_maybe} onChange={(v) => set({ allow_maybe: v })} />
              <ToggleRow label="Accompagnants (+1)" value={d.allow_plus_ones} onChange={(v) => set({ allow_plus_ones: v })} />
              <ToggleRow label="Liste des participants visible" value={d.show_participants} onChange={(v) => set({ show_participants: v })} />
            </Rows>
            {d.allow_plus_ones ? (
              <Field label="Accompagnants max par personne (vide = illimité)" keyboardType="number-pad" value={d.max_plus_ones} onChangeText={(max_plus_ones) => set({ max_plus_ones })} />
            ) : null}
            <DateTimeField label="Date limite de réponse (optionnel)" optional value={d.rsvp_deadline} onChangeText={(rsvp_deadline) => set({ rsvp_deadline })} />
            <T muted size={13} weight="medium">Co-organisateurs</T>
            {memberChips('organizers')}
          </>
        ) : null}
        <Rows>
          <ToggleRow label="Pot commun" hint="Qui répond Présent y entre tout seul (la fiche le lui dit) et voit les noms des autres membres ; les moyens de paiement seulement de qui les montre ; tout est dans Réglages › Pot commun" value={d.pot_enabled} onChange={(v) => set({ pot_enabled: v })} />
          <ToggleRow label="Covoiturage" hint="Les participants proposent leurs places ou en cherchent une, ville de départ en option" value={d.carpool_enabled} onChange={(v) => set({ carpool_enabled: v })} />
        </Rows>
        {souvenirsOn ? <SouvenirsSettings enabled={d.souvenirs_enabled} keep={d.souvenirs_keep} locked={d.souvenirs_locked} onChange={set} /> : null}
      </Section>

      {advanced ? (
        <View style={{ gap: 14 }}>
          {can('polls.create') || d.polls.length ? (
          <Section title="Mini-sondages">
            {d.polls.map((p, i) => (
              <Reveal key={p.id ?? `new-${i}`} kind={pollsGrew ? 'rise' : null} style={{ gap: 12, paddingVertical: 12, borderTopWidth: i ? 1 : 0, borderTopColor: colors.line }}>
                <Field label={`Question du sondage ${i + 1}`} value={p.question} onChangeText={(question) => setPoll(i, { question })} maxLength={200} />
                {p.options.map((o, j) => (
                  <Reveal key={o.id ?? `new-${j}`} kind={pollsGrew ? 'rise' : null} style={s.row}>
                    <Input
                      accessibilityLabel={`Sondage ${i + 1}, option ${j + 1}`}
                      placeholder={`Option ${j + 1}`}
                      value={o.label}
                      onChangeText={(label) => setPoll(i, { options: p.options.map((x, k) => (k === j ? { ...x, label } : x)) })}
                      maxLength={120}
                      style={{ flex: 1 }}
                    />
                    {p.id
                      ? <ConfirmButton small label="Retirer" confirmLabel="Retirer et ses votes" onConfirm={() => setPoll(i, { options: p.options.filter((_, k) => k !== j) })} />
                      : <Button small variant="ghost" label="Retirer" onPress={() => setPoll(i, { options: p.options.filter((_, k) => k !== j) })} />}
                  </Reveal>
                ))}
                {p.id ? <T muted size={13}>Les votes des options conservées restent enregistrés. Retirer une option supprime ses votes.</T> : null}
                <Button small variant="ghost" label="+ Ajouter une option" onPress={() => setPoll(i, { options: [...p.options, { label: '' }] })} />
                <View style={s.wrap}>
                  <Chip label="Choix multiple" selected={p.multiple_choice} onPress={() => setPoll(i, { multiple_choice: !p.multiple_choice })} />
                  <Chip label="Anonyme" selected={p.anonymous} onPress={() => setPoll(i, { anonymous: !p.anonymous })} />
                  <Chip label="Options libres" selected={p.members_can_add_options} onPress={() => setPoll(i, { members_can_add_options: !p.members_can_add_options })} />
                  <Chip label="Résultats après vote" selected={p.results_after_vote} onPress={() => setPoll(i, { results_after_vote: !p.results_after_vote })} />
                </View>
                {p.id
                  ? <ConfirmButton small label="Retirer ce sondage" confirmLabel="Retirer le sondage et ses votes" onConfirm={() => set({ polls: d.polls.filter((_, j) => j !== i) })} />
                  : <Button small variant="danger" label="Retirer ce sondage" onPress={() => set({ polls: d.polls.filter((_, j) => j !== i) })} />}
              </Reveal>
            ))}
            {/* Sans « Créer des sondages » (polls.create), la base refuse : le bouton n'est pas proposé. */}
            {can('polls.create') ? <Button
              small
              variant="ghost"
              label="+ Ajouter un sondage"
              onPress={() =>
                set({
                  polls: [...d.polls, { question: '', options: [{ label: '' }, { label: '' }], multiple_choice: false, anonymous: false, members_can_add_options: false, results_after_vote: false }],
                })
              }
            /> : null}
          </Section>
          ) : null}

          <Section title="Qui amène quoi">
            {d.bring.map((b, i) => (
              <Reveal key={b.id ?? `new-${i}`} kind={bringGrew ? 'rise' : null} style={s.row}>
                <Input
                  placeholder="Fromage, pain…"
                  accessibilityLabel={`Objet ${i + 1} à amener`}
                  value={b.label}
                  onChangeText={(label) => set({ bring: d.bring.map((x, j) => (j === i ? { ...x, label } : x)) })}
                  style={{ flex: 1 }}
                />
                <Input
                  placeholder="Qté"
                  accessibilityLabel={`Quantité de ${b.label || 'cet objet'} (plusieurs personnes peuvent se partager)`}
                  keyboardType="number-pad"
                  maxLength={3}
                  value={b.quantity ?? ''}
                  onChangeText={(quantity) => set({ bring: d.bring.map((x, j) => (j === i ? { ...x, quantity: quantity.replace(/\D/g, '') } : x)) })}
                  style={{ width: 64 }}
                />
                <Button small variant="secondary" label="✕" accessibilityLabel={`Retirer ${b.label || 'cet objet'}`}
                  onPress={() => set({ bring: d.bring.filter((_, j) => j !== i) })} />
              </Reveal>
            ))}
            <Button small variant="ghost" label="+ Ajouter un objet" onPress={() => set({ bring: [...d.bring, { label: '' }] })} />
          </Section>

          <Section title="Discussion et annonce">
            <Rows>
              <ToggleRow label="Forum de l’événement" value={d.forum_enabled} onChange={(v) => set({ forum_enabled: v })} />
              {d.who.audience === 'public' || !(d.who.invitees.length || d.who.phones.length) ? null : (
                <ToggleRow label="Prévenir les personnes invitées une à une" value={d.notify_on_publish} onChange={(v) => set({ notify_on_publish: v })} />
              )}
            </Rows>
            <T muted size={13}>Les rappels avant l’événement, chacun les choisit dans ses Réglages → Notifications.</T>
          </Section>
        </View>
      ) : (
        // Mode simple : une porte vers le reste, qui dit aussi quels réglages avancés sont actifs.
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Plus d’options : passer en mode avancé"
          onPress={() => setMode('advanced')}
          style={({ pressed }) => [s.card, s.row, { gap: 12 }, pressTransition, pressed && { backgroundColor: colors.surface2, transform: [{ scale: 0.98 }] }]}
        >
          <View style={{ flex: 1, gap: 2 }}>
            <T weight="semibold">Plus d’options</T>
            <T muted size={13}>Passe en mode Avancé : places, prix, sondage de dates, qui amène quoi… s’ajoutent au formulaire.</T>
            {hiddenActive.length ? <T size={13} color={colors.accent}>Actifs : {hiddenActive.join(', ')}</T> : null}
          </View>
          <View style={{ width: 8, height: 8, borderRightWidth: 2, borderTopWidth: 2, borderColor: colors.muted, transform: [{ rotate: '45deg' }] }} />
        </Pressable>
      )}

      {siteReview && (!eventId || ctx.status !== 'published' || widened || revalidate) ? (
        <View style={{ backgroundColor: colors.lavenderDim, padding: 14, borderRadius: 16 }} testID="site-review">
          <T size={13} color={colors.textSoft}>
            {widened ? 'Élargi au public ou aux Membres Vendredi Party, l’événement repasse par la validation. ' : ''}
            {revalidate ? 'Une fois enregistrée, ta modification repasse en validation : l’événement reste invisible jusqu’à l’accord. ' : ''}
            {d.who.audience === 'public' ? PUBLIC_REVIEW
              : 'Un admin doit valider ta proposition. Il pourra modifier n’importe quel champ avant de la publier. S’il est réservé à un ou plusieurs de tes groupes, il est publié sans validation.'}
          </T>
        </View>
      ) : null}
      {recheckGroups.length ? (
        <View style={{ backgroundColor: colors.lavenderDim, padding: 14, borderRadius: 16 }} testID="group-recheck">
          <T size={13} color={colors.textSoft}>
            {recheckGroups.map((g) => `« ${g.name} »`).join(', ')} {recheckGroups.length > 1 ? 'font' : 'fait'} valider les événements de ses membres : {groupEdit
              ? 'une fois enregistrée, ta modification y repasse en validation (sauf si tu gères le groupe).'
              : 'ton événement y sera visible une fois accepté par qui gère le groupe.'}
          </T>
        </View>
      ) : null}
      {isAdmin ? <SaveAsTemplate data={() => templateData(d as unknown as Record<string, unknown>)} /> : null}
      <ErrorText error={error} />
      <Button label={submitLabel} onPress={() => submit(false)} loading={busy} />
      {!eventId || ctx.status === 'draft' ? (
        <Button label="Enregistrer en brouillon" variant="secondary" onPress={() => submit(true)} disabled={busy} />
      ) : null}
      </Cascade>
      </View>
      {terms.sheet}
      {leaveSheet}
    </Screen>
  );
}

const PAY_MODES: { key: PaymentMode; icon: string; label: string; hint: string }[] = [
  // Espaces insécables dans les guillemets : jamais un « seul en fin de ligne.
  { key: 'organizer', icon: '🙋', label: 'On me paie', hint: 'Revolut, Twint, virement. Chacun note « J’ai payé », tu confirmes chaque paiement reçu. Tes moyens de paiement (Réglages › Pot commun) seront montrés aux personnes qui viennent.' },
  { key: 'online', icon: '🔗', label: 'Paiement en ligne', hint: 'Billetterie ou site de paiement : chacun paie sur le site, rien à confirmer dans Party.' },
  { key: 'on_site', icon: '📍', label: 'Sur place', hint: 'Le jour J. Rien à suivre dans Party.' },
];

/** « Comment on paie ? » (maquette validée le 15.11.2026) : trois choix, le lien de paiement, une précision. */
function PaymentChoice({ d, set }: { d: Draft; set: (patch: Partial<Draft>) => void }) {
  return (
    <View style={{ gap: 8 }}>
      <T muted size={13}>Comment on paie ?</T>
      <View accessibilityRole="radiogroup" style={{ gap: 8 }}>
        {PAY_MODES.map((m) => {
          const on = d.payment_mode === m.key;
          return (
            <Pressable key={m.key} accessibilityRole="radio" accessibilityState={{ checked: on }} aria-checked={on} accessibilityLabel={`${m.label} : ${m.hint}`}
              onPress={() => set({ payment_mode: m.key })}
              style={({ pressed }) => [payStyle.choice, on && payStyle.on, pressTransition, pressed && { opacity: 0.85 }]}>
              <T size={18}>{m.icon}</T>
              <View style={{ flex: 1, gap: 2 }}>
                <T weight="semibold">{m.label}</T>
                <T muted size={12}>{m.hint}</T>
              </View>
            </Pressable>
          );
        })}
      </View>
      {d.payment_mode !== 'on_site' ? (
        <Field label={d.payment_mode === 'online' ? 'Lien de paiement' : 'Lien de paiement (facultatif)'} autoCapitalize="none" keyboardType="url"
          placeholder={d.payment_mode === 'online' ? 'https://billetterie…' : 'https://revolut.me/…'}
          value={d.payment_url} onChangeText={(payment_url) => set({ payment_url })} />
      ) : null}
      {d.payment_mode !== 'on_site' ? (
        <ToggleRow label="Paiement ouvert" value={d.payment_open} onChange={(payment_open) => set({ payment_open })}
          hint={d.payment_open ? 'Les invités voient le bouton pour payer.'
            : 'Tout est prêt, mais pas encore de bouton : les invités voient « Paiement bientôt possible ». Allume-le quand c’est bon.'} />
      ) : null}
      {d.payment_mode !== 'on_site' && (!d.payment_open || !d.payment_was_open) ? (
        <ToggleRow label="Prévenir les participants à l’ouverture" value={d.payment_notify} onChange={(payment_notify) => set({ payment_notify })}
          hint={!d.payment_notify ? 'Personne ne reçoit de notification : ils verront le bouton en ouvrant l’événement.'
            : d.payment_open ? 'À l’enregistrement, les « Présent » pas encore payés reçoivent « 💳 Le paiement est ouvert ».'
            : 'Quand tu allumeras « Paiement ouvert », les « Présent » pas encore payés recevront « 💳 Le paiement est ouvert ».'} />
      ) : null}
      <Field label="Précision (facultatif)" placeholder={d.payment_mode === 'on_site' ? 'Cash ou carte à l’accueil' : d.payment_mode === 'online' ? 'Choisis « Paintball 2 h »' : 'Twint ou Revolut, avant le jour J'}
        value={d.payment_info} onChangeText={(payment_info) => set({ payment_info })} />
    </View>
  );
}

const payStyle = {
  choice: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: radius.md, backgroundColor: colors.fill, borderWidth: 1, borderColor: 'transparent' },
  on: { borderColor: colors.accent, backgroundColor: colors.accentDim },
} as const;
