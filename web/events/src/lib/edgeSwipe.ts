import { router } from 'expo-router';
import { useEffect } from 'react';
import { Platform } from 'react-native';

const EDGE = 28;            // px depuis le bord gauche
const SLOP = 10;            // px avant de décider de la direction
const RELEASE = 'transform .32s cubic-bezier(.2, .9, .3, 1)';

/** Distance que l’élan ajoute au geste (décélération du défilement iOS), vitesse en px/s. */
const project = (velocity: number) => (velocity / 1000) * 0.998 / (1 - 0.998);

// Écrans racines (onglets) : rien « derrière » à retrouver par un glisser.
const ROOTS = new Set(['/', '/activity', '/profile', '/account', '/welcome', '/sign-in']);
// Le geste ne démarre jamais dans un champ, une fenêtre (recadrage photo, feuille) ou une zone qui glisse déjà.
const OWN_GESTURE = 'input, textarea, select, [role="dialog"], [aria-modal="true"], [data-no-edge-swipe]';
const currentPath = () => location.pathname.replace(/^\/events(?=\/|$)/, '') || '/';

type Drag = { x0: number; y0: number; active: boolean; lastX: number; lastT: number; velocity: number };

/**
 * Glisser depuis le bord gauche = retour, comme sur iPhone : l’écran suit le doigt, puis part à droite
 * si le geste (élan compris) dépasse la moitié de l’écran, sinon il revient. Web seulement : dans Party,
 * le module vit dans un cadre qui reçoit ses propres touchers.
 */
export function useEdgeSwipeBack() {
  useEffect(() => {
    if (Platform.OS !== 'web' || typeof document === 'undefined') return;
    let drag: Drag | null = null;
    let leaving = false;   // retour en cours : un second geste ou toucher ne dépile pas un écran de plus
    const surface = () => document.getElementById('root');
    const place = (x: number, animated: boolean) => {
      const el = surface();
      if (!el) return;
      el.style.transition = animated ? RELEASE : 'none';
      el.style.transform = x ? `translate3d(${x}px,0,0)` : '';
      el.style.boxShadow = x ? '-12px 0 32px rgba(0,0,0,.45)' : '';
    };
    const down = (e: PointerEvent) => {
      if (leaving || !e.isPrimary || e.button > 0 || e.clientX > EDGE || !router.canGoBack()) return;
      if (ROOTS.has(currentPath()) || (e.target as Element | null)?.closest?.(OWN_GESTURE)) return;
      if (document.querySelector('[aria-modal="true"]')) return;
      drag = { x0: e.clientX, y0: e.clientY, active: false, lastX: e.clientX, lastT: e.timeStamp, velocity: 0 };
    };
    const move = (e: PointerEvent) => {
      if (!drag) return;
      const dx = e.clientX - drag.x0, dy = e.clientY - drag.y0;
      if (!drag.active) {
        if (Math.hypot(dx, dy) < SLOP) return;
        if (dx <= 0 || Math.abs(dx) < Math.abs(dy)) { drag = null; return; }
        drag.active = true;
      }
      const dt = e.timeStamp - drag.lastT;
      if (dt > 0) drag.velocity = ((e.clientX - drag.lastX) / dt) * 1000;
      drag.lastX = e.clientX;
      drag.lastT = e.timeStamp;
      place(Math.max(0, dx), false);
    };
    const up = (e: PointerEvent) => {
      const d = drag;
      drag = null;
      if (!d?.active) return;
      const paused = e.timeStamp - d.lastT > 80;   // une pause avant de lâcher = pas d’élan
      const landing = e.clientX - d.x0 + (paused ? 0 : project(d.velocity));
      if (landing > innerWidth / 2) {
        leaving = true;
        place(innerWidth, true);
        setTimeout(() => {
          router.back();
          // L'écran précédent est affiché avant de remettre le cadre en place (pas d'éclair de l'ancien écran).
          requestAnimationFrame(() => requestAnimationFrame(() => { place(0, false); leaving = false; }));
        }, 300);
      } else {
        place(0, true);
      }
    };
    const cancel = () => { if (drag?.active) place(0, true); drag = null; };
    const touchMove = (e: TouchEvent) => {
      if (!drag || e.touches.length !== 1) return;
      const dx = e.touches[0].clientX - drag.x0, dy = e.touches[0].clientY - drag.y0;
      if (drag.active || (dx > 0 && dx > Math.abs(dy))) e.preventDefault();   // la page ne défile pas sous le geste
    };
    addEventListener('pointerdown', down, true);
    addEventListener('pointermove', move, true);
    addEventListener('pointerup', up, true);
    addEventListener('pointercancel', cancel, true);
    addEventListener('touchmove', touchMove, { passive: false, capture: true });
    return () => {
      removeEventListener('pointerdown', down, true);
      removeEventListener('pointermove', move, true);
      removeEventListener('pointerup', up, true);
      removeEventListener('pointercancel', cancel, true);
      removeEventListener('touchmove', touchMove, { capture: true } as EventListenerOptions);
    };
  }, []);
}
