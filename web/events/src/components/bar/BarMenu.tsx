import { StyleSheet, Text, View } from 'react-native';

import { addLimit, barChf, canAdd, canOrder, cartLines, cartQty, linesTotal, optionsOf, type Cart, type MyBar, type MyBarItem } from '@/lib/bar';
import { eveningRoom, groupByCategory, limitsLine, roomFor, stockNote } from '@/lib/barOptions';
import { plural } from '@/lib/format';
import { colors, radius } from '@/lib/theme';

import { Badge, Button, Section, T } from '../ui';
import { Stepper } from './Stepper';

const NOTE_COLOR = { muted: colors.muted, warn: colors.coral, off: colors.redSoft } as const;

/** Ligne de la carte : prix (sauf bar offert), précision, âge, « Il en reste 3 », limites ; − / + quand on peut commander. */
function MenuRow({ item, qty, bar, room, onChange }: {
  item: MyBarItem; qty: number; bar: MyBar; room: ReturnType<typeof eveningRoom>; onChange: (n: number) => void;
}) {
  const free = optionsOf(bar).free_bar;
  const orderable = canOrder(bar);
  const limit = addLimit(item, bar.phase);
  const note = qty === 0 ? stockNote(item) : null;
  const blocked = orderable && qty >= limit.max;
  const maxReached = blocked && limit.reason === 'max_pending' && item.max_pending != null;
  const personReached = blocked && limit.reason === 'max_person' && item.max_per_person != null;
  const stockReached = blocked && limit.reason === 'stock' && qty > 0;
  const perPerson = orderable && bar.phase === 'open' && item.max_pending != null;
  const off = item.unavailable || (!!item.sold_out && qty === 0);
  return (
    <View style={[st.item, off && { opacity: 0.55 }]}>
      <View style={st.row}>
        <View style={st.tile}><Text style={{ fontSize: 22 }}>{item.emoji || '🍹'}</Text></View>
        <View style={{ flex: 1, gap: 3, minWidth: 0 }}>
          <T weight="semibold" size={15} numberOfLines={2}>{item.name}{item.detail ? <T muted size={13}>{` · ${item.detail}`}</T> : null}</T>
          <View style={st.meta}>
            {free ? null : <T size={13} weight="bold">{barChf(item.price_chf)}</T>}
            {item.age_min ? <Badge label={`${item.age_min}+`} fg={colors.onCoral} bg={colors.coral} /> : null}
            {note ? <T size={13} weight={note.tone === 'muted' ? undefined : 'bold'} color={NOTE_COLOR[note.tone]}>{note.text}</T>
              : maxReached || personReached ? <T size={13} weight="bold" color={colors.coral}>max atteint</T>
                : stockReached ? <T size={13} color={colors.coral}>{`plus que ${plural(item.available ?? 0, 'disponible')}`}</T>
                  : perPerson ? <T size={13} muted>{`${item.mine_pending + qty} / ${item.max_pending} max`}</T> : null}
            {item.mine_pending ? <T size={13} muted>{`· ${item.mine_pending} déjà en attente`}</T> : null}
          </View>
        </View>
        {orderable && !item.unavailable ? (
          <Stepper label={item.name} value={qty} onChange={onChange} max={limit.max}
            canAdd={canAdd(item, qty, bar.phase) && roomFor(item, room)} />
        ) : null}
      </View>
      {maxReached ? (
        <T size={13} color={colors.coral} style={st.warn}>
          Maximum {item.max_pending} en attente par personne : tu pourras en recommander dès qu’un te sera servi.
        </T>
      ) : null}
      {personReached ? (
        <T size={13} color={colors.coral} style={st.warn}>Maximum {item.max_per_person} {item.name} par personne pour la soirée.</T>
      ) : null}
    </View>
  );
}

/**
 * La carte du bar (Mon bar), regroupée par catégorie : choisir avec − / +, puis « Commander » (feuille « Valider la
 * commande »). Commandes au comptoir seulement : la carte se consulte, sans − / +.
 */
export function BarMenu({ bar, cart, onCart, onOrder }: { bar: MyBar; cart: Cart; onCart: (next: Cart) => void; onOrder: () => void }) {
  const options = optionsOf(bar);
  const orderable = canOrder(bar);
  const { count, total } = linesTotal(cartLines(cart, bar.items, bar.phase));
  const room = eveningRoom(bar, cart);
  const limits = bar.eligible ? limitsLine(bar) : null;
  const roomOut = orderable && (room.glasses === 0 || room.chf === 0);
  return (
    <Section title="La carte" right={options.free_bar ? <Badge label="Bar offert" fg={colors.onMint} bg={colors.mint} /> : undefined}>
      {bar.items.length === 0 ? <T muted size={14}>L’organisateur n’a pas encore ajouté d’article.</T> : null}
      {!options.guest_orders && bar.phase !== 'closed' ? (
        <T size={14} weight="semibold" color={colors.textSoft} style={st.info}>
          Commande au comptoir : montre ton QR au barman, il te sert directement.
        </T>
      ) : null}
      {groupByCategory(bar.items).map((g) => (
        <View key={g.key} style={{ gap: 12 }}>
          {g.label ? <T size={12} weight="bold" color={colors.muted} style={st.group}>{g.label.toUpperCase()}</T> : null}
          {g.items.map((item) => (
            <MenuRow key={item.id} item={item} bar={bar} room={room} qty={cartQty(cart, item, bar.phase)}
              onChange={(n) => onCart({ ...cart, [item.id]: Math.max(0, n) })} />
          ))}
        </View>
      ))}
      {limits ? <T size={13} color={roomOut ? colors.coral : colors.textSoft}>{limits}</T> : null}
      {orderable && bar.items.length ? (
        <View style={st.summary}>
          <T size={14} muted>{count ? `${plural(count, 'article')} choisi${count > 1 ? 's' : ''}` : 'Choisis tes boissons avec +'}</T>
          <Button label={count ? (options.free_bar ? 'Commander' : `Commander · ${barChf(total)}`) : 'Commander'} disabled={!count} onPress={onOrder} />
        </View>
      ) : null}
      {orderable && !options.free_bar ? <T muted size={12}>Rien n’est dû avant que le barman te serve. Ce qui n’est pas servi s’annule.</T> : null}
      {orderable && options.free_bar ? <T muted size={12}>Bar offert : rien à payer. Ce qui n’est pas servi s’annule.</T> : null}
    </Section>
  );
}

const st = StyleSheet.create({
  item: { gap: 6 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  tile: { width: 44, height: 44, borderRadius: radius.sm, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
  meta: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  warn: { padding: 10, borderRadius: radius.sm, backgroundColor: colors.coralDim },
  info: { padding: 10, borderRadius: radius.sm, backgroundColor: colors.fill },
  group: { letterSpacing: 1, paddingTop: 4 },
  summary: { gap: 8, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.line },
});
