import { StyleSheet, Text, View } from 'react-native';

import { addLimit, barChf, canAdd, canOrder, cartLines, cartQty, linesTotal, type Cart, type MyBar, type MyBarItem } from '@/lib/bar';
import { plural } from '@/lib/format';
import { colors, radius } from '@/lib/theme';

import { Badge, Button, Section, T } from '../ui';
import { Stepper } from './Stepper';

/** Ligne de la carte : prix, âge, limites ; − / + quand on peut commander. */
function MenuRow({ item, qty, bar, onChange }: { item: MyBarItem; qty: number; bar: MyBar; onChange: (n: number) => void }) {
  const orderable = canOrder(bar);
  const limit = addLimit(item, bar.phase);
  const soldOut = item.available === 0 && qty === 0;
  const blocked = orderable && qty >= limit.max;
  const maxReached = blocked && limit.reason === 'max_pending' && item.max_pending != null;
  const stockReached = blocked && limit.reason === 'stock' && !soldOut;
  const perPerson = orderable && bar.phase === 'open' && item.max_pending != null;
  return (
    <View style={st.item}>
      <View style={st.row}>
        <View style={st.tile}><Text style={{ fontSize: 22 }}>{item.emoji || '🍹'}</Text></View>
        <View style={{ flex: 1, gap: 3, minWidth: 0 }}>
          <T weight="semibold" size={15} numberOfLines={2}>{item.name}</T>
          <View style={st.meta}>
            <T size={13} weight="bold">{barChf(item.price_chf)}</T>
            {item.age_min ? <Badge label={`${item.age_min}+`} fg={colors.onCoral} bg={colors.coral} /> : null}
            {soldOut ? <T size={13} weight="bold" color={colors.redSoft}>Épuisé</T>
              : maxReached ? <T size={13} weight="bold" color={colors.coral}>max atteint</T>
                : stockReached ? <T size={13} color={colors.coral}>{`plus que ${plural(item.available ?? 0, 'disponible')}`}</T>
                  : perPerson ? <T size={13} muted>{`${item.mine_pending + qty} / ${item.max_pending} max`}</T> : null}
            {item.mine_pending ? <T size={13} muted>{`· ${item.mine_pending} déjà en attente`}</T> : null}
          </View>
        </View>
        {orderable ? (
          <Stepper label={item.name} value={qty} onChange={onChange} max={limit.max} canAdd={canAdd(item, qty, bar.phase)} />
        ) : null}
      </View>
      {maxReached ? (
        <T size={13} color={colors.coral} style={st.warn}>
          Maximum {item.max_pending} en attente par personne : tu pourras en recommander dès qu’un te sera servi.
        </T>
      ) : null}
    </View>
  );
}

/** La carte du bar (Mon bar) : choisir avec − / +, puis « Commander », qui ouvre la feuille « Valider la commande ». */
export function BarMenu({ bar, cart, onCart, onOrder }: { bar: MyBar; cart: Cart; onCart: (next: Cart) => void; onOrder: () => void }) {
  const orderable = canOrder(bar);
  const { count, total } = linesTotal(cartLines(cart, bar.items, bar.phase));
  return (
    <Section title="La carte">
      {bar.items.length === 0 ? <T muted size={14}>L’organisateur n’a pas encore ajouté d’article.</T> : null}
      {bar.items.map((item) => (
        <MenuRow key={item.id} item={item} bar={bar} qty={cartQty(cart, item, bar.phase)}
          onChange={(n) => onCart({ ...cart, [item.id]: Math.max(0, n) })} />
      ))}
      {orderable && bar.items.length ? (
        <View style={st.summary}>
          <T size={14} muted>{count ? `${plural(count, 'article')} choisi${count > 1 ? 's' : ''}` : 'Choisis tes boissons avec +'}</T>
          <Button label={count ? `Commander · ${barChf(total)}` : 'Commander'} disabled={!count} onPress={onOrder} />
        </View>
      ) : null}
      {orderable ? <T muted size={12}>Rien n’est dû avant que le barman te serve. Ce qui n’est pas servi s’annule.</T> : null}
    </Section>
  );
}

const st = StyleSheet.create({
  item: { gap: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  tile: { width: 44, height: 44, borderRadius: radius.sm, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
  meta: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  warn: { padding: 10, borderRadius: radius.sm, backgroundColor: colors.coralDim },
  summary: { gap: 8, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.line },
});
