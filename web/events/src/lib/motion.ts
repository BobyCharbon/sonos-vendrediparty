import { useRef } from 'react';
import { StyleSheet, type ViewStyle } from 'react-native';

/**
 * Animations du module (web seulement) : CSS pur, uniquement transform et opacity, joué par le compositeur.
 * Une animation d’entrée se joue quand l’élément apparaît (ouverture d’un écran, nouvelle carte, nouveau message),
 * jamais à un rechargement des données : les éléments déjà affichés gardent leur clé et ne sont pas recréés.
 * « Réduire les animations » (iPhone, Android, ordinateur) : tout apparaît directement, sans mouvement.
 */
export const reducedMotion = typeof window !== 'undefined' && typeof window.matchMedia === 'function'
  && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/** Courbes : sortie douce façon iOS, et léger rebond pour ce qui « se pose » (choix fait, réaction). */
export const ease = {
  out: 'cubic-bezier(.2, .9, .3, 1)',
  spring: 'cubic-bezier(.34, 1.4, .64, 1)',
  inOut: 'cubic-bezier(.45, 0, .55, 1)',
} as const;

export const duration = { fast: 140, base: 240, slow: 420 } as const;

/** Délai entre deux cartes qui entrent ensemble ; au-delà de quelques cartes, plus d’attente. */
const STAGGER_MS = 45;
const STAGGER_MAX = 6;

// Propriétés CSS propres à react-native-web (keyframes, transitions) : absentes des types de React Native.
type WebStyle = ViewStyle & Record<string, unknown>;
const web = (style: WebStyle) => style as ViewStyle;

const keyframes = StyleSheet.create({
  rise: web({
    animationKeyframes: [{ from: { opacity: 0, transform: 'translateY(10px)' }, to: { opacity: 1, transform: 'none' } }],
    animationDuration: `${duration.slow}ms`, animationTimingFunction: ease.out, animationFillMode: 'backwards',
  }),
  fade: web({
    animationKeyframes: [{ from: { opacity: 0 }, to: { opacity: 1 } }],
    animationDuration: `${duration.base}ms`, animationTimingFunction: ease.out, animationFillMode: 'backwards',
  }),
  drop: web({
    animationKeyframes: [{ from: { opacity: 0, transform: 'translateY(-6px)' }, to: { opacity: 1, transform: 'none' } }],
    animationDuration: `${duration.base}ms`, animationTimingFunction: ease.out, animationFillMode: 'backwards',
  }),
  pop: web({
    animationKeyframes: [{ '0%': { transform: 'scale(.6)' }, '60%': { transform: 'scale(1.15)' }, '100%': { transform: 'scale(1)' } }],
    animationDuration: '360ms', animationTimingFunction: ease.out, animationFillMode: 'backwards',
  }),
  press: web({
    animationKeyframes: [{ '0%': { transform: 'scale(1)' }, '40%': { transform: 'scale(.94)' }, '100%': { transform: 'scale(1)' } }],
    animationDuration: '320ms', animationTimingFunction: ease.out,
  }),
  bubbleMine: web({
    animationKeyframes: [{ from: { opacity: 0, transform: 'translateY(12px) scale(.9)' }, to: { opacity: 1, transform: 'none' } }],
    animationDuration: '300ms', animationTimingFunction: ease.spring, animationFillMode: 'backwards', transformOrigin: 'bottom right',
  }),
  bubbleTheirs: web({
    animationKeyframes: [{ from: { opacity: 0, transform: 'translateY(12px) scale(.9)' }, to: { opacity: 1, transform: 'none' } }],
    animationDuration: '300ms', animationTimingFunction: ease.spring, animationFillMode: 'backwards', transformOrigin: 'bottom left',
  }),
  pulse: web({
    animationKeyframes: [{ '0%': { opacity: 1 }, '50%': { opacity: 0.35 }, '100%': { opacity: 1 } }],
    animationDuration: '2400ms', animationTimingFunction: ease.inOut, animationIterationCount: 'infinite',
  }),
  glow: web({
    animationKeyframes: [{ '0%': { opacity: 0.45 }, '50%': { opacity: 1 }, '100%': { opacity: 0.45 } }],
    animationDuration: '2400ms', animationTimingFunction: ease.inOut, animationIterationCount: 'infinite',
  }),
  shimmer: web({
    animationKeyframes: [{ '0%': { opacity: 0.5 }, '50%': { opacity: 1 }, '100%': { opacity: 0.5 } }],
    animationDuration: '1400ms', animationTimingFunction: ease.inOut, animationIterationCount: 'infinite',
  }),
  recording: web({
    animationKeyframes: [{ '0%': { opacity: 1, transform: 'scale(1)' }, '50%': { opacity: 0.4, transform: 'scale(.8)' }, '100%': { opacity: 1, transform: 'scale(1)' } }],
    animationDuration: '1200ms', animationTimingFunction: ease.inOut, animationIterationCount: 'infinite',
  }),
});

export type Enter = keyof typeof keyframes;

/** Style d’animation (entrée ou boucle), rien si « réduire les animations ». `index` : décalage en cascade. */
export function enter(kind: Enter, index = 0): ViewStyle | undefined {
  if (reducedMotion) return undefined;
  if (!index) return keyframes[kind];
  return [keyframes[kind], web({ animationDelay: `${Math.min(index, STAGGER_MAX) * STAGGER_MS}ms` })] as unknown as ViewStyle;
}

/** Transition CSS des propriétés données (couleurs, transform, opacité…) quand le style change. */
export function transition(properties: string, ms: number = duration.base, curve: string = ease.out): ViewStyle | undefined {
  if (reducedMotion) return undefined;
  return web({ transitionProperty: properties, transitionDuration: `${ms}ms`, transitionTimingFunction: curve });
}

/** Retour au toucher des boutons : l’enfoncement suit le doigt, le relâchement revient en douceur. */
export const pressTransition = transition('transform, opacity, background-color, border-color', duration.fast);

/**
 * Vrai dès que `value` a changé depuis le premier affichage : une animation de retour (choix posé, nouvel état)
 * ne se joue que pour un vrai changement, pas à l’ouverture de l’écran ni à un rechargement identique.
 */
export function useChangedSinceMount<V>(value: V): boolean {
  const first = useRef(value);
  const changed = useRef(false);
  // eslint-disable-next-line react-hooks/refs -- mémoire d’affichage, pas un état : rien à re-rendre
  if (!changed.current && !Object.is(first.current, value)) changed.current = true;
  // eslint-disable-next-line react-hooks/refs
  return changed.current;
}
