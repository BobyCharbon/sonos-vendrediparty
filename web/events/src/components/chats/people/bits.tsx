import { createElement, type ReactNode } from 'react';
import { ActivityIndicator, Image, Pressable, Text, View, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';

import { Avatar } from '@/components/ui';
import { faceLook } from '@/components/pronos/KitTheme';
import { dateTile, initials } from '@/lib/format';
import { pressTransition } from '@/lib/motion';
import { font } from '@/lib/theme';

/**
 * Pièces « Néon club » des écrans de personnes (maquettes 1-neon : 2-nouveau-message, 2b-nouveau-groupe, 3-mini-profil ;
 * valeurs de _src/kit.css, les mêmes que les Pronos v2).
 */
export const K = {
  bg: '#0E0A1F', sheet: '#17122E', s1: '#1A1433',
  glass: 'rgba(255,255,255,0.06)', glassLine: 'rgba(255,255,255,0.10)', line: 'rgba(255,255,255,0.07)', line2: 'rgba(255,255,255,0.14)',
  t1: '#F4F1FF', t2: '#A79FC7', t3: '#8C84AE',
  lav: '#B9A7FF', lavA: '#CBBDFF', lavB: '#7B6CF6',
  pink: '#FF4F9A', pinkA: '#FF7DB6', pinkInk: '#FF6FAE', onPink: '#1F0618', danger: '#FF7A8A',
} as const;

type WebStyle = ViewStyle & Record<string, unknown>;
export const web = (style: WebStyle) => style as ViewStyle;
const SYSTEM = '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif';
export const txt = (size: number, weight: TextStyle['fontWeight'] = '400', color: string = K.t1, lineHeight?: number): TextStyle =>
  ({ fontFamily: SYSTEM, fontSize: size, fontWeight: weight, color, lineHeight: lineHeight ?? Math.round(size * 1.3), letterSpacing: -0.2 });
/** Titres (Bricolage 800) : nom du mini-profil, titre de l'écran, nom du groupe sur sa couverture. */
export const disp = (size: number, lineHeight = Math.round(size * 1.12)): TextStyle =>
  ({ ...font.display, fontSize: size, lineHeight, color: K.t1, letterSpacing: -size * 0.026 });

// Icônes au trait (mêmes tracés que la maquette, _src/build.py).
const PATHS = {
  chat: '<path d="M21 11.5a8.5 8.5 0 0 1-12.4 7.6L3 20.5l1.5-5A8.5 8.5 0 1 1 21 11.5z"/>',
  person: '<circle cx="12" cy="8" r="4"/><path d="M4 21a8 8 0 0 1 16 0"/>',
  flag: '<path d="M5 21V4M5 4h11.5l-2 4.5 2 4.5H5"/>',
  block: '<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
  sparkle: '<path d="M12 3c.6 4.6 2.4 6.4 7 7-4.6.6-6.4 2.4-7 7-.6-4.6-2.4-6.4-7-7 4.6-.6 6.4-2.4 7-7z"/>',
  users: '<circle cx="9" cy="8" r="3.5"/><path d="M2.5 20a6.5 6.5 0 0 1 13 0"/><path d="M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.5a6.5 6.5 0 0 1 3.5 5.5"/>',
  check: '<path d="m5 12.5 4.5 4.5L19 7.5"/>',
  x: '<path d="M6 6l12 12M18 6 6 18"/>',
  chevl: '<path d="m15 18-6-6 6-6"/>',
  chevr: '<path d="m9 18 6-6-6-6"/>',
  search: '<circle cx="11" cy="11" r="7"/><path d="m20 20-3.6-3.6"/>',
  cal: '<rect x="3" y="4.5" width="18" height="16.5" rx="3.5"/><path d="M3 9.5h18M8 2.5v4M16 2.5v4"/>',
  inbox: '<path d="M3 13h4.5l1.5 3h6l1.5-3H21"/><path d="M5.6 5h12.8L21 13v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5z"/>',
} as const;
export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 22, color = 'currentColor', stroke = 1.9 }: { name: IconName; size?: number; color?: string; stroke?: number }) {
  return createElement('svg', {
    'aria-hidden': true, focusable: 'false', width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color,
    strokeWidth: stroke, strokeLinecap: 'round', strokeLinejoin: 'round', style: { flexShrink: 0, display: 'block' },
    dangerouslySetInnerHTML: { __html: PATHS[name] },
  });
}

/** Visage d'une personne : sa photo (chemin du compartiment des photos de profil, ou lien déjà signé), sinon ses
 * initiales sur le dégradé de sa couleur (jamais le pastel des anciennes pastilles). */
export function PersonFace({ id, name, photo, size = 40, style }: { id: string; name: string; photo?: string | null; size?: number; style?: StyleProp<ViewStyle> }) {
  const round = { width: size, height: size, borderRadius: size / 2 };
  let inner: ReactNode;
  if (photo && /^https?:/.test(photo)) inner = <Image accessibilityLabel={`Photo de ${name}`} source={{ uri: photo }} style={round} />;
  else if (photo) inner = <Avatar id={id} name={name} photo={photo} size={size} profile={false} />;
  else {
    const look = faceLook(id);
    inner = (
      <View style={[round, { alignItems: 'center', justifyContent: 'center' }, web({ backgroundColor: look.main, backgroundImage: `linear-gradient(135deg, ${look.from}, ${look.to})` })]}>
        <Text style={[disp(size * 0.38, size * 0.44), { color: '#0E0A1F', letterSpacing: -0.3 }]}>{initials(name)}</Text>
      </View>
    );
  }
  return <View style={[round, { overflow: 'hidden' }, style]}>{inner}</View>;
}

/** Tuile date d'une soirée (« VEN. 21 ») : orange, menthe pour une soirée où l'on vient, lavande pour une soirée passée. */
export function DateTile({ iso, size = 40, tone = 'coral' }: { iso: string | null; size?: number; tone?: 'coral' | 'mint' | 'lav' }) {
  const t = iso ? dateTile(iso) : null;
  const g = tone === 'mint' ? ['#7CEDBB', '#22B07D', '#062A1B'] : tone === 'lav' ? ['#CBBDFF', '#7B6CF6', '#120B26'] : ['#FFC977', '#FF7A59', '#2A1406'];
  return (
    <View style={[{ width: size, height: size, borderRadius: size * 0.32, alignItems: 'center', justifyContent: 'center' },
      web({ backgroundColor: g[1], backgroundImage: `linear-gradient(150deg, ${g[0]}, ${g[1]})`, boxShadow: `inset 0 0 0 1.5px rgba(255,255,255,.3), 0 8px 18px -10px ${g[1]}` })]}>
      {t ? (
        <>
          <Text style={[txt(size < 48 ? 8 : 10, '800', g[2], size < 48 ? 9 : 12), { letterSpacing: 0.8, opacity: 0.82 }]}>{t.weekday}</Text>
          <Text style={[disp(size < 48 ? 17 : 22), { color: g[2] }]}>{t.day}</Text>
        </>
      ) : <Text style={txt(18, '800', g[2])}>?</Text>}
    </View>
  );
}

/** Étiquette de section : petites capitales espacées, icône facultative. */
export function Label({ icon, children, right, style }: { icon?: IconName; children: ReactNode; right?: ReactNode; style?: StyleProp<ViewStyle> }) {
  return (
    <View style={[{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingTop: 20, paddingBottom: 8, paddingHorizontal: 16 }, style]}>
      <View accessibilityRole="header" style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
        {icon ? <Icon name={icon} size={13} color={K.t3} stroke={2.4} /> : null}
        <Text style={[txt(12, '700', K.t3, 16), { letterSpacing: 0.9, textTransform: 'uppercase' }]}>{children}</Text>
      </View>
      {right}
    </View>
  );
}

/** Bouton « Néon » : rose (action principale, encre sombre 6:1) ou verre. */
export function NeonButton({ label, icon, onPress, tone = 'pink', disabled, loading, style, testID, accessibilityLabel }: {
  label: string; icon?: IconName; onPress: () => void; tone?: 'pink' | 'glass'; disabled?: boolean; loading?: boolean;
  style?: StyleProp<ViewStyle>; testID?: string; accessibilityLabel?: string;
}) {
  const pink = tone === 'pink';
  const fg = pink ? K.onPink : K.t1;
  return (
    <Pressable testID={testID} accessibilityRole="button" accessibilityLabel={accessibilityLabel ?? label} accessibilityState={{ disabled: !!disabled, busy: !!loading }}
      disabled={disabled || loading} onPress={onPress}
      style={({ pressed }) => [{ height: 54, borderRadius: 18, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 10, paddingHorizontal: 16 },
        pink ? web({ backgroundColor: K.pink, backgroundImage: `linear-gradient(135deg, ${K.pinkA}, ${K.pink})`,
          boxShadow: disabled ? 'none' : '0 0 0 1px rgba(255,255,255,.25) inset, 0 14px 30px -12px rgba(255,79,154,.8)' })
          : { backgroundColor: K.glass, borderWidth: 1, borderColor: K.glassLine },
        disabled && { opacity: 0.45 }, pressTransition, pressed && { transform: [{ scale: 0.97 }] }, style]}>
      {loading ? <ActivityIndicator color={fg} /> : icon ? <Icon name={icon} size={pink ? 22 : 16} color={pink ? fg : K.lav} stroke={pink ? 1.9 : 2.1} /> : null}
      <Text numberOfLines={1} style={[txt(pink ? 17 : 15, pink ? '700' : '600', fg, 22), { flexShrink: pink ? 1 : 0 }]}>{label}</Text>
    </Pressable>
  );
}

/** Rond de sélection (44 px de cible) : vide, ou rose plein avec ✓. */
export function CheckCircle({ on }: { on: boolean }) {
  return (
    <View style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center', marginRight: -8 }}>
      <View style={[{ width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
        on ? web({ backgroundColor: K.pink, backgroundImage: `linear-gradient(135deg, ${K.pinkA}, ${K.pink})`, boxShadow: '0 0 14px -2px rgba(255,79,154,.8)' })
          : { borderWidth: 2, borderColor: K.line2 }]}>
        {on ? <Icon name="check" size={16} color={K.onPink} stroke={3} /> : null}
      </View>
    </View>
  );
}
