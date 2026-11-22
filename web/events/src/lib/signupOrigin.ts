import { supabase } from '@/lib/supabase';

/**
 * Origine des inscriptions (avis 01da90202166, 22.11) : à la connexion, la base note la plateforme (app iPhone ou site)
 * et, venu du lien public « Partager » d'un événement, cet événement. Sans effet pour un compte de plus de 24 h. Les liens
 * d'invitation (événement, groupe, lien personnel) sont notés par la base elle-même, quand on y répond.
 * Le lien « Partager » ouvert avant la connexion est gardé dans l'onglet 10 minutes au plus.
 */
const KEY = 'party-signup-share';
const MAX_AGE_MS = 10 * 60 * 1000;

export function rememberSharedEvent(id: string, now: number = Date.now()): void {
  try { sessionStorage.setItem(KEY, JSON.stringify({ id, at: now })); } catch { /* Stockage indisponible. */ }
}

export function sharedEvent(now: number = Date.now()): string | null {
  try {
    const saved = JSON.parse(sessionStorage.getItem(KEY) ?? '{}') as { id?: unknown; at?: unknown };
    const fresh = typeof saved.at === 'number' && now - saved.at >= 0 && now - saved.at < MAX_AGE_MS;
    return fresh && typeof saved.id === 'string' ? saved.id : null;
  } catch {
    return null;
  }
}

export function signupPlatform(): 'ios' | 'web' {
  return typeof window !== 'undefined' && (window as Window & { PartyNative?: unknown }).PartyNative ? 'ios' : 'web';
}

/** Après la connexion par SMS : jamais bloquant (la connexion a déjà réussi). */
export async function noteSignup(): Promise<void> {
  try {
    await supabase.rpc('note_signup', { platform: signupPlatform(), shared_event: sharedEvent() });
    sessionStorage.removeItem(KEY);
  } catch { /* Rien à faire : la note n'est qu'une mesure. */ }
}
