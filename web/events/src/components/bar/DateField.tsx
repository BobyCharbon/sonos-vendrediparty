import { Pressable, View } from 'react-native';

import { colors, font } from '@/lib/theme';

import { T } from '../ui';

const box = {
  boxSizing: 'border-box', minWidth: 0, minHeight: 48, padding: '10px 12px', color: colors.text, width: '100%',
  backgroundColor: colors.fill, border: '1.5px solid transparent', borderRadius: 12, outlineColor: colors.accent,
  ...font.body, fontSize: 16, colorScheme: 'dark',
} as const;

/** Jour seul (AAAA-MM-JJ), sélecteur du téléphone ; facultatif : « ✕ Effacer » le vide (comme DateTimeField). */
export function DateField({ label, value, onChange, hint, min }: {
  label: string; value: string; onChange: (value: string) => void; hint?: string; min?: string;
}) {
  return (
    <View style={{ gap: 6, minWidth: 0 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 20 }}>
        <T muted size={13} weight="medium">{label}</T>
        {value ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Effacer : ${label}`} onPress={() => onChange('')} hitSlop={12}>
            <T size={13} weight="semibold" color={colors.accent}>✕ Effacer</T>
          </Pressable>
        ) : null}
      </View>
      <input aria-label={label} type="date" value={value} min={min} onChange={(event) => onChange(event.target.value)} style={box} />
      {hint ? <T muted size={12}>{hint}</T> : null}
    </View>
  );
}
