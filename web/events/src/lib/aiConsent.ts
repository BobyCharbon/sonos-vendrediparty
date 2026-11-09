import { supabase } from './supabase';

/**
 * Accord « IA de Party » d'un compte (un seul pour « Ton avis », l'assistant des événements et les tickets), gardé par
 * le serveur Party (app/ai_feedback.ConsentBox). Réglages › Confidentialité le montre à TOUS les comptes et permet de
 * le retirer ou de le redonner (Apple 5.1.2(i), nLPD) : POST /api/account/ai/status et /api/account/ai/consent.
 */
export type AiConsentStatus = {
  /** « accepted », « declined » ou « » (jamais demandé, ou texte d'accord changé). */
  consent: string;
  /** Date de l'accord en cours (secondes) ; null sans accord. */
  consent_at: number | null;
};

/** Même texte que la feuille d'accord (version 2 : app/static/index.html #fbAiConsent, FeedbackAI.consentText d'iOS). */
export const AI_CONSENT_TEXT = 'Quand tu utilises l’IA, Party envoie ce que tu lui confies à Anthropic (Claude) : le texte de ton avis (et la transcription de ta voix) ; avec l’assistant des événements, ta description, tes captures d’écran, tes photos et les liens que tu donnes ; pour un ticket du pot commun, sa photo. Jamais ton numéro.';

const FALLBACK = 'L’accord pour l’IA n’a pas pu être lu. Vérifie ta connexion et réessaie.';

async function call(path: string, extra: Record<string, unknown> = {}): Promise<AiConsentStatus> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error('Ta connexion a expiré : reconnecte-toi puis réessaie.');
  const response = await fetch(path, {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, ...extra }),
  });
  const body = await response.json().catch(() => ({})) as Partial<AiConsentStatus> & { detail?: unknown };
  if (!response.ok) throw new Error(typeof body.detail === 'string' && body.detail ? body.detail : FALLBACK);
  return { consent: typeof body.consent === 'string' ? body.consent : '',
    consent_at: typeof body.consent_at === 'number' ? body.consent_at : null };
}

export function aiConsentStatus(): Promise<AiConsentStatus> {
  return call('/api/account/ai/status');
}

export function setAiConsent(accept: boolean): Promise<AiConsentStatus> {
  return call('/api/account/ai/consent', { accept });
}

/** « Accord donné le 9 novembre 2026 » ou « Pas d'accord » (jamais donné, refusé ou retiré). */
export function aiConsentLabel(status: AiConsentStatus): string {
  if (status.consent !== 'accepted') return 'Pas d’accord : l’IA n’est jamais utilisée pour toi.';
  if (!status.consent_at) return 'Accord donné.';
  const day = new Date(status.consent_at * 1000).toLocaleDateString('fr-CH', { day: 'numeric', month: 'long', year: 'numeric' });
  return `Accord donné le ${day}.`;
}
