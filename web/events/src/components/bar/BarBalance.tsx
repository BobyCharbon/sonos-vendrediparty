import { StyleSheet, Text, View } from 'react-native';

import { amount, barChf, payeeLine, type MyBar } from '@/lib/bar';
import { colors, font, radius } from '@/lib/theme';

import { T } from '../ui';

type Props = {
  bar: Pick<MyBar, 'balance' | 'pending_total' | 'refund_declared' | 'payee' | 'phase'>;
  /** Carte de la fiche de l'événement : un peu plus petit, sans le détail des remboursements. */
  compact?: boolean;
};

/**
 * Le solde à rembourser, EN GRAND (exigence de l'admin) : seul ce qui a été servi est dû. Ce qui est commandé mais pas
 * encore servi s'affiche à part, « pas dû ».
 */
export function BarBalance({ bar, compact = false }: Props) {
  const label = bar.phase === 'closed' && bar.balance > 0 ? 'RESTE À REMBOURSER' : 'À REMBOURSER';
  return (
    <View style={[st.hero, compact && st.compact]}>
      <T size={12} weight="bold" color={colors.coralSoft} style={st.label}>{label}</T>
      <View style={st.amountRow} accessibilityLabel={`${label.toLowerCase()} : ${barChf(bar.balance)}`}>
        <Text testID="bar-balance" style={[st.amount, compact && st.amountCompact]}>{amount(bar.balance)}</Text>
        <Text style={st.unit}>CHF</Text>
      </View>
      <T size={compact ? 13 : 14} color={colors.textSoft}>{payeeLine(bar.payee)}</T>
      {bar.pending_total > 0 ? (
        <View style={st.pending}>
          <T size={13} color={colors.textSoft} style={{ flex: 1 }}>Commandé, pas encore servi (pas dû)</T>
          <T size={14} weight="bold">{barChf(bar.pending_total)}</T>
        </View>
      ) : null}
      {!compact && bar.refund_declared > 0 ? (
        <T size={13} color={colors.coral}>
          Remboursement annoncé : {barChf(bar.refund_declared)}, à confirmer par {bar.payee.name?.trim() || 'l’organisateur'}.
        </T>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  hero: { gap: 6, padding: 18, borderRadius: radius.lg, backgroundColor: colors.accentDim, borderWidth: 1, borderColor: '#5A2346' },
  compact: { padding: 14, gap: 4 },
  label: { letterSpacing: 1.2 },
  amountRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  amount: { ...font.display, color: colors.text, fontSize: 60, lineHeight: 64, letterSpacing: -1, fontVariant: ['tabular-nums'] },
  amountCompact: { fontSize: 44, lineHeight: 48 },
  unit: { ...font.bold, color: colors.textSoft, fontSize: 18 },
  pending: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 6, paddingTop: 10, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.12)' },
});
