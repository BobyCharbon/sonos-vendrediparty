import type { Profile } from './types';

/** Surnom : 12 caractères au plus (avis bda77087d7dc), comme la base (guard_profile) et l'app iPhone. */
export const NICKNAME_MAX = 12;

/** Prénom, nom et surnom : obligatoires. La photo est facultative (décision du 09.11.2026, Apple 5.1.1). */
export function hasCompleteIdentity(profile: Pick<Profile, 'first_name' | 'last_name' | 'display_name'> | null | undefined): boolean {
  return !!(profile?.first_name?.trim() && profile.last_name?.trim() && profile.display_name.trim());
}
