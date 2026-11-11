import { StyleSheet, Text, View } from 'react-native';

import { amount, barChf, optionsOf, payeeLine, type MyBar } from '@/lib/bar';
import { plural } from '@/lib/format';
import { colors, font, radius } from '@/lib/theme';

import { T } from '../ui';

type Props = {
  bar: Pick<MyBar, 'balance' | 'pending_total' | 'refund_declared' | 'payee' | 'phase' | 'options'> & { served?: MyBar['served'] };
  /** Carte de la fiche de l'événement : un peu plus petit, sans le détail des remboursements. */
  compact?: boolean;
};

/**
 * Le solde à rembourser, EN GRAND (exigence de l'admin) : seul ce qui a été servi est dû. Ce qui est commandé mais pas
 * encore servi s'affiche à part, « pas dû ».
 */
export function BarBalance({ bar, compact = false }: Props) {
  // Bar offert (option de l'organisateur) : rien à rembourser, on montre les verres servis à la place du solde.
  if (optionsOf(bar).free_bar && bar.balance <= 0) {
    const served = bar.served?.length ?? 0;
    return (
      <View style={[st.hero, st.free, compact && st.compact]}>
        <T size={12} weight="bold" color={colors.mint} style={st.label}>BAR OFFERT</T>
        <Text testID="bar-balance" style={[st.amount, compact && st.amountCompact, { fontSize: compact ? 30 : 40, lineHeight: compact ? 34 : 44 }]}>Rien à payer</Text>
        <T size={compact ? 13 : 14} color={colors.textSoft}>{served ? `${plural(served, 'verre servi', 'verres servis')} ce soir` : 'Les boissons sont offertes par l’organisateur.'}</T>
      </View>
    );
  }
  // Solde négatif : un verre déjà remboursé a ensuite été corrigé ou annulé, l'organisateur lui doit la différence
  // (test réel du 10.11 : « À REMBOURSER -8 CHF » s'affichait).
  const credit = bar.balance < 0;
  const label = credit ? 'À TE RENDRE' : bar.phase === 'closed' && bar.balance > 0 ? 'RESTE À REMBOURSER' : 'À REMBOURSER';
  return (
    <View style={[st.hero, compact && st.compact]}>
      <T size={12} weight="bold" color={colors.coralSoft} style={st.label}>{label}</T>
      <View style={st.amountRow} accessibilityLabel={`${label.toLowerCase()} : ${barChf(Math.abs(bar.balance))}`}>
        <Text testID="bar-balance" style={[st.amount, compact && st.amountCompact]}>{amount(Math.abs(bar.balance))}</Text>
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
  free: { backgroundColor: colors.mintDim, borderColor: colors.mint },
  label: { letterSpacing: 1.2 },
  amountRow: { flexDirection: 'row', alignItems: 'baseline', gap: 8 },
  amount: { ...font.display, color: colors.text, fontSize: 60, lineHeight: 64, letterSpacing: -1, fontVariant: ['tabular-nums'] },
  amountCompact: { fontSize: 44, lineHeight: 48 },
  unit: { ...font.bold, color: colors.textSoft, fontSize: 18 },
  pending: { flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 6, paddingTop: 10, borderTopWidth: 1, borderTopColor: 'rgba(255,255,255,0.12)' },
});
