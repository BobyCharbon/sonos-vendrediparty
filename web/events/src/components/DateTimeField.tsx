import { Pressable, View } from 'react-native';

import { colors, font } from '@/lib/theme';

import type { DateTimeFieldProps } from './DateTimeField.types';
import { T } from './ui';

/** Heures proposées : toutes les 5 minutes (une roue native sur iPhone et Android, jamais 19:03). */
const STEP_MINUTES = 5;
const TIMES = Array.from({ length: (24 * 60) / STEP_MINUTES }, (_, i) => {
  const minutes = i * STEP_MINUTES;
  return `${String(Math.floor(minutes / 60)).padStart(2, '0')}:${String(minutes % 60).padStart(2, '0')}`;
});
/** Heure choisie d’office quand on prend d’abord le jour (une soirée commence le soir). */
const DEFAULT_TIME = '19:00';

/** La saisie web reste en heure de Zurich, quel que soit le fuseau du navigateur. */
/** JJ.MM.AAAA HH:MM → { date: AAAA-MM-JJ, time: HH:MM }. */
function split(v: string | undefined) {
  const match = v?.match(/^(\d{2})\.(\d{2})\.(\d{4}) (\d{2}):(\d{2})$/);
  return match ? { date: `${match[3]}-${match[2]}-${match[1]}`, time: `${match[4]}:${match[5]}` } : { date: '', time: '' };
}
function today() {
  const n = new Date();
  return `${n.getFullYear()}-${String(n.getMonth() + 1).padStart(2, '0')}-${String(n.getDate()).padStart(2, '0')}`;
}
function join(date: string, time: string) {
  const [year, month, day] = date.split('-');
  return `${day}.${month}.${year} ${time}`;
}

const box = {
  boxSizing: 'border-box', minWidth: 0, minHeight: 48, padding: '10px 12px', color: colors.text,
  backgroundColor: colors.fill, border: '1.5px solid transparent', borderRadius: 12, outlineColor: colors.accent,
  ...font.body, fontSize: 16, colorScheme: 'dark',
} as const;

export function DateTimeField({ label, value, onChangeText, hint, optional, min }: DateTimeFieldProps) {
  const current = split(value);
  const earliest = split(min);
  const time = current.time || earliest.time || DEFAULT_TIME;
  // Valeur ancienne hors du pas de 5 min (saisie avant ce changement) : on la garde affichée telle quelle.
  const times = current.time && !TIMES.includes(current.time) ? [...TIMES, current.time].sort() : TIMES;
  // Champ vide avec une date au plus tôt (fin d’un événement) : il s’ouvre sur le début.
  const prefill = () => { if (!value && min && earliest.date) onChangeText(min); };
  return (
    <View style={{ gap: 6, minWidth: 0 }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', minHeight: 20 }}>
        <T muted size={13} weight="medium">{label}</T>
        {optional && value ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Effacer : ${label}`} onPress={() => onChangeText('')} hitSlop={12}>
            <T size={13} weight="semibold" color={colors.accent}>✕ Effacer</T>
          </Pressable>
        ) : null}
      </View>
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <input
          aria-label={`${label} : jour`}
          type="date"
          value={current.date}
          min={earliest.date || undefined}
          onFocus={prefill}
          onChange={(event) => onChangeText(event.target.value ? join(event.target.value, time) : '')}
          style={{ ...box, flex: 3, width: '100%' }}
        />
        <select
          aria-label={`${label} : heure`}
          value={current.time}
          onFocus={prefill}
          onChange={(event) => {
            const date = current.date || earliest.date || today();
            onChangeText(event.target.value ? join(date, event.target.value) : '');
          }}
          style={{ ...box, flex: 2, width: '100%', appearance: 'none', textAlign: 'center' }}
        >
          <option value="" disabled>Heure</option>
          {times.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
      </View>
      <T muted size={12}>{hint ?? 'Heure de Zurich'}</T>
    </View>
  );
}
