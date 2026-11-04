import { toQR } from 'toqr';

import { must, supabase } from './supabase';
import { notifyWallet } from './wallet';
import type { RsvpStatus } from './types';

/**
 * Billets QR d'un événement (migration 20261103130000) : la table est fermée, tout passe par des fonctions.
 * - le participant noté Présent lit son billet (my_event_ticket) ;
 * - l'organisateur, les co-organisateurs et les admins le scannent (check_in_ticket) et cochent « payé ».
 * Billets remis (migration 20261104233000) : le QR n'existe pour le participant que si l'option « Billets QR » de
 * l'événement est active ET que l'organisateur lui a remis son billet (ou confirmé sa place payée).
 */

/** Ce qu'il faut pour payer sa place, avec ou sans QR. */
export type TicketPayment = { plus_ones: number; paid: boolean; pay_pending: boolean; price_chf: number | null };

export type MyTicket =
  | { state: 'none' }
  | { state: 'waitlist' }
  /** off : option « Billets QR » éteinte ; pending : active, billet pas encore remis (jamais de jeton). */
  | ({ state: 'off' } & TicketPayment)
  | ({ state: 'pending' } & TicketPayment)
  | ({ state: 'ok'; token: string; code: string; checked_in_at: string | null } & TicketPayment);

/** Ce que l'organisateur voit d'une personne à l'entrée (jamais le jeton). */
export type TicketPerson = {
  user_id: string;
  display_name: string;
  avatar_url: string | null;
  status: RsvpStatus | null;
  waitlisted: boolean;
  plus_ones: number;
  checked_in_at: string | null;
  paid: boolean;
  /** « J'ai payé » touché par la personne, pas encore confirmé par l'organisateur. */
  pay_pending: boolean;
  pay_declared_at?: string | null;
  price_chf: number | null;
  /** Billet remis par l'organisateur (absent avant la migration 20261104233000). */
  issued?: boolean;
  /** Billet remis par la place payée (« Reçu », « payé ») : il repart si ce paiement est annulé (20261105120000). */
  issued_by_payment?: boolean;
  tickets_enabled?: boolean;
  /** Message pour l'organisateur après son geste (billet retiré avec le paiement) ; jamais venu de la base. */
  notice?: string;
};

export const TICKET_TAKEN_BACK = 'Billet retiré : il avait été remis par ce paiement. Remets-le à la main si la personne le garde.';

/** « Pas reçu » ou « payé » décoché : la base retire le billet remis par ce paiement ; on le dit à l'organisateur. */
function withPaymentNotice(before: TicketPerson | undefined, after: TicketPerson, cancelled: boolean): TicketPerson {
  const takenBack = cancelled && !!before?.issued && !!before.issued_by_payment && after.issued === false;
  return takenBack ? { ...after, notice: TICKET_TAKEN_BACK } : after;
}

/** Comment payer l'organisateur (profil de paiement du Pot commun / Tricount) ; null : gratuit ou pas présent. */
export type PayInfo = {
  organizer_id: string;
  organizer_name: string | null;
  amount: number;
  payment_info: string | null;
  iban: string | null;
  holder: string | null;
  links: Record<string, string>;
  note: string | null;
  reference: string;
};

export type ScanResult =
  | { result: 'ok' | 'already' | 'waitlist' | 'not_registered' | 'not_issued' | 'tickets_off'; person: TicketPerson }
  | { result: 'other_event'; event_title: string }
  | { result: 'unknown' };

const TOKEN = /^[0-9a-f]{64}$/i;
const CODE = /^[A-HJ-NP-Z2-9]{6}$/;

/**
 * Contenu du QR : un lien Party. Scanné avec l'appareil photo du téléphone (sans l'app), il ouvre directement
 * l'écran d'entrée de l'événement chez l'organisateur connecté.
 */
export function ticketLink(origin: string, eventId: string, token: string): string {
  return `${origin}/?tab=events&event=${eventId}&ticket=${token}`;
}

/** Ce qu'on a lu (QR, lien collé, code tapé) → jeton ou code court ; null si ce n'est pas un billet Party. */
export function parseScanned(raw: string): string | null {
  const text = raw.trim();
  if (TOKEN.test(text)) return text.toLowerCase();
  const fromLink = text.match(/[?&]ticket=([0-9a-f]{64})(?:&|#|$)/i)?.[1];
  if (fromLink) return fromLink.toLowerCase();
  const code = text.replace(/[\s-]/g, '').toUpperCase();
  return CODE.test(code) ? code : null;
}

/** Code court lisible : « K7M 2QX ». */
export function prettyCode(code: string): string {
  return `${code.slice(0, 3)} ${code.slice(3)}`;
}

/** QR en image SVG (data URI) : modules noirs sur blanc, marge de 4 modules, lisible par tous les lecteurs. */
export function qrDataUri(text: string): string {
  const modules = toQR(text);
  const size = Math.round(Math.sqrt(modules.length));
  const quiet = 4;
  let path = '';
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      if (modules[y * size + x]) path += `M${x + quiet} ${y + quiet}h1v1h-1z`;
    }
  }
  const box = size + quiet * 2;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 ${box} ${box}" shape-rendering="crispEdges"><rect width="100%" height="100%" fill="#fff"/><path d="${path}" fill="#000"/></svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/** Réponse de la base vérifiée : un billet incomplet ou inattendu ne s'affiche pas (jamais de QR cassé). */
export function asMyTicket(raw: unknown): MyTicket {
  const t = raw as (Partial<Omit<Extract<MyTicket, { state: 'ok' }>, 'state'>> & { state?: string }) | null;
  if (t?.state === 'waitlist') return { state: 'waitlist' };
  if (t?.state === 'off') return { state: 'off', ...payment(t) };
  if (t?.state === 'pending') return { state: 'pending', ...payment(t) };
  if (t?.state !== 'ok' || typeof t.token !== 'string' || !TOKEN.test(t.token) || typeof t.code !== 'string' || !CODE.test(t.code)) {
    return { state: 'none' };
  }
  return { state: 'ok', token: t.token, code: t.code, checked_in_at: t.checked_in_at ?? null, ...payment(t) };
}

function payment(t: Partial<TicketPayment>): TicketPayment {
  return { plus_ones: Number(t.plus_ones) || 0, paid: !!t.paid, pay_pending: !t.paid && !!t.pay_pending,
    price_chf: typeof t.price_chf === 'number' ? t.price_chf : null };
}

/** Fonction absente de la base (migration pas encore appliquée) : pas de billet, sans message d'erreur technique. */
const MISSING_FUNCTION = 'PGRST202';

async function ticketCall(name: string, args: Record<string, unknown>): Promise<MyTicket> {
  const { data, error } = await supabase.rpc(name, args);
  if (error && (error as { code?: string }).code === MISSING_FUNCTION) return { state: 'none' };
  if (error) throw new Error(error.message);
  return asMyTicket(data);
}

export function fetchMyTicket(eventId: string): Promise<MyTicket> {
  return ticketCall('my_event_ticket', { e: eventId });
}

export async function renewMyTicket(eventId: string): Promise<MyTicket> {
  const ticket = await ticketCall('renew_event_ticket', { e: eventId });
  notifyWallet(eventId, (await supabase.auth.getSession()).data.session?.user.id);  // nouveau QR dans Cartes
  return ticket;
}

/** « J'ai payé » (true) ou « pas encore » (false) : l'organisateur est prévenu et confirme. */
export function declarePayment(eventId: string, declared: boolean): Promise<MyTicket> {
  return ticketCall('declare_ticket_payment', { e: eventId, declared });
}

export async function fetchPayInfo(eventId: string): Promise<PayInfo | null> {
  const { data, error } = await supabase.rpc('event_pay_info', { e: eventId });
  if (error && (error as { code?: string }).code === MISSING_FUNCTION) return null;
  if (error) throw new Error(error.message);
  return (data as PayInfo | null) ?? null;
}

/** L'organisateur confirme : reçu (payé ✓) ou pas reçu (la personne est prévenue et peut redéclarer). */
export async function confirmPayment(eventId: string, member: string, received: boolean, before?: TicketPerson): Promise<TicketPerson> {
  const person = must(await supabase.rpc('confirm_ticket_payment', { e: eventId, member, received })) as TicketPerson;
  notifyWallet(eventId, member);
  return withPaymentNotice(before, person, !received);
}

/** L'organisateur remet (true) ou retire (false) le billet d'un présent ; la personne est prévenue à la remise. */
export async function issueTicket(eventId: string, member: string, issued: boolean): Promise<TicketPerson> {
  const person = must(await supabase.rpc('issue_event_ticket', { e: eventId, member, issued })) as TicketPerson;
  notifyWallet(eventId, member);  // retiré : le pass dans Cartes devient « annulé »
  return person;
}

/** « Remettre à tous les présents » : nombre de billets remis par cet appui. */
export async function issueAllTickets(eventId: string): Promise<number> {
  const count = Number(must(await supabase.rpc('issue_all_event_tickets', { e: eventId }))) || 0;
  notifyWallet(eventId);
  return count;
}

/** Option « Billets QR » de l'événement (organisateurs, admins), à tout moment, même après publication. */
export async function setTicketsEnabled(eventId: string, enabled: boolean): Promise<boolean> {
  const on = must(await supabase.rpc('set_event_tickets', { e: eventId, enabled })) as boolean;
  notifyWallet(eventId);  // éteinte : les pass déjà dans Cartes deviennent « annulés »
  return on;
}

/** IBAN lisible par groupes de 4 : « CH93 0076 2011 6238 5295 7 ». */
export function formatIban(iban: string): string {
  return iban.replace(/\s/g, '').replace(/(.{4})/g, '$1 ').trim();
}

/** « 20 » plutôt que « 20.00 ». */
export function chf(amount: number): string {
  return `${Number.isInteger(amount) ? amount : amount.toFixed(2)} CHF`;
}

export async function checkInTicket(eventId: string, scanned: string): Promise<ScanResult> {
  const result = must(await supabase.rpc('check_in_ticket', { e: eventId, scanned })) as ScanResult;
  if (result.result === 'ok') notifyWallet(eventId, result.person.user_id);  // « Arrivée enregistrée » dans Cartes
  return result;
}

export async function fetchCheckins(eventId: string): Promise<TicketPerson[]> {
  return must(await supabase.rpc('event_checkins', { e: eventId })) as TicketPerson[];
}

export async function setArrival(eventId: string, member: string, arrived: boolean): Promise<TicketPerson> {
  const person = must(await supabase.rpc('set_ticket_arrival', { e: eventId, member, arrived })) as TicketPerson;
  notifyWallet(eventId, member);
  return person;
}

export async function setPaid(eventId: string, member: string, paid: boolean, before?: TicketPerson): Promise<TicketPerson> {
  const person = must(await supabase.rpc('set_ticket_paid', { e: eventId, member, is_paid: paid })) as TicketPerson;
  notifyWallet(eventId, member);
  return withPaymentNotice(before, person, !paid);
}

/** Billet à montrer : Présent, publié, date fixée, et pas fini depuis plus d'un jour. */
export function ticketRelevant(ev: { status: string; date_mode: string; starts_at: string | null; ends_at: string | null }, now: number): boolean {
  if (ev.status !== 'published' || ev.date_mode !== 'fixed' || !ev.starts_at) return false;
  const end = new Date(ev.ends_at ?? ev.starts_at).getTime();
  return end > now - 24 * 3600_000;
}
