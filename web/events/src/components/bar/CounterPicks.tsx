import { StyleSheet, Text, View } from 'react-native';

import { barChf, MAX_LINE_QTY, type Cart, type CounterItem } from '@/lib/bar';
import { groupByCategory } from '@/lib/barOptions';
import { colors, radius } from '@/lib/theme';

import { T } from '../ui';
import { Stepper } from './Stepper';

/** Combien le barman peut encore servir sans commande de cet article (stock virtuel libre, 50 par geste). */
export const counterMax = (i: CounterItem) => (i.unavailable ? 0 : Math.min(MAX_LINE_QTY, i.available ?? MAX_LINE_QTY));

/**
 * « Servir sans commande » (option de l'organisateur) : la carte du comptoir, − / + par article ; les indisponibles
 * et les épuisés sont grisés. La base vérifie tout (engagement, stock, limites par personne).
 */
export function CounterPicks({ menu, picks, free, disabled, onPick }: {
  menu: CounterItem[]; picks: Cart; free: boolean; disabled: boolean; onPick: (item: string, qty: number) => void;
}) {
  return (
    <View style={{ gap: 8 }}>
      {groupByCategory(menu).map((g) => (
        <View key={g.key} style={{ gap: 8 }}>
          {g.label ? <T size={12} weight="bold" color={colors.muted}>{g.label.toUpperCase()}</T> : null}
          {g.items.map((i) => {
            const qty = Math.min(picks[i.item] ?? 0, counterMax(i));
            const off = counterMax(i) === 0;
            const note = i.unavailable ? 'indisponible' : i.available === 0 ? 'épuisé' : i.available != null ? `${i.available} libres` : null;
            return (
              <View key={i.item} style={[st.pick, qty > 0 && st.pickOn, off && { opacity: 0.5 }]}>
                <View style={st.tile}><Text style={{ fontSize: 20 }}>{i.emoji || '🍹'}</Text></View>
                <View style={{ flex: 1, minWidth: 0 }}>
                  <T weight="semibold" size={15} numberOfLines={2}>{i.name}{i.detail ? ` · ${i.detail}` : ''}</T>
                  <T muted size={12}>{[free ? null : barChf(i.price_chf), i.age_min ? `${i.age_min}+` : null, note].filter(Boolean).join(' · ')}</T>
                </View>
                <Stepper label={`${i.name} (sans commande)`} value={qty} max={counterMax(i)} tone="mint" hideZero
                  disabled={disabled || off} onChange={(n) => onPick(i.item, n)} />
              </View>
            );
          })}
        </View>
      ))}
    </View>
  );
}

const st = StyleSheet.create({
  pick: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.line, backgroundColor: colors.surface },
  pickOn: { borderColor: colors.mint, backgroundColor: colors.mintDim },
  tile: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
});
