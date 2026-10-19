import { useEffect, useState, type ReactNode } from 'react';
import { Platform } from 'react-native';
import { SafeAreaInsetsContext } from 'react-native-safe-area-context';

type Insets = { top: number; right: number; bottom: number; left: number };

/** Marges fournies par Party quand le module est affiché dans son cadre (même origine). */
function readShellInsets(): Insets | null {
  if (Platform.OS !== 'web' || typeof window === 'undefined' || window.parent === window) return null;
  try {
    const party = (window.parent as Window & { PartyEvents?: { frameInsets?: () => Insets } }).PartyEvents;
    return typeof party?.frameInsets === 'function' ? party.frameInsets() : null;
  } catch {
    return null; // Autre origine : on garde les marges du navigateur.
  }
}

/**
 * Dans Party, le cadre va jusqu’au bord haut de l’écran : on applique exactement la marge
 * de l’iPhone (encoche, Dynamic Island) une seule fois, quel que soit le modèle,
 * au lieu de la laisser s’additionner à celle de la page parente.
 */
export function ShellSafeArea({ children }: { children: ReactNode }) {
  const [insets, setInsets] = useState<Insets | null>(readShellInsets);
  useEffect(() => {
    if (!insets) return;
    const refresh = () => setInsets(readShellInsets());
    const onMessage = (event: MessageEvent) => {
      if (event.origin === window.location.origin && event.data?.type === 'party-shell:insets') refresh();
    };
    window.addEventListener('message', onMessage);
    window.addEventListener('resize', refresh);
    return () => {
      window.removeEventListener('message', onMessage);
      window.removeEventListener('resize', refresh);
    };
  }, [insets]);
  if (!insets) return <>{children}</>;
  return <SafeAreaInsetsContext.Provider value={insets}>{children}</SafeAreaInsetsContext.Provider>;
}
