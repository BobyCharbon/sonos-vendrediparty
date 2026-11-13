/**
 * Bandeau « Active les notifications » en haut d'un événement (avis c77d117ab172, 13.11) : beaucoup n'ont jamais activé
 * les notifications sans le savoir. Le bandeau voit l'état réel de CET appareil (app iPhone : réglage d'iOS ; web :
 * Web Push de ce navigateur) et propose de les activer ; refusées : comment les rallumer.
 */
import { enableWebPush, webPushState } from './push';

export type NotifyState = 'on' | 'off' | 'denied' | 'install' | 'unsupported';

type NativePush = { status: () => Promise<{ status: string }>; enable: () => Promise<{ status: string }> };

const KEY = 'vp_notify_banner_later';
export const LATER_HOURS = 24;

function nativePush(): NativePush | null {
  const find = (w: Window | null | undefined) =>
    (w as (Window & { PartyNative?: { push?: Partial<NativePush> } }) | null | undefined)?.PartyNative?.push ?? null;
  let push: Partial<NativePush> | null = null;
  try { push = find(window) ?? find(window.parent); } catch { push = find(window); }
  return push?.status && push.enable ? (push as NativePush) : null;
}

const fromNative = (status: string): NotifyState => (status === 'granted' ? 'on' : status === 'denied' ? 'denied' : 'off');

export async function notifyState(): Promise<NotifyState> {
  const native = nativePush();
  if (native) return fromNative((await native.status()).status);
  const web = await webPushState();
  if (web.subscribed) return 'on';
  if (web.needsInstall) return 'install';
  if (!web.supported) return 'unsupported';
  return web.permission === 'denied' ? 'denied' : 'off';
}

/** « Activer » : la demande du système, dans le geste. App iPhone refusée avant : ouvre les Réglages d'iOS. */
export async function enableNotifications(): Promise<NotifyState> {
  const native = nativePush();
  if (native) return fromNative((await native.enable()).status);
  return (await enableWebPush()).subscribed ? 'on' : 'off';
}

export const isNativeApp = () => !!nativePush();

/** « Plus tard » : caché 24 h, puis il revient (l'admin veut qu'on s'en rende compte). */
export function laterUntil(now: number = Date.now()): void {
  try { localStorage.setItem(KEY, String(now + LATER_HOURS * 3_600_000)); } catch { /* navigation privée */ }
}

export function hiddenForNow(now: number = Date.now()): boolean {
  try { return Number(localStorage.getItem(KEY) || 0) > now; } catch { return false; }
}

/** Le bandeau se montre-t-il ? Seulement quand c'est éteint (ou bloqué) et qu'on peut y faire quelque chose. */
export function shouldShow(state: NotifyState | null, hidden: boolean): boolean {
  return !hidden && (state === 'off' || state === 'denied');
}
