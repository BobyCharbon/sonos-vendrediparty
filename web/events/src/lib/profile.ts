import type { Profile } from './types';

export function hasCompleteIdentity(profile: Pick<Profile, 'first_name' | 'last_name' | 'display_name' | 'avatar_url'> | null | undefined): boolean {
  return !!(profile?.first_name?.trim() && profile.last_name?.trim() && profile.display_name.trim() && profile.avatar_url?.trim());
}
