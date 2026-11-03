import { useEffect, useState } from 'react';
import { Image, Pressable, StyleSheet, View } from 'react-native';

import { supabase } from '@/lib/supabase';
import { pressTransition } from '@/lib/motion';

import { ErrorText } from './ui';

/**
 * « Ajouter à l'app Cartes Apple » (badge officiel d'Apple, en français, non modifié) sous le billet.
 * - Safari (iPhone, iPad, Mac) : le serveur prépare le .pkpass, la page l'ouvre, Safari propose de l'ajouter ;
 * - app iPhone (WKWebView, qui n'ouvre pas les .pkpass) : pont natif PassKit (window.PartyNative.wallet) ;
 * - Android, ordinateurs hors Mac : rien (pas de Wallet).
 * Masqué tant que les certificats ne sont pas installés sur le serveur (/api/wallet/status).
 */
type NativeWallet = { wallet?: { available?: boolean; add?: (url: string) => Promise<boolean> } };

/** Badge d'Apple : 113,408 × 35,291 ; hauteur à l'écran ≥ 30 px, marge libre ≥ 10 % de la hauteur. */
const BADGE_HEIGHT = 44;
const BADGE_RATIO = 113.408 / 35.291;

let serverReady: Promise<boolean> | null = null;
function walletOnServer(): Promise<boolean> {
  serverReady ??= fetch('/api/wallet/status', { credentials: 'same-origin' })
    .then((r) => (r.ok ? r.json() : { enabled: false }))
    .then((j: { enabled?: boolean }) => !!j.enabled, () => false);
  return serverReady;
}

function nativeWallet(): NativeWallet['wallet'] | null {
  const w = (globalThis as { PartyNative?: NativeWallet }).PartyNative?.wallet;
  return w?.available && typeof w.add === 'function' ? w : null;
}

/** Safari sur un appareil Apple : ouvre les .pkpass. iPad récents : « Macintosh » + écran tactile. */
export function appleWalletDevice(nav: { userAgent: string; maxTouchPoints?: number } = navigator): boolean {
  const ua = nav.userAgent;
  if (/iPhone|iPad|iPod/.test(ua)) return true;
  return /Macintosh/.test(ua) && /Safari\//.test(ua) && !/Chrome|Chromium|CriOS|Edg|Firefox|FxiOS|OPR/.test(ua);
}

async function preparePass(eventId: string): Promise<string> {
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  if (!token) throw new Error('Reconnecte-toi pour ajouter ton billet.');
  const r = await fetch('/api/wallet/ticket', {
    method: 'POST',
    credentials: 'same-origin',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token, event_id: eventId }),
  });
  const body = (await r.json().catch(() => ({}))) as { url?: string; detail?: string };
  if (!r.ok || !body.url) throw new Error(body.detail || 'Le billet n’a pas pu être préparé. Réessaie.');
  return body.url;
}

export function WalletButton({ eventId }: { eventId: string }) {
  const [shown, setShown] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!nativeWallet() && !appleWalletDevice()) return;
    let alive = true;
    void walletOnServer().then((ok) => { if (alive) setShown(ok); });
    return () => { alive = false; };
  }, []);

  if (!shown) return null;

  const add = async () => {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const url = await preparePass(eventId);
      const native = nativeWallet();
      if (native?.add) await native.add(new URL(url, location.href).href);
      else location.assign(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Le billet n’a pas pu être ajouté. Réessaie.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <View style={st.wrap}>
      <Pressable
        testID="wallet-add"
        accessibilityRole="button"
        accessibilityLabel="Ajouter à l’app Cartes Apple"
        accessibilityState={{ busy }}
        disabled={busy}
        onPress={() => { void add(); }}
        style={({ pressed }) => [pressTransition, busy ? st.busy : pressed && st.pressed]}
      >
        <Image
          source={{ uri: '/static/wallet/badge-fr.svg' }}
          style={st.badge}
          accessibilityIgnoresInvertColors
        />
      </Pressable>
      <ErrorText error={error} />
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { alignItems: 'center', gap: 6, paddingVertical: BADGE_HEIGHT * 0.1 },
  badge: { height: BADGE_HEIGHT, width: BADGE_HEIGHT * BADGE_RATIO },
  busy: { opacity: 0.5 },
  pressed: { opacity: 0.8 },
});
