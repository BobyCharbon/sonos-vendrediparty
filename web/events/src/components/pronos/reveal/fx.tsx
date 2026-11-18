import { useCallback, useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore, type DependencyList, type ReactNode } from 'react';
import { Text, View, type StyleProp, type TextStyle, type ViewProps } from 'react-native';

import { CONFETTI } from './theme';

/**
 * Moteur des scènes (dévoilement, trophée, résultat, classement) : Web Animations, ressorts façon SwiftUI, « Passer »
 * (tout va à l'état final), « Réduire les animations » (état final direct, rien ne bouge). Les éléments sont rendus
 * dans leur état FINAL ; les animations partent de l'état initial grâce à `fill: both` : sauter = finir, c'est tout.
 */

const query = '(prefers-reduced-motion: reduce)';
function subscribe(cb: () => void) {
  if (typeof window === 'undefined' || !window.matchMedia) return () => undefined;
  const m = window.matchMedia(query);
  m.addEventListener?.('change', cb);
  return () => m.removeEventListener?.('change', cb);
}
const readReduced = () => typeof window !== 'undefined' && !!window.matchMedia && window.matchMedia(query).matches;

/** « Réduire les animations » (suit le réglage du système en direct). */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, readReduced, () => false);
}

export type Spring = { easing: string; duration: number };

let linearOk: boolean | null = null;
const canLinear = () => {
  if (linearOk == null) linearOk = typeof CSS !== 'undefined' && !!CSS.supports && CSS.supports('animation-timing-function', 'linear(0, 1)');
  return linearOk;
};

/** Ressort SwiftUI `.spring(response:dampingFraction:)` → courbe CSS `linear()` + durée (repli : courbe à rebond). */
export function spring(response = 0.35, damping = 0.7): Spring {
  const w0 = (2 * Math.PI) / response;
  const z = damping;
  const settle = Math.min(2.2, Math.log(800) / (z * w0));
  if (!canLinear()) return { easing: z < 0.75 ? 'cubic-bezier(.34,1.4,.64,1)' : 'cubic-bezier(.22,1,.36,1)', duration: Math.round(settle * 700) };
  const pts: string[] = [];
  for (let i = 0; i <= 48; i++) {
    const t = (settle * i) / 48;
    let x: number;
    if (z < 1) {
      const wd = w0 * Math.sqrt(1 - z * z);
      x = 1 - Math.exp(-z * w0 * t) * (Math.cos(wd * t) + ((z * w0) / wd) * Math.sin(wd * t));
    } else x = 1 - Math.exp(-w0 * t) * (1 + w0 * t);
    pts.push((i === 48 ? 1 : x).toFixed(4));
  }
  return { easing: `linear(${pts.join(',')})`, duration: Math.round(settle * 1000) };
}

export const EASE = { out: 'cubic-bezier(.22,1,.36,1)', inOut: 'cubic-bezier(.65,0,.35,1)' } as const;

/** Graine fixe : la même pluie de confettis à chaque fois (jamais de hasard qui ressemble à un tirage). */
export function rng(seed: number) {
  let s = seed | 0;
  return () => {
    s = (s + 0x6d2b79f5) | 0;
    let t = Math.imul(s ^ (s >>> 15), 1 | s);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

type El = HTMLElement;
export type Anim = (target: string | El | null | undefined, frames: Keyframe[], delay: number, dur: number | Spring, easing?: string,
  fill?: FillMode) => void;
export type StageCtx = {
  a: Anim;
  q: (k: string) => El | null;
  qa: (k: string) => El[];
  root: El;
  /** Une boucle (respiration, halo) : coupée par « Réduire les animations », jamais finie par « Passer ». */
  loop: (target: El | null, frames: Keyframe[], options: KeyframeAnimationOptions) => void;
};

/** Vue repérée par une clé (`data-k`) pour la scène. */
export function K({ k, data, ...rest }: ViewProps & { k: string; data?: Record<string, string> }) {
  return <View {...rest} {...({ dataSet: { k, ...data } } as object)} />;
}

/**
 * Une scène : `build` lance toutes les animations à t = 0 ; `ended` passe à vrai à `end` ms, à « Passer » ou tout de
 * suite si « Réduire les animations ». `skip` finit tout d'un coup (un toucher n'importe où, comme les maquettes).
 */
export function useStage(build: (s: StageCtx) => void, end: number, deps: DependencyList) {
  const reduced = useReducedMotion();
  const root = useRef<View>(null);
  const anims = useRef<Animation[]>([]);
  const [endedFor, setEndedFor] = useState<unknown>(null);
  const runKey = deps.map(String).join('|');
  const ended = reduced || endedFor === runKey;

  const finish = useCallback(() => {
    for (const an of anims.current) {
      try {
        if (an.effect?.getComputedTiming().endTime !== Infinity) an.finish();
      } catch { /* déjà annulée */ }
    }
    setEndedFor(runKey);
  }, [runKey]);

  useLayoutEffect(() => {
    const el = root.current as unknown as El | null;
    const list: Animation[] = [];
    anims.current = list;
    if (reduced || !el || typeof el.animate !== 'function') return undefined;
    const a: Anim = (target, frames, delay, dur, easing, fill = 'both') => {
      const node = typeof target === 'string' ? el.querySelector<El>(`[data-k="${target}"]`) : target;
      if (!node) return;
      const timing: KeyframeAnimationOptions = typeof dur === 'number'
        ? { delay, duration: dur, easing: easing ?? EASE.out, fill }
        : { delay, duration: dur.duration, easing: dur.easing, fill };
      try {
        list.push(node.animate(frames, timing));
      } catch {
        list.push(node.animate(frames, { ...timing, easing: EASE.out }));
      }
    };
    const loop = (target: El | null, frames: Keyframe[], options: KeyframeAnimationOptions) => {
      if (target) list.push(target.animate(frames, options));
    };
    build({
      a, loop, root: el,
      q: (k) => el.querySelector<El>(`[data-k="${k}"]`),
      qa: (k) => Array.from(el.querySelectorAll<El>(`[data-k="${k}"]`)),
    });
    // À la fin, tout est posé même si l'onglet était en arrière-plan (la ligne de temps y est suspendue).
    const timer = setTimeout(() => {
      for (const an of list) {
        try {
          if (an.effect?.getComputedTiming().endTime !== Infinity) an.finish();
        } catch { /* annulée */ }
      }
      setEndedFor(runKey);
    }, end);
    return () => {
      clearTimeout(timer);
      for (const an of list) an.cancel();
      el.querySelectorAll('[data-fx]').forEach((n) => n.replaceChildren());
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- la scène se rejoue seulement quand ses données changent
  }, [reduced, runKey]);

  return { root, ended, reduced, skip: finish };
}

/** Calque vide (confettis, paillettes) que la scène remplit elle-même : React n'y touche jamais. */
export function FxLayer({ style }: { style?: ViewProps['style'] }) {
  return <View pointerEvents="none" aria-hidden style={style} {...({ dataSet: { fx: '1' } } as object)} />;
}

/** Confettis aux 6 couleurs des groupes : `count` morceaux, 1 200 ms au plus chacun, une seule fois. */
export function confetti(layer: El | null, a: Anim, { start, count = 90, seed = 11 }: { start: number; count?: number; seed?: number }) {
  if (!layer) return;
  const w = layer.clientWidth || 390;
  const h = layer.clientHeight || 844;
  const r = rng(seed);
  for (let i = 0; i < count; i++) {
    const piece = document.createElement('i');
    const k = r();
    const sz = 6 + r() * 7;
    piece.style.cssText = `position:absolute;left:0;top:0;width:${k < 0.45 ? sz * 0.55 : sz}px;height:${k < 0.45 ? sz * 1.5 : sz}px;`
      + `background:${CONFETTI[i % CONFETTI.length]};border-radius:${k > 0.75 ? '50%' : '2px'};opacity:0;will-change:transform`;
    layer.appendChild(piece);
    const x0 = w * 0.5 + (r() - 0.5) * 120;
    const y0 = -20;
    const x1 = r() * w;
    const y1 = h * (0.45 + r() * 0.55);
    const rot = (r() * 2 - 1) * 720;
    const d = 900 + r() * 300;
    const delay = start + r() * 160;
    const mx = (x0 + x1) / 2 + (r() - 0.5) * 80;
    const my = y0 + (y1 - y0) * 0.35;
    a(piece, [
      { transform: `translate(${x0}px,${y0}px) rotate(0deg) scale(.6)`, opacity: 0 },
      { transform: `translate(${mx}px,${my}px) rotate(${rot * 0.4}deg) scale(1)`, opacity: 1, offset: 0.25 },
      { transform: `translate(${x1}px,${y1}px) rotate(${rot}deg) scale(1)`, opacity: 1, offset: 0.8 },
      { transform: `translate(${x1 + (r() - 0.5) * 30}px,${y1 + 40}px) rotate(${rot * 1.1}deg) scale(.9)`, opacity: 0 },
    ], delay, d, 'cubic-bezier(.2,.7,.3,1)');
  }
}

/** Paillettes dorées qui MONTENT dans le faisceau (trophée) : jamais de confettis, réservés à une bonne réponse. */
export function glitter(layer: El | null, a: Anim, { start, count = 40, bottom = 500 }: { start: number; count?: number; bottom?: number }) {
  if (!layer) return;
  const w = layer.clientWidth || 390;
  const r = rng(5);
  for (let i = 0; i < count; i++) {
    const g = document.createElement('i');
    const s = 5 + r() * 7;
    const x = w / 2 + (r() - 0.5) * 230;
    g.style.cssText = `position:absolute;left:0;top:0;width:${s}px;height:${s}px;background:${['#FFE27A', '#FFF6CC', '#FFB347', '#CBBDFF'][i % 4]};`
      + 'clip-path:polygon(50% 0,62% 38%,100% 50%,62% 62%,50% 100%,38% 62%,0 50%,38% 38%);opacity:0';
    layer.appendChild(g);
    a(g, [
      { transform: `translate(${x}px,${bottom}px) scale(.4)`, opacity: 0 },
      { transform: `translate(${x + (r() - 0.5) * 30}px,${bottom - 120 - r() * 60}px) scale(1)`, opacity: 1, offset: 0.35 },
      { transform: `translate(${x + (r() - 0.5) * 60}px,${bottom - 350 + r() * 90}px) scale(.6)`, opacity: 0 },
    ], start + r() * 1100, 1100 + r() * 500, 'cubic-bezier(.2,.6,.3,1)');
  }
}

/**
 * Compteur qui monte RÉGULIÈREMENT de 0 à `to` (sortie douce), jamais de chiffres au hasard. Arrivé (ou sauté,
 * ou « Réduire les animations ») : la valeur finale tout de suite.
 */
export function Roll({ to, delay, duration = 450, done, prefix = '+', style }: {
  to: number; delay: number; duration?: number; done: boolean; prefix?: string; style?: StyleProp<TextStyle>;
}) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (done) return undefined;
    let raf = 0;
    const t0 = performance.now() + delay;
    const tick = (now: number) => {
      const k = Math.max(0, Math.min(1, (now - t0) / duration));
      setN(Math.round((1 - Math.pow(1 - k, 3)) * to));
      if (k < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [to, delay, duration, done]);
  return <Text style={style}>{prefix}{done ? to : n}</Text>;
}

/** Texte annoncé une fois aux lecteurs d'écran (après l'ouverture de la scène). */
export function Announce({ children }: { children: ReactNode }) {
  const [shown, setShown] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setShown(true), 300);
    return () => clearTimeout(t);
  }, []);
  return (
    <View accessibilityLiveRegion="polite" aria-live="polite" style={{ position: 'absolute', width: 1, height: 1, overflow: 'hidden', opacity: 0 }}>
      {shown ? <Text>{children}</Text> : null}
    </View>
  );
}
