import type { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { PrimaryButton, SectionLabel } from '@/components/pronos/Kit';
import { enter, pressTransition } from '@/lib/motion';

/**
 * Habillage commun des étapes de création (direction C « Néon club », jetons des maquettes 2-*) : fond de nuit avec halos,
 * barre « ✕ / ‹ · Modèle · 1 sur 3 » et ses 3 segments, étiquettes de section, bouton principal collé en bas.
 */

// Propriétés CSS du web (dégradés, flou, sticky…) : absentes des types de React Native, rendues telles quelles.
export const web = (style: Record<string, unknown>) => style as ViewStyle;
export const noOutline = { outlineStyle: 'none' } as unknown as TextStyle;
export const webText = (style: TextStyle & Record<string, unknown>) => style as TextStyle;

/** Jetons de la direction C (sombre). */
export const C = {
  bg: '#0E0A1F', s1: '#1A1433', s2: '#251D47', glass: 'rgba(37,29,71,0.8)',
  line: 'rgba(255,255,255,0.08)', lineStrong: 'rgba(255,255,255,0.14)',
  t1: '#F4F1FF', t2: '#A79FC7', t3: '#8F88AE',
  lav: '#B9A7FF', lavDeep: '#7B6CF6', lavText: '#C9BCFF',
  mint: '#5BE3A6', lemon: '#FFE27A', amber: '#FFB347', pink: '#FF4F9A', pinkFill: '#D42A76',
};

/** Typographie française : espace insécable avant « ? ! : ; » (jamais un « ? » seul en début de ligne). */
export const nb = (s: string) => s.replace(/ ([?!:;»])/g, '\u00a0$1');

/** Questions et titres : arrondi 800 ; chiffres : larges et tabulaires. */
export const rounded = webText({ fontFamily: 'ui-rounded, "SF Pro Rounded", -apple-system, system-ui, sans-serif', fontWeight: '800', letterSpacing: -0.4 });
export const digits = webText({ fontFamily: '-apple-system, "SF Pro Display", system-ui, sans-serif', fontWeight: '800',
  fontVariant: ['tabular-nums'], fontStretch: '125%' });
export const body = webText({ fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, sans-serif' });

export function Txt({ children, size = 15, color = C.t1, weight = '400', style, numberOfLines }: {
  children: ReactNode; size?: number; color?: string; weight?: TextStyle['fontWeight']; style?: StyleProp<TextStyle>; numberOfLines?: number;
}) {
  return <Text numberOfLines={numberOfLines} style={[body, { fontSize: size, color, fontWeight: weight }, style]}>{children}</Text>;
}

/** Écran d'une étape : la barre en haut, le contenu qui défile, le bouton collé en bas. */
export function StepScreen({ nav, children, footer, scrollRef }: { nav: ReactNode; children: ReactNode; footer?: ReactNode; scrollRef?: React.Ref<ScrollView> }) {
  return (
    <SafeAreaView style={st.screen} edges={['top', 'left', 'right']}>
      {nav}
      <ScrollView ref={scrollRef} style={{ flex: 1 }} contentContainerStyle={st.content} keyboardShouldPersistTaps="handled">
        {children}
      </ScrollView>
      {footer ? <View style={st.footer}>{footer}</View> : null}
    </SafeAreaView>
  );
}

/** « ✕ » (étape 1) ou « ‹ » ; au centre « Modèle · 1 sur 3 » et les trois segments. */
export function StepNav({ step, title, icon, onBack, backLabel }: { step: 1 | 2 | 3; title: string; icon: '✕' | '‹'; onBack: () => void; backLabel: string }) {
  return (
    <View style={st.nav}>
      <Pressable accessibilityRole="button" accessibilityLabel={backLabel} onPress={onBack}
        style={({ pressed }) => [st.round, pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
        <Text style={[body, { color: C.t1, fontSize: icon === '✕' ? 18 : 24, fontWeight: '600', marginTop: icon === '‹' ? -2 : 0 }]}>{icon}</Text>
      </Pressable>
      <View style={st.navMid} accessibilityRole="header" accessibilityLabel={`${title}, étape ${step} sur 3`}>
        <Text style={[body, { color: C.t1, fontSize: 15, fontWeight: '700' }]}>{title}<Text style={{ color: C.t2, fontWeight: '500' }}> · {step} sur 3</Text></Text>
        <View style={st.segments}>
          {[1, 2, 3].map((i) => (
            <View key={i} style={[st.seg, i <= step && st.segDone, i === step && st.segNow]} />
          ))}
        </View>
      </View>
      <View style={{ width: 44 }} />
    </View>
  );
}

/** Étiquette de section, avec une pastille à droite (« Facultatif », « 3 sur 8 »…). */
export function Block({ label, right, children, style, index = 0 }: { label?: string; right?: string; children: ReactNode; style?: StyleProp<ViewStyle>; index?: number }) {
  return (
    <View style={[{ gap: 12 }, enter('rise', index), style]}>
      {label ? (
        <View style={st.labelRow}>
          <SectionLabel>{label}</SectionLabel>
          {right ? <View style={st.tag}><Txt size={13} color={C.t2} weight="600">{right}</Txt></View> : null}
        </View>
      ) : null}
      {children}
    </View>
  );
}

/** Puce horizontale (familles, types de réponse, unités) : choisie = claire. */
export function Chip({ label, icon, on, onPress, testID, a11y }: { label: string; icon?: ReactNode; on: boolean; onPress: () => void; testID?: string; a11y?: string }) {
  return (
    <Pressable accessibilityRole="radio" accessibilityState={{ selected: on }} aria-checked={on} accessibilityLabel={a11y ?? label}
      testID={testID} onPress={onPress}
      style={({ pressed }) => [st.chip, on && st.chipOn, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
      {icon}
      <Txt size={16} weight="600" color={on ? '#1D1530' : C.t1}>{label}</Txt>
    </Pressable>
  );
}

export function ChipRow({ children }: { children: ReactNode }) {
  return (
    <ScrollView horizontal showsHorizontalScrollIndicator={false} style={st.chipScroll} contentContainerStyle={st.chipRow}>
      {children}
    </ScrollView>
  );
}

/** Bouton principal collé en bas (sur un fondu du fond). */
export function Footer({ label, onPress, disabled, loading, testID, note }: { label: string; onPress: () => void; disabled?: boolean; loading?: boolean; testID?: string; note?: ReactNode }) {
  return (
    <View style={{ gap: 10 }}>
      {note}
      <PrimaryButton label={label} onPress={onPress} disabled={disabled} loading={loading} testID={testID} />
    </View>
  );
}

/** Carte radio (qui joue, patates, dévoilement) : choisie = contour lavande + halo + coche. */
export function RadioCard({ on, onPress, children, style, testID, a11y, corner }: {
  on: boolean; onPress: () => void; children: ReactNode; style?: StyleProp<ViewStyle>; testID?: string; a11y: string;
  /** Coche en haut à droite (cartes côte à côte) plutôt qu'au bout de la rangée. */
  corner?: boolean;
}) {
  return (
    <Pressable accessibilityRole="radio" accessibilityState={{ selected: on }} aria-checked={on} accessibilityLabel={a11y} testID={testID} onPress={onPress}
      style={({ pressed }) => [st.radio, on && st.radioOn, pressTransition, pressed && { transform: [{ scale: 0.98 }] }, style]}>
      {children}
      <View style={[st.tick, on && st.tickOn, corner && st.tickCorner]}>{on ? <Text style={{ color: '#fff', fontSize: 14, fontWeight: '800' }}>✓</Text> : null}</View>
    </Pressable>
  );
}

export const st = StyleSheet.create({
  screen: web({ flex: 1, backgroundColor: C.bg,
    backgroundImage: 'radial-gradient(90% 40% at 0% 0%, rgba(123,108,246,0.22), transparent 70%), radial-gradient(80% 35% at 100% 0%, rgba(255,79,154,0.14), transparent 70%)' }),
  content: { paddingHorizontal: 20, paddingTop: 8, paddingBottom: 40, gap: 28, width: '100%', maxWidth: 560, alignSelf: 'center' },
  footer: web({ paddingHorizontal: 20, paddingTop: 14, paddingBottom: 18, width: '100%', maxWidth: 560, alignSelf: 'center',
    backgroundImage: `linear-gradient(180deg, rgba(14,10,31,0), ${C.bg} 40%)` }),
  nav: { flexDirection: 'row', alignItems: 'center', paddingHorizontal: 12, height: 64, width: '100%', maxWidth: 580, alignSelf: 'center' },
  round: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: C.glass,
    borderWidth: 1, borderColor: C.lineStrong },
  navMid: { flex: 1, alignItems: 'center', gap: 6 },
  segments: { flexDirection: 'row', gap: 6 },
  seg: { width: 22, height: 5, borderRadius: 3, backgroundColor: 'rgba(255,255,255,0.16)' },
  segDone: { backgroundColor: C.lavDeep },
  segNow: web({ width: 40, backgroundColor: C.lav, boxShadow: `0 0 10px ${C.lavDeep}` }),
  labelRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  tag: { paddingHorizontal: 12, height: 28, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.08)', justifyContent: 'center' },
  chipScroll: { marginHorizontal: -20, flexGrow: 0 },
  chipRow: { paddingHorizontal: 20, gap: 8 },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 8, height: 44, paddingHorizontal: 16, borderRadius: 22,
    backgroundColor: C.glass, borderWidth: 1, borderColor: C.lineStrong },
  chipOn: web({ backgroundColor: '#F4F1FF', borderColor: '#F4F1FF', boxShadow: '0 4px 18px rgba(185,167,255,0.35)' }),
  radio: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 22, backgroundColor: C.glass,
    borderWidth: 2, borderColor: C.line, minHeight: 72 },
  radioOn: web({ borderColor: C.lav, boxShadow: `0 0 0 4px rgba(185,167,255,0.18), 0 8px 26px rgba(123,108,246,0.25)` }),
  tick: { width: 30, height: 30, borderRadius: 15, borderWidth: 2, borderColor: 'rgba(255,255,255,0.22)', alignItems: 'center', justifyContent: 'center',
    marginLeft: 'auto' },
  tickOn: { backgroundColor: C.lavDeep, borderColor: C.lavDeep },
  tickCorner: { position: 'absolute', top: 12, right: 12 },
});
