import { createElement, useEffect, useId, useState, type ReactNode } from 'react';
import { ActivityIndicator, Image, Pressable, StyleSheet, Text, View, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';

import { Avatar } from '@/components/ui';
import { initials } from '@/lib/format';
import { useGroupImage } from '@/lib/groups';
import { kindLabel, NO_VALUE, PATATE, type Face, type PronoKind } from '@/lib/pronos';

import {
  alpha, faceLook, groupLook, pronoFont, pronoMotion, shapeColor, shapeOf, usePronoScheme, usePronoTheme, useReducedMotion, web,
  type ShapeKey, type ShapeRef,
} from './KitTheme';

/**
 * KIT des Pronos v2 (web) — direction C « Néon club ». Maquettes : scratchpad pronos-v2/maquettes (1-kit.css, 3-*, 4-kit.css).
 * Tout s'importe d'ici : `import { CoverBand, Seal, … } from '@/components/pronos/Kit'`.
 * Mode clair : entourer une page plein écran de `<PronoTheme scheme="auto">` ; sans cela, tout est sombre.
 * « Réduire les animations » : chaque animation est coupée (useReducedMotion). Formes + couleurs : jamais la couleur seule.
 *
 * MODE D'EMPLOI (props ; ? = facultatif)
 * Thème
 *  - PronoTheme({ scheme?: 'auto'|'dark'|'light', children }) : fournisseur ; jetons statiques PronoTheme.dark / .light
 *    (bg, s1, s1b, glass, glassLine, s3, line, line2, t1, t2, t3, lav, lavA, lavB, pink, pinkInk, pinkFill, mint, mintInk,
 *    gold, goldInk, miss, amber, amberInk, danger, potato, potatoInk, onPotato, ink, halo, cardShadow, shadow),
 *    .font (round, roundBold, num, text, semibold, bold, label), .radius, .space, .motion, .shapes.
 *  - usePronoTheme() → couleurs du thème courant ; usePronoScheme() → 'dark'|'light' ; useReducedMotion() → boolean.
 *  - PronoBackground({ children, style? }) : fond de page (couleur + halo lavande en haut).
 * Couvertures, cartes
 *  - CoverBand({ group?, event?, cover?, height? = 64 (vedette 88), hero? (fiche : 236, fondu vers le fond), children? (posés
 *    par-dessus), style? }) : dégradé + emoji en filigrane SEULEMENT ; puces facultatives : context?: string (puce du groupe en
 *    haut à gauche), kind?: PronoKind (puce du type en haut à droite), award?: string (libellé de la puce trophée).
 *  - GlassCard({ children, solid? (surface pleine + ombre), glow?: 'urgent'|'won'|'soon', radius? = 24, padding? = 18, style?, testID? })
 *  - SectionLabel({ children, right?: ReactNode, caps? = true (CAPITALES 11/700) | false (13/600), style? })
 *  - PrimaryButton({ label, onPress, tone?: 'pink'|'mint'|'glass'|'lav', size?: 'md' (52)|'lg' (58), icon?: 'lock'|ReactNode,
 *    disabled?, loading?, testID?, accessibilityLabel?, style? })
 *  - Segmented({ items: { key, label, count?, soft? }[], value, onChange(key), testID? }) : onglets « À jouer / En attente / Terminés ».
 * Joueurs
 *  - PronoAvatar({ face, size? = 28, ring?: couleur, me? (pastille ✓ menthe) }) : photo, sinon initiales sur dégradé.
 *  - AvatarStack({ faces, extra?: nombre « +N », size? = 28, max? = 4, ring? }) : pile qui se chevauche, le 1er au-dessus.
 *  - Seal({ emoji?, face?, color?: couleur du groupe, size? = 30, broken? (craque), me? (✓), ghost? (« ? » pas encore),
 *    lock? = true, ring?, index? (décalage d'apparition), label? }) : sceau festonné ; ≥ 80 = sceau vedette (halo qui respire).
 *  - SealRow({ faces, total?, me?: boolean|id, color?, size?, max? = 6, layout?: 'row'|'overlap'|'grid', ring? })
 *    row / overlap : total = nombre de réponses scellées (« +N » au-delà de `max`) ; me = true : mon sceau d'abord (✓).
 *    grid : total = joueurs attendus ; montre les noms + les sceaux « pas encore » sans nom (nombre seulement).
 * Temps
 *  - Countdown({ closesAt, variant?: 'card' (défaut, carte entière de la fiche)|'chip' (puce des listes), label?, onEnd?, testID? }) : 3 paliers
 *    (> 1 h calme ; < 1 h minutes ambre + point qui respire ; < 60 s anneau rose qui se vide) ; « Fermé » après.
 * Réponses
 *  - ChoicePill({ label, shape: ShapeKey|index, selected?, color?, onPress?, result?: 'right'|'wrong', sub?, compact?,
 *    disabled?, trailing?, testID?, accessibilityLabel? }) : pastille à forme (64) ; compact = 48 (cartes de liste).
 *  - ShapeKey = 'triangle'|'diamond'|'circle'|'square'|'hexagon'|'star'|'down'|'plus' ; SHAPE_KEYS[i] = forme de la i-ème réponse.
 *  - ShapeMark({ shape, size? = 20, color?, filled? = true }) : ▲ ◆ ● ■ ⬢ ★ ▼ ✚ dessinés (couleur de la forme par défaut).
 *  - KindIcon({ kind, size? = 11, color? }) ; KindChip({ kind, label? }) ; kindLabel(kind) → « Choix », « Oui / Non »…
 * Patates (n'afficher que si showPatates(p) : lib/pronos)
 *  - PatateBadge({ n, tone?: 'neutral'|'win'|'lav'|'gold'|'potato'|'miss', sign? (+), size?: 'md'|'lg' })
 *  - BagChip({ bag: { balance } | null, onPress?, label? = 'Ton sac', testID? })
 *  - FieldLine({ total, planters?, style? }) : « 🎊 42 sur la piste · 6 lanceurs ».
 *  - NoValueNote({ children?, style? }) : rappel « Les confettis n'ont aucune valeur… » (obligatoire sous chaque sac).
 *  - PatateSlider({ value, onChange, max? = 20, available?: sac + déjà planté ici, showNumber? = true, caption?, testID? })
 * Effets (KitFx) : Confetti({ run, variant?: 'confetti'|'sparkle', count? }), Spotlight({ on, color? }),
 *   NumberRoll({ value, from? = 0, duration? = 300, sign?, suffix?, style? }).
 */

export * from './KitTheme';
export { kindLabel } from '@/lib/pronos';
export { Confetti, NumberRoll, PatateSlider, Spotlight } from './KitFx';

// ───────── Animations (CSS, transform et opacité seulement) ─────────
const anim = StyleSheet.create({
  rise: web({ animationKeyframes: [{ from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'none' } }],
    animationDuration: '420ms', animationTimingFunction: pronoMotion.quint, animationFillMode: 'backwards' }),
  sealIn: web({ animationKeyframes: [{ from: { opacity: 0, transform: 'scale(.4) rotate(-20deg)' }, to: { opacity: 1, transform: 'none' } }],
    animationDuration: '500ms', animationTimingFunction: pronoMotion.spring, animationFillMode: 'backwards' }),
  breathe: web({ animationKeyframes: [{ '0%': { opacity: 1, transform: 'scale(1)' }, '50%': { opacity: 0.35, transform: 'scale(.8)' }, '100%': { opacity: 1, transform: 'scale(1)' } }],
    animationDuration: '1600ms', animationTimingFunction: pronoMotion.inOut, animationIterationCount: 'infinite' }),
  halo: web({ animationKeyframes: [{ '0%': { opacity: 0.55 }, '50%': { opacity: 0.85 }, '100%': { opacity: 0.55 } }],
    animationDuration: '2400ms', animationTimingFunction: pronoMotion.inOut, animationIterationCount: 'infinite' }),
  pulseCard: web({ animationKeyframes: [{ '0%': { transform: 'scale(1)' }, '50%': { transform: 'scale(1.012)' }, '100%': { transform: 'scale(1)' } }],
    animationDuration: '1000ms', animationTimingFunction: pronoMotion.inOut, animationIterationCount: 'infinite' }),
  crackL: web({ animationKeyframes: [{ '0%': { transform: 'none', opacity: 1 }, '100%': { transform: 'translate(-14%, 8%) rotate(-16deg)', opacity: 0 } }],
    animationDuration: '480ms', animationTimingFunction: pronoMotion.quint, animationFillMode: 'forwards' }),
  crackR: web({ animationKeyframes: [{ '0%': { transform: 'none', opacity: 1 }, '100%': { transform: 'translate(14%, 10%) rotate(14deg)', opacity: 0 } }],
    animationDuration: '480ms', animationTimingFunction: pronoMotion.quint, animationFillMode: 'forwards' }),
  glide: web({ animationKeyframes: [{ from: { transform: 'translateX(0) scale(1.1)' }, to: { transform: 'translateX(-6%) scale(1.1)' } }],
    animationDuration: '14s', animationTimingFunction: pronoMotion.inOut, animationIterationCount: 'infinite', animationDirection: 'alternate' }),
  pop: web({ animationKeyframes: [{ '0%': { transform: 'scale(.4)', opacity: 0 }, '100%': { transform: 'scale(1)', opacity: 1 } }],
    animationDuration: '300ms', animationTimingFunction: pronoMotion.spring, animationFillMode: 'backwards' }),
});
/** Style d'animation, rien si « Réduire les animations ». */
export function useAnim(kind: keyof typeof anim, delayMs = 0): ViewStyle | undefined {
  const reduced = useReducedMotion();
  if (reduced) return undefined;
  return delayMs ? ([anim[kind], web({ animationDelay: `${delayMs}ms` })] as unknown as ViewStyle) : anim[kind];
}
const pressStyle = (reduced: boolean) => (reduced ? undefined : web({ transitionProperty: 'transform, box-shadow, background-color, border-color',
  transitionDuration: `${pronoMotion.press}ms`, transitionTimingFunction: pronoMotion.spring }));

// ───────── Dessins (SVG dans la page : le module ne tourne que sur le web) ─────────
const svg = (props: Record<string, unknown>, ...children: ReactNode[]) => createElement('svg', { 'aria-hidden': true, focusable: 'false', ...props }, ...children);
const path = (d: string, props: Record<string, unknown> = {}) => createElement('path', { d, key: d, ...props });

/** Bord festonné : r(θ) = R·(1 − a·(1 − cos nθ)/2), dans un carré de 100. */
function sealPath(lobes: number, amp: number): string {
  const pts: string[] = [];
  for (let i = 0; i < 180; i += 1) {
    const t = (i / 180) * Math.PI * 2;
    const r = 49.5 * (1 - amp * (1 - Math.cos(lobes * t)) / 2);
    pts.push(`${(50 + r * Math.cos(t)).toFixed(2)},${(50 + r * Math.sin(t)).toFixed(2)}`);
  }
  return `M${pts.join(' L')}Z`;
}
const SEAL_SMALL = sealPath(12, 0.09);
const SEAL_BIG = sealPath(18, 0.06);

type Paint = { fill: string; stroke?: string; strokeWidth?: number; strokeLinejoin: 'round' };
const SHAPE_PATHS: Record<ShapeKey, (p: Paint) => ReactNode> = {
  triangle: (p) => path('M10 2.5 18 17H2z', p),
  diamond: (p) => path('M10 1.5 18.5 10 10 18.5 1.5 10z', p),
  circle: (p) => createElement('circle', { key: 'c', cx: 10, cy: 10, r: 8.2, ...p }),
  square: (p) => createElement('rect', { key: 'r', x: 2.5, y: 2.5, width: 15, height: 15, rx: 2.5, ...p }),
  hexagon: (p) => path('M10 1.5 17.4 5.75v8.5L10 18.5 2.6 14.25v-8.5z', p),
  star: (p) => path('M10 1.6l2.5 5.2 5.7.8-4.1 4 1 5.7L10 14.6l-5.1 2.7 1-5.7-4.1-4 5.7-.8z', p),
  down: (p) => path('M10 17.5 18 3H2z', p),
  plus: (p) => path('M7.5 2h5v5.5H18v5h-5.5V18h-5v-5.5H2v-5h5.5z', p),
};

/** Forme d'une réponse (▲ ◆ ● ■ ⬢ ★ ▼ ✚), dessinée ; `filled={false}` : contour seulement. */
export function ShapeMark({ shape, size = 20, color, filled = true }: { shape: ShapeRef; size?: number; color?: string; filled?: boolean }) {
  const scheme = usePronoScheme();
  const s = shapeOf(shape);
  const col = color ?? s[scheme];
  const paint: Paint = filled ? { fill: col, stroke: s.key === 'triangle' || s.key === 'down' ? col : undefined, strokeWidth: 1.2, strokeLinejoin: 'round' }
    : { fill: 'none', stroke: col, strokeWidth: 1.8, strokeLinejoin: 'round' };
  return svg({ width: size, height: size, viewBox: '0 0 20 20', style: { display: 'block', flex: 'none' } }, SHAPE_PATHS[s.key](paint));
}

const LOCK = (fill: string) => svg({ width: '100%', height: '100%', viewBox: '0 0 12 12' },
  createElement('rect', { key: 'b', x: 3, y: 5.4, width: 6, height: 4.4, rx: 1, fill }),
  path('M4.3 5.5V4.2a1.7 1.7 0 0 1 3.4 0v1.3', { fill: 'none', stroke: fill, strokeWidth: 1.2 }));
const CHECK = (stroke: string, w = 1.8) => svg({ width: '100%', height: '100%', viewBox: '0 0 12 12' },
  path('M3 6.2l2 2 4-4.4', { fill: 'none', stroke, strokeWidth: w, strokeLinecap: 'round', strokeLinejoin: 'round' }));
const CLOCK = (stroke: string, size = 14) => svg({ width: size, height: size, viewBox: '0 0 24 24' },
  createElement('circle', { key: 'c', cx: 12, cy: 12, r: 9, fill: 'none', stroke, strokeWidth: 2 }),
  path('M12 7v5l3 2', { fill: 'none', stroke, strokeWidth: 2, strokeLinecap: 'round', strokeLinejoin: 'round' }));
const CALENDAR = (stroke: string, size = 14) => svg({ width: size, height: size, viewBox: '0 0 24 24' },
  createElement('rect', { key: 'r', x: 3.5, y: 5, width: 17, height: 15, rx: 3, fill: 'none', stroke, strokeWidth: 2 }),
  path('M3.5 10h17M8 3v4M16 3v4', { fill: 'none', stroke, strokeWidth: 2, strokeLinecap: 'round' }));
const INFO = (stroke: string) => svg({ width: 14, height: 14, viewBox: '0 0 24 24' },
  createElement('circle', { key: 'c', cx: 12, cy: 12, r: 9, fill: 'none', stroke, strokeWidth: 1.8 }),
  path('M12 11v6M12 7.5v.5', { fill: 'none', stroke, strokeWidth: 2, strokeLinecap: 'round' }));

// ───────── Fond de page ─────────
export function PronoBackground({ children, style }: { children?: ReactNode; style?: StyleProp<ViewStyle> }) {
  const c = usePronoTheme();
  return (
    <View style={[{ flex: 1, backgroundColor: c.bg }, web({ backgroundImage: `radial-gradient(120% 420px at 70% -80px, ${c.halo}, transparent 70%)` }), style]}>
      {children}
    </View>
  );
}

// ───────── Avatars ─────────
/** Visage : vraie photo quand elle existe, sinon initiales sur dégradé (couleur stable de la personne). */
export function PronoAvatar({ face, size = 28, ring, me }: { face: Face; size?: number; ring?: string; me?: boolean }) {
  const c = usePronoTheme();
  const look = faceLook(face.id);
  const showMe = me ?? false;
  return (
    <View style={[{ width: size, height: size, borderRadius: size / 2 }, ring ? web({ boxShadow: `0 0 0 2px ${ring}` }) : null]}
      accessibilityLabel={face.me ? 'Toi' : face.name}>
      {face.avatar_url ? (
        <Avatar id={face.id} name={face.name} photo={face.avatar_url} size={size} profile={false} />
      ) : (
        <View style={[{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center' },
          web({ backgroundColor: look.main, backgroundImage: `linear-gradient(135deg, ${look.from}, ${look.to})` })]}>
          <Text style={[pronoFont.round, { color: '#1D1530', fontSize: Math.max(9, size * 0.36), letterSpacing: -0.3 }]}>{initials(face.name)}</Text>
        </View>
      )}
      {showMe ? (
        <View style={[st.badge, { width: Math.max(13, size * 0.42), height: Math.max(13, size * 0.42), right: -3, bottom: -3, backgroundColor: c.mint },
          web({ boxShadow: `0 0 0 2px ${ring ?? c.s1}` })]}>{CHECK(c.ink)}</View>
      ) : null}
    </View>
  );
}

/** Pile de visages qui se chevauchent (le premier au-dessus, anneau de la couleur de la surface), puis « +N ». */
export function AvatarStack({ faces, extra, size = 28, max = 4, ring }: { faces: Face[]; extra?: number; size?: number; max?: number; ring?: string }) {
  const c = usePronoTheme();
  const shown = faces.slice(0, max);
  const more = extra ?? Math.max(0, faces.length - shown.length);
  const r = ring ?? c.s1;
  if (!shown.length && !more) return null;
  const names = faces.map((f) => (f.me ? 'toi' : f.name)).join(', ');
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }} accessible accessibilityLabel={more ? `${names} et ${more} autre${more > 1 ? 's' : ''}` : names}>
      {shown.map((f, i) => (
        <View key={f.id} style={{ marginLeft: i ? -Math.round(size * 0.22) : 0, zIndex: shown.length - i }}>
          <PronoAvatar face={f} size={size} ring={r} />
        </View>
      ))}
      {more > 0 ? (
        <View style={[{ marginLeft: shown.length ? -2 : 0, height: size, minWidth: size, paddingHorizontal: 4, borderRadius: size / 2, alignItems: 'center',
          justifyContent: 'center', backgroundColor: c.s1b }, web({ boxShadow: `0 0 0 2px ${r}, inset 0 0 0 1px ${c.line2}` })]}>
          <Text style={[pronoFont.bold, { color: c.t1, fontSize: Math.max(10, size * 0.38), fontVariant: ['tabular-nums'] }]}>+{more}</Text>
        </View>
      ) : null}
    </View>
  );
}

// ───────── Sceaux ─────────
type SealProps = {
  emoji?: string | null; face?: Face | null; color?: string | null; size?: number; broken?: boolean; me?: boolean; ghost?: boolean;
  lock?: boolean; ring?: string; index?: number; label?: string;
};

function SealWax({ id, size, color, hero }: { id: string; size: number; color?: string | null; hero: boolean }) {
  const g = groupLook(color);
  const d = size >= 40 ? SEAL_BIG : SEAL_SMALL;
  return svg({ width: size, height: size, viewBox: '0 0 100 100', style: { position: 'absolute', inset: 0, display: 'block' } },
    createElement('defs', { key: 'd' },
      createElement('linearGradient', { key: 'g', id: `${id}g`, x1: 0, y1: 0, x2: 1, y2: 1 },
        createElement('stop', { key: 'a', offset: 0, stopColor: g.from }), createElement('stop', { key: 'b', offset: 1, stopColor: g.to })),
      createElement('radialGradient', { key: 'h', id: `${id}h`, cx: 0.32, cy: 0.26, r: 0.6 },
        createElement('stop', { key: 'a', offset: 0, stopColor: '#fff', stopOpacity: 0.55 }), createElement('stop', { key: 'b', offset: 0.5, stopColor: '#fff', stopOpacity: 0 }))),
    path(d, { fill: `url(#${id}g)` }),
    path(d, { key: 'hi', fill: `url(#${id}h)` }),
    createElement('circle', { key: 'in', cx: 50, cy: 50, r: hero ? 38 : 37, fill: 'none', stroke: hero ? 'rgba(255,255,255,.6)' : 'rgba(29,21,48,.16)',
      strokeWidth: hero ? 1.6 : 3, strokeDasharray: hero ? '4 5' : undefined }));
}

/** Sceau festonné à la couleur du groupe : une réponse cachée. `broken` le fait craquer (dévoilement). */
export function Seal({ emoji, face, color, size = 30, broken, me, ghost, lock = true, ring, index = 0, label }: SealProps) {
  const c = usePronoTheme();
  const rawId = useId();
  const id = `seal${rawId.replace(/[^a-zA-Z0-9]/g, '')}`;
  const reduced = useReducedMotion();
  const enterStyle = useAnim('sealIn', index * 60);
  const haloStyle = useAnim('halo');
  const hero = size >= 80;
  const g = groupLook(color);
  const r = ring ?? c.s1;
  const a11y = label ?? (ghost ? 'Pas encore joué' : face ? `Réponse scellée de ${face.me ? 'toi' : face.name}` : 'Réponse scellée');
  if (ghost) {
    return (
      <View accessible accessibilityRole="image" accessibilityLabel={a11y}
        style={[{ width: size, height: size, borderRadius: size / 2, borderWidth: 1.5, borderStyle: 'dashed', borderColor: c.t3, alignItems: 'center', justifyContent: 'center' }]}>
        <Text style={[pronoFont.bold, { color: c.t2, fontSize: size * 0.36 }]}>?</Text>
      </View>
    );
  }
  const inner = face ? (
    size >= 40
      ? <PronoAvatar face={{ ...face, avatar_url: hero ? face.avatar_url : null }} size={Math.round(size * 0.56)} />
      : <Text style={[pronoFont.round, { color: me || face.me ? c.ink : 'rgba(29,21,48,0.8)', fontSize: Math.max(9, size * 0.3), letterSpacing: -0.3 }]}>{initials(face.name)}</Text>
  ) : emoji ? <Text style={{ fontSize: size * 0.42, lineHeight: size * 0.5 }}>{emoji}</Text> : null;
  const body = (
    <>
      <SealWax id={id} size={size} color={color} hero={hero} />
      <View style={[StyleSheet.absoluteFill, { alignItems: 'center', justifyContent: 'center' }]}>{inner}</View>
    </>
  );
  const badgeSize = Math.max(12, Math.round(size * (hero ? 0.3 : 0.4)));
  const isMe = me ?? face?.me ?? false;
  return (
    <View accessible accessibilityRole="image" accessibilityLabel={a11y}
      style={[{ width: size, height: size }, size >= 40 ? web({ filter: `drop-shadow(0 6px 12px ${alpha(g.to, 0.45)})` }) : null,
        isMe && size < 40 ? web({ filter: `drop-shadow(0 0 8px ${alpha(g.to, 0.7)})` }) : null, broken ? null : enterStyle]}>
      {hero ? <View pointerEvents="none" style={[{ position: 'absolute', inset: -size * 0.18, borderRadius: size }, web({ backgroundImage: `radial-gradient(circle, ${alpha(g.to, 0.55)}, transparent 65%)` }), haloStyle]} /> : null}
      {broken ? (
        <>
          <View style={[StyleSheet.absoluteFill, web({ clipPath: 'polygon(0 0, 52% 0, 44% 30%, 56% 52%, 42% 74%, 50% 100%, 0 100%)' }),
            reduced ? web({ opacity: 0.35, transform: 'translate(-8%, 4%) rotate(-10deg)' }) : anim.crackL]}>{body}</View>
          <View style={[StyleSheet.absoluteFill, web({ clipPath: 'polygon(52% 0, 100% 0, 100% 100%, 50% 100%, 42% 74%, 56% 52%, 44% 30%)' }),
            reduced ? web({ opacity: 0.35, transform: 'translate(8%, 6%) rotate(9deg)' }) : anim.crackR]}>{body}</View>
        </>
      ) : body}
      {!broken && (isMe || lock) ? (
        <View style={[st.badge, { width: badgeSize, height: badgeSize, right: -size * 0.04, bottom: -size * 0.04, padding: badgeSize * 0.14,
          backgroundColor: isMe ? c.mint : '#160F2C' }, web({ boxShadow: `0 0 0 2px ${r}` })]}>
          {isMe ? CHECK(c.ink) : LOCK('#F4F1FF')}
        </View>
      ) : null}
    </View>
  );
}

/** Rangée de sceaux : un par réponse cachée (le mien d'abord, ✓ menthe), puis « +N ». 'grid' : noms + « pas encore ». */
export function SealRow({ faces, total, me, color, size, max = 6, layout = 'row', ring }: {
  faces: Face[]; total?: number; me?: string | boolean | null; color?: string | null; size?: number; max?: number;
  layout?: 'row' | 'overlap' | 'grid'; ring?: string;
}) {
  const c = usePronoTheme();
  const isMe = (f: Face) => !!f.me || (typeof me === 'string' && f.id === me);
  const mine = faces.filter(isMe);
  // me = true sans visage marqué : j'ai joué, mon sceau vient en premier (« Toi »).
  const ordered = [...(me === true && !mine.length ? [{ id: 'me', name: 'Toi', avatar_url: null, me: true }] : mine), ...faces.filter((f) => !isMe(f))];
  if (layout === 'grid') {
    const s = size ?? 48;
    const waiting = Math.max(0, (total ?? ordered.length) - ordered.length);
    const ghosts = Math.min(waiting, 10);
    return (
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', rowGap: 14 }} accessibilityLabel={`${ordered.length} réponse${ordered.length > 1 ? 's' : ''} scellée${ordered.length > 1 ? 's' : ''}${waiting ? `, ${waiting} pas encore` : ''}`}>
        {ordered.map((f, i) => (
          <View key={f.id} style={{ width: '20%', alignItems: 'center', gap: 6 }}>
            <Seal face={f} color={color} size={s} me={isMe(f)} index={i} ring={ring} lock={!isMe(f)} />
            <Text numberOfLines={1} style={[pronoFont.semibold, { color: c.t1, fontSize: 13 }]}>{isMe(f) ? 'Toi' : f.name.split(' ')[0]}</Text>
          </View>
        ))}
        {Array.from({ length: ghosts }, (_, i) => (
          <View key={`g${i}`} style={{ width: '20%', alignItems: 'center' }}><Seal ghost size={s} /></View>
        ))}
        {waiting > ghosts ? <Text style={[pronoFont.bold, { color: c.t2, alignSelf: 'center' }]}>+{waiting - ghosts}</Text> : null}
      </View>
    );
  }
  const s = size ?? (layout === 'overlap' ? 40 : 30);
  const shown = ordered.slice(0, max);
  const more = Math.max(0, (total ?? ordered.length) - shown.length);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: layout === 'row' ? 5 : 0 }}
      accessible accessibilityLabel={`${ordered.length} réponse${ordered.length > 1 ? 's' : ''} scellée${ordered.length > 1 ? 's' : ''}`}>
      {shown.map((f, i) => (
        <View key={f.id} style={{ marginLeft: layout === 'overlap' && i ? -s * 0.25 : 0, zIndex: shown.length - i }}>
          <Seal face={f} color={color} size={s} me={isMe(f)} index={i} ring={ring} />
        </View>
      ))}
      {more > 0 ? (
        layout === 'overlap' ? (
          <View style={[{ marginLeft: -s * 0.15, width: s, height: s, borderRadius: s / 2, alignItems: 'center', justifyContent: 'center', backgroundColor: c.s1 },
            web({ boxShadow: `0 0 0 2px ${ring ?? c.bg}, inset 0 0 0 1px ${c.glassLine}` })]}>
            <Text style={[pronoFont.bold, { color: c.t1, fontSize: 13 }]}>+{more}</Text>
          </View>
        ) : <Text style={[pronoFont.bold, { color: c.t2, fontSize: 13, marginLeft: 6 }]}>+{more}</Text>
      ) : null}
    </View>
  );
}

// ───────── Compte à rebours (3 paliers) ─────────
const TZ = 'Europe/Zurich';
const hourOf = (d: Date) => {
  const [h, m] = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: false }).format(d).split(':');
  return m === '00' ? `${Number(h)} h` : `${Number(h)} h ${m}`;
};
const ymd = (d: Date) => new Intl.DateTimeFormat('en-CA', { timeZone: TZ }).format(d);
const pad = (n: number) => String(n).padStart(2, '0');

/** « ce soir », « demain », « sam. 21 nov. » (heure de Suisse). */
function dayWord(d: Date, now: Date): string {
  const days = Math.round((Date.parse(`${ymd(d)}T00:00:00Z`) - Date.parse(`${ymd(now)}T00:00:00Z`)) / 86_400_000);
  if (days === 0) return Number(new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, hour: 'numeric', hour12: false }).format(d)) >= 17 ? 'ce soir' : 'aujourd’hui';
  if (days === 1) return 'demain';
  return new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' }).format(d);
}

/** « Ce soir », « Demain », « Samedi » (cette semaine), sinon « Sam. 28 nov. ». */
function dayLong(d: Date, now: Date): string {
  const days = Math.round((Date.parse(`${ymd(d)}T00:00:00Z`) - Date.parse(`${ymd(now)}T00:00:00Z`)) / 86_400_000);
  const word = days < 2 ? dayWord(d, now)
    : new Intl.DateTimeFormat('fr-CH', days < 7 ? { timeZone: TZ, weekday: 'long' } : { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' }).format(d);
  return word.charAt(0).toUpperCase() + word.slice(1);
}

export type CountdownTier ='calm' | 'soon' | 'last' | 'closed';
export function countdownTier(closesAt: string, now: number): CountdownTier {
  const left = Date.parse(closesAt) - now;
  if (left <= 0) return 'closed';
  if (left < 60_000) return 'last';
  if (left < 3_600_000) return 'soon';
  return 'calm';
}

/** Heure qui avance : chaque seconde sous 1 h, chaque 30 s sinon. */
function useNow(closesAt: string): number {
  const [now, setNow] = useState(() => Date.now());
  const left = Date.parse(closesAt) - now;
  const step = left < 3_660_000 && left > -2000 ? 1000 : 30_000;
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), step);
    return () => clearInterval(t);
  }, [step]);
  return now;
}

function Ring({ fraction, size, color, track, children }: { fraction: number; size: number; color: string; track: string; children?: ReactNode }) {
  const reduced = useReducedMotion();
  const sw = size >= 40 ? 4 : 3.5;
  const rad = (size - sw) / 2;
  const len = 2 * Math.PI * rad;
  return (
    <View style={{ width: size, height: size, alignItems: 'center', justifyContent: 'center' }}>
      {svg({ width: size, height: size, viewBox: `0 0 ${size} ${size}`, style: { position: 'absolute', inset: 0, transform: 'rotate(-90deg)' } },
        createElement('circle', { key: 't', cx: size / 2, cy: size / 2, r: rad, fill: 'none', stroke: track, strokeWidth: sw }),
        createElement('circle', { key: 'r', cx: size / 2, cy: size / 2, r: rad, fill: 'none', stroke: color, strokeWidth: sw, strokeLinecap: 'round',
          strokeDasharray: len, strokeDashoffset: len * (1 - Math.max(0, Math.min(1, fraction))),
          style: reduced ? undefined : { transition: 'stroke-dashoffset 1s linear' } }))}
      {children}
    </View>
  );
}

/** Compte à rebours : > 1 h calme (date ou « Dans 2 h 14 ») ; < 1 h minutes en ambre ; < 60 s anneau rose qui se vide. */
export function Countdown({ closesAt, variant = 'card', label = 'Fin des réponses', onEnd, testID }: {
  closesAt: string; variant?: 'chip' | 'card'; label?: string; onEnd?: () => void; testID?: string;
}) {
  const c = usePronoTheme();
  const now = useNow(closesAt);
  const tier = countdownTier(closesAt, now);
  const breathe = useAnim('breathe');
  const pulse = useAnim('pulseCard');
  const end = new Date(closesAt);
  const left = Math.max(0, Date.parse(closesAt) - now);
  const secs = Math.ceil(left / 1000);
  useEffect(() => { if (tier === 'closed') onEnd?.(); }, [tier, onEnd]);
  const nowD = new Date(now);
  const when = `${dayWord(end, nowD)} ${hourOf(end)}`;
  const a11y = tier === 'closed' ? 'Réponses fermées'
    : tier === 'last' ? `Fin dans ${secs} secondes`
      : tier === 'soon' ? `Fin dans ${Math.ceil(left / 60_000)} minutes`
        : `Fin ${when}`;

  if (variant === 'card') {
    const days = Math.floor(left / 86_400_000);
    const hours = Math.floor((left % 86_400_000) / 3_600_000);
    const mins = Math.floor((left % 3_600_000) / 60_000);
    const tone = tier === 'soon' ? c.amberInk : tier === 'last' ? c.pinkInk : c.lav;
    const cardTone = tier === 'soon' ? { borderColor: alpha(c.amber, 0.45), backgroundColor: alpha(c.amber, 0.09) }
      : tier === 'last' ? { borderColor: alpha('#F2468F', 0.5), backgroundColor: alpha('#F2468F', 0.1) } : null;
    const unit = (n: string, u: string) => (
      <Text key={u}><Text style={[pronoFont.num, { color: c.t1, fontSize: 22 }]}>{n}</Text><Text style={[pronoFont.semibold, { color: c.t2, fontSize: 12 }]}>{` ${u}  `}</Text></Text>
    );
    return (
      <View testID={testID} accessible accessibilityRole="timer" accessibilityLabel={a11y}
        style={[st.cdCard, { backgroundColor: c.glass, borderColor: c.glassLine }, web({ backdropFilter: 'blur(20px)' }), cardTone, tier === 'last' ? pulse : null]}>
        {tier === 'last' ? (
          <Ring fraction={secs / 60} size={48} color={c.pink} track={alpha(c.pink, 0.18)}>
            <Text style={[pronoFont.num, { color: c.pinkInk, fontSize: 16 }]}>{secs}</Text>
          </Ring>
        ) : (
          <View style={[st.cdIco, { backgroundColor: alpha(tier === 'soon' ? c.amber : c.lavA, tier === 'soon' ? 0.18 : 0.14) }]}>{CLOCK(tone, 20)}</View>
        )}
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={[pronoFont.semibold, { color: tier === 'soon' ? c.amberInk : c.t2, fontSize: 13 }]}>
            {tier === 'closed' ? 'Réponses fermées' : tier === 'soon' ? 'Moins d’une heure' : tier === 'last' ? 'Dernières secondes' : label}
          </Text>
          <Text style={[pronoFont.roundBold, { color: c.t1, fontSize: 16, marginTop: 1 }]} numberOfLines={1}>
            {tier === 'calm' ? `${dayLong(end, nowD)}, ${hourOf(end)}`
              : `${tier === 'closed' ? 'Fermé' : 'Fin'} à ${hourOf(end)}${dayWord(end, nowD) === 'ce soir' ? ', ce soir' : ''}`}
          </Text>
          {tier === 'soon' ? (
            <View style={[st.cdBar, { backgroundColor: c.line }]}><View style={{ height: 4, borderRadius: 2, width: `${(left / 3_600_000) * 100}%`, backgroundColor: c.amber }} /></View>
          ) : null}
        </View>
        {tier === 'calm' ? (
          <Text>{days ? unit(String(days), 'j') : null}{unit(days ? pad(hours) : String(hours), 'h')}{unit(pad(mins), 'min')}</Text>
        ) : tier === 'soon' ? (
          <Text style={[pronoFont.num, { color: c.amberInk, fontSize: 26 }]}>{pad(Math.floor(secs / 60))}:{pad(secs % 60)}</Text>
        ) : null}
      </View>
    );
  }

  // Puce (cartes de liste)
  if (tier === 'last') {
    return (
      <View testID={testID} accessible accessibilityRole="timer" accessibilityLabel={a11y}
        style={[st.cd, { paddingLeft: 6, backgroundColor: alpha(c.pink, 0.14), borderColor: alpha(c.pink, 0.4) }]}>
        <Ring fraction={secs / 60} size={22} color={c.pink} track={alpha(c.pink, 0.18)} />
        <Text style={[pronoFont.num, { color: c.pinkInk, fontSize: 13 }]}>0:{pad(secs)}</Text>
      </View>
    );
  }
  if (tier === 'soon') {
    return (
      <View testID={testID} accessible accessibilityRole="timer" accessibilityLabel={a11y}
        style={[st.cd, { backgroundColor: alpha(c.amber, 0.14), borderColor: alpha(c.amber, 0.35) }]}>
        <View style={[{ width: 7, height: 7, borderRadius: 4, backgroundColor: c.amber }, breathe]} />
        <Text style={[pronoFont.num, { color: c.amberInk, fontSize: 13 }]}>{Math.ceil(left / 60_000)} min</Text>
      </View>
    );
  }
  const close = left < 86_400_000;
  const text = tier === 'closed' ? 'Fermé' : close
    ? `Dans ${Math.floor(left / 3_600_000)} h ${pad(Math.floor((left % 3_600_000) / 60_000))}`
    : `Jusqu’à ${new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'short' }).format(end)} ${hourOf(end)}`;
  return (
    <View testID={testID} accessible accessibilityRole="timer" accessibilityLabel={a11y} style={[st.cd, { backgroundColor: c.s3, borderColor: c.line }]}>
      {tier === 'closed' ? <View style={{ width: 13, height: 13 }}>{LOCK(c.t2)}</View> : close ? CLOCK(c.t2) : CALENDAR(c.t2)}
      <Text style={[pronoFont.bold, { color: c.t2, fontSize: 13, fontVariant: ['tabular-nums'] }]}>{text}</Text>
    </View>
  );
}

// ───────── Patates ─────────
type BadgeTone = 'neutral' | 'win' | 'lav' | 'gold' | 'potato' | 'miss';
/** « +14 🥔 » en pastille. Jamais de signe moins sur la récolte d'un prono (une perte s'affiche en gris, sans chiffre négatif). */
export function PatateBadge({ n, tone = 'neutral', sign, size = 'md' }: { n: number; tone?: BadgeTone; sign?: boolean; size?: 'md' | 'lg' }) {
  const c = usePronoTheme();
  const tones: Record<BadgeTone, { bg: string; bd: string; fg: string }> = {
    neutral: { bg: c.s3, bd: c.line, fg: c.t1 },
    win: { bg: alpha(c.mint, 0.14), bd: alpha(c.mint, 0.4), fg: c.mintInk },
    lav: { bg: alpha(c.lavA, 0.14), bd: alpha(c.lavA, 0.35), fg: c.lav },
    gold: { bg: alpha(c.gold, 0.14), bd: alpha(c.gold, 0.4), fg: c.goldInk },
    potato: { bg: alpha(c.potato, 0.12), bd: alpha(c.potato, 0.35), fg: c.potatoInk },
    miss: { bg: c.s3, bd: c.line, fg: c.miss },
  };
  const t = tones[tone];
  const big = size === 'lg';
  const shown = `${sign && n > 0 ? '+' : n < 0 ? '−' : ''}${Math.abs(n)}`;
  return (
    <View accessible accessibilityLabel={`${sign && n > 0 ? 'plus ' : n < 0 ? 'moins ' : ''}${Math.abs(n)} confetti${Math.abs(n) > 1 ? 's' : ''}`}
      style={[st.pt, { height: big ? 34 : 26, paddingHorizontal: big ? 12 : 9, borderRadius: big ? 17 : 13, backgroundColor: t.bg, borderColor: t.bd }]}>
      <Text style={[pronoFont.num, { color: t.fg, fontSize: big ? 17 : 13 }]}>{shown}</Text>
      <Text style={{ fontSize: big ? 15 : 12 }}>{PATATE}</Text>
    </View>
  );
}

/** « Ton sac : 85 🥔 » (capsule patate). Rien si `bag` est vide. */
export function BagChip({ bag, onPress, label = 'Ton sac', testID = 'prono-bag-chip' }: { bag: { balance: number; refill_at?: string | null; max_stake?: number | null } | null | undefined; onPress?: () => void; label?: string; testID?: string }) {
  const c = usePronoTheme();
  const reduced = useReducedMotion();
  if (!bag) return null;
  const inner = (
    <>
      <Text style={[pronoFont.bold, { color: c.potatoInk, fontSize: 14 }]}>{label} :</Text>
      <Text style={[pronoFont.num, { color: c.potatoInk, fontSize: 15 }]}>{bag.balance}</Text>
      <Text style={{ fontSize: 13 }}>{PATATE}</Text>
    </>
  );
  const style = [st.bag, { backgroundColor: alpha(c.potato, 0.12), borderColor: alpha(c.potato, 0.35) }];
  const a11y = `${label} : ${bag.balance} confettis`;
  if (!onPress) return <View testID={testID} accessible accessibilityLabel={a11y} style={style}>{inner}</View>;
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={`${a11y}. Ouvrir ton sac`} onPress={onPress}
      style={({ pressed }) => [style, { minHeight: 44 }, pressStyle(reduced), pressed && { transform: [{ scale: 0.97 }] }]}>
      {inner}
    </Pressable>
  );
}

/** « 🎊 42 sur la piste · 6 lanceurs » (jamais de multiplicateur avant le dévoilement). */
export function FieldLine({ total, planters, style }: { total: number; planters?: number | null; style?: StyleProp<TextStyle> }) {
  const c = usePronoTheme();
  return (
    <Text style={[pronoFont.text, { color: c.t2, fontSize: 13, lineHeight: 18 }, style]}>
      <Text>{PATATE} </Text><Text style={[pronoFont.bold, { color: c.t1 }]}>{total}</Text> sur la piste
      {planters != null ? ` · ${planters} lanceur${planters > 1 ? 's' : ''}` : ''}
    </Text>
  );
}

/** Rappel obligatoire sous chaque sac : les patates n'ont aucune valeur. */
export function NoValueNote({ children, style }: { children?: ReactNode; style?: StyleProp<ViewStyle> }) {
  const c = usePronoTheme();
  return (
    <View style={[{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }, style]} testID="prono-no-value">
      <View style={{ marginTop: 1 }}>{INFO(c.t3)}</View>
      <Text style={[pronoFont.text, { flex: 1, color: c.t2, fontSize: 12, lineHeight: 16 }]}>{NO_VALUE}{children ? <> {children}</> : null}</Text>
    </View>
  );
}

// ───────── Types de prono ─────────
const KIND_GLYPH: Record<PronoKind, string> = {
  choice: '◆', yesno: '◐', overunder: '±', number: '#', when: '◷', person: '👤', majority: '👥', award: '🏆', text: '✎',
};
/** Petit signe du type (◆ Choix, ◐ Oui / Non, ± Plus / Moins, # Nombre, ◷ Heure, 👤, 👥, 🏆, ✎). */
export function KindIcon({ kind, size = 11, color }: { kind: PronoKind; size?: number; color?: string }) {
  return <Text aria-hidden style={{ fontSize: size, color, lineHeight: size + 2 }}>{KIND_GLYPH[kind] ?? '◆'}</Text>;
}
/** Puce blanche du type, en haut à droite d'une couverture. */
export function KindChip({ kind, label }: { kind: PronoKind; label?: string }) {
  const c = usePronoTheme();
  return (
    <View style={[st.kind, { backgroundColor: c.kindChip }]}>
      <KindIcon kind={kind} size={11} color="#1D1530" />
      <Text style={[pronoFont.bold, { color: '#1D1530', fontSize: 12 }]}>{label ?? kindLabel(kind)}</Text>
    </View>
  );
}

// ───────── Couverture ─────────
type CoverGroup = { emoji?: string | null; color?: string | null; photo?: string | null; name?: string | null } | null | undefined;

/** Bande de couverture : dégradé du groupe (ou de l'événement), emoji en filigrane, puces contexte / type ; `hero` pour la fiche. */
export function CoverBand({ group, event, cover, height, hero, context, kind, award, children, style }: {
  group?: CoverGroup; event?: { title: string } | null; cover?: { color?: string | null; emoji?: string | null; photo?: string | null } | null;
  height?: number; hero?: boolean; context?: string | null; kind?: PronoKind; award?: string; children?: ReactNode; style?: StyleProp<ViewStyle>;
}) {
  const c = usePronoTheme();
  const glide = useAnim('glide');
  const color = cover?.color ?? group?.color ?? (event ? 'coral' : 'lavender');
  const emoji = cover?.emoji ?? group?.emoji ?? (event ? '🎉' : '🔮');
  const photo = useGroupImage({ photo: cover?.photo ?? group?.photo ?? null });
  const g = groupLook(color);
  const ctx = context ?? null;
  if (hero) {
    const h = height ?? 236;
    const bgImage = c.scheme === 'light'
      ? `radial-gradient(120% 90% at 12% -10%, ${alpha(g.from, 0.9)}, transparent 62%), linear-gradient(180deg, ${g.to} 0%, ${alpha(g.from, 0.6)} 52%, ${c.bg} 100%)`
      : `radial-gradient(70% 55% at 92% 38%, rgba(255,79,154,.20), transparent 70%), radial-gradient(120% 90% at 12% -10%, ${alpha(g.from, 0.85)}, transparent 62%), linear-gradient(180deg, ${g.to} 0%, ${g.dim} 46%, ${c.bg} 100%)`;
    return (
      <View style={[{ height: h, overflow: 'hidden', backgroundColor: c.bg }, style]}>
        <View pointerEvents="none" style={[StyleSheet.absoluteFill, web({ backgroundImage: bgImage,
          maskImage: 'linear-gradient(180deg, #000 58%, transparent 100%)', WebkitMaskImage: 'linear-gradient(180deg, #000 58%, transparent 100%)' })]}>
          {photo ? <Image source={{ uri: photo }} resizeMode="cover" style={[StyleSheet.absoluteFill, { opacity: 0.5 }]} /> : null}
          <View style={[{ position: 'absolute', top: '-40%', right: '-30%', width: '140%', height: '160%' },
            web({ backgroundImage: 'conic-gradient(from 200deg at 70% 0%, transparent 0deg, rgba(255,255,255,.10) 8deg, transparent 18deg, transparent 30deg, rgba(255,255,255,.06) 36deg, transparent 46deg)' })]} />
          {photo ? null : <Text style={[st.fili, { right: -34, top: 38, fontSize: 212, lineHeight: 212, opacity: 0.16 }]}>{emoji}</Text>}
        </View>
        {children}
      </View>
    );
  }
  const h = height ?? 64;
  return (
    <View style={[{ height: h, overflow: 'hidden' }, web({ backgroundColor: g.main, backgroundImage: `linear-gradient(135deg, ${g.from}, ${g.to})` }), style]}>
      {photo ? <Image source={{ uri: photo }} resizeMode="cover" style={StyleSheet.absoluteFill} /> : null}
      {photo ? null : <Text aria-hidden style={[st.fili, { right: -14, top: -26, fontSize: 112, lineHeight: 112, opacity: 0.22 }, web({ filter: 'saturate(.6)' }), h > 70 ? glide : null]}>{emoji}</Text>}
      <View pointerEvents="none" style={[{ position: 'absolute', left: 0, right: 0, bottom: 0, height: 34 }, web({ backgroundImage: `linear-gradient(to bottom, transparent, ${c.s1})` })]} />
      {ctx ? (
        <View style={[st.ctx, { backgroundColor: c.chipDark }, web({ backdropFilter: 'blur(12px)' })]}>
          <Text numberOfLines={1} style={[pronoFont.semibold, { color: '#fff', fontSize: 13 }]}>{ctx}</Text>
        </View>
      ) : null}
      {kind ? <View style={{ position: 'absolute', right: 12, top: 12 }}><KindChip kind={kind} label={kind === 'award' && award ? award : undefined} /></View> : null}
      {children}
    </View>
  );
}

// ───────── Surfaces, titres, boutons ─────────
/** Carte en verre (ou pleine avec `solid`), rayon 24. `glow` : urgent (rose), won (menthe), soon (ambre). */
export function GlassCard({ children, solid, glow, radius = 24, padding = 18, style, testID }: {
  children?: ReactNode; solid?: boolean; glow?: 'urgent' | 'won' | 'soon'; radius?: number; padding?: number; style?: StyleProp<ViewStyle>; testID?: string;
}) {
  const c = usePronoTheme();
  const glowStyle = glow === 'urgent' ? web({ borderColor: alpha(c.pink, 0.5), boxShadow: `0 0 0 1px ${alpha(c.pink, 0.18)}, 0 22px 50px -22px ${alpha(c.pink, 0.75)}` })
    : glow === 'won' ? web({ borderColor: alpha(c.mint, 0.42), boxShadow: `0 0 0 1px ${alpha(c.mint, 0.12)}, 0 22px 50px -26px ${alpha(c.mint, 0.6)}` })
      : glow === 'soon' ? web({ borderColor: alpha(c.amber, 0.45) }) : null;
  return (
    <View testID={testID} style={[{ borderRadius: radius, padding, borderWidth: 1 },
      solid ? [{ backgroundColor: c.s1, borderColor: c.line }, web({ boxShadow: c.shadow })]
        : [{ backgroundColor: c.glass, borderColor: c.glassLine }, web({ backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)' })],
      glowStyle, style]}>
      {children}
    </View>
  );
}

/** Titre de section : CAPITALES espacées (listes) ou casse normale (fiche) ; `right` à droite. */
export function SectionLabel({ children, right, caps = true, style }: { children: ReactNode; right?: ReactNode; caps?: boolean; style?: StyleProp<ViewStyle> }) {
  const c = usePronoTheme();
  const text = caps ? [pronoFont.label, { color: c.t2 }] : [pronoFont.semibold, { color: c.t2, fontSize: 13, lineHeight: 18 }];
  return (
    <View style={[{ flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: 10 }, style]}>
      <Text accessibilityRole="header" style={text}>{children}</Text>
      {right != null ? (typeof right === 'string' ? <Text style={[pronoFont.text, { color: c.t3, fontSize: 13 }]}>{right}</Text> : right) : null}
    </View>
  );
}

/** Bouton principal : rose plein (texte blanc AA), menthe, verre ou lavande ; 52 (md) ou 58 (lg). */
export function PrimaryButton({ label, onPress, tone = 'pink', size = 'md', icon, disabled, loading, testID, accessibilityLabel, style }: {
  label: string; onPress?: () => void; tone?: 'pink' | 'mint' | 'glass' | 'lav'; size?: 'md' | 'lg'; icon?: 'lock' | ReactNode;
  disabled?: boolean; loading?: boolean; testID?: string; accessibilityLabel?: string; style?: StyleProp<ViewStyle>;
}) {
  const c = usePronoTheme();
  const reduced = useReducedMotion();
  const fg = tone === 'pink' ? '#FFFFFF' : tone === 'mint' ? '#0E0A1F' : tone === 'lav' ? '#160F2C' : c.t1;
  const fill = tone === 'pink'
    ? web({ backgroundColor: c.pinkFill, backgroundImage: `linear-gradient(160deg, #F04A93, ${c.pinkFill} 60%, #BC1F66)`,
      boxShadow: '0 14px 30px -14px rgba(255,79,154,.85), inset 0 1px 0 rgba(255,255,255,.28)' })
    : tone === 'mint'
      ? web({ backgroundColor: '#3FCF8E', backgroundImage: 'linear-gradient(160deg, #7BF0BD, #3FCF8E)', boxShadow: '0 12px 26px -14px rgba(91,227,166,.9), inset 0 1px 0 rgba(255,255,255,.45)' })
      : tone === 'lav'
        ? web({ backgroundColor: c.lavB, backgroundImage: `linear-gradient(160deg, ${c.lavA}, ${c.lavB})` })
        : [{ backgroundColor: c.s3, borderWidth: 1, borderColor: c.line2 }];
  const lg = size === 'lg';
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={accessibilityLabel ?? label}
      accessibilityState={{ disabled: !!disabled || !!loading, busy: !!loading }} disabled={disabled || loading} onPress={onPress}
      style={({ pressed }) => [st.btn, { height: lg ? 58 : 52, borderRadius: lg ? 18 : 16 }, fill, pressStyle(reduced),
        (disabled || loading) && { opacity: 0.5 }, pressed && { transform: [{ scale: 0.97 }] }, style]}>
      {loading ? <ActivityIndicator color={fg} /> : (
        <>
          {icon === 'lock' ? <View style={{ width: 18, height: 18 }}>{LOCK(fg)}</View> : icon ?? null}
          <Text style={[lg ? pronoFont.round : pronoFont.bold, { color: fg, fontSize: lg ? 19 : 17 }]}>{label}</Text>
        </>
      )}
    </Pressable>
  );
}

/** Onglets segmentés (« À jouer 5 · En attente 3 · Terminés »). */
export function Segmented<K extends string>({ items, value, onChange, testID }: {
  items: { key: K; label: string; count?: number | null; soft?: boolean }[]; value: K; onChange: (k: K) => void; testID?: string;
}) {
  const c = usePronoTheme();
  const reduced = useReducedMotion();
  return (
    <View testID={testID} accessibilityRole="tablist" style={[st.seg, { backgroundColor: c.s3, borderColor: c.line }]}>
      {items.map((it) => {
        const on = it.key === value;
        return (
          <Pressable key={it.key} testID={testID ? `${testID}-${it.key}` : undefined} accessibilityRole="tab" accessibilityState={{ selected: on }}
            accessibilityLabel={it.count ? `${it.label}, ${it.count}` : it.label} onPress={() => onChange(it.key)}
            style={[st.segBtn, reduced ? null : web({ transitionProperty: 'background-color', transitionDuration: '350ms', transitionTimingFunction: pronoMotion.quint }),
              on && [{ backgroundColor: c.s1 }, web({ boxShadow: c.scheme === 'light' ? '0 1px 3px rgba(29,21,48,.12)' : 'inset 0 1px 0 rgba(255,255,255,.06), 0 6px 16px -8px rgba(0,0,0,.6)' })]]}>
            <Text style={[pronoFont.semibold, { color: on ? c.t1 : c.t2, fontSize: 14 }]}>{it.label}</Text>
            {it.count ? (
              <View style={[st.segCount, { backgroundColor: it.soft ? c.line2 : c.pinkFill }]}>
                <Text style={[pronoFont.num, { color: it.soft ? c.t1 : '#fff', fontSize: 12 }]}>{it.count}</Text>
              </View>
            ) : null}
          </Pressable>
        );
      })}
    </View>
  );
}

// ───────── Pastilles de réponse ─────────
/** Pastille de réponse à forme : verre, tuile de la forme (couleur de la FORME), rond de sélection. */
export function ChoicePill({ label, shape, selected, color, onPress, result, sub, compact, disabled, trailing, testID, accessibilityLabel }: {
  label: string; shape: ShapeRef; selected?: boolean; color?: string; onPress?: () => void; result?: 'right' | 'wrong'; sub?: string;
  compact?: boolean; disabled?: boolean; trailing?: ReactNode; testID?: string; accessibilityLabel?: string;
}) {
  const c = usePronoTheme();
  const scheme = usePronoScheme();
  const reduced = useReducedMotion();
  const sc = result === 'wrong' ? c.miss : result === 'right' ? c.mint : color ?? shapeColor(shape, scheme);
  const on = !!selected || result === 'right';
  const a11y = accessibilityLabel ?? `${label}${sub ? `, ${sub}` : ''}${result === 'right' ? ', bonne réponse' : ''}`;
  if (compact) {
    return (
      <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={a11y} accessibilityState={{ selected: !!selected, disabled: !!disabled }}
        disabled={disabled || !onPress} onPress={onPress}
        style={({ pressed }) => [st.pillCompact, { backgroundColor: c.s3, borderColor: c.line2 }, pressStyle(reduced),
          on && { borderColor: sc, backgroundColor: alpha(sc, 0.14) }, result === 'wrong' && { opacity: 0.6 }, pressed && { transform: [{ scale: 0.97 }] }]}>
        <ShapeMark shape={shape} size={11} color={sc} />
        <Text numberOfLines={1} style={[pronoFont.semibold, { color: c.t1, fontSize: 15, flexShrink: 1 }]}>{label}</Text>
      </Pressable>
    );
  }
  const onFg = scheme === 'light' ? '#FFFFFF' : c.ink;
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={a11y} accessibilityState={{ selected: !!selected, disabled: !!disabled }}
      disabled={disabled || !onPress} onPress={onPress}
      style={({ pressed }) => [st.pill, { backgroundColor: c.glass, borderColor: c.glassLine }, web({ backdropFilter: 'blur(20px)' }), pressStyle(reduced),
        on && web({ borderColor: sc, backgroundImage: `linear-gradient(90deg, ${alpha(sc, 0.22)}, ${alpha(sc, 0.06)})`,
          boxShadow: `0 0 0 4px ${alpha(sc, 0.14)}, 0 14px 34px -12px ${alpha(sc, 0.7)}` }),
        result === 'wrong' && { opacity: 0.55 }, pressed && { transform: [{ scale: 0.97 }] }]}>
      <View style={[st.shapeTile, { backgroundColor: on ? sc : alpha(sc, 0.16) }]}>
        <ShapeMark shape={shape} size={20} color={on ? onFg : sc} />
      </View>
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={[pronoFont.roundBold, { color: c.t1, fontSize: 18, lineHeight: 22 }]}>{label}</Text>
        {sub ? <Text style={[pronoFont.text, { color: c.t2, fontSize: 13, marginTop: 1 }]}>{sub}</Text> : null}
      </View>
      {trailing ?? (
        <View style={[st.radio, { borderColor: on ? sc : alpha(c.scheme === 'light' ? '#1D1530' : '#F4F1FF', 0.28) }, on && { backgroundColor: sc }]}>
          {on ? <View style={{ width: 14, height: 14 }}>{CHECK(onFg, 2)}</View> : null}
        </View>
      )}
    </Pressable>
  );
}

const st = StyleSheet.create({
  badge: { position: 'absolute', borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  fili: { position: 'absolute', transform: [{ rotate: '-14deg' }] },
  ctx: { position: 'absolute', left: 12, top: 12, zIndex: 1, flexDirection: 'row', alignItems: 'center', gap: 6, height: 26, paddingLeft: 8,
    paddingRight: 10, borderRadius: 13, maxWidth: 240 },
  kind: { height: 26, paddingHorizontal: 10, borderRadius: 13, flexDirection: 'row', alignItems: 'center', gap: 5 },
  cd: { height: 32, paddingLeft: 10, paddingRight: 12, borderRadius: 16, flexDirection: 'row', alignItems: 'center', gap: 7, borderWidth: 1, alignSelf: 'flex-start' },
  cdCard: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 12, paddingLeft: 12, paddingRight: 14, borderRadius: 20, borderWidth: 1 },
  cdIco: { width: 40, height: 40, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  cdBar: { height: 4, borderRadius: 2, marginTop: 8, overflow: 'hidden' },
  pt: { flexDirection: 'row', alignItems: 'center', gap: 4, borderWidth: 1, alignSelf: 'flex-start' },
  bag: { flexDirection: 'row', alignItems: 'center', gap: 5, height: 34, paddingHorizontal: 11, borderRadius: 999, borderWidth: 1, alignSelf: 'flex-start' },
  btn: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, paddingHorizontal: 20, width: '100%' },
  seg: { height: 44, padding: 4, borderRadius: 15, flexDirection: 'row', gap: 4, borderWidth: 1 },
  segBtn: { flex: 1, borderRadius: 11, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 6 },
  segCount: { minWidth: 20, height: 20, paddingHorizontal: 6, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  pillCompact: { height: 48, paddingHorizontal: 10, borderRadius: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 7,
    borderWidth: 1, flex: 1, minWidth: 0 },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 14, width: '100%', minHeight: 64, paddingVertical: 9, paddingLeft: 10, paddingRight: 14,
    borderRadius: 20, borderWidth: 1.5 },
  shapeTile: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  radio: { width: 26, height: 26, borderRadius: 13, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
});

