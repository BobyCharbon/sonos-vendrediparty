import { createContext, createElement, useContext, type ReactNode } from 'react';
import { Platform, useColorScheme, type TextStyle, type ViewStyle } from 'react-native';

/**
 * Jetons « Néon club » des Discussions v2 (maquettes discussions/1-neon, kit.css) : mêmes valeurs que les Pronos v2
 * (components/pronos/KitTheme.tsx, ios PronoKit.swift), plus ce qui est propre aux discussions (bulles, encre sur rose,
 * soirées en orange). Lavande = toi / choisi ; rose = agir ou à lire ; orange = une soirée ; menthe = « Je viens ».
 *
 * `N` = le thème sombre (celui de Party) : `N.bg`, `N.pink`… ; `N.dark` / `N.light` pour choisir ; dans un composant :
 * `const c = useNeon()` (sombre comme tout Party, sauf sous `<NeonTheme scheme="light">` ou `"auto"` = suit l'appareil).
 */

// Propriétés CSS du web (dégradés, flou, masques, ombres) : absentes des types de React Native, rendues par react-native-web.
export type WebStyle = ViewStyle & Record<string, unknown>;
export const web = (style: WebStyle) => style as ViewStyle;
export const webText = (style: TextStyle & Record<string, unknown>) => style as TextStyle;

export type NeonScheme = 'dark' | 'light';

const dark = {
  scheme: 'dark' as NeonScheme,
  stage: '#0A0718', bg: '#0E0A1F', s1: '#1A1433', s1b: '#211943', s2: '#2A2150',
  glass: 'rgba(255,255,255,0.06)', glass2: 'rgba(255,255,255,0.09)', glassLine: 'rgba(255,255,255,0.10)',
  line: 'rgba(255,255,255,0.08)', line2: 'rgba(255,255,255,0.14)',
  t1: '#F4F1FF', t2: '#A79FC7', t3: '#8C84AE',
  /** Lavande : texte et icônes ; lavHi → lavB : dégradé du filtre choisi, de ma bulle claire. */
  lav: '#B9A7FF', lavHi: '#CBBDFF', lavB: '#7B6CF6',
  /** Ma bulle : blanc dessus ≥ 4,7:1. */
  mineA: '#6E5CF0', mineB: '#5A48DA',
  theirs: '#1C1638', theirsLine: 'rgba(185,167,255,0.10)',
  /** Rose : pastilles, @, bouton principal ; encre foncée dessus (6,2:1), jamais du blanc (3,1:1). */
  pink: '#FF4F9A', pinkA: '#FF7DB6', pinkInk: '#FF6FAE', onPink: '#1F0618',
  mint: '#5BE3A6', gold: '#FFE27A', coral: '#FFB347', sky: '#6CC7FF', danger: '#FF7A8A',
  /** Soirées : tuile date orange (encre brune dessus). */
  partyA: '#FFC977', partyB: '#FF7A59', onParty: '#2A1406',
  /** Pastille d'une discussion en sourdine (grise, jamais cachée). */
  muteBg: '#2A2150', muteInk: '#A79FC7',
  chipOn: '#120B26', halo: 'rgba(123,108,246,0.26)', sheet: '#17122E', scrim: 'rgba(6,3,16,0.62)',
  glowA: 'rgba(123,108,246,0.30)', glowB: 'rgba(255,79,154,0.12)',
  shadow: '0 18px 40px -18px rgba(0,0,0,.7)',
};
export type NeonColors = typeof dark;

const light: NeonColors = {
  ...dark,
  scheme: 'light',
  stage: '#E9E4FA', bg: '#F6F3FF', s1: '#FFFFFF', s1b: '#FBF9FF', s2: '#EEE9FF',
  glass: 'rgba(255,255,255,0.72)', glass2: 'rgba(255,255,255,0.9)', glassLine: 'rgba(29,21,48,0.08)',
  line: 'rgba(29,21,48,0.08)', line2: 'rgba(29,21,48,0.14)',
  t1: '#1D1530', t2: '#564E78', t3: '#6E6790',
  lav: '#6A5AE0',
  theirs: '#FFFFFF', theirsLine: 'rgba(29,21,48,0.08)',
  pinkInk: '#C21F68',
  mint: '#0A7A4E', coral: '#B25E00', danger: '#C6334A',
  muteBg: '#E3DDF7', muteInk: '#564E78',
  chipOn: '#FFFFFF', halo: 'rgba(123,108,246,0.14)', sheet: '#FFFFFF', scrim: 'rgba(29,21,48,0.38)',
  glowA: 'rgba(123,108,246,0.16)', glowB: 'rgba(255,79,154,0.08)',
  shadow: '0 16px 36px -20px rgba(40,30,90,.35)',
};

export const N = Object.assign({ ...dark }, { dark, light });

const SYSTEM = Platform.OS === 'web' ? '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif' : undefined;

/** Typo : Bricolage pour les titres (jamais pour lire les messages), système pour le reste, chiffres tabulaires. */
export const chatFont = {
  /** Grand titre 36/40, noms d'en-tête, chiffre des tuiles date. */
  display: { fontFamily: 'BricolageGrotesque_800ExtraBold', fontWeight: '800', letterSpacing: -0.4 } as TextStyle,
  text: { fontFamily: SYSTEM, fontWeight: '400' } as TextStyle,
  medium: { fontFamily: SYSTEM, fontWeight: '500' } as TextStyle,
  semibold: { fontFamily: SYSTEM, fontWeight: '600' } as TextStyle,
  bold: { fontFamily: SYSTEM, fontWeight: '700' } as TextStyle,
  heavy: { fontFamily: SYSTEM, fontWeight: '800' } as TextStyle,
  num: webText({ fontFamily: SYSTEM, fontVariant: ['tabular-nums'] }),
  /** Étiquette 12/16 700 en capitales espacées. */
  label: { fontFamily: SYSTEM, fontWeight: '700', fontSize: 12, lineHeight: 16, letterSpacing: 0.9, textTransform: 'uppercase' } as TextStyle,
};

const SchemeContext = createContext<'auto' | NeonScheme>('dark');

/** Thème des Discussions pour une page : sombre (défaut, comme Party), clair, ou celui de l'appareil. */
export function NeonTheme({ scheme, children }: { scheme: 'auto' | NeonScheme; children: ReactNode }) {
  return createElement(SchemeContext.Provider, { value: scheme }, children);
}

/** Couleurs du thème courant. */
export function useNeon(): NeonColors {
  const wanted = useContext(SchemeContext);
  const system = useColorScheme();
  return (wanted === 'auto' ? system : wanted) === 'light' ? light : dark;
}

/** Lueurs douces en haut de l'écran (seulement en haut : le reste reste calme). */
export function glow(c: NeonColors): ViewStyle {
  return web({
    position: 'absolute', top: 0, left: 0, right: 0, height: 420, pointerEvents: 'none',
    backgroundImage: `radial-gradient(120% 46% at 92% -12%, ${c.glowA}, transparent 60%), radial-gradient(80% 34% at -18% 2%, ${c.glowB}, transparent 62%)`,
  });
}

/** Couleur #RRGGBB → rgba(…, a). */
export function alpha(hex: string, a: number): string {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
