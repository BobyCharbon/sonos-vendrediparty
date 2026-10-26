import { Children, useEffect, useState, type ReactNode } from 'react';
import {
  ActivityIndicator,
  Image,
  Pressable,
  ScrollView,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  useWindowDimensions,
  View,
  type StyleProp,
  type TextInputProps,
  type TextStyle,
  type ViewStyle,
} from 'react-native';
import { SafeAreaView, type Edge } from 'react-native-safe-area-context';

import { avatarColor, initials } from '@/lib/format';
import { colors, font, radius, type FontWeight } from '@/lib/theme';
import { PROFILE_PHOTOS } from '@/lib/photos';
import { supabase } from '@/lib/supabase';

export function Screen({
  children,
  scroll = true,
  edges = ['top'],
  contentStyle,
}: {
  children: ReactNode;
  scroll?: boolean;
  edges?: Edge[];
  contentStyle?: StyleProp<ViewStyle>;
}) {
  return (
    <SafeAreaView style={s.screen} edges={[...new Set<Edge>([...edges, 'left', 'right'])]}>
      {scroll ? (
        <ScrollView contentContainerStyle={[s.content, contentStyle]} keyboardShouldPersistTaps="handled">
          {children}
        </ScrollView>
      ) : (
        <View style={[{ flex: 1 }, contentStyle]}>{children}</View>
      )}
    </SafeAreaView>
  );
}

export function Title({ children, size = 28, style }: { children: ReactNode; size?: number; style?: StyleProp<TextStyle> }) {
  return <Text style={[s.title, { fontSize: size }, style]}>{children}</Text>;
}

export function T({
  children,
  muted,
  size = 15,
  weight = 'body',
  color,
  style,
  numberOfLines,
}: {
  children: ReactNode;
  muted?: boolean;
  size?: number;
  weight?: FontWeight;
  color?: string;
  style?: StyleProp<TextStyle>;
  numberOfLines?: number;
}) {
  return (
    <Text
      numberOfLines={numberOfLines}
      style={[{ color: color ?? (muted ? colors.muted : colors.text), fontSize: size, ...font[weight] }, style]}
    >
      {children}
    </Text>
  );
}

export function Card({ children, style }: { children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return <View style={[s.card, style]}>{children}</View>;
}

export function Section({ title, right, children, style }: { title: string; right?: ReactNode; children: ReactNode; style?: StyleProp<ViewStyle> }) {
  return (
    <Card style={style}>
      <View style={s.rowBetween}>
        <Title size={18} style={{ flexShrink: 1 }}>{title}</Title>
        {right}
      </View>
      {children}
    </Card>
  );
}

type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'dangerSolid';

export function Button({
  label,
  onPress,
  variant = 'primary',
  disabled,
  loading,
  style,
  small,
}: {
  label: string;
  onPress?: () => void;
  variant?: ButtonVariant;
  disabled?: boolean;
  loading?: boolean;
  style?: StyleProp<ViewStyle>;
  small?: boolean;
}) {
  const v = buttonVariants[variant];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: !!(disabled || loading), busy: !!loading }}
      onPress={onPress}
      disabled={disabled || loading}
      style={({ pressed }) => [
        s.button,
        small && { minHeight: 44, paddingHorizontal: 14 },
        { backgroundColor: v.bg, borderColor: v.border, opacity: disabled ? 0.45 : pressed ? 0.88 : 1 },
        pressed && !disabled && s.pressed,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={v.fg} />
      ) : (
        <Text style={{ color: v.fg, ...font.bold, fontSize: small ? 13 : 15 }}>{label}</Text>
      )}
    </Pressable>
  );
}

const buttonVariants: Record<ButtonVariant, { bg: string; fg: string; border: string }> = {
  // Plein et lisible : rose profond + texte blanc ; secondaire = remplissage translucide (pas de simple contour).
  primary: { bg: colors.action, fg: colors.onAction, border: colors.action },
  secondary: { bg: colors.fill, fg: colors.text, border: 'transparent' },
  ghost: { bg: 'transparent', fg: colors.accent, border: 'transparent' },
  danger: { bg: 'rgba(255,99,99,0.12)', fg: colors.redSoft, border: 'transparent' },
  dangerSolid: { bg: colors.red, fg: colors.onRed, border: colors.red },
};

export function Chip({
  label,
  selected,
  onPress,
  color = colors.accent,
  disabled = false,
}: {
  label: string;
  selected?: boolean;
  onPress?: () => void;
  color?: string;
  disabled?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected, disabled }}
      onPress={onPress}
      disabled={disabled}
      style={({ pressed }) => [
        s.chip,
        pressed && !disabled && s.pressed,
        selected ? { backgroundColor: color, borderColor: color } : { backgroundColor: colors.fill, borderColor: 'transparent' },
        disabled && { opacity: 0.45 },
      ]}
    >
      <Text style={{ color: selected ? colors.onAccent : colors.textSoft, ...(selected ? font.bold : font.semibold), fontSize: 13 }}>{selected && !/^[✕✓+]/.test(label) ? '✓ ' : ''}{label}</Text>
    </Pressable>
  );
}

export function Badge({ label, fg, bg }: { label: string; fg: string; bg: string }) {
  return (
    <View style={[s.badge, { backgroundColor: bg }]}>
      <Text style={{ color: fg, ...font.bold, fontSize: 12 }}>{label}</Text>
    </View>
  );
}

export function Segmented<K extends string>({
  options,
  value,
  onChange,
  disabled = false,
}: {
  options: { key: K; label: string; dot?: boolean }[];
  value: K;
  onChange: (k: K) => void;
  disabled?: boolean;
}) {
  const { width } = useWindowDimensions();
  // Sous 360 px, quatre onglets ne tiennent pas sur une ligne : grille régulière 2 × 2.
  const grid = options.length > 3 && width < 360;
  return (
    <View style={[s.segmented, grid && { flexWrap: 'wrap' }]} accessibilityRole="tablist">
      {options.map((o) => {
        const on = o.key === value;
        return (
          <Pressable
            key={o.key}
            accessibilityRole="tab"
            accessibilityLabel={o.label}
            accessibilityState={{ selected: on, disabled }}
            aria-selected={on}
            disabled={disabled}
            onPress={() => onChange(o.key)}
            style={({ pressed }) => [
              s.segment,
              grid && { flexBasis: '45%' },
              on && s.segmentOn,
              pressed && !on && { backgroundColor: colors.fill },
            ]}
          >
            <Text numberOfLines={1} style={{ color: on ? colors.onAction : colors.textSoft, ...font.semibold, fontSize: 13 }}>{o.label}</Text>
            {o.dot ? <View style={[s.dot, on && { backgroundColor: colors.onAccent }]} /> : null}
          </Pressable>
        );
      })}
    </View>
  );
}

/** Bouton en deux temps pour les actions irréversibles (pas de boîte de dialogue navigateur). */
export function ConfirmButton({
  label,
  confirmLabel,
  onConfirm,
  small,
  style,
}: {
  label: string;
  confirmLabel: string;
  onConfirm: () => void | Promise<unknown>;
  small?: boolean;
  style?: StyleProp<ViewStyle>;
}) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  if (!armed) return <Button small={small} variant="danger" label={label} style={style} onPress={() => setArmed(true)} />;
  return (
    <View style={[s.row, style]}>
      <Button small={small} variant="secondary" label="Garder" style={{ flex: 1 }} onPress={() => setArmed(false)} />
      <Button
        small={small}
        variant="dangerSolid"
        label={confirmLabel}
        loading={busy}
        style={{ flex: 1 }}
        onPress={async () => {
          setBusy(true);
          try {
            await onConfirm();
          } finally {
            setBusy(false);
            setArmed(false);
          }
        }}
      />
    </View>
  );
}

/** Pastilles d’avatars qui se chevauchent, avec « +N » au-delà de la limite. */
export function AvatarStack({ people, max = 5, size = 26 }: { people: { id: string; name: string }[]; max?: number; size?: number }) {
  if (!people.length) return null;
  const shown = people.slice(0, max);
  const rest = people.length - shown.length;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center' }} accessibilityLabel={people.map((p) => p.name).join(', ')}>
      {shown.map((p, i) => (
        <View key={p.id} style={{ marginLeft: i ? -size * 0.3 : 0, borderRadius: 999, borderWidth: 2, borderColor: colors.surface }}>
          <Avatar id={p.id} name={p.name} size={size} />
        </View>
      ))}
      {rest > 0 ? <T muted size={12} style={{ marginLeft: 6 }}>+{rest}</T> : null}
    </View>
  );
}

export function ToggleRow({
  label,
  hint,
  value,
  onChange,
  disabled = false,
}: {
  label: string;
  hint?: string;
  value: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <View style={s.toggleRow}>
      <View style={{ flex: 1, gap: 2 }}>
        <T>{label}</T>
        {hint ? <T muted size={12}>{hint}</T> : null}
      </View>
      <Switch
        accessibilityLabel={label}
        value={value}
        disabled={disabled}
        onValueChange={onChange}
        trackColor={{ false: colors.fillStrong, true: colors.mint }}
        thumbColor="#FFFFFF"
        {...{ activeThumbColor: '#FFFFFF' }}
        ios_backgroundColor={colors.fillStrong}
      />
    </View>
  );
}

/** Champ qui s’entoure d’un halo néon tant qu’il a le focus (on voit où l’on écrit). */
function useFocusRing(props: TextInputProps) {
  const [focused, setFocused] = useState(false);
  return {
    focused,
    handlers: {
      onFocus: (e: Parameters<NonNullable<TextInputProps['onFocus']>>[0]) => { setFocused(true); props.onFocus?.(e); },
      onBlur: (e: Parameters<NonNullable<TextInputProps['onBlur']>>[0]) => { setFocused(false); props.onBlur?.(e); },
    },
  };
}

export function Field({ label, hint, ...props }: TextInputProps & { label: string; hint?: string }) {
  const ring = useFocusRing(props);
  return (
    <View style={{ gap: 6 }}>
      <T muted size={13} weight="medium">{label}</T>
      <TextInput
        placeholderTextColor={colors.muted}
        accessibilityLabel={label}
        {...props}
        {...ring.handlers}
        style={[s.input, ring.focused && s.inputFocus, props.multiline && { height: 104, paddingTop: 12, textAlignVertical: 'top' }, props.style]}
      />
      {hint ? <T muted size={12}>{hint}</T> : null}
    </View>
  );
}

export function Input(props: TextInputProps) {
  const ring = useFocusRing(props);
  return <TextInput placeholderTextColor={colors.muted} {...props} {...ring.handlers} style={[s.input, ring.focused && s.inputFocus, props.style]} />;
}

export function Avatar({ id, name, size = 32, photo }: { id: string; name: string; size?: number; photo?: string | null }) {
  const [signed, setSigned] = useState<{ path: string; url: string } | null>(null);
  const url = signed && signed.path === photo ? signed.url : null;
  useEffect(() => {
    let mounted = true;
    if (photo) {
      void supabase.storage.from(PROFILE_PHOTOS).createSignedUrl(photo, 300).then(({ data }) => {
        if (mounted && data?.signedUrl) setSigned({ path: photo, url: data.signedUrl });
      }).catch(() => {});
    }
    return () => { mounted = false; };
  }, [photo]);
  return (
    <View style={[s.avatar, { width: size, height: size, backgroundColor: avatarColor(id) }]}>
      {url
        ? <Image accessibilityLabel={`Photo de ${name}`} source={{ uri: url }} style={{ width: size, height: size, borderRadius: size / 2 }} onError={() => setSigned(null)} />
        : <Text style={{ color: colors.onAccent, ...font.bold, fontSize: size * 0.36 }}>{initials(name)}</Text>}
    </View>
  );
}

export function Loading() {
  return (
    <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.bg }}>
      <ActivityIndicator color={colors.accent} />
    </View>
  );
}

export function ErrorText({ error }: { error: string | null }) {
  if (!error) return null;
  return <Text accessibilityRole="alert" accessibilityLiveRegion="polite" style={{ color: colors.coralSoft, fontSize: 14, ...font.body }}>{error}</Text>;
}

export function Empty({ children }: { children: ReactNode }) {
  return (
    <View style={{ padding: 24, alignItems: 'center' }}>
      <T muted style={{ textAlign: 'center' }}>{children}</T>
    </View>
  );
}

/** Ligne de réglage iOS : pictogramme sur pastille colorée, libellé, aide, chevron ; surlignée sous le doigt. */
export function LinkRow({ label, hint, onPress, icon, tint = colors.surface2 }: {
  label: string; hint?: string; onPress: () => void; icon?: string; tint?: string;
}) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress}
      style={({ pressed }) => [s.toggleRow, s.linkRow, pressed && { backgroundColor: 'rgba(255,255,255,0.06)' }]}>
      {icon ? <View style={[s.iconTile, { backgroundColor: tint }]}><Text style={{ fontSize: 16 }}>{icon}</Text></View> : null}
      <View style={{ flex: 1, gap: 2 }}>
        <T>{label}</T>
        {hint ? <T muted size={12}>{hint}</T> : null}
      </View>
      <View style={s.disclosure} />
    </Pressable>
  );
}

/** Liste compacte façon Réglages : les lignes se suivent, séparées par un trait fin (sans grands espaces). */
export function Rows({ children }: { children: ReactNode }) {
  const rows = Children.toArray(children).filter(Boolean);
  return (
    <View>
      {rows.map((row, i) => (
        <View key={i}>
          {i ? <View style={s.divider} /> : null}
          {row}
        </View>
      ))}
    </View>
  );
}

/** Séparateur d’une liste groupée, aligné sur le texte (après le pictogramme), comme dans Réglages. */
export function RowDivider({ inset = 58 }: { inset?: number }) {
  return <View style={[s.divider, { marginLeft: inset }]} />;
}

export const s = StyleSheet.create({
  screen: { flex: 1, backgroundColor: colors.bg },
  // Colonne centrée : sur le web desktop l'app garde une largeur de téléphone
  content: { padding: 16, gap: 14, paddingBottom: 48, width: '100%', maxWidth: 640, alignSelf: 'center' },
  title: { color: colors.text, ...font.display, letterSpacing: -0.4 },
  card: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: radius.lg, padding: 16, gap: 12 },
  rowBetween: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  button: { minHeight: 52, paddingVertical: 12, borderRadius: radius.md, borderWidth: 1, alignItems: 'center', justifyContent: 'center', paddingHorizontal: 18 },
  chip: { minHeight: 44, paddingHorizontal: 12, paddingVertical: 8, borderRadius: radius.pill, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  badge: { alignSelf: 'flex-start', paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill },
  segmented: { flexDirection: 'row', gap: 2, padding: 3, borderRadius: 13, backgroundColor: colors.fill },
  segment: { flexGrow: 1, flexShrink: 1, flexBasis: 'auto', minWidth: 0, minHeight: 44, paddingVertical: 8, paddingHorizontal: 10, borderRadius: 10, alignItems: 'center', justifyContent: 'center', flexDirection: 'row', gap: 6 },
  segmentOn: { backgroundColor: colors.accent, shadowColor: colors.accent, shadowOpacity: 0.35, shadowRadius: 10, shadowOffset: { width: 0, height: 3 } },
  dot: { width: 7, height: 7, borderRadius: 4, backgroundColor: colors.accent },
  toggleRow: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52 },
  input: {
    height: 48,
    borderRadius: 12,
    borderWidth: 1.5,
    borderColor: 'transparent',
    backgroundColor: colors.fill,
    color: colors.text,
    paddingHorizontal: 12,
    ...font.body,
    fontSize: 16,
  },
  inputFocus: { borderColor: colors.accent, backgroundColor: colors.fillStrong },
  avatar: { borderRadius: 999, alignItems: 'center', justifyContent: 'center' },
  pressed: { transform: [{ scale: 0.97 }] },
  linkRow: { marginHorizontal: -8, paddingHorizontal: 8, paddingVertical: 8, borderRadius: 12 },
  iconTile: { width: 30, height: 30, borderRadius: 8, alignItems: 'center', justifyContent: 'center' },
  disclosure: { width: 8, height: 8, borderRightWidth: 2, borderTopWidth: 2, borderColor: colors.muted, opacity: 0.7, transform: [{ rotate: '45deg' }], marginRight: 4 },
  headerButton: { flexDirection: 'row', alignItems: 'center', gap: 4, minHeight: 44, paddingHorizontal: 8 },
  chevron: { width: 12, height: 12, borderLeftWidth: 2.5, borderBottomWidth: 2.5, borderColor: colors.accent, transform: [{ rotate: '45deg' }], marginLeft: 6, marginRight: 2 },
  divider: { height: 1, backgroundColor: colors.line },
});

/** ‹ Retour d’en-tête, comme sur iPhone : chevron et nom de l’écran précédent, teintés. */
export function HeaderBack({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`Retour : ${label}`} onPress={onPress}
      style={({ pressed }) => [s.headerButton, { opacity: pressed ? 0.4 : 1 }]}>
      <View style={s.chevron} />
      <Text numberOfLines={1} style={{ color: colors.accent, fontSize: 17, maxWidth: 160, ...font.medium }}>{label}</Text>
    </Pressable>
  );
}

/** Action d’en-tête en texte teinté (« Modifier »…) ; l’action principale est en gras. */
export function HeaderAction({ label, onPress, prominent }: { label: string; onPress: () => void; prominent?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
      style={({ pressed }) => [s.headerButton, { opacity: pressed ? 0.4 : 1 }]}>
      <Text style={{ color: colors.accent, fontSize: 17, ...(prominent ? font.semibold : font.body) }}>{label}</Text>
    </Pressable>
  );
}
