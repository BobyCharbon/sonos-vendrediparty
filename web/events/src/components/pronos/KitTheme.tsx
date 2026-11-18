import { createContext, createElement, useContext, useSyncExternalStore, type ReactNode } from 'react';
import { Platform, useColorScheme, type TextStyle, type ViewStyle } from 'react-native';

import { GROUP_COLORS } from '@/lib/groups';

/**
 * Jetons de la direction C « Néon club » (Pronos v2, maquettes 1-kit.css, 3-1-fiche-choix.html, 4-kit.css).
 * Mêmes valeurs que ios/Party/Pronos/PronoKit.swift (PronoTheme). Importer depuis '@/components/pronos/Kit'.
 */

// Propriétés CSS du web (dégradés, flou, masques) : absentes des types de React Native, rendues par react-native-web.
export type WebStyle = ViewStyle & Record<string, unknown>;
export const web = (style: WebStyle) => style as ViewStyle;
export const webText = (style: TextStyle & Record<string, unknown>) => style as TextStyle;

export type PronoScheme = 'dark' | 'light';

const dark = {
  scheme: 'dark' as PronoScheme,
  bg: '#0E0A1F', stage: '#0A0718', s1: '#1A1433', s1b: '#211943',
  glass: 'rgba(255,255,255,0.06)', glassLine: 'rgba(255,255,255,0.10)', s3: 'rgba(255,255,255,0.06)',
  line: 'rgba(255,255,255,0.08)', line2: 'rgba(255,255,255,0.14)',
  t1: '#F4F1FF', t2: '#A79FC7', t3: '#8C84AE',
  lav: '#B9A7FF', lavA: '#B9A7FF', lavB: '#7B6CF6',
  pink: '#FF4F9A', pinkInk: '#FF6FAE', pinkFill: '#D42A76',
  mint: '#5BE3A6', mintInk: '#5BE3A6', gold: '#FFE27A', goldInk: '#FFE27A',
  miss: '#8B84A8', amber: '#FFB347', amberInk: '#FFB347', danger: '#FF7A8A',
  potato: '#F5C27A', potatoInk: '#F5C27A', onPotato: '#2A1A06',
  ink: '#0E0A1F', halo: 'rgba(123,108,246,0.22)', chipDark: 'rgba(14,10,31,0.55)', kindChip: 'rgba(255,255,255,0.88)',
  cardShadow: '0 1px 0 rgba(255,255,255,.04) inset, 0 18px 40px -24px rgba(0,0,0,.8)',
  shadow: '0 18px 40px -18px rgba(0,0,0,.7)',
};
export type PronoColors = typeof dark;

const light: PronoColors = {
  scheme: 'light',
  bg: '#F6F3FF', stage: '#0A0718', s1: '#FFFFFF', s1b: '#FBF9FF',
  glass: 'rgba(255,255,255,0.72)', glassLine: 'rgba(26,20,51,0.08)', s3: 'rgba(29,21,48,0.05)',
  line: 'rgba(29,21,48,0.08)', line2: 'rgba(29,21,48,0.14)',
  t1: '#1D1530', t2: '#564E78', t3: '#6E6790',
  lav: '#6A5AE0', lavA: '#B9A7FF', lavB: '#7B6CF6',
  pink: '#FF4F9A', pinkInk: '#D42A76', pinkFill: '#D42A76',
  mint: '#5BE3A6', mintInk: '#0A7A4E', gold: '#FFE27A', goldInk: '#8A6200',
  miss: '#6E6790', amber: '#FFB347', amberInk: '#B25E00', danger: '#C6334A',
  potato: '#F5C27A', potatoInk: '#A0601A', onPotato: '#2A1A06',
  ink: '#0E0A1F', halo: 'rgba(123,108,246,0.10)', chipDark: 'rgba(14,10,31,0.55)', kindChip: 'rgba(255,255,255,0.88)',
  cardShadow: '0 1px 2px rgba(29,21,48,.05), 0 14px 34px -20px rgba(76,52,160,.30)',
  shadow: '0 16px 36px -20px rgba(40,30,90,.35)',
};

const SYSTEM = Platform.OS === 'web' ? '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif' : undefined;
const ROUNDED = Platform.OS === 'web' ? 'ui-rounded, "SF Pro Rounded", -apple-system, BlinkMacSystemFont, system-ui, sans-serif' : undefined;

/** Typo : questions en ui-rounded 800, chiffres larges et tabulaires, étiquettes en capitales espacées. */
export const pronoFont = {
  /** Question, grand titre : ui-rounded 800 (tailles : 22/26 carte, 30/34 fiche, 34/40 titre, 17/21 compacte). */
  round: { fontFamily: ROUNDED, fontWeight: '800' } as TextStyle,
  roundBold: { fontFamily: ROUNDED, fontWeight: '700' } as TextStyle,
  /** Chiffres : SF Pro large (font-stretch expanded), 800, tabulaires. */
  num: webText({ fontFamily: SYSTEM, fontWeight: '800', fontVariant: ['tabular-nums'], fontStretch: 'expanded', letterSpacing: -0.2 }),
  text: { fontFamily: SYSTEM, fontWeight: '500' } as TextStyle,
  semibold: { fontFamily: SYSTEM, fontWeight: '600' } as TextStyle,
  bold: { fontFamily: SYSTEM, fontWeight: '700' } as TextStyle,
  /** Étiquette : 11/14 700 CAPITALES +0,08 em. */
  label: { fontFamily: SYSTEM, fontWeight: '700', fontSize: 11, lineHeight: 14, letterSpacing: 0.9, textTransform: 'uppercase' } as TextStyle,
};

export const pronoRadius = { card: 24, inner: 16, pill: 20, tile: 14, button: 16, buttonLg: 18, chip: 999, yesNo: 28 };
export const pronoSpace = { screen: 16, screenFiche: 20, card: 18, betweenCards: 14, betweenSections: 28, betweenPills: 10 };
/** Courbes et durées (coupées par « Réduire les animations »). */
export const pronoMotion = {
  spring: 'cubic-bezier(.34,1.56,.64,1)', quint: 'cubic-bezier(.22,1,.36,1)', inOut: 'cubic-bezier(.45,0,.55,1)',
  press: 350, rise: 420, stagger: 50, seal: 500, roll: 300,
};

/** Formes des réponses (toujours forme + couleur + texte). Couleurs sombre / clair. */
export const SHAPES = [
  { key: 'triangle', glyph: '▲', name: 'triangle', dark: '#FF6FAE', light: '#C8327A' },
  { key: 'diamond', glyph: '◆', name: 'losange', dark: '#6CC7FF', light: '#1F6FD1' },
  { key: 'circle', glyph: '●', name: 'rond', dark: '#FFB347', light: '#B86A00' },
  { key: 'square', glyph: '■', name: 'carré', dark: '#B9A7FF', light: '#6A5AE0' },
  { key: 'hexagon', glyph: '⬢', name: 'hexagone', dark: '#5BE3A6', light: '#13915C' },
  { key: 'star', glyph: '★', name: 'étoile', dark: '#FFE27A', light: '#9A7B00' },
  { key: 'down', glyph: '▼', name: 'triangle pointe en bas', dark: '#9DDBFF', light: '#1C6E9E' },
  { key: 'plus', glyph: '✚', name: 'croix', dark: '#FF9F7A', light: '#B4471F' },
] as const;
export type ShapeKey = 'triangle' | 'diamond' | 'circle' | 'square' | 'hexagon' | 'star' | 'down' | 'plus';
/** Forme de la n-ième réponse (▲ ◆ ● ■ ⬢ ★ ▼ ✚). */
export const SHAPE_KEYS: ShapeKey[] = SHAPES.map((s) => s.key);
export type ShapeRef = ShapeKey | number;
export function shapeOf(s: ShapeRef) {
  return typeof s === 'number' ? SHAPES[((s % SHAPES.length) + SHAPES.length) % SHAPES.length] : SHAPES.find((x) => x.key === s) ?? SHAPES[0];
}
export function shapeColor(s: ShapeRef, scheme: PronoScheme = 'dark'): string {
  return shapeOf(s)[scheme];
}

/** Couleurs d'un groupe (6 couleurs de groups.ts : from → to) ; inconnue : lavande (événement : orange). */
export function groupLook(color?: string | null) {
  const key = (color && color in GROUP_COLORS ? color : 'lavender') as keyof typeof GROUP_COLORS;
  return GROUP_COLORS[key];
}
/** Dégradé 135° d'un groupe. */
export function groupGradient(color?: string | null, angle = 135): ViewStyle {
  const g = groupLook(color);
  return web({ backgroundColor: g.main, backgroundImage: `linear-gradient(${angle}deg, ${g.from}, ${g.to})` });
}
/** Les 6 couleurs de Party (confettis, barres). */
export const GROUP_FX_COLORS = ['#FF4F9A', '#FFB347', '#5BE3A6', '#6CC7FF', '#B9A7FF', '#FFE27A'] as const;

/** Couleur #RRGGBB → rgba(…, a). */
export function alpha(hex: string, a: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}

/** Couleur stable d'une personne (dégradé des avatars sans photo). */
export function faceLook(id: string) {
  const keys = Object.keys(GROUP_COLORS) as (keyof typeof GROUP_COLORS)[];
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return GROUP_COLORS[keys[h % keys.length]!];
}

// ───────── Thème courant (sombre par défaut, comme Party) ─────────
const SchemeContext = createContext<PronoScheme>('dark');

/**
 * Thème des Pronos. `<PronoTheme scheme="auto">` autour d'une page Pronos plein écran (suit l'appareil : mode clair
 * compris) ; sans fournisseur, tout est sombre (comme le reste de Party). Jetons : PronoTheme.dark / .light / .font /
 * .radius / .space / .motion / .shapes ; dans un composant : `const c = usePronoTheme()`.
 */
function PronoThemeProvider({ scheme = 'auto', children }: { scheme?: 'auto' | PronoScheme; children: ReactNode }) {
  const system = useColorScheme();
  const value: PronoScheme = scheme === 'auto' ? (system === 'light' ? 'light' : 'dark') : scheme;
  return createElement(SchemeContext.Provider, { value }, children);
}
export const PronoTheme = Object.assign(PronoThemeProvider, {
  dark, light, font: pronoFont, radius: pronoRadius, space: pronoSpace, motion: pronoMotion, shapes: SHAPES,
});

/** Couleurs du thème courant. */
export function usePronoTheme(): PronoColors {
  return useContext(SchemeContext) === 'light' ? light : dark;
}
export function usePronoScheme(): PronoScheme {
  return useContext(SchemeContext);
}

// ───────── « Réduire les animations » ─────────
const QUERY = '(prefers-reduced-motion: reduce)';
function subscribe(cb: () => void) {
  if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return () => undefined;
  const mq = window.matchMedia(QUERY);
  mq.addEventListener?.('change', cb);
  return () => mq.removeEventListener?.('change', cb);
}
const snapshot = () => typeof window !== 'undefined' && typeof window.matchMedia === 'function' && window.matchMedia(QUERY).matches;

/** Vrai si l'appareil demande moins d'animations (suit le réglage en direct). */
export function useReducedMotion(): boolean {
  return useSyncExternalStore(subscribe, snapshot, () => false);
}
