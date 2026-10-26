import { Pressable, View } from 'react-native';

import { colors, font } from '@/lib/theme';

import type { DateTimeFieldProps } from './DateTimeField.types';
import { T } from './ui';

/** La saisie web reste en heure de Zurich, quel que soit le fuseau du navigateur. */
/** JJ.MM.AAAA HH:MM → valeur d’un <input type="datetime-local">. */
function toInput(v: string | undefined) {
  const match = v?.match(/^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})$/);
  return match ? `${match[3]}-${match[2]}-${match[1]}T${match[4]}:${match[5]}` : '';
}

export function DateTimeField({ label, value, onChangeText, hint, optional, min }: DateTimeFieldProps) {
  const local = toInput(value);
  return (
    <View style={{ gap: 6, minWidth: 0 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 20 }}>
        <T muted size={13}>{label}</T>
        {optional && value ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Effacer : ${label}`} onPress={() => onChangeText('')} hitSlop={12}>
            <T size={13} weight="semibold" color={colors.accent}>✕ Effacer</T>
          </Pressable>
        ) : null}
      </View>
      <input
        aria-label={label}
        type="datetime-local"
        value={local}
        min={toInput(min) || undefined}
        step={300}
        // Champ vide avec une date au plus tôt (fin d’un événement) : il s’ouvre sur le début.
        onFocus={() => { if (!value && min && toInput(min)) onChangeText(min); }}
        onChange={(event) => {
          const [day, time] = event.target.value.split('T');
          if (!day || !time) return onChangeText('');
          const [year, month, date] = day.split('-');
          onChangeText(`${date}.${month}.${year} ${time.slice(0, 5)}`);
        }}
        style={{
          boxSizing: 'border-box', width: '100%', minWidth: 0, minHeight: 48,
          padding: '10px 12px', color: colors.text, backgroundColor: colors.bg,
          border: `1px solid ${colors.lineStrong}`, borderRadius: 12,
          ...font.body, fontSize: 16, colorScheme: 'dark',
        }}
      />
      <T muted size={12}>{hint ?? 'Heure de Zurich'}</T>
    </View>
  );
}
