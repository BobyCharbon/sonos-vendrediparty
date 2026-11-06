import type { Session } from '@supabase/supabase-js';
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { AppState, Platform } from 'react-native';

import { belowVip, roleBook, setRoleBook, type Role } from './roles';
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
  rank: number; // place de mon rôle dans la liste des rôles (Guest 0 … Admin en haut), root 99
  /** Rôles du plus bas au plus haut (table public.roles ; anciens rôles figés si la base ne l'a pas). */
  roles: Role[];
  can: (perm: string) => boolean;
  /** Compte actif qui peut ouvrir les événements : ceux qu'il voit (publics, son groupe, ses invitations). */
  eventsOpen: boolean;
  refreshProfile: () => Promise<void>;
  signOut: () => Promise<void>;
};

const AuthContext = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(null);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [access, setAccess] = useState<{ perms: string[]; rank: number; roles: Role[] }>({ perms: [], rank: -1, roles: roleBook() });
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
      // Événements ouverts à tous les comptes (décision du 04.11) : plus de « Bientôt » ni d'accès bêta à lire.
      const [dir, perms, rank, roles] = await Promise.all([
        supabase.rpc('get_member_directory').eq('id', userId).single(),
        supabase.rpc('my_permissions'),
        supabase.rpc('my_rank'),
        supabase.from('roles').select('key, label, color, icon, rank, builtin').order('rank'),
      ]);
      if (dir.error) throw dir.error;
      if (request !== profileRequest.current) return;
      const all = (perms.data as string[] | null) ?? [];
      if (!roles.error) setRoleBook(roles.data as Role[]);  // base sans la table : on garde les anciens rôles
      setAccess({ perms: all, rank: (rank.data as number | null) ?? -1, roles: roleBook() });
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
    const timer = profile?.role && belowVip(profile?.role) && profile?.role !== 'basic' ? setInterval(refresh, 15_000) : undefined;  // accès aux sorties donné par un admin
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
      roles: access.roles,
      can: (perm: string) => !!session && profile?.id === session.user.id && access.perms.includes(perm),
      eventsOpen: !!session && profile?.id === session.user.id && profile.status === 'active',
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

/** Photo de profil lisible par ce compte (règle de stockage « photos du groupe autorisé ») : la sienne, ou celles des
 * autres avec « Voir les événements » ou un droit de gestion des membres. Sinon on ne la demande pas (400 en console
 * chez les Membres et Guests : campagne des bots, 06.11) et les initiales restent. */
const PHOTO_PERMS = ['events.view', 'members.approve', 'members.view_identity', 'members.roles', 'members.ban'];
export function useMaySeePhoto(): (path: string) => boolean {
  const ctx = useContext(AuthContext);
  return (path: string) => {
    if (!ctx?.session) return false;
    return path.startsWith(`${ctx.session.user.id}/`) || PHOTO_PERMS.some((p) => ctx.can(p));
  };
}

/** Utilisateur connecté et actif (les écrans protégés ne s'affichent que dans ce cas). */
export function useMe(): Profile {
  const { profile } = useAuth();
  if (!profile) throw new Error('Profil absent');
  return profile;
}
