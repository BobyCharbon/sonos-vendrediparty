import { useEffect, useState } from 'react';

import { useSignal } from './data';
import { supabase } from './supabase';

/**
 * Agenda de Party (17.11, maquette A « Néon nuit » validée) : calculs et appels communs aux écrans `/agenda`.
 * Contrat : fonctions `agenda_*` de la base (migration 20261117140000) ; l'agenda pense en heure de Suisse.
 * Pont iPhone facultatif : `window.PartyNative.agenda` (calendriers de l'iPhone, lus et calculés sur l'appareil).
 */

export const TZ = 'Europe/Zurich';

// ───────────── Dates en heure de Suisse ─────────────
/** Jour « AAAA-MM-JJ » en heure de Suisse. */
export type DayKey = string;

const partsFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});

function zparts(d: Date) {
  const p: Record<string, number> = {};
  for (const x of partsFmt.formatToParts(d)) if (x.type !== 'literal') p[x.type] = Number(x.value);
  return { y: p.year, m: p.month, d: p.day, h: p.hour % 24, mi: p.minute };
}

const pad = (n: number) => String(n).padStart(2, '0');

export function dayKey(d: Date): DayKey {
  const p = zparts(d);
  return `${p.y}-${pad(p.m)}-${pad(p.d)}`;
}

function splitKey(key: DayKey) {
  const [y, m, d] = key.split('-').map(Number);
  return { y, m, d };
}

function offsetMinutes(t: number): number {
  const p = zparts(new Date(t));
  return Math.round((Date.UTC(p.y, p.m - 1, p.d, p.h, p.mi) - Math.floor(t / 60000) * 60000) / 60000);
}

/** Instant d'une heure de Suisse : ce jour, `minutes` après minuit (1440 = minuit suivant). */
export function zdate(key: DayKey, minutes = 0): Date {
  const { y, m, d } = splitKey(key);
  const guess = Date.UTC(y, m - 1, d, 0, minutes);
  const off = offsetMinutes(guess);
  let t = guess - off * 60000;
  const off2 = offsetMinutes(t);
  if (off2 !== off) t = guess - off2 * 60000;
  return new Date(t);
}

export function addDays(key: DayKey, n: number): DayKey {
  const { y, m, d } = splitKey(key);
  const u = new Date(Date.UTC(y, m - 1, d + n));
  return `${u.getUTCFullYear()}-${pad(u.getUTCMonth() + 1)}-${pad(u.getUTCDate())}`;
}

export function addMonths(key: DayKey, n: number): DayKey {
  const { y, m } = splitKey(key);
  const u = new Date(Date.UTC(y, m - 1 + n, 1));
  return `${u.getUTCFullYear()}-${pad(u.getUTCMonth() + 1)}-01`;
}

/** 1 = lundi … 7 = dimanche. */
export function isoWeekday(key: DayKey): number {
  const { y, m, d } = splitKey(key);
  return ((new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7) + 1;
}

export function weekStart(key: DayKey): DayKey {
  return addDays(key, 1 - isoWeekday(key));
}

export function monthStart(key: DayKey): DayKey {
  return `${key.slice(0, 7)}-01`;
}

export function dayOfMonth(key: DayKey): number {
  return splitKey(key).d;
}

export function sameMonth(a: DayKey, b: DayKey): boolean {
  return a.slice(0, 7) === b.slice(0, 7);
}

/** Minutes depuis minuit (heure de Suisse). */
export function minutesOf(d: Date): number {
  const p = zparts(d);
  return p.h * 60 + p.mi;
}

/** Numéro de semaine ISO (réglage « Numéros de semaine »). */
export function isoWeekNumber(key: DayKey): number {
  const { y, m, d } = splitKey(key);
  const date = new Date(Date.UTC(y, m - 1, d));
  date.setUTCDate(date.getUTCDate() + 4 - (date.getUTCDay() || 7));
  const yearStart = new Date(Date.UTC(date.getUTCFullYear(), 0, 1));
  return Math.ceil(((date.getTime() - yearStart.getTime()) / 86400000 + 1) / 7);
}

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);
const MONTHS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août', 'septembre', 'octobre', 'novembre', 'décembre'];
const MONTHS_SHORT = ['janv.', 'févr.', 'mars', 'avr.', 'mai', 'juin', 'juil.', 'août', 'sept.', 'oct.', 'nov.', 'déc.'];
const DAYS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche'];
const DAYS_SHORT = ['lun.', 'mar.', 'mer.', 'jeu.', 'ven.', 'sam.', 'dim.'];
export const WEEK_LETTERS = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];
export const DAY_NAMES = DAYS;

/** « LUN » */
export function dayAbbr(key: DayKey): string {
  return DAYS_SHORT[isoWeekday(key) - 1].replace('.', '').toUpperCase();
}
/** « Sam. 28 nov. » */
export function shortDay(key: DayKey): string {
  const { m, d } = splitKey(key);
  return `${cap(DAYS_SHORT[isoWeekday(key) - 1])} ${d} ${MONTHS_SHORT[m - 1]}`;
}
/** « sam. 28 » */
export function tinyDay(key: DayKey): string {
  return `${DAYS_SHORT[isoWeekday(key) - 1]} ${splitKey(key).d}`;
}
/** « Vendredi 20 novembre » */
export function longDay(key: DayKey): string {
  const { m, d } = splitKey(key);
  return `${cap(DAYS[isoWeekday(key) - 1])} ${d} ${MONTHS[m - 1]}`;
}
/** « Novembre » (« Novembre 2027 » hors de l'année en cours). */
export function monthTitle(key: DayKey, today: DayKey): string {
  const { y, m } = splitKey(key);
  return `${cap(MONTHS[m - 1])}${y !== splitKey(today).y ? ` ${y}` : ''}`;
}
/** « 16 – 22 nov. » ou « 30 nov. – 6 déc. » */
export function weekTitle(start: DayKey): string {
  const end = addDays(start, 6);
  const a = splitKey(start);
  const b = splitKey(end);
  return a.m === b.m ? `${a.d} – ${b.d} ${MONTHS_SHORT[b.m - 1]}` : `${a.d} ${MONTHS_SHORT[a.m - 1]} – ${b.d} ${MONTHS_SHORT[b.m - 1]}`;
}
/** « Semaine du 23 au 29 novembre » (annonce VoiceOver d'un changement de période). */
export function weekSpoken(start: DayKey): string {
  const end = addDays(start, 6);
  return `Semaine du ${splitKey(start).d} au ${splitKey(end).d} ${MONTHS[splitKey(end).m - 1]}`;
}
export function monthShort(key: DayKey): string {
  return cap(MONTHS_SHORT[splitKey(key).m - 1]);
}

/** « 18:30 » */
export function hm(d: Date): string {
  const p = zparts(d);
  return `${pad(p.h)}:${pad(p.mi)}`;
}
/** « 18 h 30 », « 19 h », « 0 h » (texte courant). */
export function hText(d: Date): string {
  const p = zparts(d);
  return p.mi ? `${p.h} h ${pad(p.mi)}` : `${p.h} h`;
}
/** « 19 h – 23 h » */
export function spanText(a: Date, b: Date): string {
  return `${hText(a)} – ${hText(b)}`;
}
/** Délai minimum avant un rendez-vous : « Sur le moment », « 30 min », « 2 h », « 24 h », « 7 jours ». */
export function noticeText(minutes: number): string {
  if (!minutes) return 'Sur le moment';
  if (minutes >= 2880 && minutes % 1440 === 0) return `${minutes / 1440} jours`;
  return minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h${minutes % 60 ? ` ${pad(minutes % 60)}` : ''}`;
}
/** Durée « 1 h », « 1 h 30 », « 45 min ». */
export function durationText(minutes: number): string {
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  return m ? `${h} h ${pad(m)}` : `${h} h`;
}
/** « 15 nov. » */
export function dateShort(iso: string): string {
  const { m, d } = splitKey(dayKey(new Date(iso)));
  return `${d} ${MONTHS_SHORT[m - 1]}`;
}
/** « 17.11.2026 » */
export function dateDots(iso: string): string {
  const { y, m, d } = splitKey(dayKey(new Date(iso)));
  return `${pad(d)}.${pad(m)}.${y}`;
}
/** « il y a 5 min », « il y a 2 h », « il y a 3 jours ». */
export function agoText(iso: string | null | undefined, now = Date.now()): string {
  if (!iso) return '';
  const min = Math.max(0, Math.round((now - new Date(iso).getTime()) / 60000));
  if (min < 1) return 'à l’instant';
  if (min < 60) return `il y a ${min} min`;
  const h = Math.round(min / 60);
  if (h < 48) return `il y a ${h} h`;
  return `il y a ${Math.round(h / 24)} jours`;
}

// ───────────── Calendriers et rendez-vous ─────────────
export const CAL_COLORS: Record<string, string> = {
  pink: '#FF4F9A', coral: '#FFB347', mint: '#5BE3A6', sky: '#6CC7FF', lavender: '#B9A7FF', lemon: '#FFE27A', violet: '#9B7BFF', gray: '#9A93B5',
};
export const CAL_COLOR_NAMES: Record<string, string> = {
  pink: 'Rose', coral: 'Orange', mint: 'Vert', sky: 'Bleu', lavender: 'Lavande', lemon: 'Citron', violet: 'Violet', gray: 'Gris',
};
export const calColor = (c?: string | null) => CAL_COLORS[c ?? ''] ?? CAL_COLORS.sky;

export type Calendar = {
  id: string; kind: 'party' | 'personal' | 'ics'; name: string; color: string; visible: boolean; counts_busy: boolean;
  ics_url: string | null; fetched_at: string | null; fetch_error: string | null; created_at: string;
};
export type Repeat = 'none' | 'daily' | 'weekly' | 'biweekly' | 'monthly' | 'yearly';
export type Item = {
  id: string; calendar_id: string; title: string; place: string | null; notes: string | null; starts_at: string; ends_at: string;
  all_day: boolean; repeat: Repeat; repeat_until: string | null; alert_minutes: number | null; busy: boolean; series_start: string;
  booking: { id: string; status: string; link_name: string } | null;
};
export type PartyEvent = {
  event_id: string; title: string; starts_at: string; ends_at: string | null; all_day: boolean | null; location_name: string | null;
  status: 'published' | 'cancelled'; icon: string | null; organizer: boolean; answer: 'yes' | 'maybe' | 'no' | null;
};
export type PollEvent = { event_id: string; title: string; options: { id: string; starts_at: string; ends_at: string | null; my_vote: string | null }[] };
export type AgendaWindow = { items: Item[]; party: PartyEvent[]; polls: PollEvent[] };
export type IcsEvent = { uid: string; title: string; place: string | null; starts_at: string; ends_at: string; all_day: boolean; busy: boolean };
export type DeviceEvent = { id: string; calendarId: string; title: string; location?: string | null; start: string; end: string; allDay?: boolean; color?: string };
export type Prefs = {
  welcome_seen?: boolean; view?: View; week_numbers?: boolean; show_declined?: boolean; show_polls?: boolean;
  free_group?: string; free_mode?: 'evening' | 'day'; share_hint_dismissed?: boolean; native_denied_seen?: boolean;
};
export type View = 'day' | 'week' | 'month';

export const REPEATS: { key: Repeat; label: string }[] = [
  { key: 'none', label: 'Jamais' }, { key: 'daily', label: 'Chaque jour' }, { key: 'weekly', label: 'Chaque semaine' },
  { key: 'biweekly', label: 'Toutes les 2 semaines' }, { key: 'monthly', label: 'Chaque mois' }, { key: 'yearly', label: 'Chaque année' },
];
export const ALERTS: { minutes: number | null; label: string }[] = [
  { minutes: null, label: 'Aucune' }, { minutes: 0, label: 'À l’heure' }, { minutes: 15, label: '15 min avant' },
  { minutes: 60, label: '1 h avant' }, { minutes: 1440, label: 'La veille' },
];

/** Un élément affiché dans l'agenda, d'où qu'il vienne. */
export type Entry = {
  key: string;
  kind: 'item' | 'party' | 'poll' | 'ics' | 'device';
  title: string;
  start: Date;
  end: Date;
  allDay: boolean;
  /** Nom du calendrier, écrit sous le titre (jamais la couleur seule). */
  source: string;
  color: string;
  place?: string | null;
  answer?: PartyEvent['answer'];
  organizer?: boolean;
  cancelled?: boolean;
  eventId?: string;
  icon?: string | null;
  item?: Item;
  busy: boolean;
};

/** Appel d'une fonction de la base ; l'erreur garde la phrase de la base (« forbidden: … » → « … »). */
export async function rpc<T>(fn: string, args?: Record<string, unknown>): Promise<T> {
  const { data, error } = await supabase.rpc(fn, args ?? {});
  if (error) throw new AgendaError(error.message);
  return data as T;
}

export class AgendaError extends Error {
  code: string;
  constructor(raw: string) {
    const m = /^([a-z_]+): (.*)$/s.exec(raw ?? '');
    super(m ? m[2].charAt(0).toUpperCase() + m[2].slice(1) : 'Ça n’a pas marché. Réessaie dans un instant.');
    this.code = m ? m[1] : 'error';
  }
}

export const isTerms = (e: unknown) => e instanceof AgendaError && e.code === 'terms_required';
export const isProfile = (e: unknown) => e instanceof AgendaError && e.code === 'profile_incomplete';
export const errorText = (e: unknown) => (e instanceof Error ? e.message : 'Ça n’a pas marché. Réessaie dans un instant.');

/** Agendas ajoutés avec un lien : lus par le serveur Party, pour leur seul propriétaire. */
export async function fetchIcs(calendarId: string, from: Date, to: Date): Promise<IcsEvent[]> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) return [];
  const r = await fetch('/api/account/agenda/ics', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
    body: JSON.stringify({ token, calendar_id: calendarId, from: from.toISOString(), to: to.toISOString() }),
  });
  if (!r.ok) return [];
  const body = (await r.json()) as { events?: IcsEvent[] };
  return body.events ?? [];
}

// ───────────── Pont iPhone (facultatif) ─────────────
export type NativeAccess = 'full' | 'denied' | 'notDetermined' | 'writeOnly' | 'restricted';
export type NativeCalendar = { id: string; title: string; color: string; source: string; shown: boolean; countsBusy: boolean; excluded?: string };
/** Clé d'un calendrier de l'iPhone dans un lien de dispo (jamais son nom : seul l'iPhone le connaît). */
export const iosKey = (id: string) => `ios:${id}`;
type NativeAgenda = {
  status: () => Promise<{ access: NativeAccess }>;
  requestAccess: () => Promise<{ access: NativeAccess }>;
  calendars: () => Promise<NativeCalendar[]>;
  setCalendar: (id: string, v: { shown?: boolean; countsBusy?: boolean }) => Promise<{ ok: boolean }>;
  events: (from: string, to: string) => Promise<DeviceEvent[]>;
  syncBusy: () => Promise<{ sent: number; updatedAt: string }>;
  addToPhone: (e: { title: string; start: string; end: string; location?: string }) => Promise<{ saved: boolean }>;
};

/** Le pont de l'app iPhone, s'il existe (navigateur : null, l'agenda marche sans). */
export function nativeAgenda(): NativeAgenda | null {
  const n = (globalThis as { PartyNative?: { agenda?: Partial<NativeAgenda> } }).PartyNative?.agenda;
  return n && typeof n.status === 'function' && typeof n.calendars === 'function' && typeof n.events === 'function' ? (n as NativeAgenda) : null;
}

export async function nativeAccess(): Promise<NativeAccess | null> {
  const n = nativeAgenda();
  if (!n) return null;
  try { return (await n.status()).access; } catch { return null; }
}

// ───────────── Une période de l'agenda ─────────────
export type Loaded = { entries: Entry[]; calendars: Calendar[]; prefs: Prefs; native: NativeAccess | null };

export async function loadPeriod(from: Date, to: Date): Promise<Loaded> {
  const [win, calendars, prefs, native] = await Promise.all([
    rpc<AgendaWindow>('agenda_window', { from_ts: from.toISOString(), to_ts: to.toISOString() }),
    rpc<Calendar[]>('agenda_calendars_list'),
    rpc<Prefs>('agenda_prefs_get').catch((): Prefs => ({})),
    nativeAccess(),
  ]);
  const byId = new Map(calendars.map((c) => [c.id, c]));
  const party = calendars.find((c) => c.kind === 'party');
  const entries: Entry[] = [];
  for (const it of win.items) {
    const cal = byId.get(it.calendar_id);
    if (cal && !cal.visible) continue;
    entries.push({ key: `i:${it.id}:${it.starts_at}`, kind: 'item', title: it.title, start: new Date(it.starts_at), end: new Date(it.ends_at),
      allDay: it.all_day, source: cal?.name ?? 'Juste pour moi', color: calColor(cal?.color ?? 'mint'), place: it.place, item: it, busy: it.busy });
  }
  if (!party || party.visible) {
    for (const ev of win.party) {
      if (ev.answer === 'no' && !prefs.show_declined) continue;
      const start = new Date(ev.starts_at);
      const end = ev.ends_at ? new Date(ev.ends_at) : new Date(start.getTime() + 4 * 3600_000);
      entries.push({ key: `p:${ev.event_id}`, kind: 'party', title: ev.title, start, end, allDay: !!ev.all_day, source: 'Mes soirées Party',
        color: CAL_COLORS.pink, place: ev.location_name, answer: ev.answer, organizer: ev.organizer, cancelled: ev.status === 'cancelled',
        eventId: ev.event_id, icon: ev.icon, busy: ev.answer === 'yes' || ev.answer === 'maybe' || ev.organizer });
    }
  }
  if (prefs.show_polls !== false) {
    for (const poll of win.polls) {
      for (const o of poll.options) {
        const start = new Date(o.starts_at);
        const end = o.ends_at ? new Date(o.ends_at) : new Date(start.getTime() + 4 * 3600_000);
        entries.push({ key: `v:${o.id}`, kind: 'poll', title: poll.title, start, end, allDay: false, source: 'Sondage à voter',
          color: CAL_COLORS.pink, eventId: poll.event_id, busy: false, answer: null });
      }
    }
  }
  // Agendas ajoutés avec un lien : lus par le serveur (contenu jamais montré à personne d'autre).
  const ics = calendars.filter((c) => c.kind === 'ics' && c.visible);
  const icsEvents = await Promise.all(ics.map((c) => fetchIcs(c.id, from, to).catch((): IcsEvent[] => [])));
  ics.forEach((c, i) => {
    for (const ev of icsEvents[i]) {
      entries.push({ key: `x:${c.id}:${ev.uid}:${ev.starts_at}`, kind: 'ics', title: ev.title || 'Occupé', start: new Date(ev.starts_at),
        end: new Date(ev.ends_at), allDay: ev.all_day, source: `${c.name} · ajouté avec un lien`, color: calColor(c.color), place: ev.place,
        busy: ev.busy });
    }
  });
  // Calendriers de l'iPhone : affichés ici seulement, rien ne part (pont natif).
  const n = nativeAgenda();
  if (n && native === 'full') {
    try {
      const [cals, evs] = await Promise.all([n.calendars(), n.events(from.toISOString(), to.toISOString())]);
      const shown = new Map(cals.filter((c) => c.shown).map((c) => [c.id, c]));
      for (const ev of evs) {
        const c = shown.get(ev.calendarId);
        if (!c) continue;
        entries.push({ key: `d:${ev.id}:${ev.start}`, kind: 'device', title: ev.title || 'Occupé', start: new Date(ev.start), end: new Date(ev.end),
          allDay: !!ev.allDay, source: `${c.title} · iPhone`, color: ev.color || c.color, place: ev.location ?? null, busy: true });
      }
    } catch { /* L'iPhone ne répond pas : l'agenda Party reste lisible. */ }
  }
  entries.sort((a, b) => a.start.getTime() - b.start.getTime() || Number(b.allDay) - Number(a.allDay));
  return { entries, calendars, prefs, native };
}

/** Éléments qui touchent ce jour (journée entière ou heures qui le recoupent). */
export function entriesOn(entries: Entry[], key: DayKey): Entry[] {
  const a = zdate(key).getTime();
  const b = zdate(addDays(key, 1)).getTime();
  return entries.filter((e) => e.start.getTime() < b && e.end.getTime() > a);
}

/** Le soir (18 h – minuit) est-il libre ce jour-là ? (« 🌙 Soirée libre ») */
export function eveningFree(entries: Entry[], key: DayKey): boolean {
  const a = zdate(key, 18 * 60).getTime();
  const b = zdate(key, 24 * 60).getTime();
  return !entries.some((e) => e.busy && !e.allDay && e.start.getTime() < b && e.end.getTime() > a);
}

/** « ⚠️ En même temps que « Courses » » : le premier autre élément aux heures qui recoupent. */
export function overlapOf(e: Entry, all: Entry[]): Entry | null {
  if (e.allDay) return null;
  return all.find((o) => o !== e && !o.allDay && o.kind !== 'poll' && o.start < e.end && o.end > e.start) ?? null;
}

export async function savePrefs(patch: Prefs): Promise<void> {
  try { await rpc('agenda_prefs_save', { prefs: patch }); } catch { /* Préférence d'affichage : jamais bloquant. */ }
}

// ───────────── Pastille des demandes en attente ─────────────
/** Pastille « 1 » (demandes de rendez-vous en attente) : relue au signal `user:<id>` de la base, et toutes les 2 min. */
export function useAgendaBadge(me: string | null | undefined): number {
  const [pending, setPending] = useState(0);
  const [tick, setTick] = useState(0);
  useSignal(me ? [`user:${me}`] : [], () => setTick((n) => n + 1));
  useEffect(() => {
    if (!me) return undefined;
    let alive = true;
    void rpc<{ pending: number }>('agenda_badge').then((b) => { if (alive) setPending(Number(b?.pending) || 0); }).catch(() => undefined);
    const again = setTimeout(() => setTick((n) => n + 1), 120_000);
    return () => { alive = false; clearTimeout(again); };
  }, [me, tick]);
  return pending;
}

// ───────────── Partage des dispos et « Qui est libre ? » ─────────────
export type SharingGroup = { id: string; name: string; emoji: string; color: string; system: boolean; members: number; shared: boolean; consented_at: string | null };
export type Sharing = {
  share_party: boolean; share_manual: boolean; busy_updated_at: string | null; busy_count: number; links_active: number; groups: SharingGroup[];
};
export type FreeMember = { id: string; name: string; avatar_url: string | null; me: boolean; shares: boolean; updated_at?: string | null; busy?: [string, string][] };
export type GroupFree = {
  group: { id: string; name: string; emoji: string; color: string; system: boolean }; from: string; to: string; i_share: boolean; members: FreeMember[];
};

export type FreeMode = 'evening' | 'day';
/** Moments comparés (avis du 23.11) : le soir 18 h – 23 h (barre 18 h → minuit), la journée 8 h – 17 h (barre 8 h → 18 h). */
export const MODES: Record<FreeMode, { core: [number, number]; bar: [number, number]; whole: string; label: string; ticks: string[] }> = {
  evening: { core: [18 * 60, 23 * 60], bar: [18 * 60, 24 * 60], whole: 'toute la soirée', label: '18 h – 23 h', ticks: ['18 h', '21 h', '0 h'] },
  day: { core: [8 * 60, 17 * 60], bar: [8 * 60, 18 * 60], whole: 'toute la journée', label: '8 h – 17 h', ticks: ['8 h', '13 h', '18 h'] },
};

type Span = [number, number];
const spansOf = (m: FreeMember): Span[] => (m.busy ?? []).map(([s, e]) => [new Date(s).getTime(), new Date(e).getTime()]);

export type PersonState = { available: boolean; text: string; busyIn: Span[] };

/** Disponible ou Occupé ce soir-là, en mots (« Disponible dès 18 h 30 », « Occupé jusqu'à 21 h »). */
export function personState(m: FreeMember, key: DayKey, mode: FreeMode): PersonState {
  const cfg = MODES[mode];
  const cs = zdate(key, cfg.core[0]).getTime();
  const ce = zdate(key, cfg.core[1]).getTime();
  const bs = zdate(key, cfg.bar[0]).getTime();
  const be = zdate(key, cfg.bar[1]).getTime();
  const busyIn = spansOf(m).filter(([s, e]) => s < be && e > bs).map(([s, e]): Span => [Math.max(s, bs), Math.min(e, be)]);
  const inCore = busyIn.filter(([s, e]) => s < ce && e > cs);
  const t = (ms: number) => hText(new Date(ms));
  if (!inCore.length) {
    const before = busyIn.filter(([, e]) => e <= cs).reduce((x, [, e]) => Math.max(x, e), bs);
    const after = busyIn.filter(([s]) => s >= ce).reduce((x, [s]) => Math.min(x, s), be);
    const text = before > bs && after < be ? `Disponible de ${t(before)} à ${t(after)}`
      : before > bs ? `Disponible dès ${t(before)}`
      : after < be ? `Disponible jusqu’à ${t(after)}`
      : `Disponible ${cfg.whole}`;
    return { available: true, text, busyIn };
  }
  const covers = inCore.some(([s, e]) => s <= cs && e >= ce);
  if (covers) return { available: false, text: cfg.whole, busyIn };
  const first = inCore[0];
  const last = inCore[inCore.length - 1];
  const text = first[0] <= cs ? `jusqu’à ${t(Math.max(...inCore.filter(([s]) => s <= cs).map(([, e]) => e)))}`
    : last[1] >= ce ? `dès ${t(last[0])}`
    : `de ${t(first[0])} à ${t(first[1])}`;
  return { available: false, text, busyIn };
}

export type Candidate = { key: DayKey; free: number; sharing: number; start: Date; end: Date };

/** Soirs (ou journées) classés : le plus de personnes disponibles d'abord, puis le plus tôt. */
export function rankDays(data: GroupFree, mode: FreeMode, now = Date.now()): Candidate[] {
  const sharing = data.members.filter((m) => m.shares);
  if (!sharing.length) return [];
  const cfg = MODES[mode];
  const out: Candidate[] = [];
  let key = dayKey(new Date(data.from));
  const last = dayKey(new Date(data.to));
  for (let i = 0; i < 62 && key <= last; i++, key = addDays(key, 1)) {
    const start = zdate(key, cfg.core[0]);
    const end = zdate(key, cfg.core[1]);
    if (start.getTime() < now || end.getTime() > new Date(data.to).getTime()) continue;
    const free = sharing.filter((m) => personState(m, key, mode).available).length;
    out.push({ key, free, sharing: sharing.length, start, end });
  }
  return out.sort((a, b) => b.free - a.free || a.start.getTime() - b.start.getTime());
}

// ───────────── Liens de dispo ─────────────
export type FieldMode = 'off' | 'optional' | 'required';
export type BookingFields = { first_name: FieldMode; last_name: FieldMode; email: FieldMode; phone: FieldMode; message: FieldMode };
export type Rule = { days: number[]; from: string; to: string };
export type Link = {
  id: string; token: string; path: string; name: string; emoji: string | null; display_name: string | null; rules: Rule[];
  horizon_days: number; duration_min: number;
  /** Durées proposées (la personne qui réserve choisit) ; absent = la seule duration_min (liens d'avant). */
  durations?: number[];
  /** Délai minimum avant un rendez-vous, en minutes (0 = sur le moment ; 720 par défaut). */
  min_notice_min?: number;
  booking_enabled: boolean; booking_fields: BookingFields; message_label: string | null;
  status: 'active' | 'stopped' | 'expired'; expires_at: string | null; stopped_at: string | null; views: number; last_viewed_at: string | null;
  pending: number; created_at: string;
  /** Calendriers qui rendent occupé pour ce lien (id Party / agenda .ics, « ios:<id> ») ; null = tout (liens d'avant). */
  calendars: string[] | null;
  /** Sans fin : il ne s'arrête que quand on l'arrête. */
  permanent: boolean;
  /** Marges : pas disponible N minutes avant / après chaque rendez-vous (0 à 240). */
  buffer_before_min: number; buffer_after_min: number;
  /** Adresse lisible : nom du lien (« semaine ») et chemin complet (« /agenda/ludovic/semaine ») ; null sans adresse lisible. */
  slug: string | null; nice_path: string | null;
};
export type Links = { links: Link[]; max: number; missing: null | 'profile' | 'terms'; notify: boolean; pending: number; handle: string | null };

/** « Général · Après-midi » → « general-apres-midi » (lettres, chiffres, tirets ; `typing` garde le tiret final). */
export function slugify(text: string, max = 40, typing = false): string {
  const s = text.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+/, '').slice(0, max);
  return typing ? s : s.replace(/-+$/, '');
}

export const FIELD_LABELS: { key: keyof BookingFields; label: string }[] = [
  { key: 'first_name', label: 'Prénom' }, { key: 'last_name', label: 'Nom' }, { key: 'email', label: 'Adresse e-mail' },
  { key: 'phone', label: 'Téléphone' }, { key: 'message', label: 'Votre message' },
];
export const DEFAULT_FIELDS: BookingFields = { first_name: 'required', last_name: 'optional', email: 'required', phone: 'off', message: 'optional' };

export type Model = 'week' | 'evening' | 'weekend' | 'custom';
export const MODELS: { key: Model; emoji: string; name: string; hint: string; rules: Rule[] }[] = [
  { key: 'week', emoji: '💼', name: 'Jours de semaine', hint: 'Lun → ven · 9 h – 18 h', rules: [{ days: [1, 2, 3, 4, 5], from: '09:00', to: '18:00' }] },
  { key: 'evening', emoji: '🌆', name: 'Après le travail', hint: 'Lun → ven · 18 h – 23 h', rules: [{ days: [1, 2, 3, 4, 5], from: '18:00', to: '23:00' }] },
  { key: 'weekend', emoji: '🏖️', name: 'Week-end', hint: 'Sam, dim · 10 h – 23 h', rules: [{ days: [6, 7], from: '10:00', to: '23:00' }] },
  { key: 'custom', emoji: '✏️', name: 'Personnalisé', hint: 'Tes jours, tes heures', rules: [{ days: [1, 2, 3, 4], from: '18:00', to: '23:00' }] },
];

const hourWord = (t: string) => {
  const [h, m] = t.split(':').map(Number);
  return m ? `${h} h ${pad(m)}` : `${h} h`;
};

/** « Lun → ven · 9 h – 18 h » ; « Sam, dim · 10 h – 23 h ». */
export function rulesText(rules: Rule[]): string {
  return rules.map((r) => {
    const d = [...r.days].sort();
    const names = d.map((x) => cap(DAYS_SHORT[x - 1]).replace('.', ''));
    const run = d.length > 2 && d.every((x, i) => !i || x === d[i - 1] + 1);
    return `${run ? `${names[0]} → ${names[names.length - 1].toLowerCase()}` : names.join(', ')} · ${hourWord(r.from)} – ${hourWord(r.to)}`;
  }).join(' · ');
}

export function linkUrl(link: Pick<Link, 'path'> & { nice_path?: string | null }): string {
  // Jamais un domaine écrit en dur : l'adresse du site ouvert (PUBLIC_URL). L'adresse lisible d'abord, si elle existe.
  const origin = typeof location !== 'undefined' ? location.origin : '';
  return `${origin}${link.nice_path || link.path}`;
}

export type Booking = {
  id: string; link_id: string; link_name: string; link_emoji: string | null; starts_at: string; ends_at: string;
  status: 'pending' | 'accepted' | 'refused' | 'expired' | 'cancelled' | 'to_confirm'; created_at: string; expires_at: string | null;
  decided_at: string | null; item_id: string | null; first_name: string | null; last_name: string | null; email: string | null;
  phone: string | null; message: string | null; message_label: string | null; verified: boolean;
};

/** « encore 47 h » */
export function hoursLeft(iso: string | null, now = Date.now()): string {
  if (!iso) return '';
  const h = Math.max(0, Math.ceil((new Date(iso).getTime() - now) / 3600_000));
  return h <= 1 ? 'encore moins d’1 h' : `encore ${h} h`;
}

/**
 * Web : les agendas ajoutés avec un lien qui comptent (« comptent comme Occupé » pour les groupes, ou choisis par un lien
 * de dispo) envoient leurs heures prises, calendrier par calendrier (début et fin seulement, jamais titre ni lieu), par
 * `agenda_set_busy('web')`. Sans partage ni lien actif, la base refuse : rien ne part.
 */
export async function syncWebBusy(calendars?: Calendar[]): Promise<void> {
  const cals = calendars ?? await rpc<Calendar[]>('agenda_calendars_list');
  const links = await rpc<Links>('agenda_links').then((l) => l.links.filter((x) => x.status === 'active')).catch((): Link[] => []);
  const forLinks = new Set(links.flatMap((l) => l.calendars ?? []));
  const counted = cals.filter((c) => c.kind === 'ics' && (c.counts_busy || forLinks.has(c.id)));
  const from = new Date();
  const to = new Date(from.getTime() + 60 * 86400_000);
  const lists = await Promise.all(counted.map((c) => fetchIcs(c.id, from, to).catch((): IcsEvent[] => [])));
  const blocks = lists.flatMap((list, i) => list.filter((e) => e.busy)
    .map((e) => ({ s: e.starts_at, e: e.ends_at, c: counted[i].id, g: counted[i].counts_busy })));
  await rpc('agenda_set_busy', { source: 'web', blocks }).catch(() => undefined);
}

/** Après un changement des calendriers d'un lien : l'iPhone (ou le web) renvoie aussitôt ses plages « pris ». */
export async function syncBusyNow(): Promise<void> {
  const n = nativeAgenda();
  try {
    if (n) await n.syncBusy();
    else await syncWebBusy();
  } catch { /* Jamais bloquant : la prochaine ouverture renverra. */ }
}

/** À l'ouverture de l'agenda (une fois par visite) : les plages du web et de l'iPhone suivent, si le partage est actif. */
let synced = false;
export async function syncBusyOnOpen(): Promise<void> {
  if (synced) return;
  synced = true;
  try {
    const sharing = await rpc<Sharing>('agenda_sharing');
    if (!sharing.groups.some((g) => g.shared) && !sharing.links_active) return;
    const n = nativeAgenda();
    if (n) await n.syncBusy().catch(() => undefined);
    else await syncWebBusy();
  } catch { /* Jamais bloquant : la base garde le dernier envoi. */ }
}
