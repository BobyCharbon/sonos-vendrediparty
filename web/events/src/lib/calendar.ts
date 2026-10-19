import { Linking, Platform } from 'react-native';

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
