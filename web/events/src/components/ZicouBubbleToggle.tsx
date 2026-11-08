import { useState } from 'react';

import { compagnonOn } from '@/lib/features';
import { Card, ToggleRow } from './ui';

/** Même clé que app/static/pet/zicou-home.js (même origine que la page Party) : "1" = bulle masquée sur cet appareil. */
const OFF_KEY = 'zc_bubble_off';

function readShown(): boolean {
  try { return localStorage.getItem(OFF_KEY) !== '1'; } catch { return true; }
}

/** L'app iOS dessine sa propre bulle (Réglages natifs) : cette ligne ne sert que dans le navigateur. */
function inNativeApp(): boolean {
  return typeof window !== 'undefined' && !!(window as { PartyNative?: { zicou?: unknown } }).PartyNative?.zicou;
}

/** Réglages › « Bulle de Zicou » (avis 3cd6d282745b) : afficher ou masquer sa petite tête sur cet appareil. */
export function ZicouBubbleToggle() {
  const [shown, setShown] = useState(readShown);
  if (!compagnonOn || typeof window === 'undefined' || inNativeApp()) return null;

  function change(on: boolean) {
    setShown(on);
    try {
      if (on) localStorage.removeItem(OFF_KEY);
      else localStorage.setItem(OFF_KEY, '1');
    } catch { /* navigation privée : le choix vaut pour cette visite */ }
    if (window.parent !== window) window.parent.postMessage({ type: 'party-events:zicou-bubble', on }, location.origin);
  }

  return (
    <Card style={{ paddingVertical: 4 }}>
      <ToggleRow label="Bulle de Zicou" hint="Sa petite tête en haut de l’app ; masquée, Zicou reste dans son onglet."
        value={shown} onChange={change} />
    </Card>
  );
}
