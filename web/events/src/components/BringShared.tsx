import { useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import type { BringItem } from '@/lib/types';

import { Button, Meter, T } from './ui';

type Names = Map<string, string>;

/** « 6 / 15 » et « Léa 2 · Tom 4 » : ce qui est déjà pris, et par qui. */
export function bringShares(item: BringItem, names: Names, me: string) {
  const claims = item.bring_claims ?? [];
  const taken = claims.reduce((sum, c) => sum + c.quantity, 0);
  const mine = claims.find((c) => c.user_id === me)?.quantity ?? 0;
  const who = claims
    .filter((c) => c.quantity > 0)
    .map((c) => `${c.user_id === me ? 'Moi' : names.get(c.user_id) ?? '?'} ${c.quantity}`)
    .join(' · ');
  return { taken, mine, left: Math.max((item.quantity ?? 0) - taken, 0), who };
}

/** Un objet à partager (« 15 bouteilles ») : chacun dit combien il en amène, sans jamais dépasser la quantité demandée
 * (la base refuse le surplus, même si deux personnes répondent en même temps). */
export function SharedBringRow({ item, me, names, canParticipate, onChange, onError }: {
  item: BringItem;
  me: string;
  names: Names;
  canParticipate: boolean;
  onChange: () => void;
  onError: (message: string) => void;
}) {
  const [busy, setBusy] = useState(false);
  const total = item.quantity ?? 0;
  const shares = bringShares(item, names, me);
  // « + » / « − » successifs : la quantité voulue s'affiche tout de suite et les envois se suivent (le dernier gagne),
  // au lieu de repartir d'une fiche pas encore relue (des touchers se perdaient).
  const [wanted, setWanted] = useState<number | null>(null);
  if (wanted !== null && !busy && wanted === shares.mine) setWanted(null);
  const target = useRef<number | null>(null);
  const mine = wanted ?? shares.mine;
  const taken = shares.taken - shares.mine + mine;
  const left = Math.max(total - taken, 0);
  const { who } = shares;

  const write = (count: number) => (count > 0
    ? supabase.from('bring_claims').upsert({ item_id: item.id, user_id: me, quantity: count }, { onConflict: 'item_id,user_id' })
    : supabase.from('bring_claims').delete().eq('item_id', item.id).eq('user_id', me));

  const bring = async (delta: number) => {
    const next = Math.max(0, Math.min((target.current ?? mine) + delta, shares.mine + Math.max(total - shares.taken, 0)));
    const running = target.current !== null;
    target.current = next;
    setWanted(next);
    if (running) return;
    setBusy(true);
    let sent: number | null = null;
    let failure: string | null = null;
    while (target.current !== sent && !failure) {
      sent = target.current;
      const { error } = await write(sent ?? 0);
      failure = error ? error.message : null;
    }
    target.current = null;
    if (failure) setWanted(null);
    setBusy(false);
    onError(failure ?? '');
    onChange();
  };

  return (
    <View style={styles.box}>
      <View style={styles.line}>
        <T style={{ flex: 1 }}>{item.label}</T>
        <T muted>{taken} / {total}</T>
      </View>
      <Meter parts={[{ fraction: total ? taken / total : 0, color: left ? colors.accent : colors.mint }]} />
      {who ? <T muted size={12}>{who}</T> : null}
      {!left && !mine ? <T size={12} color={colors.mint}>Tout est pris, merci !</T> : null}
      {canParticipate && (left > 0 || mine > 0) ? (
        <View style={styles.line}>
          <T style={{ flex: 1 }}>{mine ? `J’en amène ${mine}` : 'J’en amène…'}</T>
          <Button small variant="secondary" label="−" accessibilityLabel={`En amener un de moins : ${item.label}`} style={styles.step}
            disabled={mine === 0} onPress={() => void bring(-1)} />
          <T style={styles.count}>{mine}</T>
          <Button small label="+" accessibilityLabel={`En amener un de plus : ${item.label}`} style={styles.step}
            disabled={left === 0} onPress={() => void bring(1)} />
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: 6 },
  line: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  // ± : 44 × 44 au moins (cible tactile Apple).
  step: { minWidth: 44, paddingHorizontal: 0 },
  count: { minWidth: 24, textAlign: 'center', fontWeight: '700' },
});
