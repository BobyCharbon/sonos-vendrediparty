import { supabase } from './supabase';

/**
 * Souvenirs (avis 74d36b93e7bd, 24.11.2026, migration 20261124090000) : l'appareil jetable de la soirée (3 poses, jamais
 * revues), dévoilé en story de 24 h, puis « Mes souvenirs » (13 mois) si l'organisation a laissé l'enregistrement.
 * Tout passe par le relais du serveur Party (`POST /api/account/souvenirs/rpc`, liste blanche) : les fichiers sont sur
 * son disque ; il donne pour chaque photo que la base me laisse voir un lien court signé (`url` = écran 2048 px,
 * `original` = pleine résolution 7 jours) et signe chaque visage. La base décide de tout ; ces fonctions ne font que l'appeler.
 * Dans l'app iPhone, appareil photo, story et Photothèque sont NATIFS (`window.PartyNative.souvenirs`, voir
 * scratchpad pont-ios.md) ; l'app rappelle `window.PartySouvenirs.changed(eventId)` quand elle a fini.
 */

export type Phase = 'off' | 'soon' | 'open' | 'waiting' | 'story' | 'after';

/** souvenir_counter : le NOMBRE de photos seulement (jamais qui ni quoi). */
export type Counter = {
  enabled: boolean; keep?: boolean; locked?: boolean; phase?: Phase; count?: number;
  take_from?: string | null; take_until?: string | null; reveal_at?: string | null; story_until?: string | null;
  can_reveal_now?: boolean; member?: boolean; staff?: boolean; max?: number; taken?: number; left?: number;
  can_take?: boolean; seen?: boolean;
};
export type Author = { id: string; name: string; avatar_url: string | null; photo?: string | null };
export type Photo = {
  id: string; event_id: string; path: string; taken_at: string; mine: boolean; author: Author | null;
  /** Version écran (2048 px), lien signé par le serveur Party (~10 min) ; null si la base ne la montre plus. */
  url: string | null;
  /** L'original (7 jours, puis 2560 px) : « Enregistrer » et téléchargement. */
  original?: string | null;
  origin?: 'taken' | 'kept'; kept?: boolean; can_keep?: boolean; hidden_at?: string | null;
  /** Relecture : motifs des signalements ouverts (jamais qui a signalé). */
  reasons?: string[] | null;
  /** Relecture : false = « Remettre » refusé par la base (ma photo, ou « Je suis sur la photo » : la modération décide). */
  can_restore?: boolean;
};
export type Story = { event_id: string; title: string; keep: boolean; until: string; photos: Photo[] };
export type Mine = { keep: boolean; phase: Phase; photos: Photo[] };
export type Review = { phase: Phase; photos: Photo[]; reported: Photo[] };

export const MAX_POSES = 3;
/** Annuler la photo prise : 5 s à l'écran (8 s en base, pour le réseau). */
export const CANCEL_SECONDS = 5;

/** Refus de la base ou du serveur : `code` garde la clé (terms_required, profile_required, closed, full…). */
export class SouvenirError extends Error {
  code: string;
  constructor(code: string, message: string) {
    super(message);
    this.code = code;
  }
}
export const isTermsRefusal = (e: unknown) => e instanceof SouvenirError && e.code === 'terms_required';
export const errorText = (e: unknown) => (e instanceof Error ? e.message : 'Ça n’a pas marché. Réessaie dans un instant.');

const NETWORK = 'La connexion a échoué. Vérifie ton réseau puis réessaie.';

async function sessionToken(): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new SouvenirError('auth', 'Ta connexion a expiré. Reconnecte-toi.');
  return token;
}

/** Réponse d'erreur du serveur : {code, detail} (refus de la base) ou {detail} (FastAPI). */
async function refusalOf(r: Response): Promise<SouvenirError> {
  let body: { code?: string; detail?: unknown } = {};
  try { body = await r.json(); } catch { /* corps vide : phrase générique */ }
  const detail = typeof body.detail === 'string' && body.detail.trim() ? body.detail.trim()
    : r.status >= 500 ? 'Le serveur ne répond pas. Réessaie dans un instant.' : 'Ça n’a pas marché. Réessaie dans un instant.';
  const text = detail.charAt(0).toUpperCase() + detail.slice(1);
  return new SouvenirError(body.code ?? (r.status === 401 ? 'auth' : 'error'), text);
}

/** Une fonction souvenir_* (ou report_content « souvenir ») par le relais du serveur. */
export async function souvenirCall<T>(fn: string, args: Record<string, unknown>): Promise<T> {
  const token = await sessionToken();
  let r: Response;
  try {
    r = await fetch('/api/account/souvenirs/rpc', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin',
      body: JSON.stringify({ token, fn, args }),
    });
  } catch {
    throw new SouvenirError('network', NETWORK);
  }
  if (!r.ok) throw await refusalOf(r);
  const body = (await r.json()) as { result: T };
  return body.result;
}

export const fetchCounter = (eventId: string) => souvenirCall<Counter>('souvenir_counter', { e: eventId });
export const fetchStory = (eventId: string) => souvenirCall<Story>('souvenir_story', { e: eventId });
export const fetchMine = (eventId: string) => souvenirCall<Mine>('souvenir_mine', { e: eventId });
export const fetchReview = (eventId: string) => souvenirCall<Review>('souvenir_review', { e: eventId });
export const markSeen = (eventId: string) => souvenirCall('souvenir_mark_seen', { e: eventId });
export const cancelPhoto = (id: string) => souvenirCall<{ cancelled: boolean; left: number }>('souvenir_cancel', { id });
export const deletePhoto = (id: string) => souvenirCall('souvenir_delete', { id });
export const removePhoto = (id: string) => souvenirCall('souvenir_remove', { id });
export const restorePhoto = (id: string) => souvenirCall('souvenir_restore', { id });
export const keepPhoto = (id: string) => souvenirCall('souvenir_keep', { id });
export const unkeepPhoto = (id: string) => souvenirCall('souvenir_unkeep', { id });
export const revealNow = (eventId: string) => souvenirCall<Counter>('souvenir_reveal_now', { e: eventId });

/** « Signaler » une photo : masquée aussitôt pour tous ; l'organisation et la modération de Party sont prévenues. */
/** Liens des photos signalées (écran Signalements de la modération) : le serveur demande d'abord à la base. */
export async function souvenirLinks(paths: string[]): Promise<Map<string, string>> {
  if (!paths.length) return new Map();
  const token = await sessionToken();
  const r = await fetch('/api/account/souvenirs/links', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, credentials: 'same-origin', body: JSON.stringify({ token, paths }),
  });
  if (!r.ok) return new Map();
  return new Map(Object.entries(((await r.json()) as { links: Record<string, string> }).links ?? {}));
}

export function reportPhoto(id: string, reason: string, comment: string) {
  return souvenirCall('report_content', { p_kind: 'souvenir', p_target: id, p_reason: reason, p_comment: comment.trim() || null });
}

/** Envoi trop long (réseau d'une cave, d'un sous-sol) : on arrête au bout de 60 s (photo pleine résolution), la même
 *  photo peut repartir. */
export const UPLOAD_TIMEOUT_MS = 60_000;
const SLOW = 'L’envoi prend trop de temps : le réseau est faible. Ta photo n’est pas partie ; touche « Réessayer ».';

/** Envoie la photo TELLE QUELLE (jamais réduite dans le navigateur : l'original est gardé 7 jours) ; le serveur retire
 *  GPS et numéros de série, fait la version écran, puis souvenir_take (la base décide). Code `timeout` après le délai,
 *  `network` sans réseau : la même photo peut repartir (« Réessayer »). */
export async function uploadPhoto(eventId: string, file: Blob): Promise<{ id: string; left: number; taken: number }> {
  const token = await sessionToken();
  const body = file;
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), UPLOAD_TIMEOUT_MS);
  let r: Response;
  try {
    r = await fetch(`/api/account/souvenirs/photo?event_id=${encodeURIComponent(eventId)}`, {
      method: 'POST', headers: { Authorization: `Bearer ${token}`, 'Content-Type': body.type || 'application/octet-stream' },
      credentials: 'same-origin', body, signal: stop.signal,
    });
  } catch {
    throw stop.signal.aborted ? new SouvenirError('timeout', SLOW) : new SouvenirError('network', NETWORK);
  } finally {
    clearTimeout(timer);
  }
  if (!r.ok) throw await refusalOf(r);
  return (await r.json()) as { id: string; left: number; taken: number };
}
/** Refus qu'un nouvel essai avec la même photo peut régler (réseau, délai, serveur occupé). */
export const canRetry = (e: unknown) => e instanceof SouvenirError && (e.code === 'network' || e.code === 'timeout' || e.code === 'error');

// ───────────── Pont iPhone (facultatif) ─────────────
type NativeSouvenirs = { camera?: (eventId: string) => unknown; story?: (eventId: string) => unknown; save?: (url: string) => unknown };

/** Le pont de l'app iPhone, s'il existe (navigateur : null, la page fait tout elle-même). */
export function nativeSouvenirs(): NativeSouvenirs | null {
  const n = (globalThis as { PartyNative?: { souvenirs?: NativeSouvenirs } }).PartyNative?.souvenirs;
  return n && typeof n === 'object' ? n : null;
}

/** Lien de téléchargement (serveur Party : `download` = pièce jointe, avec ce nom). */
export function downloadUrl(url: string, name: string): string {
  return `${url}${url.includes('?') ? '&' : '?'}download=${encodeURIComponent(name)}`;
}

// ───────────── Textes ─────────────
const TZ = 'Europe/Zurich';
const whenFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'short', day: '2-digit', month: '2-digit' });
const hourFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, hour: 'numeric', minute: '2-digit' });
const clockFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
const dateFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric' });

/** « sam. 21.11 » (fr-CH écrit « sam., 21.11. ») */
const dayOf = (d: Date) => whenFmt.format(d).replace(',', '').replace(/\.$/, '');

/** « sam. 21.11 à 23 h » / « sam. 21.11 à 23 h 30 » (la maquette). */
export function revealWhen(iso: string): string {
  const d = new Date(iso);
  const [h, m] = hourFmt.format(d).split(/[:h ]+/).filter(Boolean);
  return `${dayOf(d)} à ${Number(h)} h${m && m !== '00' ? ` ${m}` : ''}`;
}
/** « ven. 20.11 · 21:15 » : le moment d'une photo. */
export const photoWhen = (iso: string) => `${dayOf(new Date(iso))} · ${clockFmt.format(new Date(iso))}`;
export const shortDate = (iso: string) => dateFmt.format(new Date(iso));

/** « 13 h 30 », « 42 min », « 1 j 3 h » : le temps qui reste. */
export function remaining(until: string | null | undefined, now = Date.now()): string {
  if (!until) return '';
  const ms = Math.max(0, new Date(until).getTime() - now);
  const min = Math.ceil(ms / 60_000);
  if (min < 60) return `${min} min`;
  const h = Math.floor(min / 60);
  if (h < 24) return `${h} h ${String(min % 60).padStart(2, '0')}`;
  return `${Math.floor(h / 24)} j ${h % 24} h`;
}
/** « 23 h » : les heures entières qui restent (au moins 1). */
export const hoursLeft = (until: string, now = Date.now()) => Math.max(1, Math.ceil((new Date(until).getTime() - now) / 3_600_000));

export const posesLabel = (n: number) => `${n} ${n > 1 ? 'poses' : 'pose'}`;

/** Avis de la fiche, sous le titre « 📸 Souvenirs actif » : court, et dit que l'organisation peut voir les photos avant. */
export function noticeText(c: Counter): string {
  const when = c.reveal_at ? ` ${revealWhen(c.reveal_at)}` : '';
  return `3 photos chacun, dévoilées à tous${when} pendant 24 h. L’organisation peut les voir avant.`
    + (c.keep === false ? ' Effacées après la story : personne ne les garde.' : '');
}

/** Motifs de « Signaler une photo » (maquette v2) ; my_image = le droit à l'image. */
export const PHOTO_REASONS = [
  { key: 'my_image', label: 'Je suis sur la photo et je ne veux pas qu’elle soit montrée', hint: 'Droit à l’image' },
  { key: 'shocking', label: 'Choquante ou sexuelle', hint: 'Haine, violence, contenu sexuel' },
  { key: 'harassment', label: 'Moquerie ou harcèlement', hint: 'Pour se moquer de quelqu’un' },
  { key: 'other', label: 'Autre chose', hint: 'Explique en quelques mots' },
] as const;
export const PHOTO_REPORT_THANKS = 'Merci. La photo est masquée ; l’organisation et la modération de Party sont prévenues.';
export const reasonLabel = (key: string) => PHOTO_REASONS.find((r) => r.key === key)?.label
  ?? ({ spam: 'Spam', scam: 'Arnaque ou vente', money: 'Demande d’argent' } as Record<string, string>)[key] ?? key;

// ───────────── window.PartySouvenirs.changed(eventId) ─────────────
const listeners = new Map<string, Set<() => void>>();

/** L'app iPhone (appareil photo ou story natifs refermés) rappelle `window.PartySouvenirs.changed(eventId)` : chaque carte
 *  Souvenirs de cet événement relit son état (souvenir_counter). Sans identifiant : toutes. Renvoie le désabonnement. */
export function onSouvenirsChanged(eventId: string, reload: () => void): () => void {
  if (typeof window !== 'undefined') {
    (window as { PartySouvenirs?: { changed: (id?: string) => void } }).PartySouvenirs = {
      changed(id?: string) {
        for (const [key, set] of listeners) if (!id || key === String(id).toLowerCase()) set.forEach((fn) => fn());
      },
    };
  }
  const key = eventId.toLowerCase();
  const set = listeners.get(key) ?? new Set();
  set.add(reload);
  listeners.set(key, set);
  return () => {
    set.delete(reload);
    if (!set.size) listeners.delete(key);
  };
}
