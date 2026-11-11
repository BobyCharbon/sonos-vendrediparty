/**
 * Proposer les notifications à qui a installé Party en app web (retour de l'admin du 11.11.2026) : des amis l'ont mise
 * sur l'écran d'accueil (Safari iPhone, Android) sans jamais aller les activer dans Réglages. Une petite fenêtre le
 * propose, dans le module Événements seulement (pas dans Musique ni Jeux). iPhone : la demande système n'est permise
 * qu'en app web installée et sur un toucher : la fenêtre a donc son bouton « Activer ».
 */
import { insideInstalledApp } from './installPrompt';

const KEY = 'vp_push_invite';
export const LATER_DAYS = 7;
export const MAX_ASKS = 3;

type Memory = { asks: number; last: number };

function read(): Memory {
  try {
    const raw = JSON.parse(localStorage.getItem(KEY) ?? 'null') as Partial<Memory> | null;
    return { asks: Number(raw?.asks) || 0, last: Number(raw?.last) || 0 };
  } catch {
    return { asks: 0, last: 0 };
  }
}

/** « Plus tard » : on redemande dans une semaine, au plus 3 fois en tout. */
export function rememberAsked(now: number = Date.now()) {
  const m = read();
  try { localStorage.setItem(KEY, JSON.stringify({ asks: m.asks + 1, last: now })); } catch { /* navigation privée */ }
}

/** Écrans du module où la fenêtre peut s'ouvrir : la liste et la fiche d'un événement (jamais Réglages, connexion…). */
export function isEventsScreen(path: string): boolean {
  return path === '/' || /^\/event\/[0-9a-f-]{36}$/i.test(path);
}

/** Onglet affiché dans la page Party autour du module (le même cadre sert aussi à Réglages). */
export function partyTab(): string | null {
  try {
    if (window.parent === window) return 'events';  // module ouvert seul : c'est la page Événements
    return window.parent.document.body.dataset.tab ?? null;
  } catch {
    return null;
  }
}

type Situation = {
  installedWebApp: boolean;  // app web sur l'écran d'accueil (pas l'app iPhone native, qui a ses propres notifications)
  supported: boolean;
  permission: NotificationPermission | 'unavailable';
  memory: Memory;
  now: number;
};

/** Faut-il proposer les notifications maintenant ? Jamais si déjà décidé (autorisées ou refusées dans le système). */
export function shouldInvite(s: Situation): boolean {
  if (!s.installedWebApp || !s.supported || s.permission !== 'default') return false;
  if (s.memory.asks >= MAX_ASKS) return false;
  return !s.memory.last || s.now - s.memory.last >= LATER_DAYS * 86_400_000;
}

function nativeApp(): boolean {
  const has = (w: Window | null | undefined) => !!(w as (Window & { PartyNative?: unknown }) | null | undefined)?.PartyNative;
  try { return has(window) || has(window.parent); } catch { return has(window); }
}

export function currentSituation(now: number = Date.now()): Situation {
  if (typeof window === 'undefined') return { installedWebApp: false, supported: false, permission: 'unavailable', memory: { asks: 0, last: 0 }, now };
  const supported = window.isSecureContext && 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  return {
    installedWebApp: !nativeApp() && insideInstalledApp(),
    supported,
    permission: supported ? Notification.permission : 'unavailable',
    memory: read(),
    now,
  };
}
