/**
 * Annonces d'un événement aux groupes (décision de l'admin du 06.11.2026 ; base : migration 20261106220000).
 * - « Prévenir le groupe » (events.announce_group) : éteint par défaut, absent pour un événement public.
 * - Un simple membre du groupe fait une DEMANDE : un admin du groupe accepte ou refuse ; sans réponse en 48 h, elle part.
 * - Créateur / admin / organisateur du groupe, ou groupe aux notifications « libres » : l'annonce part directement.
 */
import { check, must, supabase } from './supabase';
import { VIP_GROUP_KEY } from './types';

export type AnnounceMode = 'direct' | 'request';

/** Une demande « À valider » (annonce, ou événement proposé à un groupe qui demande une validation). */
export type GroupRequest = {
  kind: 'announce' | 'event';
  id: string;
  event_id: string;
  group_id: string;
  group: string;
  title: string;
  starts_at: string | null;
  all_day: boolean | null;
  date_mode: 'fixed' | 'poll';
  location_name: string | null;
  cover_url: string | null;
  description: string;
  organizer: string;
  requested_at: string;
  members: number;
  auto_at?: string;
  message_title?: string;
  message_body?: string;
  announce?: boolean;
};

/** Statut vu par l'organisateur, par groupe. */
export type AnnounceStatus = {
  group: string;
  status: 'pending' | 'accepted' | 'refused' | 'auto' | 'direct' | 'group_pending' | 'group_refused';
  answered_by: string | null;
  auto_at: string | null;
};

export type Answer = { status: string; already: boolean; answered_by?: string };

export async function fetchGroupRequests(): Promise<GroupRequest[]> {
  return (must(await supabase.rpc('my_group_requests')) ?? []) as GroupRequest[];
}

export async function answerRequest(r: GroupRequest, accept: boolean): Promise<Answer> {
  const res = r.kind === 'announce'
    ? await supabase.rpc('answer_announcement', { a: r.id, accept })
    : await supabase.rpc('answer_group_event', { e: r.event_id, g: r.group_id, accept });
  return must(res) as Answer;
}

/** Après une réponse : ce qui s'est passé, en une phrase (la première réponse gagne). */
export function answerSentence(r: GroupRequest, accept: boolean, a: Answer): string {
  if (a.already) {
    const who = a.answered_by && a.answered_by !== 'Quelqu’un' ? a.answered_by : 'Un autre admin';
    return `${who} a déjà répondu : rien n’a changé.`;
  }
  if (r.kind === 'event') {
    return accept ? `« ${r.title} » est maintenant visible par ${r.group}.` : `« ${r.title} » ne sera pas visible par ${r.group}.`;
  }
  return accept ? `C’est parti : ${r.group} est prévenu.` : `Refusé : ${r.group} n’est pas prévenu, l’événement reste visible.`;
}

export async function fetchAnnounceStatus(eventId: string): Promise<AnnounceStatus[]> {
  return (must(await supabase.rpc('event_announcement_status', { e: eventId })) ?? []) as AnnounceStatus[];
}

/** Pour chaque groupe (et Vendredi Party si vip) : l'annonce partira-t-elle directement ou sera-t-elle à valider ? */
export async function fetchAnnounceModes(groupIds: string[], vip = false): Promise<Record<string, AnnounceMode>> {
  const ids = [...groupIds];
  if (vip) {
    const row = must(await supabase.from('member_groups').select('id').eq('system_key', VIP_GROUP_KEY).maybeSingle()) as { id: string } | null;
    if (row) ids.push(row.id);
  }
  if (!ids.length) return {};
  return (must(await supabase.rpc('my_announce_modes', { groups: ids })) ?? {}) as Record<string, AnnounceMode>;
}

/** Allume « Prévenir le groupe » sur un événement déjà publié (la base ouvre la demande ou envoie). */
export async function turnOnAnnounce(eventId: string): Promise<void> {
  check(await supabase.from('events').update({ announce_group: true }).eq('id', eventId));
}

export async function setGroupRules(groupId: string, needApproval: boolean, mode: 'request' | 'free'): Promise<void> {
  check(await supabase.rpc('set_group_event_rules', { grp: groupId, need_approval: needApproval, mode }));
}

/** La phrase sous l'interrupteur « Prévenir le groupe ». modes : un par groupe choisi (direct ou à valider). */
export function announceSentence(on: boolean, modes: AnnounceMode[]): string {
  const asks = modes.some((m) => m === 'request');
  if (!on) return 'Le groupe voit l’événement dans Party, sans notification.';
  if (!asks) return 'Le groupe reçoit une notification dès la publication.';
  return 'Ta demande sera envoyée à l’admin du groupe ; sans réponse sous 48 h, l’annonce part automatiquement.';
}

/** Statut affiché à l'organisateur sur la fiche. */
export function statusLine(s: AnnounceStatus, when: (iso: string) => string): string {
  switch (s.status) {
    case 'pending': return `${s.group} · Annonce en attente${s.auto_at ? ` (part d’office ${when(s.auto_at)})` : ''}`;
    case 'accepted': return `${s.group} · Annonce envoyée${s.answered_by ? ` (acceptée par ${s.answered_by})` : ''}`;
    case 'auto': return `${s.group} · Annonce envoyée (sans réponse en 48 h)`;
    case 'direct': return `${s.group} · Annonce envoyée`;
    case 'refused': return `${s.group} · Annonce refusée${s.answered_by ? ` par ${s.answered_by}` : ''} : pas de notification, l’événement reste visible`;
    case 'group_pending': return `${s.group} · En attente de validation du groupe (invisible pour lui d’ici là)`;
    case 'group_refused': return `${s.group} · Refusé par le groupe${s.answered_by ? ` (${s.answered_by})` : ''} : invisible pour lui`;
    default: return s.group;
  }
}
