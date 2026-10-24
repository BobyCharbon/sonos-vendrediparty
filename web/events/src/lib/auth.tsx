import type { Session } from '@supabase/supabase-js';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AppState, Platform } from 'react-native';

import { supabase } from './supabase';
import { ADMIN_PERMS, type Profile } from './types';
import { syncWebPush, unregisterPushToken } from './push';

type AuthState = {
  loading: boolean;
  session: Session | null;
  profile: Profile | null;
  profileError: string | null;
  isAdmin: boolean; // a au moins un droit d'administration (Réglages → Administration)
  perms: string[];
  rank: number; // invité 0 … admin 4, root 99
  can: (perm: string) => boolean;
  /** Membre du groupe, mais les sorties sont encore réservées aux bêta-testeurs (production). */
  eventsSoon: boolean;
  refreshProfile: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

/** En production, Party sert le module avec data-events="beta" : les sorties ne s'ouvrent qu'aux bêta-testeurs. */
const betaOnly = typeof document !== 'undefined' && document.documentElement.dataset.events === 'beta';

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [access, setAccess] = useState<{ perms: string[]; rank: number; soon: boolean }>({ perms: [], rank: -1, soon: false });
  const [sessionReady, setSessionReady] = useState(false);
  const [profileError, setProfileError] = useState<string | null>(null);
  const profileRequest = useRef(0);

  const loadProfile = useCallback(async (userId: string | undefined) => {
    const request = ++profileRequest.current;
    if (!userId) {
      setProfile(null);
      setProfileError(null);
      return;
    }
    try {
      const [dir, perms, rank, beta] = await Promise.all([
        supabase.rpc('get_member_directory').eq('id', userId).single(),
        supabase.rpc('my_permissions'),
        supabase.rpc('my_rank'),
        betaOnly ? supabase.rpc('is_beta_tester') : Promise.resolve({ data: true }),
      ]);
      if (dir.error) throw dir.error;
      if (request !== profileRequest.current) return;
      const all = (perms.data as string[] | null) ?? [];
      // Hors bêta, un membre garde son compte Party mais pas encore les sorties.
      const soon = beta.data !== true && all.includes('events.view');
      setAccess({ perms: soon ? all.filter((p) => p !== 'events.view') : all, rank: (rank.data as number | null) ?? -1, soon });
      setProfile(dir.data as Profile);
      setProfileError(null);
    } catch {
      if (request === profileRequest.current) {
        setProfileError('Impossible de charger ton profil. Vérifie ta connexion puis réessaie.');
      }
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    supabase.auth.getSession().then(({ data, error }) => {
      if (error) throw error;
      if (!mounted) return;
      setSession(data.session);
    }).catch(() => {
      if (mounted) setProfileError('Impossible de retrouver ta connexion. Réessaie dans un instant.');
    }).finally(() => {
      if (mounted) setSessionReady(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_event, next) => {
      setSession(next);
      setSessionReady(true);
      // Le profil est chargé dans un effet séparé, hors du verrou Auth.
    });
    return () => {
      mounted = false;
      sub.subscription.unsubscribe();
    };
  }, []);

  useEffect(() => {
    if (!sessionReady) return;
    const task = setTimeout(() => { void loadProfile(session?.user.id); }, 0);
    return () => clearTimeout(task);
  }, [sessionReady, session?.user.id, loadProfile]);

  const loading = !sessionReady || (!!session && profile?.id !== session.user.id && !profileError);

  useEffect(() => {
    if (session && profile?.id === session.user.id && access.perms.includes('events.view')) {
      void syncWebPush().catch(() => { /* Les réglages proposent de réparer l’activation. */ });
    }
  }, [session, profile?.id, access.perms]);

  // Une validation faite par l'admin devient visible sans reconnecter le membre.
  useEffect(() => {
    if (!session?.user.id) return;
    const refresh = () => { void loadProfile(session.user.id); };
    const appState = AppState.addEventListener('change', (state) => {
      if (state === 'active') refresh();
    });
    const timer = profile?.role === 'guest' ? setInterval(refresh, 15_000) : undefined;  // accès aux sorties donné par un admin
    if (Platform.OS === 'web') window.addEventListener('focus', refresh);
    return () => {
      appState.remove();
      clearInterval(timer);
      if (Platform.OS === 'web') window.removeEventListener('focus', refresh);
    };
  }, [session?.user.id, profile?.role, loadProfile]);

  const value = useMemo<AuthState>(
    () => ({
      loading,
      session,
      profile,
      profileError,
      isAdmin: !!session && profile?.id === session.user.id && ADMIN_PERMS.some((p) => access.perms.includes(p)),
      perms: access.perms,
      rank: access.rank,
      can: (perm: string) => !!session && profile?.id === session.user.id && access.perms.includes(perm),
      eventsSoon: !!session && profile?.id === session.user.id && access.soon,
      refreshProfile: () => loadProfile(session?.user.id),
      signOut: async () => {
        await unregisterPushToken().catch((error) => console.warn('Déconnexion push :', error));
        const { error } = await supabase.auth.signOut({ scope: 'local' });
        if (error) setProfileError('La déconnexion n’a pas abouti. Vérifie ta connexion et réessaie.');
      },
    }),
    [loading, session, profile, profileError, loadProfile, access],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth doit être utilisé dans <AuthProvider>');
  return ctx;
}

/** Utilisateur connecté et actif (les écrans protégés ne s'affichent que dans ce cas). */
export function useMe(): Profile {
  const { profile } = useAuth();
  if (!profile) throw new Error('Profil absent');
  return profile;
}
