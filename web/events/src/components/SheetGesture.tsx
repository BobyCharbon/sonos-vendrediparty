import { useEffect, useRef, type RefObject } from 'react';
import { Platform, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { colors } from '@/lib/theme';

/**
 * Feuilles et fenêtres du module (Inviter, QR, Signaler, billet, payer, CGU) : on les ferme comme une feuille iOS
 * (retour de l'admin du 06.11, vidéo : « je ne peux pas abaisser la fiche ») :
 * - glisser vers le bas depuis la poignée, le titre ou n'importe où hors du contenu qui défile ; depuis le contenu
 *   seulement quand il est tout en haut (sinon le doigt fait défiler, comme avant) ;
 * - au-delà d'un seuil (distance ou vitesse) la feuille part vers le bas puis se ferme ; sinon elle revient ;
 * - ✕ en haut à droite (SheetClose), toucher le fond assombri (SheetBackdrop) ferme aussi.
 * Les écouteurs sont posés sur la feuille seulement (jamais html / body ni « * », voir CLAUDE.md, défilement tactile).
 * Web seulement : le module tourne dans la vue web de l'app (WKWebView) et dans Chrome Android.
 */

const DECIDE = 6;              // px avant de choisir : abaisser la feuille ou laisser défiler
const CLOSE_DISTANCE = 0.25;   // part de la hauteur de la feuille…
const CLOSE_MIN = 110;         // …et au moins ces px
const CLOSE_SPEED = 0.6;       // px/ms : un petit coup sec vers le bas ferme aussi
const OUT_MS = 220;
const SHEET_GAP = 10;        // px entre la barre d'état et le haut de la feuille
const ATTACH_EVERY_MS = 50;
const ATTACH_TRIES = 60;    // 3 s au plus
const BACK = 'transform .28s cubic-bezier(.2, .9, .3, 1)';

type Drag = { y0: number; x0: number; inScroller: boolean; on: boolean | null; dy: number; lastY: number; lastT: number; speed: number };

/** Le nœud DOM d'une View ou d'une ScrollView de react-native-web. */
function domNode(ref: RefObject<unknown>): HTMLElement | null {
  const value = ref.current as { getScrollableNode?: () => HTMLElement } | HTMLElement | null;
  if (!value) return null;
  if (typeof (value as { getScrollableNode?: unknown }).getScrollableNode === 'function') {
    return (value as { getScrollableNode: () => HTMLElement }).getScrollableNode();
  }
  return value instanceof HTMLElement ? value : null;
}

/** Glisser vers le bas pour fermer : `sheet` suit le doigt ; `scroller` (facultatif) garde son défilement. */
export function useSheetDrag(visible: boolean, onClose: () => void, sheet: RefObject<unknown>, scroller?: RefObject<unknown>) {
  const close = useRef(onClose);
  useEffect(() => { close.current = onClose; }, [onClose]);

  useEffect(() => {
    if (Platform.OS !== 'web' || !visible) return;
    let drag: Drag | null = null;
    let leaving = false;
    let el: HTMLElement | null = null;
    const place = (y: number, transition: string) => {
      if (!el) return;
      el.style.transition = transition;
      el.style.transform = y ? `translate3d(0, ${y}px, 0)` : '';
    };
    const start = (e: TouchEvent) => {
      if (leaving || e.touches.length !== 1) { drag = null; return; }
      const box = domNode(scroller ?? { current: null });
      const t = e.touches[0];
      drag = { y0: t.clientY, x0: t.clientX, inScroller: !!box && box.contains(e.target as Node), on: null, dy: 0,
        lastY: t.clientY, lastT: e.timeStamp, speed: 0 };
    };
    const move = (e: TouchEvent) => {
      if (!drag || e.touches.length !== 1) return;
      const t = e.touches[0];
      const dy = t.clientY - drag.y0, dx = t.clientX - drag.x0;
      if (drag.on === null) {
        if (Math.abs(dy) < DECIDE && Math.abs(dx) < DECIDE) {
          // Pas encore décidé : on retient le geste qui descend dès le départ (sinon iOS lance le rebond du contenu).
          const box = domNode(scroller ?? { current: null });
          if (dy > 0 && Math.abs(dy) >= Math.abs(dx) && (!drag.inScroller || !box || box.scrollTop <= 0)) e.preventDefault();
          return;
        }
        const box = domNode(scroller ?? { current: null });
        drag.on = dy > 0 && Math.abs(dy) > Math.abs(dx) && (!drag.inScroller || !box || box.scrollTop <= 0);
        if (!drag.on) { drag = null; return; }
      }
      e.preventDefault();   // la feuille suit le doigt, le contenu ne rebondit pas
      const dt = e.timeStamp - drag.lastT;
      if (dt > 0) drag.speed = (t.clientY - drag.lastY) / dt;
      drag.lastY = t.clientY;
      drag.lastT = e.timeStamp;
      drag.dy = Math.max(0, dy);
      place(drag.dy, 'none');
    };
    const end = () => {
      const d = drag;
      drag = null;
      if (!d?.on || !el) return;
      const height = el.getBoundingClientRect().height || innerHeight;
      if (d.dy > Math.max(CLOSE_MIN, height * CLOSE_DISTANCE) || (d.speed > CLOSE_SPEED && d.dy > 30)) {
        leaving = true;
        place(height + 40, `transform ${OUT_MS}ms ease-in`);
        setTimeout(() => close.current(), OUT_MS);
      } else {
        place(0, BACK);
      }
    };
    // La Modal monte son contenu un peu après « visible » (animation d'entrée) : on attend le nœud de la feuille.
    let tries = 0;
    let timer: ReturnType<typeof setTimeout>;
    const attach = () => {
      el = domNode(sheet);
      if (!el) {
        if (++tries < ATTACH_TRIES) timer = setTimeout(attach, ATTACH_EVERY_MS);
        return;
      }
      place(0, 'none');
      el.addEventListener('touchstart', start, { passive: true });
      el.addEventListener('touchmove', move, { passive: false });
      el.addEventListener('touchend', end);
      el.addEventListener('touchcancel', end);
    };
    timer = setTimeout(attach, 0);
    return () => {
      clearTimeout(timer);
      if (!el) return;
      el.removeEventListener('touchstart', start);
      el.removeEventListener('touchmove', move);
      el.removeEventListener('touchend', end);
      el.removeEventListener('touchcancel', end);
      place(0, 'none');
    };
  }, [visible, sheet, scroller]);

  useSheetSignal(visible);
}

/**
 * Marge du haut d'une feuille : sous la barre d'état et la Dynamic Island. Sans elle la poignée tombait dans la zone
 * de la barre d'état d'iOS (≈ 54 pt), qui garde les touchers pour elle : impossible d'attraper la poignée.
 */
export function useSheetTop(): number {
  return useSafeAreaInsets().top + SHEET_GAP;
}

let openSheets = 0;

/** Dit à la page Party qu'une feuille est ouverte : elle masque ce qui flotte par-dessus le module (pastille de Zicou). */
export function useSheetSignal(visible: boolean) {
  useEffect(() => {
    if (Platform.OS !== 'web' || !visible || typeof window === 'undefined') return;
    const send = () => {
      if (window.parent !== window) window.parent.postMessage({ type: 'party-events:sheet', open: openSheets > 0 }, location.origin);
    };
    openSheets += 1;
    send();
    return () => { openSheets = Math.max(0, openSheets - 1); send(); };
  }, [visible]);
}

/** ✕ en haut à droite d'une feuille (44 px de zone de toucher). */
export function SheetClose({ onPress, label = 'Fermer', style }: { onPress: () => void; label?: string; style?: object }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} hitSlop={8} onPress={onPress} style={[st.close, style]}>
      {/* Croix dessinée (pas le caractère ✕ : absent de certaines polices, il s'affichait « ? » sur le simulateur). */}
      <View style={[st.bar, { transform: [{ rotate: '45deg' }] }]} />
      <View style={[st.bar, { transform: [{ rotate: '-45deg' }] }]} />
    </Pressable>
  );
}

/** Le fond assombri : le toucher ferme la feuille (pas un bouton pour les lecteurs d'écran : ✕ est là pour ça). */
export function SheetBackdrop({ onPress }: { onPress: () => void }) {
  return <Pressable accessible={false} focusable={false} onPress={onPress} style={st.backdrop} testID="sheet-backdrop" />;
}

/** Haut d'une fenêtre centrée : la poignée (elle s'abaisse) et ✕ à droite. */
export function SheetTop({ onClose, label = 'Fermer la fenêtre' }: { onClose: () => void; label?: string }) {
  return (
    <View style={st.top}>
      <View style={st.grabber} />
      <SheetClose label={label} onPress={onClose} style={st.topClose} />
    </View>
  );
}

const st = StyleSheet.create({
  // 44×44 (cible tactile minimale) : hitSlop est ignoré par react-native-web, le ✕ ne mesurait que 36 px sur le web.
  close: { width: 44, height: 44, borderRadius: 22, backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center' },
  bar: { position: 'absolute', width: 14, height: 2, borderRadius: 1, backgroundColor: colors.textSoft },
  backdrop: { position: 'fixed' as 'absolute', top: 0, left: 0, right: 0, bottom: 0 },
  top: { height: 28, justifyContent: 'center', marginTop: -6 },
  topClose: { position: 'absolute', right: -6, top: -4 },
  grabber: { alignSelf: 'center', width: 40, height: 5, borderRadius: 3, backgroundColor: colors.lineStrong },
});
