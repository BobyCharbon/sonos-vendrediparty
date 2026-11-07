import { isNetworkError } from './errors';

/** Erreurs de la connexion par SMS (Supabase Auth, en anglais) en phrases claires (campagne 2, 07.11 : « HTTP 504 »,
 * « For security purposes, you can only request this after 0 seconds. » s'affichaient tels quels ; hors ligne, le bon
 * code donnait « Code incorrect ou expiré »). */

type AuthFailure = { message?: string | null; status?: number | null; code?: string | null; name?: string | null } | null | undefined;
export type AuthStep = 'send' | 'verify';

export const OFFLINE = 'Pas de connexion. Vérifie ton réseau puis réessaie.';
const UNAVAILABLE = 'Le service de connexion ne répond pas pour l’instant. Réessaie dans un instant.';
const TOO_MANY = 'Trop de demandes de code. Réessaie dans quelques minutes.';
const BAD_CODE = 'Code incorrect ou expiré.';
const BAD_PHONE = 'Ce numéro n’est pas valide. Vérifie-le puis réessaie.';
const FALLBACK: Record<AuthStep, string> = {
  send: 'Le code n’a pas pu être envoyé. Réessaie dans une minute.',
  verify: 'La connexion n’a pas pu se faire. Réessaie.',
};

function offline(error: NonNullable<AuthFailure>): boolean {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
  return error.name === 'AuthRetryableFetchError' && !error.status || isNetworkError(error.message ?? '');
}

/** Phrase à afficher pour une erreur de signInWithOtp (send) ou verifyOtp (verify). */
export function authErrorMessage(error: AuthFailure, step: AuthStep): string {
  if (!error) return FALLBACK[step];
  const message = error.message ?? '';
  if (offline(error)) return OFFLINE;
  const wait = /only request this after (\d+) seconds?/i.exec(message);
  if (wait) {
    const seconds = Number(wait[1]);
    return seconds > 1 ? `Attends ${seconds} secondes avant de redemander un code.` : 'Attends quelques secondes avant de redemander un code.';
  }
  if (error.status === 429 || /rate limit|too many/i.test(message) || /rate_limit/.test(error.code ?? '')) return TOO_MANY;
  if ((error.status ?? 0) >= 500 || /HTTP 5\d\d|timeout|timed out|gateway/i.test(message)) return UNAVAILABLE;
  if (step === 'verify' && (/expired|invalid|otp/i.test(message) || /otp_expired|invalid/.test(error.code ?? '') || error.status === 403 || error.status === 401)) return BAD_CODE;
  if (step === 'send' && /phone|number/i.test(message)) return BAD_PHONE;
  return FALLBACK[step];
}
