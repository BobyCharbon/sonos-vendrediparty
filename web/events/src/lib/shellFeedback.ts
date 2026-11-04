import { useEffect, useState } from 'react';
import { Platform } from 'react-native';

/** Ligne « Ton avis » / « Retours » des Réglages, décrite par la page Party (index.html, fbInfo / fbShare). */
export type ShellFeedback = { allowed: boolean; label: string; badge: string | null };

function parse(value: unknown): ShellFeedback | null {
  if (!value || typeof value !== 'object') return null;
  const v = value as Record<string, unknown>;
  const label = v.label === 'Retours' ? 'Retours' : 'Ton avis';
  const badge = typeof v.badge === 'string' && /^\d{1,2}\+?$/.test(v.badge) ? v.badge : null;
  return { allowed: v.allowed === true, label, badge };
}

function readShell(): ShellFeedback | null {
  if (Platform.OS !== 'web' || typeof window === 'undefined' || window.parent === window) return null;
  try {
    const info = (window.parent as Window & { fbInfo?: () => unknown }).fbInfo;
    return typeof info === 'function' ? parse(info()) : null;
  } catch {
    return null; // Autre origine : rien à lire.
  }
}

/** « Ton avis » est sorti de la barre d'onglets (onglet Zicou, 4.11) : sa pastille vit sur cette ligne des Réglages. */
export function useShellFeedback(): ShellFeedback | null {
  const [info, setInfo] = useState<ShellFeedback | null>(readShell);
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;
    const onMessage = (event: MessageEvent) => {
      if (event.origin !== window.location.origin || event.data?.type !== 'party-shell:feedback') return;
      const next = parse(event.data);
      if (next) setInfo(next);
    };
    window.addEventListener('message', onMessage);
    return () => window.removeEventListener('message', onMessage);
  }, []);
  return info;
}
