import { useEffect } from 'react';
import { Platform } from 'react-native';

// « Retour » de la barre verticale de l'iPhone Duo (app Party) : il touche le bouton retour visible de l'écran, comme
// le doigt en haut à gauche (retour de l'admin du 19.11). Une feuille ouverte : son ✕ (« Fermer »). Rien à toucher : pas
// de bouton dans la barre. Seul compte un bouton qu'on voit vraiment (au-dessus de tout à sa place : pas l'écran d'en dessous).
const BUTTONS = '[role="button"], button';
// Nom du bouton (étiquette d'accessibilité, sinon son texte) : ‹ Retour…, Annuler (« Nouveau message »), ✕ Fermer.
const BACK = /^(Retour|Annuler|Fermer)\b/;
const CLOSE = /^Fermer\b/;
const name = (el: Element) => (el.getAttribute('aria-label') || el.textContent || '').trim();

function reachable(el: Element) {
  const r = el.getBoundingClientRect();
  if (r.width <= 0 || r.height <= 0) return false;
  const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
  return !!hit && el.contains(hit);
}

const first = (root: ParentNode, wanted: RegExp) => {
  const found = [...root.querySelectorAll(BUTTONS)].filter((el) => wanted.test(name(el)) && reachable(el)) as HTMLElement[];
  const at = (el: HTMLElement) => el.getBoundingClientRect();
  return found.sort((a, b) => at(a).top - at(b).top || at(a).left - at(b).left)[0] ?? null;
};

export function backButton(): HTMLElement | null {
  const dialogs = [...document.querySelectorAll('[aria-modal="true"], [role="dialog"]')].filter((d) => d.getClientRects().length > 0);
  const sheet = dialogs[dialogs.length - 1];
  if (sheet) return first(sheet, CLOSE) ?? first(sheet, BACK);
  return first(document, BACK);
}

/** Dans Party : dit à la page s'il y a un retour à toucher, et le touche à sa demande (`party-shell:back`). */
export function useShellBack() {
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof window === 'undefined' || window.parent === window) return;
    let last: boolean | null = null;
    let queued = 0;
    const report = () => {
      queued = 0;
      const can = !!backButton();
      if (can === last) return;
      last = can;
      window.parent.postMessage({ type: 'party-events:back', can }, location.origin);
    };
    const later = () => { if (!queued) queued = requestAnimationFrame(report); };
    const watch = new MutationObserver(later);
    watch.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ['style', 'class', 'aria-hidden'] });
    const onMessage = (e: MessageEvent) => {
      if (e.origin === location.origin && e.data?.type === 'party-shell:back') backButton()?.click();
    };
    window.addEventListener('message', onMessage);
    window.addEventListener('resize', later);
    later();
    return () => { watch.disconnect(); cancelAnimationFrame(queued); window.removeEventListener('message', onMessage); window.removeEventListener('resize', later); };
  }, []);
}
