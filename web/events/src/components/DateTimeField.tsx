import { View } from 'react-native';

import { colors, fonts } from '@/lib/theme';

import type { DateTimeFieldProps } from './DateTimeField.types';
import { T } from './ui';

/** La saisie web reste en heure de Zurich, quel que soit le fuseau du navigateur. */
export function DateTimeField({ label, value, onChangeText, hint }: DateTimeFieldProps) {
  const match = value.match(/^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})$/);
  const local = match ? `${match[3]}-${match[2]}-${match[1]}T${match[4]}:${match[5]}` : '';
  return (
    <View style={{ gap: 6, minWidth: 0 }}>
      <T muted size={13}>{label}</T>
      <input
        aria-label={label}
        type="datetime-local"
        value={local}
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
          fontFamily: fonts.body, fontSize: 16, colorScheme: 'dark',
        }}
      />
      <T muted size={12}>{hint ?? 'Heure de Zurich'}</T>
    </View>
  );
}
