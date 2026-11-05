import { Pressable, StyleSheet, View } from 'react-native';

import { enter, pressTransition, useChangedSinceMount } from '@/lib/motion';
import { rsvpChoices } from '@/lib/rsvp';
import { colors, font, radius } from '@/lib/theme';
import type { RsvpStatus } from '@/lib/types';

import { T } from './ui';

type Props = {
  options: RsvpStatus[];
  /** Réponse actuelle (pleine couleur), ou rien. */
  selected?: RsvpStatus | null;
  /** Choix en cours d’enregistrement. */
  busy?: RsvpStatus | null;
  disabled?: boolean;
  onSelect: (choice: RsvpStatus) => void;
  /** Libellé lu par VoiceOver pour chaque choix (par défaut : le libellé visible). */
  accessibilityLabel?: (choice: RsvpStatus) => string;
  /** Libellé affiché (par ex. « Liste d’attente » quand l’événement est complet). */
  label?: (choice: RsvpStatus) => string;
};

/**
 * Présent / Peut-être / Absent : un seul langage visuel partout (liste et détail).
 * Chaque choix a sa couleur et son pictogramme ; le choix fait est plein, les autres restent lisibles mais en retrait.
 * Retour immédiat : le choix touché se remplit tout de suite (pendant l’enregistrement) et son pictogramme « se pose ».
 */
export function RsvpButtons({ options, selected, busy, disabled, onSelect, accessibilityLabel, label }: Props) {
  const current = busy ?? selected ?? null;
  // Le pictogramme ne rebondit que pour un choix fait ici, pas à l’ouverture de l’écran ni à un rechargement.
  const changed = useChangedSinceMount(current);
  return (
    <View style={st.row} accessibilityRole="radiogroup">
      {options.map((k) => {
        const c = rsvpChoices[k];
        const on = current === k;
        const dimmed = !!current && !on;
        return (
          <Pressable
            key={k}
            accessibilityRole="button"
            accessibilityLabel={accessibilityLabel?.(k) ?? c.label}
            accessibilityState={{ selected: on, disabled: !!disabled, busy: busy === k }}
            disabled={disabled || !!busy}
            onPress={() => onSelect(k)}
            style={({ pressed }) => [
              st.choice,
              pressTransition,
              on ? { backgroundColor: c.bg, borderColor: c.bg } : { backgroundColor: `${c.bg}14`, borderColor: `${c.bg}38` },
              dimmed && { opacity: 0.6 },
              disabled && !on && { opacity: 0.4 },
              pressed && st.pressed,
              busy === k && { opacity: 0.85 },
            ]}
          >
            <View key={on ? 'on' : 'off'} style={[on && changed ? enter('pop') : null, st.icon, { backgroundColor: on ? 'rgba(0,0,0,0.16)' : `${c.bg}26` }]}>
              <T size={14} style={{ ...font.bold, lineHeight: 16 }} color={on ? c.fg : c.bg}>{c.icon}</T>
            </View>
            <T size={14} numberOfLines={2} style={{ ...font.semibold, textAlign: 'center' }} color={on ? c.fg : colors.text}>{label?.(k) ?? c.label}</T>
          </Pressable>
        );
      })}
    </View>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8 },
  choice: { flex: 1, minWidth: 0, minHeight: 60, alignItems: 'center', justifyContent: 'center', gap: 4,
    paddingVertical: 8, paddingHorizontal: 4, borderRadius: radius.md, borderWidth: 1 },
  icon: { width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center' },
  pressed: { transform: [{ scale: 0.96 }] },
});
