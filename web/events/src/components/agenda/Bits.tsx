import { router, type Href } from 'expo-router';
import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { HeaderBack, T, Title } from '@/components/ui';
import { BADGE_RED } from '@/lib/activityBadge';
import type { FieldMode, PartyEvent } from '@/lib/agenda';
import { duration, pressTransition, transition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

/**
 * Pièces communes des écrans de l'Agenda (direction A « Néon nuit », maquettes-app.html validée le 17.11) : en-tête
 * « ‹ Retour » + grand titre, pastilles d'action, étiquettes de section, cases à cocher, choix Non / Facultatif /
 * Obligatoire, rayures « Occupé » (jamais la couleur seule : toujours un mot en plus).
 */

type WebStyle = ViewStyle & Record<string, unknown>;
const web = (style: WebStyle) => style as ViewStyle;

/** Rayures « Occupé » : se voient même sans les couleurs (daltonisme, gris). */
export const hatched = web({
  backgroundColor: '#2C2350',
  backgroundImage: 'repeating-linear-gradient(135deg, rgba(185,167,255,0.55) 0 3px, transparent 3px 8px)',
});

/** Retour : à l'écran d'avant s'il y en a un, sinon à `fallback`. */
export function goBack(fallback: string) {
  if (router.canGoBack()) router.back();
  else router.replace(fallback as Href);
}

/** En-tête : ‹ et nom de l'écran d'avant, actions à droite, puis le grand titre (et sa ligne d'aide). */
export function TopBar({ back, fallback, right, title, subtitle, titleRight }: {
  back: string; fallback: string; right?: ReactNode; title?: string; subtitle?: ReactNode; titleRight?: ReactNode;
}) {
  return (
    <View style={{ gap: 6 }}>
      <View style={st.bar}>
        <View style={{ marginLeft: -8, flexShrink: 1, minWidth: 0 }}><HeaderBack label={back} onPress={() => goBack(fallback)} /></View>
        <View style={st.barRight}>{right}</View>
      </View>
      {title ? (
        <View style={st.titleRow}>
          <Title level={1} size={32} style={{ flexShrink: 1 }}>{title}</Title>
          {titleRight}
        </View>
      ) : null}
      {subtitle ? (typeof subtitle === 'string' ? <T muted size={14}>{subtitle}</T> : subtitle) : null}
    </View>
  );
}

/** Bouton pilule d'en-tête : « Calendriers », « + Ajouter » (néon), « 👥 Qui est libre ? » (vert). */
export function PillButton({ label, onPress, tone = 'plain', a11y, testID, badge }: {
  label: string; onPress: () => void; tone?: 'plain' | 'accent' | 'mint' | 'outline'; a11y?: string; testID?: string; badge?: number;
}) {
  const t = TONES[tone];
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={a11y ?? label} testID={testID} onPress={onPress}
      style={({ pressed }) => [st.pill, { backgroundColor: t.bg, borderColor: t.border }, tone === 'accent' && st.glow,
        pressTransition, pressed && { opacity: 0.85, transform: [{ scale: 0.96 }] }]}>
      <Text numberOfLines={1} style={{ color: t.fg, fontSize: 14, ...font.semibold }}>{label}</Text>
      {badge ? <Badge count={badge} /> : null}
    </Pressable>
  );
}

const TONES = {
  plain: { bg: colors.surface, fg: colors.text, border: 'transparent' },
  accent: { bg: colors.action, fg: colors.onAction, border: colors.action },
  mint: { bg: 'rgba(91,227,166,0.14)', fg: '#9BF0C8', border: 'rgba(91,227,166,0.45)' },
  outline: { bg: 'transparent', fg: colors.text, border: colors.accent },
};

/** Pastille rouge « 1 » (demandes de rendez-vous en attente). */
export function Badge({ count, style }: { count: number; style?: StyleProp<ViewStyle> }) {
  if (!count) return null;
  return (
    <View style={[st.badge, style]} testID="agenda-badge">
      <Text style={st.badgeText}>{count > 99 ? '99+' : count}</Text>
    </View>
  );
}

/** Étiquette de section en capitales espacées (« QUI LE VOIT · COCHE LES GROUPES »). */
export function Label({ children, right }: { children: string; right?: ReactNode }) {
  return (
    <View style={st.labelRow}>
      <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 1, flex: 1 }}>{children.toUpperCase()}</T>
      {right}
    </View>
  );
}

/** Bloc de lignes groupées (fond un ton plus clair, coins arrondis). */
export function Group({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[st.group, style]}>{children}</View>;
}

export function Divider() {
  return <View style={{ height: 1, backgroundColor: colors.line, marginLeft: 14 }} />;
}

/** Case à cocher sur toute la ligne (cible de 44 px au moins). */
export function CheckRow({ label, hint, checked, onChange, left, testID, disabled }: {
  label: string; hint?: string; checked: boolean; onChange: (v: boolean) => void; left?: ReactNode; testID?: string; disabled?: boolean;
}) {
  return (
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked, disabled }} accessibilityLabel={hint ? `${label}, ${hint}` : label}
      aria-checked={checked} testID={testID} disabled={disabled} onPress={() => onChange(!checked)}
      style={({ pressed }) => [st.row, transition('background-color', duration.fast), pressed && { backgroundColor: colors.fill }, disabled && { opacity: 0.5 }]}>
      {left}
      <View style={{ flex: 1, minWidth: 0, gap: 1 }}>
        <T size={16} weight="semibold">{label}</T>
        {hint ? <T muted size={13}>{hint}</T> : null}
      </View>
      <View style={[st.box, checked && st.boxOn, transition('background-color, border-color', duration.fast)]}>
        {checked ? <Text style={{ color: '#fff', fontSize: 16, ...font.bold }}>✓</Text> : null}
      </View>
    </Pressable>
  );
}

/** « Non / Facultatif / Obligatoire » d'un champ demandé à la personne. */
export function FieldChoice({ label, value, onChange, locked }: { label: string; value: FieldMode; onChange: (v: FieldMode) => void; locked?: boolean }) {
  const opts: { key: FieldMode; label: string }[] = [{ key: 'off', label: 'Non' }, { key: 'optional', label: 'Facultatif' }, { key: 'required', label: 'Obligatoire' }];
  return (
    <View style={st.fieldRow}>
      <T size={15} weight="semibold">{label}</T>
      <View style={st.seg} accessibilityRole="radiogroup" accessibilityLabel={label}>
        {opts.map((o) => {
          const on = o.key === value;
          return (
            <Pressable key={o.key} accessibilityRole="radio" aria-checked={on} accessibilityState={{ checked: on, disabled: locked && !on }}
              accessibilityLabel={`${label} : ${o.label}`} disabled={locked} onPress={() => onChange(o.key)}
              style={[st.segItem, on && st.segOn, transition('background-color', duration.fast), locked && !on && { opacity: 0.4 }]}>
              <Text numberOfLines={1} style={{ fontSize: 13, color: on ? colors.text : colors.muted, ...(on ? font.bold : font.semibold) }}>{o.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

/** Réponse à une soirée Party, en mots (« ✓ Présent », « Peut-être », « À répondre »). */
export function AnswerTag({ answer, organizer, cancelled }: { answer: PartyEvent['answer'] | undefined; organizer?: boolean; cancelled?: boolean }) {
  const t = cancelled ? { label: 'Annulé', fg: colors.redSoft, bg: colors.redDim }
    : answer === 'yes' ? { label: '✓ Présent', fg: colors.mint, bg: 'rgba(91,227,166,0.14)' }
    : answer === 'maybe' ? { label: 'Peut-être', fg: colors.coralSoft, bg: colors.coralDim }
    : answer === 'no' ? { label: 'Pas présent', fg: colors.muted, bg: colors.fill }
    : organizer ? { label: 'J’organise', fg: colors.lavender, bg: colors.lavenderDim }
    : { label: 'À répondre', fg: colors.coral, bg: 'rgba(255,179,71,0.16)' };
  return (
    <View style={[st.tag, { backgroundColor: t.bg }]}>
      <Text style={{ color: t.fg, fontSize: 13, ...font.bold }}>{t.label}</Text>
    </View>
  );
}

/** Pastille d'état d'un lien : un mot ET un symbole (● Actif, ❚❚ Arrêté). */
export function StatusPill({ status }: { status: 'active' | 'stopped' | 'expired' }) {
  const t = status === 'active' ? { label: '● Actif', fg: colors.mint, bg: 'rgba(91,227,166,0.14)' }
    : status === 'stopped' ? { label: '❚❚ Arrêté', fg: colors.textSoft, bg: colors.fillStrong }
    : { label: '⏱ Expiré', fg: colors.coralSoft, bg: colors.coralDim };
  return (
    <View style={[st.tag, { backgroundColor: t.bg }]}>
      <Text style={{ color: t.fg, fontSize: 13, ...font.bold }}>{t.label}</Text>
    </View>
  );
}

/** Note discrète avec une icône (ⓘ, 🔒…). */
export function Note({ icon = 'ⓘ', children, color = colors.muted }: { icon?: string; children: ReactNode; color?: string }) {
  return (
    <View style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-start' }}>
      <T size={14} color={color}>{icon}</T>
      <T size={13} color={color} style={{ flex: 1 }}>{children}</T>
    </View>
  );
}

export const ast = StyleSheet.create({
  card: { backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.line, padding: 16, gap: 10 },
  neonCard: { borderRadius: radius.lg, borderWidth: 1.5, borderColor: 'rgba(255,79,154,0.55)', padding: 16, gap: 10,
    backgroundColor: '#2A1638', shadowColor: colors.accent, shadowOpacity: 0.25, shadowRadius: 18, shadowOffset: { width: 0, height: 6 } },
  okCard: { borderRadius: radius.lg, borderWidth: 1, borderColor: 'rgba(91,227,166,0.45)', backgroundColor: 'rgba(91,227,166,0.10)', padding: 14, gap: 4 },
  bottom: { gap: 8, paddingTop: 6 },
});

const st = StyleSheet.create({
  bar: { flexDirection: 'row', alignItems: 'center', minHeight: 48, gap: 6 },
  barRight: { flexShrink: 0, marginLeft: 'auto', flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center', gap: 6 },
  titleRow: { flexDirection: 'row', alignItems: 'center', gap: 10, justifyContent: 'space-between', flexWrap: 'wrap' },
  pill: { flexDirection: 'row', alignItems: 'center', gap: 6, minHeight: 44, paddingHorizontal: 13, borderRadius: radius.pill, borderWidth: 1 },
  glow: { shadowColor: colors.accent, shadowOpacity: 0.45, shadowRadius: 14, shadowOffset: { width: 0, height: 4 } },
  badge: { minWidth: 20, height: 20, paddingHorizontal: 6, borderRadius: 10, backgroundColor: BADGE_RED, alignItems: 'center', justifyContent: 'center' },
  badgeText: { color: '#fff', fontSize: 12, lineHeight: 14, ...font.bold },
  labelRow: { flexDirection: 'row', alignItems: 'center', marginTop: 6, paddingHorizontal: 4 },
  group: { backgroundColor: colors.surface, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.line, overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingHorizontal: 14, paddingVertical: 8 },
  box: { width: 28, height: 28, borderRadius: 8, borderWidth: 2, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  boxOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  fieldRow: { gap: 6, paddingHorizontal: 14, paddingVertical: 10 },
  seg: { flexDirection: 'row', padding: 3, borderRadius: 12, backgroundColor: colors.fill, gap: 2 },
  segItem: { flex: 1, minHeight: 40, borderRadius: 9, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 2,
    borderBottomWidth: 2, borderBottomColor: 'transparent' },
  segOn: { backgroundColor: colors.surface2, borderBottomColor: colors.accent },
  tag: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
});
