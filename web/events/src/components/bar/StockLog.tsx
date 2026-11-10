import { StyleSheet, View } from 'react-native';

import { barChf, type StockLogEntry } from '@/lib/bar';
import { formatTime } from '@/lib/format';

import { Section, T } from '../ui';

/** « Il en reste 5 », « +12 en réassort », « indisponible », « prix 4.50 CHF » : ce qu'a fait chaque geste. */
export function stockLogText(l: StockLogEntry): string {
  switch (l.kind) {
    case 'stock_set': return `il en reste ${l.qty ?? 0}`;
    case 'restock': return `+${l.qty ?? 0} en réassort`;
    case 'unavailable': return 'indisponible pour l’instant';
    case 'available': return 'de nouveau dispo';
    case 'price_set': return `prix ${barChf(Number(l.amount ?? 0))}`;
    default: return l.kind;
  }
}

/** Journal des gestes de la soirée sur la carte (organisateur) : qui, quoi, combien. */
export function StockLog({ log }: { log: StockLogEntry[] | undefined }) {
  if (!log?.length) return null;
  return (
    <Section title="Gestes sur la carte">
      {log.map((l, i) => (
        <View key={`${l.at}-${i}`} style={st.line}>
          <T muted size={13} style={st.hour}>{formatTime(l.at)}</T>
          <T size={14} style={{ flex: 1 }}>{l.actor ?? '?'} · {l.item ?? 'article'} : {stockLogText(l)}</T>
        </View>
      ))}
    </Section>
  );
}

const st = StyleSheet.create({
  line: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  hour: { width: 46, fontVariant: ['tabular-nums'] },
});
