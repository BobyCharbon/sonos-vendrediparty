import { createElement, useEffect, useState } from 'react';
import { Platform } from 'react-native';

import { compagnonOn } from '@/lib/features';
import { supabase } from '@/lib/supabase';

/** Présentation commune du web (app/static/pet/profile-zicou.js) : celle de la fiche d'un joueur dans les jeux. */
type ZicouProfileApi = {
  load: (token: string, member: string) => Promise<unknown>;
  html: (data: unknown) => string;
  bind: (el: HTMLElement, actions: { visit: (id: string) => void; adopt: () => void }) => void;
};

const SCRIPTS = ['/static/pet/skin.js', '/static/pet/acc-a.js', '/static/pet/acc-b.js', '/static/pet/profile-zicou.js'];
const STYLE = '/static/pet/profile-zicou.css';
let assets: Promise<ZicouProfileApi | null> | null = null;

function script(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[data-zp-src="${src}"]`)) return resolve();
    const el = Object.assign(document.createElement('script'), { src, async: false });
    el.dataset.zpSrc = src;
    el.onload = () => resolve();
    el.onerror = () => reject(new Error(src));
    document.head.append(el);
  });
}

/** Charge une seule fois le dessin de Zicou et la présentation de la fiche (servis par Party, même origine). */
function loadAssets(): Promise<ZicouProfileApi | null> {
  assets ??= (async () => {
    if (!document.querySelector(`link[href="${STYLE}"]`)) {
      document.head.append(Object.assign(document.createElement('link'), { rel: 'stylesheet', href: STYLE }));
    }
    for (const src of SCRIPTS) await script(src);
    return (globalThis as { ZicouProfile?: ZicouProfileApi }).ZicouProfile ?? null;
  })().catch(() => {
    assets = null;   // Zicou éteint (404) ou réseau : réessayé à la prochaine fiche
    return null;
  });
  return assets;
}

/** Ouvre l'onglet Zicou de la page Party qui entoure le module (visite d'un ami, ou adopter le mien). */
function openZicou(visit?: string) {
  if (window.parent !== window) {
    window.parent.postMessage({ type: 'party-events:open-tab', tab: 'pet', ...(visit ? { visit } : {}) }, location.origin);
  } else {
    location.assign(visit ? `/?pet=1&visit=${encodeURIComponent(visit)}` : '/?pet=1');
  }
}

/**
 * Fiche d'un membre › son Zicou : bloc vedette lumineux s'il en a un, œuf terne « Pas encore de Zicou » sinon.
 * Rien quand le Zicou est éteint (production) ou que la personne est bloquée (le serveur répond 404).
 */
export function ZicouOnProfile({ memberId }: { memberId: string }) {
  const [html, setHtml] = useState('');
  const [box, setBox] = useState<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!compagnonOn || Platform.OS !== 'web') return;
    let alive = true;
    void (async () => {
      const api = await loadAssets();
      const token = (await supabase.auth.getSession()).data.session?.access_token;
      if (!api || !token || !alive) return;
      const data = await api.load(token, memberId);
      if (alive) setHtml(data ? api.html(data) : '');
    })();
    return () => { alive = false; };
  }, [memberId]);

  // Touchers (visite, adopter) : délégués sur le bloc, une fois par élément.
  useEffect(() => {
    const api = (globalThis as { ZicouProfile?: ZicouProfileApi }).ZicouProfile;
    if (box && api) api.bind(box, { visit: (id) => openZicou(id), adopt: () => openZicou() });
  }, [box]);

  if (!html) return null;
  // Chaîne produite par profile-zicou.js : tout texte y passe par esc() (nom du Zicou déjà filtré par le serveur).
  return createElement('div', { ref: setBox, 'data-testid': 'zicou-profile', dangerouslySetInnerHTML: { __html: html } });
}
