import type { TextStyle, ViewStyle } from 'react-native';

import { palette } from '@/lib/groups';

/**
 * Jetons du dévoilement, du résultat et du classement (direction C « Néon club », maquettes 4-* du 18.11).
 * Propres à reveal/ et board/ pour ne dépendre de rien d'autre ; mêmes valeurs que le kit commun des Pronos.
 */

type WebStyle = Omit<ViewStyle, 'position'> & { position?: ViewStyle['position'] | 'fixed' } & Record<string, unknown>;
type WebText = TextStyle & Record<string, unknown>;
/** Propriétés CSS du web (dégradés, flou, clip-path…), rendues telles quelles par react-native-web. */
export const web = (style: WebStyle) => style as ViewStyle;
export const webText = (style: WebText) => style as TextStyle;

export const N = {
  stage: '#0A0718',
  bg: '#0E0A1F',
  s1: '#1A1433',
  s3: '#221A3D',
  glass: 'rgba(30,23,58,0.86)',
  line: 'rgba(255,255,255,0.08)',
  line2: 'rgba(255,255,255,0.14)',
  lav: '#B9A7FF',
  lav2: '#7B6CF6',
  pink: '#FF4F9A',
  pinkBtn: '#D42A76',
  mint: '#5BE3A6',
  lemon: '#FFE27A',
  miss: '#8B84A8',
  missText: '#C9C4DD',
  warn: '#FFB347',
  warnText: '#FFD08F',
  t1: '#F4F1FF',
  t2: '#A79FC7',
  t3: '#6E6790',
  ink: '#1D1530',
} as const;

const SYSTEM = '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif';
const ROUNDED = 'ui-rounded, "SF Pro Rounded", -apple-system, system-ui, sans-serif';

/** Questions, prénoms en grand : arrondi, 800. */
export const round = (size: number, lineHeight = Math.round(size * 1.12)): TextStyle =>
  webText({ fontFamily: ROUNDED, fontWeight: '800', fontSize: size, lineHeight, letterSpacing: -0.2, color: N.t1 });
/** Texte courant. */
export const text = (size: number, weight: TextStyle['fontWeight'] = '500', color: string = N.t1): TextStyle =>
  ({ fontFamily: SYSTEM, fontWeight: weight, fontSize: size, color });
/** Chiffres : larges, tabulaires (jamais de chiffres qui sautent). */
export const num = (size: number, color: string = N.t1): TextStyle =>
  webText({ fontFamily: SYSTEM, fontWeight: '800', fontSize: size, color, fontVariant: ['tabular-nums'], fontStretch: '125%',
    letterSpacing: -0.2 });
/** Petites capitales espacées (« LA BONNE RÉPONSE »). */
export const label = (color: string = N.t2): TextStyle =>
  ({ fontFamily: SYSTEM, fontWeight: '700', fontSize: 12, letterSpacing: 1, textTransform: 'uppercase', color });
/** Bandeau compressé (« LE RÉSULTAT »). */
export const band: TextStyle = webText({ fontFamily: SYSTEM, fontWeight: '900', fontSize: 15, letterSpacing: 2, color: N.ink,
  fontStretch: '75%' });

/** Couleurs du terrain : le groupe, sinon la lavande de Party (événement, personnes choisies). */
export function terrainLook(group: { color?: string | null; emoji?: string } | null | undefined) {
  const p = group ? palette(group.color) : { from: '#CBBDFF', to: '#7B6CF6', main: '#B9A7FF' };
  return { from: p.from, to: p.to, main: p.main, emoji: group?.emoji ?? '🔮' };
}

/** Les 6 couleurs des groupes, pour les confettis (jamais d'autres). */
export const CONFETTI = ['#FF4F9A', '#FF8FC0', '#FF7A59', '#FFC977', '#22B07D', '#7CEDBB', '#3D8BFF', '#8FD6FF', '#7B6CF6', '#CBBDFF',
  '#FFB347', '#FFEA9C'];

/** Formes des réponses (forme + libellé, jamais la couleur seule) : mêmes clés et même ordre que le kit (ShapeKey). */
export type ShapeKey = 'triangle' | 'diamond' | 'circle' | 'square' | 'hexagon' | 'star' | 'down' | 'plus';
export const SHAPES: readonly { key: ShapeKey; name: string; clip: string }[] = [
  { key: 'triangle', name: 'triangle', clip: 'polygon(50% 6%, 96% 92%, 4% 92%)' },
  { key: 'diamond', name: 'losange', clip: 'polygon(50% 0, 100% 50%, 50% 100%, 0 50%)' },
  { key: 'circle', name: 'rond', clip: 'circle(48% at 50% 50%)' },
  { key: 'square', name: 'carré', clip: 'inset(8% round 14%)' },
  { key: 'hexagon', name: 'hexagone', clip: 'polygon(25% 4%, 75% 4%, 100% 50%, 75% 96%, 25% 96%, 0 50%)' },
  { key: 'star', name: 'étoile', clip: 'polygon(50% 2%, 63% 36%, 98% 38%, 70% 60%, 80% 96%, 50% 75%, 20% 96%, 30% 60%, 2% 38%, 37% 36%)' },
  { key: 'down', name: 'triangle à l’envers', clip: 'polygon(4% 8%, 96% 8%, 50% 94%)' },
  { key: 'plus', name: 'croix', clip: 'polygon(35% 0, 65% 0, 65% 35%, 100% 35%, 100% 65%, 65% 65%, 65% 100%, 35% 100%, 35% 65%, 0 65%, 0 35%, 35% 35%)' },
];
export const shapeAt = (i: number) => SHAPES[((i % SHAPES.length) + SHAPES.length) % SHAPES.length];
