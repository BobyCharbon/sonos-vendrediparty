import { useFocusEffect } from 'expo-router';
import { useCallback, useEffect, useRef } from 'react';

import { friendlyError } from './errors';
import { formatShort } from './format';
import { isTermsError } from './moderation';
import { must, supabase } from './supabase';
import { chf } from './tickets';

/**
 * Bar de la soirée (migration 20261110120000, maquettes v6 du 10.11) : tables fermées, tout passe par les fonctions
 * public.bar_* et my_bar. La base décide de tout (droits, stock virtuel, maximum en attente, engagement, prix figé) ;
 * l'écran ne fait qu'afficher et anticiper (bouton + éteint avant le refus de la base).
 */

export type BarPhase = 'waiting' | 'preorder' | 'open' | 'closed';
export type PayMethod = 'revolut' | 'twint' | 'iban';
export type AgeMin = 0 | 16 | 18;
export type CancelReason = 'mine' | 'organizer' | 'closed' | 'removed' | 'absent' | null;

export type MyBarItem = {
  id: string; name: string; emoji: string | null; price_chf: number; age_min: AgeMin; max_pending: number | null;
  /** Stock virtuel encore libre (stock − servis − en attente) ; null : illimité. */
  available: number | null;
  /** Mes verres de cet article commandés, pas encore servis. */
  mine_pending: number;
  /** Total de mes verres en attente de cet article, aux prix de la commande (absent des anciennes versions de la base). */
  mine_pending_chf?: number;
};
export type Payee = {
  id: string | null; name: string | null; method: PayMethod; repay_by: string | null;
  iban: string | null; holder: string | null; link: string | null;
};
export type MyBar = {
  phase: BarPhase; eligible: boolean; manage: boolean; serve: boolean;
  closes_at: string; preorder_until: string | null;
  pledge_text: string; pledge_version: number;
  payee: Payee;
  qr: { token: string; code: string } | null;
  balance: number; pending_total: number; refund_declared: number;
  items: MyBarItem[];
  served: { at: string; item: string; emoji: string | null; price_chf: number }[];
  cancelled: { item: string; emoji: string | null; reason: CancelReason; at: string | null }[];
  pledges: string[];
};

export type BarItem = {
  id: string; name: string; emoji: string | null; price_chf: number; stock: number | null; age_min: AgeMin;
  max_pending: number | null; sort: number; active: boolean; served: number; pending: number; available: number | null;
};
export type BarStaff = { id: string; name: string; avatar_url: string | null; served: number };
export type BarPerson = {
  id: string; name: string; avatar_url: string | null; balance: number; pending: number; served: number;
  declared: { id: string; amount: number; at: string }[] | null; refunded: number;
};
export type BarOverview = {
  phase: BarPhase; orders_open: boolean; preorder_enabled: boolean; preorder_until: string | null;
  closes_at: string; closed_at: string | null; payee_id: string | null; pay_method: PayMethod; repay_by: string | null;
  pledge_text: string; terms_version: number;
  items: BarItem[]; staff: BarStaff[]; people: BarPerson[];
  totals: { served: number; served_chf: number; refunded_chf: number };
  cancellations: { at: string; name: string | null; item: string | null; qty: number | null; kind: string }[];
};
export type BarUnit = {
  id: string; item: string; name: string; emoji: string | null; price_chf: number;
  status: 'pending' | 'served' | 'cancelled' | 'corrected'; ordered_at: string; served_at: string | null; served_by: string | null;
};
export type BarPersonDetail = { id: string; name: string | null; balance: number; pledges: string[]; units: BarUnit[] };

/** `prices` : prix figé de chaque verre en attente, dans l'ordre où la base les sert (le prix de la carte a pu changer). */
export type ScanLine = { item: string; name: string; emoji: string | null; price_chf: number; age_min: AgeMin; qty: number; stock: number | null; prices?: number[] };
export type BarScan =
  | { result: 'ok'; member: string; name: string; avatar_url: string | null; pledged_at: string | null; balance: number; pending: ScanLine[] }
  | { result: 'closed' | 'not_present'; name: string | null }
  | { result: 'unknown' | 'other_event' };
export type ServeResult = {
  serve_id: string; total: number; balance: number; balance_before?: number; replayed?: boolean;
  lines?: { item: string; name: string; emoji: string | null; qty: number }[];
};
export type ItemInput = {
  id?: string; name: string; emoji: string | null; price_chf?: number; stock?: number | null; age_min?: AgeMin;
  max_pending?: number | null; active?: boolean;
};
export type BarSettings = Partial<{
  orders_open: boolean; preorder_enabled: boolean; preorder_until: string | null; closes_at: string;
  pay_method: PayMethod; repay_by: string | null; payee_id: string;
}>;

/** Refus de la base : message lisible (sans « stock: »), et le code gardé pour que l'écran réagisse. */
export class BarError extends Error {
  readonly code: string | null;
  constructor(message: string, code: string | null) {
    super(message);
    this.name = 'BarError';
    this.code = code;
  }
}

const CODE = /^([a-z_]+): /;
const capitalize = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
/** Fonction absente de la base (migration pas encore appliquée). */
const MISSING_FUNCTION = 'PGRST202';

export function barError(message: string | undefined, fallback: string): BarError {
  const raw = (message ?? '').trim();
  if (!raw) return new BarError(fallback, null);
  // CGU exigées : on garde « terms_required: … » pour que l'écran ouvre la feuille des CGU puis réessaie.
  if (isTermsError(raw)) return new BarError(raw, 'terms_required');
  const code = raw.match(CODE)?.[1] ?? null;
  return new BarError(capitalize(friendlyError(raw.replace(CODE, ''))), code);
}

export const errorCode = (e: unknown): string | null => (e instanceof BarError ? e.code : null);
export const errorText = (e: unknown, fallback: string): string => (e instanceof Error && e.message ? e.message : fallback);

async function call<T>(name: string, args: Record<string, unknown>, fallback: string): Promise<T> {
  const { data, error } = await supabase.rpc(name, args);
  if (error) throw barError(error.message, fallback);
  return data as T;
}

/** Bar de l'événement vu par moi ; null : pas de bar (ou base pas encore migrée). */
export async function fetchMyBar(e: string): Promise<MyBar | null> {
  const { data, error } = await supabase.rpc('my_bar', { e });
  if (error && (error as { code?: string }).code === MISSING_FUNCTION) return null;
  if (error) throw barError(error.message, 'Le bar n’a pas pu être lu.');
  return (data as MyBar | null) ?? null;
}

export const barOrder = (e: string, lines: { item: string; qty: number }[], pledgeText: string, pledgeVersion: number) =>
  call<MyBar>('bar_order', { e, lines, pledge_text: pledgeText, pledge_version: pledgeVersion }, 'La commande n’a pas pu être envoyée.');
export const barCancelMine = (e: string, item: string, qty: number) =>
  call<MyBar>('bar_cancel_mine', { e, item, qty }, 'L’annulation n’a pas pu être enregistrée.');
export const barDeclareRefund = (e: string, amount: number) =>
  call<MyBar>('bar_declare_refund', { e, amount }, 'Le remboursement n’a pas pu être annoncé.');

export const barScan = (e: string, scanned: string) => call<BarScan>('bar_scan', { e, scanned }, 'Le QR n’a pas pu être lu.');
export const barServe = (e: string, member: string, lines: { item: string; qty: number }[], clientKey: string) =>
  call<ServeResult>('bar_serve', { e, member, lines, client_key: clientKey }, 'Le service n’a pas pu être enregistré.');
export const barUndoServe = (e: string, serve: string) =>
  call<{ undone: number; balance: number }>('bar_undo_serve', { e, serve }, 'L’annulation n’a pas pu être enregistrée.');

export const barOverview = (e: string) => call<BarOverview | null>('bar_overview', { e }, 'Le bar n’a pas pu être lu.');
export const barCreate = (e: string) => call<BarOverview>('bar_create', { e }, 'Le bar n’a pas pu être créé.');
export const barSaveItem = (e: string, item: ItemInput) =>
  call<{ id: string; overbooked: number; name: string }>('bar_save_item', { e, item }, 'L’article n’a pas pu être enregistré.');
export const barSaveSettings = (e: string, settings: BarSettings) =>
  call<BarOverview>('bar_save_settings', { e, settings }, 'Les réglages n’ont pas pu être enregistrés.');
export const barSetStaff = (e: string, member: string, barman: boolean) =>
  call<BarOverview>('bar_set_staff', { e, member, barman }, 'Le barman n’a pas pu être enregistré.');
export const barConfirmRefund = (e: string, refund: string, received: boolean) =>
  call<BarOverview>('bar_confirm_refund', { e, refund, received }, 'La réponse n’a pas pu être enregistrée.');
export const barPerson = (e: string, member: string) => call<BarPersonDetail>('bar_person', { e, member }, 'La fiche n’a pas pu être lue.');
export const barCancelUnits = (e: string, member: string, item: string, qty: number) =>
  call<BarPersonDetail>('bar_cancel_units', { e, member, item, qty }, 'L’annulation n’a pas pu être enregistrée.');
export const barCorrectUnit = (e: string, unit: string) =>
  call<BarPersonDetail>('bar_correct_unit', { e, unit }, 'La correction n’a pas pu être enregistrée.');

// --- Fonctions pures ------------------------------------------------------------------------------------------------

/** Au centime (4.06 × 3 = 12.18, jamais 12.180000000000001). */
export const round2 = (n: number) => Math.round(n * 100) / 100;
/** « 4.50 CHF », « 3 CHF » (chf() des billets, arrondi au centime). */
export const barChf = (n: number) => chf(round2(n));
/** Montant sans « CHF », pour le grand chiffre : « 4.06 », « 0 ». */
export function amount(n: number): string {
  const r = round2(n);
  return Number.isInteger(r) ? String(r) : r.toFixed(2);
}

export const METHOD_LABEL: Record<PayMethod, string> = { revolut: 'Revolut', twint: 'Twint', iban: 'virement' };

const TZ = 'Europe/Zurich';
const dayFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' });

/** Date seule (« 2026-11-23 ») → « dim. 23 nov. ». */
export function dayLabel(date: string): string {
  const d = new Date(`${date.slice(0, 10)}T12:00:00Z`);
  return Number.isNaN(d.getTime()) ? date : dayFmt.format(d);
}

/** « ven. 6 nov. à 19:30 » */
export const whenLabel = (iso: string) => formatShort(iso).replace(' · ', ' à ').toLowerCase();

/** « à Boby · Revolut · avant dim. 23 nov. » */
export function payeeLine(p: Pick<Payee, 'name' | 'method' | 'repay_by'>): string {
  const who = p.name?.trim() || 'l’organisateur';
  return `à ${who} · ${capitalize(METHOD_LABEL[p.method])} · ${p.repay_by ? `avant ${dayLabel(p.repay_by)}` : 'après la soirée'}`;
}

export const PHASE_LABEL: Record<BarPhase, string> = {
  waiting: 'Pas encore ouvert', preorder: 'Précommande ouverte', open: 'Bar ouvert', closed: 'Bar fermé',
};

/** Ce que l'invité peut faire maintenant, en une phrase. */
export function phaseLine(bar: { phase: BarPhase; preorder_until: string | null; closes_at: string }): string {
  if (bar.phase === 'waiting') return 'Le bar n’est pas encore ouvert.';
  if (bar.phase === 'closed') return 'Le bar est fermé.';
  if (bar.phase === 'preorder') {
    return bar.preorder_until ? `Précommande ouverte jusqu’au ${whenLabel(bar.preorder_until)}.` : 'Précommande ouverte.';
  }
  return `Bar ouvert jusqu’au ${whenLabel(bar.closes_at)}.`;
}

export const CANCEL_LABEL: Record<Exclude<CancelReason, null>, string> = {
  mine: 'annulé par toi', organizer: 'annulé par l’organisateur', closed: 'bar fermé, rien à payer', removed: 'retiré de la carte', absent: 'annulé : plus noté « Présent »',
};
export const cancelLabel = (reason: CancelReason) => (reason ? CANCEL_LABEL[reason] : 'corrigé : servi par erreur');

/** Ce qui reste à rembourser, hors remboursements déjà annoncés (en attente de confirmation). */
export const owedNow = (bar: Pick<MyBar, 'balance' | 'refund_declared'>) => Math.max(0, round2(bar.balance - bar.refund_declared));

export const itemLabel = (i: { emoji: string | null; name: string }) => (i.emoji ? `${i.emoji} ${i.name}` : i.name);

// --- Commande de l'invité -------------------------------------------------------------------------------------------

/** La base refuse plus de 50 verres d'un même article par commande. */
export const MAX_LINE_QTY = 50;

export type Cart = Readonly<Record<string, number>>;
export type AddLimit = { max: number; reason: 'stock' | 'max_pending' | 'line' };

export const canOrder = (bar: Pick<MyBar, 'eligible' | 'phase'>) => bar.eligible && (bar.phase === 'open' || bar.phase === 'preorder');

/** Combien je peux mettre dans ma commande pour cet article, et ce qui bloque d'abord. Précommande : sans maximum en
 * attente (la base l'ignore), mais toujours dans le stock. */
export function addLimit(item: MyBarItem, phase: BarPhase): AddLimit {
  let limit: AddLimit = { max: MAX_LINE_QTY, reason: 'line' };
  if (item.available != null && item.available < limit.max) limit = { max: Math.max(0, item.available), reason: 'stock' };
  if (phase === 'open' && item.max_pending != null) {
    const left = Math.max(0, item.max_pending - item.mine_pending);
    if (left < limit.max) limit = { max: left, reason: 'max_pending' };
  }
  return limit;
}

/** « + » autorisé ? */
export function canAdd(item: MyBarItem, qty: number, phase: BarPhase): boolean {
  return (phase === 'open' || phase === 'preorder') && qty < addLimit(item, phase).max;
}

/** Quantité retenue, ramenée sous la limite du moment (le stock a pu baisser pendant que je choisissais). */
export const cartQty = (cart: Cart, item: MyBarItem, phase: BarPhase) => Math.min(cart[item.id] ?? 0, addLimit(item, phase).max);

export type CartLine = { item: MyBarItem; qty: number };

export function cartLines(cart: Cart, items: MyBarItem[], phase: BarPhase): CartLine[] {
  return items.map((item) => ({ item, qty: cartQty(cart, item, phase) })).filter((l) => l.qty > 0);
}

export function linesTotal(lines: { qty: number; item: { price_chf: number } }[]): { count: number; total: number } {
  return lines.reduce((acc, l) => ({ count: acc.count + l.qty, total: round2(acc.total + l.qty * l.item.price_chf) }), { count: 0, total: 0 });
}

export const orderPayload = (lines: CartLine[]) => lines.map((l) => ({ item: l.item.id, qty: l.qty }));

// --- Service au bar --------------------------------------------------------------------------------------------------

/** Au plus ce qui est en attente, et ce qu'il reste physiquement (stock − servis) si le stock est fixé. */
export const serveMax = (line: ScanLine) => Math.max(0, Math.min(line.qty, line.stock ?? line.qty));

/** Montant débité pour `qty` verres de cette ligne : les prix figés à la commande (test réel du 10.11 : le panneau annonçait
 * 22.50 CHF au nouveau prix, la base débitait 21.00 au prix de la commande). */
export function serveAmount(line: ScanLine, qty: number): number {
  const prices = line.prices ?? [];
  const known = prices.slice(0, qty).reduce((a, p) => a + Number(p), 0);
  return round2(known + Math.max(qty - prices.length, 0) * line.price_chf);
}

export function servePicks(pending: ScanLine[], picks: Cart): { count: number; total: number; lines: { line: ScanLine; qty: number }[] } {
  const lines = pending.map((line) => ({ line, qty: Math.min(picks[line.item] ?? 0, serveMax(line)) })).filter((l) => l.qty > 0);
  const count = lines.reduce((a, l) => a + l.qty, 0);
  const total = round2(lines.reduce((a, l) => a + serveAmount(l.line, l.qty), 0));
  return { count, total, lines };
}

/** Rappel d'âge pour le barman : « Vodka Red Bull : 18+, vérifie l'âge si tu as un doute. » */
export const ageWarnings = (pending: ScanLine[]) =>
  pending.filter((l) => l.age_min > 0).map((l) => `${l.name} : ${l.age_min}+, vérifie l’âge si tu as un doute.`);

/** Clé d'un geste « Servir » : rejouée telle quelle (double toucher, reprise réseau), la base ne sert pas deux fois. */
export function newClientKey(): string {
  const c = globalThis.crypto;
  if (typeof c?.randomUUID === 'function') return c.randomUUID();
  const bytes = new Uint8Array(16);
  c.getRandomValues(bytes);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
}

// --- Gestion (organisateurs) -----------------------------------------------------------------------------------------

export type ItemDraft = { name: string; emoji: string; price: string; stock: string; maxPending: string; age: AgeMin; active: boolean };

export const draftOf = (i?: BarItem): ItemDraft => ({
  name: i?.name ?? '', emoji: i?.emoji ?? '', price: i ? String(i.price_chf) : '', stock: i?.stock != null ? String(i.stock) : '',
  maxPending: i?.max_pending != null ? String(i.max_pending) : '', age: i?.age_min ?? 0, active: i?.active ?? true,
});

const WHOLE = /^\d+$/;

/** Formulaire d'article → ce qu'attend bar_save_item, ou la première erreur, en clair (mêmes bornes que la base). */
export function parseItemDraft(d: ItemDraft, id?: string): { input: ItemInput } | { error: string } {
  const name = d.name.trim();
  if (!name || name.length > 40) return { error: 'Donne un nom à l’article (40 signes au plus).' };
  const emoji = d.emoji.trim();
  if ([...emoji].length > 8) return { error: 'Un emoji suffit (8 signes au plus).' };
  const priceText = d.price.trim().replace(',', '.');
  const price = Number(priceText);
  if (!priceText || !Number.isFinite(price) || price < 0 || price > 500 || round2(price) !== price) {
    return { error: 'Prix : de 0 à 500 CHF, au centime près (par exemple 4.50).' };
  }
  const stockText = d.stock.trim();
  if (stockText && (!WHOLE.test(stockText) || Number(stockText) > 100000)) return { error: 'Stock : un nombre entier, ou vide pour illimité.' };
  const maxText = d.maxPending.trim();
  if (maxText && (!WHOLE.test(maxText) || Number(maxText) < 1 || Number(maxText) > 50)) {
    return { error: 'Maximum en attente : de 1 à 50, ou vide pour sans limite.' };
  }
  return { input: {
    ...(id ? { id, active: d.active } : {}), name, emoji: emoji || null, price_chf: price,
    stock: stockText ? Number(stockText) : null, max_pending: maxText ? Number(maxText) : null, age_min: d.age,
  } };
}

export type EventPeople = {
  /** Créateur puis co-organisateurs : peuvent recevoir les remboursements et gèrent le bar. */
  organizers: string[];
  /** Notés « Présent » (hors liste d'attente) : seuls à pouvoir devenir barmans. */
  present: string[];
  profiles: Map<string, { name: string; avatar_url: string | null }>;
};

export async function fetchEventPeople(eventId: string): Promise<EventPeople> {
  const ev = must(await supabase.from('events').select('created_by, event_organizers(user_id), rsvps(user_id, status, waitlisted)')
    .eq('id', eventId).single()) as { created_by: string | null; event_organizers: { user_id: string }[];
    rsvps: { user_id: string; status: string; waitlisted: boolean }[] };
  const organizers = [...new Set([ev.created_by, ...ev.event_organizers.map((o) => o.user_id)].filter((x): x is string => !!x))];
  const present = ev.rsvps.filter((r) => r.status === 'yes' && !r.waitlisted).map((r) => r.user_id);
  const ids = [...new Set([...organizers, ...present])];
  const rows = ids.length ? must(await supabase.from('profiles').select('id, display_name, avatar_url').in('id', ids)) : [];
  const profiles = new Map((rows as { id: string; display_name: string; avatar_url: string | null }[])
    .map((p) => [p.id, { name: p.display_name, avatar_url: p.avatar_url }]));
  return { organizers, present, profiles };
}

/** Stock virtuel d'un article, en parts de la barre (servis / réservés / libres) ; null : illimité ou stock 0. */
export function stockParts(i: Pick<BarItem, 'stock' | 'served' | 'pending'>): { served: number; pending: number; free: number } | null {
  if (i.stock == null || i.stock <= 0) return null;
  const served = Math.min(1, i.served / i.stock);
  const pending = Math.min(1 - served, i.pending / i.stock);
  return { served, pending, free: Math.max(0, 1 - served - pending) };
}

// --- Relecture -------------------------------------------------------------------------------------------------------

export const BAR_REFRESH_MS = 10_000;

/** Relecture toutes les 10 s tant que l'écran est affiché (arrêtée hors de l'écran ou onglet caché). */
export function useBarRefresh(reload: () => unknown, active = true) {
  const latest = useRef(reload);
  useEffect(() => { latest.current = reload; }, [reload]);
  useFocusEffect(useCallback(() => {
    if (!active) return undefined;
    const timer = setInterval(() => {
      if (typeof document === 'undefined' || document.visibilityState !== 'hidden') void latest.current();
    }, BAR_REFRESH_MS);
    return () => clearInterval(timer);
  }, [active]));
}
