import { router } from 'expo-router';
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Pressable, type StyleProp, type ViewStyle } from 'react-native';

import { MiniProfileSheet } from '@/components/chats/people/MiniProfileSheet';
import { useAuth } from '@/lib/auth';

/**
 * Mini-profil (Discussions v2, maquette 1-neon/3) : la même feuille au toucher d'un nom ou d'une photo, PARTOUT
 * (participants, invités, groupes, pronos, bar, covoiturage, billets…). « Envoyer un message » en principal, Fiche,
 * En commun, Bloquer · Signaler. Moi : ma fiche complète.
 */
type MiniProfile = { open(userId: string): void };

const MEMBER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

// Ouvreur du fournisseur monté (un seul, dans app/_layout.tsx) : Avatar, NameLinks… l'appellent hors des hooks.
let current: ((id: string) => void) | null = null;

/** Ouvre le mini-profil ; sans fournisseur (page publique, avant connexion) : la fiche, comme avant. */
export function openMiniProfile(id: string): void {
  if (!MEMBER_ID.test(id)) return;
  if (current) current(id);
  else router.push(`/member/${id}`);
}

const Context = createContext<MiniProfile>({ open: openMiniProfile });

export function useMiniProfile(): MiniProfile {
  return useContext(Context);
}

export function MiniProfileProvider({ children }: { children: ReactNode }) {
  const { session } = useAuth();
  const me = session?.user.id ?? null;
  const [userId, setUserId] = useState<string | null>(null);
  const open = useCallback((id: string) => {
    if (!MEMBER_ID.test(id)) return;
    // Moi : rien à m'écrire, ma fiche complète (rôle, numéro, groupes).
    if (id === me) router.push(`/member/${id}`);
    else setUserId(id);
  }, [me]);
  useEffect(() => {
    if (!me) return undefined;
    current = open;
    return () => { if (current === open) current = null; };
  }, [me, open]);
  const value = useMemo(() => ({ open: openMiniProfile }), []);
  const close = useCallback(() => setUserId(null), []);
  return (
    <Context.Provider value={value}>
      {children}
      {me && userId ? <MiniProfileSheet key={userId} userId={userId} onClose={close} /> : null}
    </Context.Provider>
  );
}

/** Un visage ou un nom qui se touche pour ouvrir le mini-profil ; `size` : son côté, pour une cible de 44 px au moins. */
export function PersonTap({ id, name, size = 44, children, style }: { id: string; name: string; size?: number; children: ReactNode; style?: StyleProp<ViewStyle> }) {
  const pad = Math.max(0, (44 - size) / 2);  // hitSlop est ignoré sur le web : marge négative, la mise en page ne bouge pas
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Profil de ${name}`} onPress={() => openMiniProfile(id)}
      style={({ pressed }) => [{ padding: pad, margin: -pad }, style, pressed && { opacity: 0.7 }]}>
      {children}
    </Pressable>
  );
}
