import type { ReactNode } from 'react';
import { Pressable, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { Avatar } from '@/components/ui';
import type { Face } from '@/lib/pronos';

import { N, label, num, terrainLook, text, web, type SHAPES } from './theme';

/** Petites pièces communes au dévoilement, au résultat, au classement et au sac. */

export function Shape({ shape, size = 32, on = false, dim = false, color }: {
  shape: (typeof SHAPES)[number]; size?: number; on?: boolean; dim?: boolean; color?: string;
}) {
  const fill = on ? N.ink : (color ?? N.t1);
  return (
    <View accessibilityLabel={shape.name} style={[{ width: size, height: size, borderRadius: size / 2, alignItems: 'center', justifyContent: 'center',
      backgroundColor: on ? N.mint : 'rgba(255,255,255,0.08)', borderWidth: 1, borderColor: on ? N.mint : N.line2, opacity: dim ? 0.45 : 1 }]}>
      <View style={web({ width: size * 0.42, height: size * 0.42, backgroundColor: fill, clipPath: shape.clip })} />
    </View>
  );
}

/** Visage avec son anneau (le mien : anneau blanc en plus). */
export function FaceRing({ face, size = 32, ring = N.bg, glow }: { face: Face; size?: number; ring?: string; glow?: string }) {
  return (
    <View style={[{ borderRadius: 999, borderWidth: 2, borderColor: ring },
      face.me && web({ boxShadow: `0 0 0 2px ${N.t1}` }), glow ? web({ boxShadow: `0 0 0 2px ${glow}, 0 0 18px ${glow}99` }) : null]}>
      <Avatar id={face.id} name={face.name} photo={face.avatar_url} size={size} profile={false} />
    </View>
  );
}

/** Visages qui se chevauchent. */
export function FaceStack({ faces, size = 24, ring = N.s1, max = 7, k }: { faces: Face[]; size?: number; ring?: string; max?: number; k?: string }) {
  const shown = faces.slice(0, max);
  const extra = faces.length - shown.length;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }} accessibilityLabel={faces.map((f) => (f.me ? 'toi' : f.name)).join(', ')}>
      {shown.map((f, i) => (
        <View key={f.id} style={{ marginLeft: i ? -size * 0.22 : 0, zIndex: max - i }} {...(k ? ({ dataSet: { [k]: f.id } } as object) : {})}>
          <FaceRing face={f} size={size} ring={ring} />
        </View>
      ))}
      {extra > 0 ? <Text style={[text(12, '700', N.t2), { marginLeft: 4 }]}>+{extra}</Text> : null}
    </View>
  );
}

const CHIP = {
  plain: { bg: 'rgba(255,255,255,0.07)', bd: N.line, fg: N.t1 },
  mint: { bg: 'rgba(91,227,166,0.14)', bd: 'rgba(91,227,166,0.35)', fg: N.mint },
  lemon: { bg: 'rgba(255,226,122,0.13)', bd: 'rgba(255,226,122,0.35)', fg: N.lemon },
  warn: { bg: 'rgba(255,179,71,0.13)', bd: 'rgba(255,179,71,0.35)', fg: N.warn },
  lav: { bg: 'rgba(185,167,255,0.14)', bd: 'rgba(185,167,255,0.35)', fg: N.lav },
};

export function Chip({ children, tone = 'plain', style, big }: { children: ReactNode; tone?: keyof typeof CHIP; style?: StyleProp<ViewStyle>; big?: boolean }) {
  const c = CHIP[tone];
  return (
    <View style={[{ flexDirection: 'row', alignItems: 'center', alignSelf: 'flex-start', gap: 6, height: big ? 30 : 28, paddingHorizontal: 12,
      borderRadius: 999, backgroundColor: c.bg, borderWidth: 1, borderColor: c.bd }, style]}>
      <Text style={text(big ? 14 : 13, '600', c.fg)} numberOfLines={1}>{children}</Text>
    </View>
  );
}

/** Puce du terrain (groupe : sa couleur ; événement : lavande). */
export function TerrainChip({ group, title }: { group: { color?: string | null; emoji?: string; name: string } | null; title: string }) {
  const t = terrainLook(group);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, height: 30, paddingHorizontal: 12, borderRadius: 999,
      backgroundColor: `${t.main}29`, borderWidth: 1, borderColor: `${t.from}59`, maxWidth: 220 }}>
      <Text style={text(14, '600')} numberOfLines={1}>{title}</Text>
    </View>
  );
}

/** Bouton de verre (Passer, Voir tout, Partager…), 44 px de cible au moins. */
export function GlassButton({ label: l, onPress, round, testID, style, a11y }: {
  label: string; onPress: () => void; round?: boolean; testID?: string; style?: StyleProp<ViewStyle>; a11y?: string;
}) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={a11y ?? l} onPress={onPress} testID={testID}
      style={({ pressed }) => [web({ height: 44, minWidth: 44, paddingHorizontal: round ? 0 : 16, borderRadius: 999, alignItems: 'center',
        justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.08)', borderWidth: 1, borderColor: N.line2,
        backdropFilter: 'blur(20px)', WebkitBackdropFilter: 'blur(20px)', cursor: 'pointer' }),
      round ? { width: 44 } : null, pressed && { transform: [{ scale: 0.96 }], opacity: 0.9 }, style]}>
      <Text style={text(15, '700')} numberOfLines={1}>{l}</Text>
    </Pressable>
  );
}

/** Bouton principal : rose profond en remplissage, texte blanc (contraste AA). */
export function PinkButton({ label: l, onPress, testID, style }: { label: string; onPress: () => void; testID?: string; style?: StyleProp<ViewStyle> }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress} testID={testID}
      style={({ pressed }) => [web({ height: 52, borderRadius: 999, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18,
        backgroundColor: N.pinkBtn, boxShadow: '0 8px 28px -8px rgba(255,79,154,.7), inset 0 1px 0 rgba(255,255,255,.18)', cursor: 'pointer' }),
      pressed && { transform: [{ scale: 0.97 }] }, style]}>
      <Text style={text(17, '700', '#FFFFFF')} numberOfLines={1}>{l}</Text>
    </Pressable>
  );
}

/** Couverture du terrain : deux taches floues de sa couleur et son emoji en filigrane. */
export function Cover({ group, height = 300, base = N.bg, k }: { group: { color?: string | null; emoji?: string } | null; height?: number; base?: string; k?: string }) {
  const t = terrainLook(group);
  return (
    <View pointerEvents="none" aria-hidden style={{ position: 'absolute', left: 0, right: 0, top: 0, height, overflow: 'hidden' }}>
      <View {...(k ? ({ dataSet: { k: `${k}1` } } as object) : {})}
        style={web({ position: 'absolute', width: 300, height: 300, left: -80, top: -140, borderRadius: 999, backgroundColor: t.to, opacity: 0.55, filter: 'blur(60px)' })} />
      <View {...(k ? ({ dataSet: { k: `${k}2` } } as object) : {})}
        style={web({ position: 'absolute', width: 250, height: 250, right: -40, top: -120, borderRadius: 999, backgroundColor: N.lav2, opacity: 0.45, filter: 'blur(60px)' })} />
      <Text style={web({ position: 'absolute', right: -30, top: 20, fontSize: 190, opacity: 0.12, transform: 'rotate(-12deg)' }) as object}>{t.emoji}</Text>
      <View style={web({ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, backgroundImage: `linear-gradient(180deg, ${base}00 0%, ${base} 96%)` })} />
    </View>
  );
}

/** Rappel obligatoire sous chaque sac (conformité 🔴). */
export function NoValueNote({ boxed }: { boxed?: boolean }) {
  const body = 'Les patates n’ont aucune valeur : elles ne s’achètent pas, ne se vendent pas, ne s’échangent pas.';
  if (!boxed) return <Text style={[text(12.5, '500', N.t2), { textAlign: 'center', marginTop: 10, lineHeight: 18 }]}>{body}</Text>;
  return (
    <View style={{ flexDirection: 'row', gap: 12, padding: 14, borderRadius: 16, backgroundColor: 'rgba(185,167,255,0.08)', borderWidth: 1,
      borderColor: 'rgba(185,167,255,0.22)', marginTop: 20 }} testID="prono-novalue">
      <Text style={{ fontSize: 20, lineHeight: 22 }}>🥔</Text>
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={[text(14, '500'), { lineHeight: 20 }]}>{body}</Text>
        <Text style={[text(13, '500', N.t2), { lineHeight: 18 }]}>Juste pour le plaisir de voir juste entre amis.</Text>
      </View>
    </View>
  );
}

/** Titre de section (« LA RÉPARTITION · 30 🥔 dans le champ »). */
export function SectionHead({ left, right }: { left: string; right?: string }) {
  return (
    <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 24, marginBottom: 10, paddingHorizontal: 4, gap: 8 }}>
      <Text style={label()} numberOfLines={1}>{left}</Text>
      {right ? <Text style={label()} numberOfLines={1}>{right}</Text> : null}
    </View>
  );
}

/** Surface de carte (fond s1, rayon 24). */
export const card: ViewStyle = { backgroundColor: N.s1, borderRadius: 24, borderWidth: 1, borderColor: N.line };

/** « 18 🥔 » en chiffres tabulaires. */
export function Potatoes({ n, size = 17, color = N.t1, sign = '' }: { n: number; size?: number; color?: string; sign?: string }) {
  return <Text style={num(size, color)}>{sign}{n} 🥔</Text>;
}
