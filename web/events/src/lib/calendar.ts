import { Linking, Platform } from 'react-native';

import { supabase } from './supabase';
import type { EventRow } from './types';

type CalendarEvent = Pick<EventRow, 'id' | 'title' | 'description' | 'starts_at' | 'ends_at' | 'location_name' | 'location_address'>;
export type CalendarPlatform = 'ios' | 'android' | 'desktop';

const DEFAULT_DURATION = 3 * 3600_000;

/** iPhone, iPad (y compris iPadOS qui se présente comme un Mac tactile) ou Android. */
export function calendarPlatform(): CalendarPlatform {
  if (Platform.OS === 'ios') return 'ios';
  if (Platform.OS === 'android') return 'android';
  if (typeof navigator === 'undefined') return 'desktop';
  const ua = navigator.userAgent;
  if (/iPhone|iPad|iPod/i.test(ua) || (/Macintosh/i.test(ua) && navigator.maxTouchPoints > 1)) return 'ios';
  if (/Android/i.test(ua)) return 'android';
  return 'desktop';
}

const location = (ev: CalendarEvent) => [ev.location_name, ev.location_address].filter(Boolean).join(', ');
const end = (ev: CalendarEvent) => ev.ends_at ?? new Date(new Date(ev.starts_at!).getTime() + DEFAULT_DURATION).toISOString();
const pageUrl = (ev: CalendarEvent) => (typeof window !== 'undefined' ? `${window.location.origin}/events/event/${ev.id}` : '');

/** Fichier .ics servi par Party : iOS ouvre directement la feuille « Ajouter au calendrier ». */
export function icsUrl(ev: CalendarEvent): string | null {
  if (!ev.starts_at) return null;
  const q = new URLSearchParams({
    uid: ev.id,
    title: ev.title,
    start: ev.starts_at,
    end: end(ev),
    location: location(ev),
    description: (ev.description ?? '').slice(0, 1500),
    url: pageUrl(ev),
  });
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  return `${origin}/api/calendar.ics?${q.toString()}`;
}

type PollEvent = Pick<EventRow, 'id' | 'title' | 'description' | 'location_name' | 'location_address'>;
type ProposedDate = { id: string; starts_at: string; ends_at?: string | null };

/**
 * Sondage de dates (avis 9ddbdea7fe8f, 10.11) : toutes les dates proposées dans UN fichier .ics, chacune « À confirmer » ;
 * l’iPhone propose « Tout ajouter » en un toucher. Les dates déjà passées ne sont pas envoyées.
 */
export function pollDatesIcsUrl(ev: PollEvent, dates: ProposedDate[], now: number = Date.now()): string | null {
  const upcoming = upcomingDates(dates, now);
  if (!upcoming.length) return null;
  const q = new URLSearchParams({
    uid: ev.id,
    title: ev.title,
    location: location(ev as CalendarEvent),
    description: (ev.description ?? '').slice(0, 1500),
    url: typeof window !== 'undefined' ? `${window.location.origin}/events/event/${ev.id}` : '',
  });
  for (const d of upcoming) q.append('d', `${d.id}|${d.starts_at}|${d.ends_at ?? ''}`);
  const origin = typeof window !== 'undefined' ? window.location.origin : '';
  return `${origin}/api/calendar-dates.ics?${q.toString()}`;
}

/** Lien Google Agenda : Android l’ouvre dans l’application Google Agenda. */
export function googleCalendarUrl(ev: CalendarEvent): string | null {
  if (!ev.starts_at) return null;
  const stamp = (iso: string) => new Date(iso).toISOString().replace(/[-:]/g, '').replace(/\.\d{3}/, '');
  const details = [ev.description?.slice(0, 1500), pageUrl(ev)].filter(Boolean).join('\n\n');
  const q = new URLSearchParams({
    action: 'TEMPLATE',
    text: ev.title,
    dates: `${stamp(ev.starts_at)}/${stamp(end(ev))}`,
    details,
    location: location(ev),
    ctz: 'Europe/Zurich',
  });
  return `https://calendar.google.com/calendar/render?${q.toString()}`;
}

/**
 * Ouvre le fichier .ics au niveau de la fenêtre principale (le module tourne dans une iframe de Party) :
 * Safari iOS affiche alors l’événement avec « Ajouter », sans quitter la page.
 */
export function openIcs(url: string) {
  if (Platform.OS !== 'web' || typeof window === 'undefined') {
    void Linking.openURL(url);
    return;
  }
  try {
    (window.top ?? window).location.href = url;
  } catch {
    window.location.href = url;
  }
}

export function openGoogleCalendar(url: string) {
  if (Platform.OS === 'web' && typeof window !== 'undefined') {
    // Nouvel onglet : Android propose l’app Google Agenda, la page Party reste ouverte.
    const opened = window.open(url, '_blank');
    if (opened) opened.opener = null;
    else (window.top ?? window).location.href = url;
    return;
  }
  void Linking.openURL(url);
}

/** Calendrier natif de l'app iPhone (avis 9ddbdea7fe8f) ; null dans un navigateur. */
type NativeCalendar = {
  add(req: { eventId: string; title: string; location: string; notes: string; url: string;
    dates: { id: string; start: string; end: string }[] }): Promise<{ added?: number; total?: number; denied?: boolean }>;
  status(eventId: string): Promise<{ added: number }>;
  settle(req: { eventId: string; title?: string; start?: string | null; end?: string | null; cancelled?: boolean }): Promise<{ changed: boolean }>;
  pending(): Promise<string[]>;
};

export function nativeCalendar(): NativeCalendar | null {
  if (typeof window === 'undefined') return null;
  return (window as unknown as { PartyNative?: { calendar?: NativeCalendar } }).PartyNative?.calendar ?? null;
}

/** Dates à venir du sondage, au plus 20 (comme le fichier .ics). */
export function upcomingDates<T extends { starts_at: string }>(dates: T[], now: number = Date.now()): T[] {
  return dates.filter((d) => new Date(d.starts_at).getTime() > now).slice(0, 20);
}

type SettleEvent = Pick<EventRow, 'id' | 'title' | 'status' | 'date_mode' | 'starts_at' | 'ends_at'>;

/**
 * Date fixée (ou événement annulé) : l'app garde la bonne entrée sous le vrai titre et retire les autres dates
 * « À confirmer ». Sans app ou sans dates ajoutées : rien. Les erreurs n'empêchent jamais l'écran de s'afficher.
 */
export async function settleNativeDates(ev: SettleEvent | null, eventId?: string, declined = false): Promise<void> {
  const native = nativeCalendar();
  if (!native) return;
  try {
    if (!ev) {
      if (eventId) await native.settle({ eventId, cancelled: true });  // événement supprimé ou plus visible
      return;
    }
    // Annulé, ou « Non » à la date retenue : toutes ses dates partent de l'agenda.
    if (ev.status === 'cancelled' || (declined && ev.date_mode === 'fixed')) await native.settle({ eventId: ev.id, cancelled: true });
    else if (ev.date_mode === 'fixed' && ev.starts_at) await native.settle({ eventId: ev.id, title: ev.title, start: ev.starts_at, end: ev.ends_at });
  } catch { /* App plus ancienne ou calendrier inaccessible : on réessaiera au prochain passage. */ }
}

/**
 * Au démarrage (une fois par connexion) : les sondages dont l'app garde des dates « À confirmer » sont relus ; date
 * fixée ou événement annulé / disparu → l'app fait le ménage, même si la personne n'a pas rouvert la fiche.
 */
export async function sweepNativeCalendar(): Promise<void> {
  const native = nativeCalendar();
  if (!native) return;
  try {
    const ids = (await native.pending()).filter((id) => /^[0-9a-f-]{36}$/i.test(id)).slice(0, 50);
    if (!ids.length) return;
    const { data, error } = await supabase.from('events').select('id, title, status, date_mode, starts_at, ends_at').in('id', ids);
    if (error) return;
    const rows = (data ?? []) as SettleEvent[];
    const me = (await supabase.auth.getSession()).data.session?.user.id;
    const answers = me ? ((await supabase.from('rsvps').select('event_id, status').eq('user_id', me).in('event_id', ids)).data ?? []) : [];
    const declined = new Set(answers.filter((a) => a.status === 'no').map((a) => a.event_id as string));
    for (const id of ids) await settleNativeDates(rows.find((r) => r.id === id) ?? null, id, declined.has(id));
  } catch { /* Hors ligne ou app plus ancienne : au prochain démarrage. */ }
}

/**
 * Dates d'un sondage à mettre dans l'agenda (retour de l'admin du 11.11) : celles votées Oui ou Si besoin ; sans aucun
 * vote, toutes. À venir seulement, comme le calendrier abonné de la base (fonction calendar_feed).
 */
export function datesToAdd<T extends ProposedDate>(dates: T[], votes: Record<string, string | null | undefined>, now: number = Date.now()): T[] {
  const voted = dates.some((d) => votes[d.id]);
  return upcomingDates(voted ? dates.filter((d) => votes[d.id] === 'yes' || votes[d.id] === 'if_needed') : dates, now);
}

/**
 * Agendas proposés pour s'abonner (avis du 19.11 : sous Android, tout partait dans Google Agenda, que beaucoup n'utilisent
 * pas). `copy` : le lien à coller dans n'importe quel agenda (Samsung via l'app ICSx⁵).
 */
export type AgendaApp = 'apple' | 'google' | 'outlook' | 'copy';
export type AgendaVia = CalendarPlatform | AgendaApp;

export function agendaApps(platform: CalendarPlatform = calendarPlatform()): AgendaApp[] {
  return platform === 'android' ? ['google', 'outlook', 'copy'] : ['apple', 'google', 'outlook', 'copy'];
}

/** Adresse que l'agenda relit tout seul : Google et Outlook par leur page d'abonnement, l'iPhone et le Mac par webcal://. */
export function subscribeLink(token: string, origin: string, via: AgendaVia = calendarPlatform()): string {
  const https = `${origin.replace(/^webcal:/, 'https:')}/api/calendar-feed/${token}.ics`;
  const webcal = https.replace(/^https?:/, 'webcal:');
  if (via === 'android' || via === 'google') return `https://calendar.google.com/calendar/render?cid=${encodeURIComponent(webcal)}`;
  if (via === 'outlook') return `https://outlook.live.com/calendar/0/addfromweb?url=${encodeURIComponent(https)}&name=${encodeURIComponent('Vendredi Party')}`;
  if (via === 'copy') return https;
  return webcal;
}

/** Ouvre l'agenda choisi pour s'abonner (rien à ouvrir pour `copy` : l'écran copie le lien). */
export function openSubscription(token: string, via: AgendaVia) {
  if (via === 'copy') return;
  const url = subscribeLink(token, window.location.origin, via);
  if (url.startsWith('https:')) openGoogleCalendar(url);
  else openIcs(url);
}

/** Lien de l'agenda « Vendredi Party » sans événement (Réglages › Agenda Vendredi Party). */
export async function myAgendaLink(): Promise<{ token: string; subscribed: boolean } | null> {
  try {
    const { data, error } = await supabase.rpc('calendar_feed_link');
    const r = data as { token?: unknown; subscribed?: unknown } | null;
    if (error || !r || typeof r.token !== 'string' || !/^[0-9a-f]{36}$/.test(r.token)) return null;
    return { token: r.token, subscribed: r.subscribed === true };
  } catch {
    return null;
  }
}

/** Le calendrier « Vendredi Party » de la personne : son lien, s'il est déjà abonné (lu par un agenda) et si l'événement y est. */
export type AgendaLink = { token: string; subscribed: boolean; added: boolean };

/**
 * Demandé à l'avance (le toucher ouvre ensuite l'agenda sans attendre, sinon Safari peut le bloquer). Ne rien ajouter :
 * seul le toucher ajoute l'événement (add = true). Sans compte ou base injoignable : null (on garde l'ancien ajout).
 */
export async function agendaLink(eventId: string, add = false): Promise<AgendaLink | null> {
  try {
    const { data, error } = await supabase.rpc('calendar_feed_token', { e: eventId, add });
    const r = data as Partial<AgendaLink> | null;
    if (error || !r || typeof r.token !== 'string' || !/^[0-9a-f]{36}$/.test(r.token)) return null;
    return { token: r.token, subscribed: r.subscribed === true, added: r.added === true };
  } catch {
    return null;
  }
}

export type AddDatesResult = 'added' | 'subscribed' | 'copied' | 'native' | 'file' | 'denied';

/**
 * Ajout à l'agenda, partout la même méthode (retours de l'admin du 11.11) : l'événement entre dans le calendrier
 * « Vendredi Party » de la personne, que son agenda relit tout seul (date, lieu, titre, description modifiés suivent).
 * Première fois : l'agenda propose de s'abonner ; ensuite, rien à ouvrir. Sans lien : `fallback` (ancien ajout ponctuel).
 */
export async function addToAgenda(eventId: string, link: AgendaLink | null, fallback: () => Promise<AddDatesResult> | AddDatesResult,
  via: AgendaVia = calendarPlatform(), again = false): Promise<AddDatesResult> {
  if (!link) return fallback();
  // `again` : la personne dit que l'agenda n'est pas sur son téléphone (une lecture ne prouve pas l'abonnement).
  const open = !link.subscribed || again;
  if (open) openSubscription(link.token, via);
  const saved = await agendaLink(eventId, true);
  const done: AddDatesResult = via === 'copy' && open ? 'copied' : open ? 'subscribed' : 'added';
  if (!saved) return open ? done : fallback();
  // App iPhone : les dates déjà mises directement dans le calendrier feraient doublon avec l'agenda abonné.
  try { await nativeCalendar()?.settle({ eventId, cancelled: true }); } catch { /* app plus ancienne */ }
  return done;
}

/** Sondage : sans agenda abonné possible, l'app iPhone les met dans le calendrier ; sinon le fichier .ics, comme avant. */
export async function addPollDates(ev: PollEvent, dates: ProposedDate[], link?: AgendaLink | null, via?: AgendaVia, again = false): Promise<AddDatesResult> {
  return addToAgenda(ev.id, link ?? null, () => pollDatesOnce(ev, dates), via, again);
}

/** Sondage sans agenda abonné possible : l'app iPhone met les dates dans le calendrier, sinon le fichier .ics. */
export async function pollDatesOnce(ev: PollEvent, dates: ProposedDate[]): Promise<AddDatesResult> {
  {
    const native = nativeCalendar();
    if (native) {
      try {
        const r = await native.add({ eventId: ev.id, title: ev.title, location: location(ev as CalendarEvent),
          notes: (ev.description ?? '').slice(0, 1500), url: `${window.location.origin}/events/event/${ev.id}`,
          dates: dates.map((d) => ({ id: d.id, start: d.starts_at, end: d.ends_at ?? '' })) });
        return r.denied ? 'denied' : 'native';
      } catch { /* app plus ancienne : comme dans le navigateur */ }
    }
    const url = pollDatesIcsUrl(ev, dates);
    if (url) openIcs(url);
    return 'file';
  }
}
