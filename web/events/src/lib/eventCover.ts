import { supabase } from './supabase';

/**
 * Couverture d'un événement changée après coup (25.11) : tout passe par le serveur Party (app/event_covers.py), qui
 * vérifie les droits (comme « Modifier »), télécharge et réencode toute image (EXIF et GPS retirés) puis écrit dans la
 * base avec le jeton de la personne. L'app ne choisit une photo proposée que par son numéro (`pick`), jamais par une adresse.
 */
export type Suggested = { pick: string; thumb: string; credit: string; alt: string };
export type Suggestions = { photos: Suggested[]; ai: boolean; ai_note: '' | 'consent' | 'off'; source: 'pexels' | 'openverse' };
export type Official = { found: true; pick: string; thumb: string; domain: string; page: string; title: string } | { found: false; message: string };
export type Saved = { cover_url: string | null; cover_credit: string | null; cover_credit_url: string | null; status: string };

/** Refus du serveur : `code` vaut « terms_required » quand les CGU doivent d'abord être acceptées. */
export class CoverError extends Error {
  code: string;
  constructor(message: string, code = '') {
    super(message);
    this.code = code;
  }
}

async function call<T>(path: string, body: Record<string, unknown>): Promise<T> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new CoverError('Ta connexion a expiré : reconnecte-toi puis réessaie.');
  let r: Response;
  try {
    r = await fetch(`/api/account/event-cover/${path}`, {
      method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, ...body }),
    });
  } catch {
    throw new CoverError('La connexion a échoué. Vérifie ton réseau puis réessaie.');
  }
  const out = (await r.json().catch(() => ({}))) as { detail?: unknown; code?: string };
  if (!r.ok) {
    const text = typeof out.detail === 'string' && out.detail ? out.detail : 'Ça n’a pas marché. Réessaie dans un instant.';
    throw new CoverError(text, out.code ?? '');
  }
  return out as T;
}

export const isTerms = (e: unknown) => e instanceof CoverError && e.code === 'terms_required';
export const errorText = (e: unknown) => (e instanceof Error ? e.message : 'Ça n’a pas marché. Réessaie dans un instant.');

/** Photo recadrée (objet blob: du recadrage) → envoyée en base64. */
export async function uploadCover(eventId: string, uri: string): Promise<Saved> {
  const blob = await fetch(uri).then((r) => r.blob()).catch(() => null);
  if (!blob) throw new CoverError('La photo n’a pas pu être lue. Choisis-la à nouveau.');
  const photo = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new CoverError('La photo n’a pas pu être lue. Choisis-la à nouveau.'));
    reader.readAsDataURL(blob);
  });
  return call<Saved>('photo', { event_id: eventId, photo });
}

export const suggestCovers = (eventId: string) => call<Suggestions>('suggest', { event_id: eventId });
export const officialCover = (eventId: string) => call<Official>('official', { event_id: eventId });
/** Événement supprimé : le serveur efface sa couverture (s'il ne le voit plus) ; un échec ne gêne jamais la suppression. */
export const coverDeleted = (eventId: string) => call<{ removed: number }>('deleted', { event_id: eventId }).catch(() => undefined);
export const chooseCover = (eventId: string, pick: string) => call<Saved>('choose', { event_id: eventId, pick });
export const posterCover = (eventId: string) => call<Saved>('poster', { event_id: eventId });
export const removeCover = (eventId: string) => call<Saved>('remove', { event_id: eventId });

/** « Visuel : domaine » ou « Photo : Nom / Pexels » : seulement un lien https (jamais javascript: ni data:). */
export const creditHref = (url: string | null | undefined) => (url && /^https:\/\//.test(url) ? url : undefined);

// Didacticiel (bulle « Nouveau ») : une seule fois par appareil, comme celui des Souvenirs.
const TIP_KEY = 'party-cover-tip-off';
export function coverTipSeen(): boolean {
  try { return localStorage.getItem(TIP_KEY) === '1'; } catch { return true; }
}
export function hideCoverTip() {
  try { localStorage.setItem(TIP_KEY, '1'); } catch { /* sans stockage : fermée pour cette page */ }
}
