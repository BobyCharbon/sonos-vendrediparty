import { useEffect, useState } from 'react';
import { AppState, Platform } from 'react-native';

/** Au-delà, un chargement sans réponse affiche un message et « Réessayer » (plus de squelette ni de roue sans fin). */
export const SLOW_LOAD_MS = 15_000;
/** Relecture des paiements d'une fiche payante ouverte (« J'ai payé » / « Reçu ») : page visible seulement. */
export const PAYMENTS_REFRESH_MS = 20_000;

function browserOnline(): boolean {
  return Platform.OS !== 'web' || typeof navigator === 'undefined' || navigator.onLine !== false;
}

/** Connexion du navigateur ; `onBack` est appelé au retour du réseau (la page se recharge seule). */
export function useOnline(onBack?: () => void): boolean {
  const [online, setOnline] = useState(browserOnline);
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined') return;
    const up = () => { setOnline(true); onBack?.(); };
    const down = () => setOnline(false);
    window.addEventListener('online', up);
    window.addEventListener('offline', down);
    return () => {
      window.removeEventListener('online', up);
      window.removeEventListener('offline', down);
    };
  }, [onBack]);
  return online;
}

/** Vrai quand `pending` dure plus de SLOW_LOAD_MS. */
export function useSlowLoad(pending: boolean, delay = SLOW_LOAD_MS): boolean {
  const [slow, setSlow] = useState(false);
  useEffect(() => {
    if (!pending) return;
    const timer = setTimeout(() => setSlow(true), delay);
    return () => {
      clearTimeout(timer);
      setSlow(false);
    };
  }, [pending, delay]);
  return pending && slow;
}

function pageVisible(): boolean {
  if (Platform.OS === 'web' && typeof document !== 'undefined') return document.visibilityState !== 'hidden';
  return AppState.currentState === 'active';
}

/** Compteur qui avance toutes les `every` ms tant que `active` et la page visible (clé de relecture). */
export function usePaymentsTick(active: boolean, every = PAYMENTS_REFRESH_MS): number {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(() => { if (pageVisible()) setTick((n) => n + 1); }, every);
    return () => clearInterval(timer);
  }, [active, every]);
  return tick;
}
