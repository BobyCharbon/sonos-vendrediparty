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
export async function settleNativeDates(ev: SettleEvent | null, eventId?: string): Promise<void> {
  const native = nativeCalendar();
  if (!native) return;
  try {
    if (!ev) {
      if (eventId) await native.settle({ eventId, cancelled: true });  // événement supprimé ou plus visible
      return;
    }
    if (ev.status === 'cancelled') await native.settle({ eventId: ev.id, cancelled: true });
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
    for (const id of ids) await settleNativeDates(rows.find((r) => r.id === id) ?? null, id);
  } catch { /* Hors ligne ou app plus ancienne : au prochain démarrage. */ }
}
