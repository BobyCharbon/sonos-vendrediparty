import { StyleSheet, View } from 'react-native';

import { barChf, cancelLabel, itemLabel, round2, type MyBar } from '@/lib/bar';
import { formatMessageTime, formatTime } from '@/lib/format';
import { colors, radius } from '@/lib/theme';

import { Button, Section, T } from '../ui';

/** En attente : commandé, pas encore servi (rien n'est dû) ; « Annuler 1 » libère la place pour les autres. */
export function PendingList({ bar, busy, onCancel }: { bar: MyBar; busy: string | null; onCancel: (item: string, name: string) => void }) {
  const waiting = bar.items.filter((i) => i.mine_pending > 0);
  if (!waiting.length) return null;
  return (
    <Section title="En attente" right={<T size={13} weight="bold" color={colors.coral}>{barChf(bar.pending_total)}</T>}>
      <T size={13} color={colors.textSoft}>
        Commandé, pas encore servi : rien n’est dû pour ces verres. Annule ce que tu ne boiras pas, ça libère la place pour les autres.
      </T>
      {waiting.map((i) => (
        <View key={i.id} style={st.row}>
          <View style={{ flex: 1, minWidth: 0 }}>
            <T weight="semibold" size={15} numberOfLines={2}>{itemLabel(i)}</T>
            <T muted size={12}>× {i.mine_pending} en attente · à servir</T>
          </View>
          <Button small variant="danger" label="Annuler 1" accessibilityLabel={`Annuler 1 ${i.name}`}
            loading={busy === i.id} disabled={!!busy && busy !== i.id} onPress={() => onCancel(i.id, i.name)} />
        </View>
      ))}
    </Section>
  );
}

/** Servi : chaque consommation avec son heure et son prix (figé à la commande), puis le total. */
export function ServedList({ bar }: { bar: MyBar }) {
  if (!bar.served.length) return null;
  const total = round2(bar.served.reduce((sum, u) => sum + u.price_chf, 0));
  return (
    <Section title="Servi">
      {bar.served.map((u, i) => (
        <View key={`${u.at}-${i}`} style={st.line}>
          <T muted size={13} style={st.hour}>{formatTime(u.at)}</T>
          <T size={14} style={{ flex: 1 }} numberOfLines={2}>{itemLabel({ emoji: u.emoji, name: u.item })}</T>
          <T size={14} weight="semibold">{barChf(u.price_chf)}</T>
        </View>
      ))}
      <View style={[st.line, st.total]}>
        <T size={14} weight="bold" style={{ flex: 1 }}>Total servi</T>
        <T size={14} weight="bold">{barChf(total)}</T>
      </View>
    </Section>
  );
}

/** Annulés (par moi, l'organisateur, la fermeture) et corrigés : jamais rien à payer. */
export function CancelledList({ bar }: { bar: MyBar }) {
  if (!bar.cancelled.length) return null;
  return (
    <Section title="Annulés">
      {bar.cancelled.map((u, i) => (
        <View key={`${u.at ?? ''}-${i}`} style={st.line}>
          {u.at ? <T muted size={13} style={st.hour}>{formatTime(u.at)}</T> : null}
          <View style={{ flex: 1, minWidth: 0 }}>
            <T size={14} color={colors.textSoft} numberOfLines={2}>{itemLabel({ emoji: u.emoji, name: u.item })}</T>
            <T size={12} muted>{cancelLabel(u.reason)}</T>
          </View>
        </View>
      ))}
      <T muted size={12}>Rien à payer pour ces verres.</T>
    </Section>
  );
}

/** « ✓ Engagements acceptés le 21 nov. à 22:03, 21 nov. à 23:05 » (Party garde le texte et l'heure). */
export function PledgesLine({ pledges }: { pledges: string[] }) {
  if (!pledges.length) return null;
  const when = pledges.map((p) => formatMessageTime(p)).join(', ');
  return <T size={13} color={colors.textSoft}>✓ {pledges.length > 1 ? 'Engagements acceptés' : 'Engagement accepté'} : {when}</T>;
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: radius.md, backgroundColor: colors.fill },
  line: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 28 },
  hour: { width: 46, fontVariant: ['tabular-nums'] },
  total: { paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.line },
});
