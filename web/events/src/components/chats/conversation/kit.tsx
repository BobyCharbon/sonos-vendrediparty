import { createElement } from 'react';
import { Platform, type TextStyle, type ViewStyle } from 'react-native';

/**
 * Jetons de la conversation « Néon club » (Discussions v2, maquette 1-neon/4-conversation, _src/kit.css) : fond uni,
 * ma bulle violet profond (blanc dessus ≥ 4,7:1), celles des autres #1C1638 liserées de lavande, rose = agir,
 * orange = une soirée, menthe = « Je viens » / « écrit… ». Mêmes valeurs que KitTheme.tsx (Pronos) et ChatNeon.swift.
 */
export const C = {
  bg: '#0E0A1F', s1: '#1A1433', s1b: '#211943', s2: '#2A2150', sheet: '#17122E',
  glass: 'rgba(255,255,255,0.06)', glassLine: 'rgba(255,255,255,0.10)', line: 'rgba(255,255,255,0.07)', line2: 'rgba(255,255,255,0.14)',
  t1: '#F4F1FF', t2: '#A79FC7', t3: '#8C84AE',
  lav: '#B9A7FF', lavA: '#CBBDFF', lavB: '#7B6CF6', onLav: '#120B26',
  mineA: '#6E5CF0', mineB: '#5A48DA', theirs: '#1C1638', theirsLine: 'rgba(185,167,255,0.10)',
  pink: '#FF4F9A', pinkInk: '#FF6FAE', pinkA: '#FF7DB6', onPink: '#1F0618',
  mint: '#5BE3A6', onMint: '#062A1B', gold: '#FFE27A', coral: '#FFB347', sky: '#6CC7FF', danger: '#FF7A8A',
};

// Propriétés CSS du web (dégradés, flou, ombres) : absentes des types de React Native, rendues par react-native-web.
export const web = (style: ViewStyle & Record<string, unknown>) => style as ViewStyle;
export const webText = (style: TextStyle & Record<string, unknown>) => style as TextStyle;

const SYSTEM = Platform.OS === 'web' ? '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif' : undefined;
export const cf = {
  /** Bricolage Grotesque (déjà chargée) : noms de l'en-tête, titres des cartes de soirée. Jamais pour lire. */
  display: { fontFamily: 'BricolageGrotesque_800ExtraBold', letterSpacing: -0.3 } as TextStyle,
  text: { fontFamily: SYSTEM, fontWeight: '400' } as TextStyle,
  semibold: { fontFamily: SYSTEM, fontWeight: '600' } as TextStyle,
  bold: { fontFamily: SYSTEM, fontWeight: '700' } as TextStyle,
  /** Étiquette : capitales espacées 12/16 700 (séparateurs de jour, « SOIRÉE PARTY »). */
  label: { fontFamily: SYSTEM, fontWeight: '800', fontSize: 11, lineHeight: 14, letterSpacing: 0.8, textTransform: 'uppercase' } as TextStyle,
  num: webText({ fontFamily: SYSTEM, fontVariant: ['tabular-nums'] }),
};

/** Ma bulle : dégradé #6E5CF0 → #5A48DA et halo violet. */
export const mineBubble = web({ backgroundColor: C.mineA, backgroundImage: `linear-gradient(160deg, ${C.mineA}, ${C.mineB})`,
  boxShadow: '0 10px 24px -14px rgba(110,92,240,0.9)' });
export const lavButton = web({ backgroundColor: C.lavB, backgroundImage: `linear-gradient(135deg, ${C.lavA}, ${C.lavB})`,
  boxShadow: `0 0 18px -4px ${C.lavB}` });
export const pinkButton = web({ backgroundColor: C.pink, backgroundImage: `linear-gradient(135deg, ${C.pinkA}, ${C.pink})`,
  boxShadow: '0 10px 22px -12px rgba(255,79,154,0.9)' });
export const mintButton = web({ backgroundColor: C.mint, backgroundImage: 'linear-gradient(135deg, #7CEDBB, #5BE3A6)',
  boxShadow: '0 8px 18px -10px #5BE3A6' });
export const dateTileFill = web({ backgroundColor: '#FF7A59', backgroundImage: 'linear-gradient(150deg, #FFC977, #FF7A59)',
  boxShadow: 'inset 0 0 0 1.5px rgba(255,255,255,0.3), 0 8px 18px -10px #FF7A59' });

/** Couleur du nom d'un auteur (groupe, soirée) : dans la palette Néon, jamais hors palette (audit §4, 12). */
const NAME_COLORS = [C.lavA, C.pinkInk, C.mint, C.gold, C.coral, C.sky];
export function neonName(id: string): string {
  let h = 0;
  for (let i = 0; i < id.length; i += 1) h = (h * 31 + id.charCodeAt(i)) >>> 0;
  return NAME_COLORS[h % NAME_COLORS.length];
}

/** Dessins de la maquette (sprite de _src/build.py), traits 1,9 px, couleur du texte. */
const PATHS = {
  chevl: '<path d="m15 18-6-6 6-6"/>',
  more: '<circle cx="5" cy="12" r=".9"/><circle cx="12" cy="12" r=".9"/><circle cx="19" cy="12" r=".9"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  camera: '<path d="M3 8.5A2.5 2.5 0 0 1 5.5 6h2l1.6-2.2h5.8L16.5 6h2A2.5 2.5 0 0 1 21 8.5v9a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z"/><circle cx="12" cy="12.8" r="3.6"/>',
  mic: '<rect x="9" y="3" width="6" height="11.5" rx="3"/><path d="M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21"/>',
  send: '<path d="M12 19V5M5.5 11.5 12 5l6.5 6.5"/>',
  play: '<path fill="currentColor" stroke="none" d="M7 4.6v14.8c0 .8.9 1.3 1.6.9l12-7.4c.6-.4.6-1.4 0-1.8l-12-7.4C7.9 3.3 7 3.8 7 4.6z"/>',
  pause: '<path fill="currentColor" stroke="none" d="M7 4.5h3.2v15H7zM13.8 4.5H17v15h-3.2z"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  check2: '<path d="m2.5 12.5 4.5 4.5L15.5 7.5"/><path d="m11.5 16 1 1L21.5 7.5"/>',
  pin: '<path d="M12 16.5V22M8.5 3h7l-1 6 3.5 4.5h-12L9.5 9z"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  reply: '<path d="M9 14 4 9l5-5"/><path d="M4 9h10a6 6 0 0 1 6 6v4"/>',
  down: '<path d="M12 5v14M5.5 12.5 12 19l6.5-6.5"/>',
  sparkle: '<path d="M12 3c.6 4.6 2.4 6.4 7 7-4.6.6-6.4 2.4-7 7-.6-4.6-2.4-6.4-7-7 4.6-.6 6.4-2.4 7-7z"/>',
  flag: '<path d="M5 21V4M5 4h11.5l-2 4.5 2 4.5H5"/>',
  block: '<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
  copy: '<rect x="8" y="8" width="12" height="12" rx="2.5"/><path d="M16 8V6a2 2 0 0 0-2-2H6a2 2 0 0 0-2 2v8a2 2 0 0 0 2 2h2"/>',
  pencil: '<path d="M17.6 3.4a2 2 0 0 1 2.9 2.9L8.2 18.6 4 20l1.4-4.2z"/>',
  trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/>',
  lock: '<rect x="5" y="10.5" width="14" height="10" rx="2.5"/><path d="M8 10.5V7.5a4 4 0 0 1 8 0v3"/>',
  person: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  chat: '<path d="M21 11.5a8.5 8.5 0 0 1-12.4 7.6L3 20.5l1.5-5A8.5 8.5 0 1 1 21 11.5z"/>',
  megaphone: '<path d="M4 10v4h3l7 4V6L7 10z"/><path d="M17.5 9a4 4 0 0 1 0 6"/>',
} as const;
export type IconName = keyof typeof PATHS;

/** Icône SVG dans la page (le module ne tourne que sur le web), cachée aux lecteurs d'écran : le bouton porte le nom. */
export function Icon({ name, size = 22, color = 'currentColor', stroke = 1.9 }: { name: IconName; size?: number; color?: string; stroke?: number }) {
  return createElement('svg', {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color, color, strokeWidth: stroke,
    strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true, focusable: 'false', style: { display: 'block', flex: 'none' },
    dangerouslySetInnerHTML: { __html: PATHS[name] },
  });
}

/** Modifier son message : 15 minutes après l'envoi au plus (comme la base, `edit_window`). */
export const EDIT_WINDOW_MS = 15 * 60 * 1000;
export function editable(m: { created_at: string; deleted_at: string | null; pending?: boolean; body: string; audio_seconds?: number | null }, now = Date.now()): boolean {
  return !m.deleted_at && !m.pending && Boolean(m.body?.trim()) && m.audio_seconds == null
    && now - Date.parse(m.created_at) < EDIT_WINDOW_MS;
}
