import { Modal, Pressable, StyleSheet, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { T } from '../ui';
import { isMuted, MUTE_CHOICES, muteLabel, NOTIFY_LEVELS, type MuteChoice, type NotifyLevel } from '@/lib/chats';
import { duration, enter, transition } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';

/** Libellé lu de la cloche : « Notifications : Mentions seulement », « … en sourdine ». */
export function bellLabel(level: NotifyLevel, mutedUntil: string | null): string {
  const name = NOTIFY_LEVELS.find((l) => l.key === level)?.label ?? 'Mentions seulement';
  return `Notifications : ${name}${isMuted(mutedUntil) ? ', en sourdine' : ''}`;
}

/** Cloche de l'en-tête (à droite) : 🔔, « @ » en mentions seulement, 🔕 coupée ou en sourdine. */
export function NotifyBell({ level, mutedUntil, onPress }: { level: NotifyLevel; mutedUntil: string | null; onPress: () => void }) {
  const off = level === 'none' || isMuted(mutedUntil);
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={bellLabel(level, mutedUntil)} accessibilityHint="Choisir quand être prévenu"
      onPress={onPress} style={({ pressed }) => [st.bell, pressed && { opacity: 0.5 }]}>
      <T size={20}>{off ? '🔕' : '🔔'}</T>
      {!off && level === 'mentions' ? (
        <View style={st.at}><T size={10} weight="bold" color={colors.onAccent}>@</T></View>
      ) : null}
    </Pressable>
  );
}

type Props = {
  open: boolean;
  level: NotifyLevel;
  mutedUntil: string | null;
  onClose: () => void;
  onLevel: (level: NotifyLevel) => void;
  /** null : réactiver. */
  onMute: (choice: MuteChoice | null) => void;
  onSettings: () => void;
};

/** Menu de la cloche, sous l'en-tête à droite : Tout / Mentions seulement (défaut) / Rien ; Sourdine 8 h / 1 semaine /
 * Toujours (ou Réactiver) ; « Réglages… ». Toucher à côté ferme. */
export function NotifyMenu({ open, level, mutedUntil, onClose, onLevel, onMute, onSettings }: Props) {
  const top = useSafeAreaInsets().top + 52;
  const muted = muteLabel(mutedUntil);
  const pick = (f: () => void) => () => { onClose(); f(); };
  return (
    <Modal transparent visible={open} animationType="none" onRequestClose={onClose}>
      <Pressable accessible={false} onPress={onClose} style={st.backdrop} />
      <View accessibilityRole="menu" accessibilityLabel="Notifications de la discussion" style={[st.menu, { top }, enter('drop')]}>
        <T size={12} weight="semibold" muted style={st.head}>NOTIFICATIONS</T>
        {NOTIFY_LEVELS.map((l) => (
          <Item key={l.key} label={l.label} hint={l.hint} checked={level === l.key} onPress={pick(() => onLevel(l.key))} />
        ))}
        <View style={st.sep} />
        <T size={12} weight="semibold" muted style={st.head}>{muted ? muted.toUpperCase() : 'SOURDINE'}</T>
        {muted ? <Item label="Réactiver les notifications" onPress={pick(() => onMute(null))} />
          : MUTE_CHOICES.map((c) => <Item key={c.key} label={`Sourdine ${c.label}`} onPress={pick(() => onMute(c.key))} />)}
        <View style={st.sep} />
        <Item label="Réglages…" onPress={pick(onSettings)} />
      </View>
    </Modal>
  );
}

function Item({ label, hint, checked, onPress }: { label: string; hint?: string; checked?: boolean; onPress: () => void }) {
  return (
    // menuitemradio (choix coché) : rôle ARIA que react-native-web transmet tel quel, absent des types de React Native.
    <Pressable role={(checked === undefined ? 'menuitem' : 'menuitemradio') as 'menuitem'} aria-checked={checked} accessibilityLabel={label}
      onPress={onPress} style={({ pressed }) => [st.item, transition('background-color', duration.fast), pressed && { backgroundColor: colors.fill }]}>
      <View style={{ width: 18 }}>{checked ? <T size={15} weight="bold" color={colors.accent}>✓</T> : null}</View>
      <View style={{ flex: 1, gap: 1 }}>
        <T size={15} weight={checked ? 'semibold' : 'body'}>{label}</T>
        {hint ? <T size={12} muted numberOfLines={2}>{hint}</T> : null}
      </View>
    </Pressable>
  );
}

const st = StyleSheet.create({
  bell: { minWidth: 44, minHeight: 44, alignItems: 'center', justifyContent: 'center', marginRight: 4 },
  at: { position: 'absolute', right: 6, bottom: 8, width: 15, height: 15, borderRadius: 8, backgroundColor: colors.accent,
    alignItems: 'center', justifyContent: 'center' },
  backdrop: { position: 'fixed' as 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.25)' },
  menu: { position: 'absolute', right: 10, width: 290, maxWidth: '92%', paddingVertical: 6, borderRadius: radius.md,
    backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.lineStrong,
    shadowColor: '#000', shadowOpacity: 0.45, shadowRadius: 18, shadowOffset: { width: 0, height: 8 } },
  head: { paddingHorizontal: 14, paddingTop: 8, paddingBottom: 4, letterSpacing: 0.6 },
  item: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingHorizontal: 14, minHeight: 44, paddingVertical: 6 },
  sep: { height: 1, backgroundColor: colors.line, marginVertical: 4 },
});
