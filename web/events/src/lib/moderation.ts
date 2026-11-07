import { useCallback, useEffect, useState } from 'react';

import { supabase } from './supabase';

/** Modération commune à toute l'app (4.11, Apple 1.2 / Google UGC) : Signaler, blocage, conditions d'utilisation.
 * La base décide de tout (filtre, droits, limites) ; ces fonctions ne font que l'appeler. */

export type ReportKind = 'group_message' | 'direct_message' | 'event_message' | 'profile' | 'profile_photo' | 'event'
  | 'rsvp_note' | 'poll' | 'poll_option' | 'bring_item'
  | 'pet_name' | 'pet_item' | 'pet_offer' | 'pet_showcase' | 'pet_word';
export type ReportReason = 'harassment' | 'shocking' | 'spam' | 'scam' | 'other';
export type ReportTarget = { kind: ReportKind; id: string; label: string };

export const REPORT_REASONS: { key: ReportReason; label: string; hint: string }[] = [
  { key: 'harassment', label: 'Harcèlement', hint: 'Insultes, menaces, moqueries répétées' },
  { key: 'shocking', label: 'Contenu choquant', hint: 'Haine, violence, contenu sexuel' },
  { key: 'spam', label: 'Spam', hint: 'Messages en masse, publicité' },
  { key: 'scam', label: 'Arnaque ou vente', hint: 'Demande d’argent, vente d’objets du jeu' },
  { key: 'other', label: 'Autre', hint: 'Explique en quelques mots' },
];

export const TERMS_PATH = '/terms';

/** Phrase d'une erreur de la base, sans sa clé technique (« content_refused: Message non envoyé… »). */
export function dbMessage(message: string | undefined | null, fallback: string): string {
  const text = (message ?? '').trim();
  const known = /^(content_refused|terms_required|terms_version|blocked|forbidden|rate_limited|not_found|self|reason|days): /;
  return known.test(text) ? text.replace(known, '') : fallback;
}

export function isTermsError(message: string | undefined | null): boolean {
  return (message ?? '').startsWith('terms_required');
}

export async function reportContent(target: ReportTarget, reason: ReportReason, comment: string): Promise<void> {
  const { error } = await supabase.rpc('report_content', {
    p_kind: target.kind, p_target: target.id, p_reason: reason, p_comment: comment.trim() || null,
  });
  if (error) throw new Error(dbMessage(error.message, 'Le signalement n’a pas pu être envoyé. Réessaie.'));
}

export async function setBlocked(userId: string, blocked: boolean): Promise<void> {
  const { error } = await supabase.rpc('set_block', { target: userId, blocked });
  if (error) throw new Error(blocked ? 'Le blocage n’a pas pu être enregistré.' : 'Le déblocage n’a pas pu être enregistré.');
}

export type BlockedPerson = { id: string; display_name: string; avatar_url: string | null; at: string };

export async function myBlocks(): Promise<BlockedPerson[]> {
  const { data, error } = await supabase.rpc('my_blocks');
  if (error) throw new Error('La liste n’a pas pu être lue.');
  return (data as BlockedPerson[] | null) ?? [];
}

export type TermsStatus = { version: string; accepted: boolean; accepted_at: string | null; contact_email: string | null; enforced: boolean };

function isTermsStatus(value: unknown): value is TermsStatus {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    && typeof (value as TermsStatus).version === 'string' && typeof (value as TermsStatus).accepted === 'boolean';
}

/** Conditions d'utilisation du compte connecté ; `ensure()` les fait accepter avant le premier contenu. */
export function useTerms() {
  const [status, setStatus] = useState<TermsStatus | null>(null);
  // La base n'a pas répondu (serveur plus ancien, réseau) : on laisse publier, elle reste la garde (« Exiger les CGU »).
  const [unanswered, setUnanswered] = useState(false);
  const reload = useCallback(async () => {
    const { data } = await supabase.rpc('my_terms');
    const valid = isTermsStatus(data) ? data : null;
    if (valid) setStatus(valid);
    setUnanswered(!valid);
    return valid;
  }, []);
  useEffect(() => {
    // Premier chargement hors du rendu (la règle react-hooks interdit un setState synchrone ici).
    const first = setTimeout(() => void reload(), 0);
    return () => clearTimeout(first);
  }, [reload]);

  async function accept(): Promise<void> {
    const version = status?.version ?? (await reload())?.version;
    const { data, error } = await supabase.rpc('accept_terms', { p_version: version });
    if (error) throw new Error(dbMessage(error.message, 'L’acceptation n’a pas été enregistrée. Réessaie.'));
    setStatus(data as TermsStatus);
  }

  return { status, accepted: Boolean(status?.accepted) || unanswered, reload, accept };
}

/** Acceptation dite dans le geste lui-même (« En répondant, j'accepte les conditions d'utilisation » au-dessus du
 * bouton, invité sans l'app) : enregistrée par la base, à la version en cours, avant le premier contenu (le prénom). */
export async function acceptTermsIfNeeded(): Promise<void> {
  const { data } = await supabase.rpc('my_terms');
  if (!isTermsStatus(data) || data.accepted) return;
  const { error } = await supabase.rpc('accept_terms', { p_version: data.version });
  if (error) throw new Error(dbMessage(error.message, 'L’acceptation des conditions n’a pas été enregistrée. Réessaie.'));
}

export type PublicInfo = { terms_version: string; contact_email: string | null; terms_enforced: boolean };

export async function moderationInfo(): Promise<PublicInfo | null> {
  const { data } = await supabase.rpc('moderation_public_info');
  return (data as PublicInfo | null) ?? null;
}
