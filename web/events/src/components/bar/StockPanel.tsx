import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import {
  barChf, barItemAction, barSaveItem, barStaffItems, errorCode, errorText, type BarItem, type BarRights, type ItemAction, type ItemInput,
} from '@/lib/bar';
import { useQuery } from '@/lib/data';
import { colors, radius } from '@/lib/theme';

import { useTermsGate } from '../TermsSheet';
import { Badge, Button, ErrorText, Field, s, Section, T } from '../ui';
import { ItemForm } from './ItemForm';
import { stockLogText } from './StockLog';

type Ask = { item: string; action: 'remaining' | 'restock' | 'price' } | null;
const ASK_LABEL = { remaining: 'Il en reste', restock: 'Réassort : combien en plus ?', price: 'Nouveau prix (CHF)' } as const;

/** Une ligne de la carte pour le barman : ce qui reste, et les gestes que l'organisateur lui permet. */
function StockRow({ item, rights, busy, ask, onAsk, onAct, onEdit }: {
  item: BarItem; rights: BarRights; busy: boolean; ask: Ask; onAsk: (a: Ask) => void;
  onAct: (action: ItemAction, amount?: number) => void; onEdit: () => void;
}) {
  const [value, setValue] = useState('');
  const asking = ask?.item === item.id ? ask.action : null;
  const left = item.left ?? null;
  function submit() {
    const n = Number(value.trim().replace(',', '.'));
    if (!value.trim() || !Number.isFinite(n) || n < 0) return;
    onAct(asking!, n);
    setValue('');
  }
  return (
    <View style={[st.row, item.unavailable && st.off]}>
      <View style={st.head}>
        <View style={st.tile}><Text style={{ fontSize: 20 }}>{item.emoji || '🍹'}</Text></View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <T weight="semibold" size={15} numberOfLines={2}>{item.name}{item.detail ? ` · ${item.detail}` : ''}</T>
          <T muted size={12}>
            {left == null ? 'Illimité' : `Il en reste ${left}`}{item.pending ? ` · ${item.pending} en attente` : ''} · {barChf(item.price_chf)}
          </T>
        </View>
        {item.unavailable ? <Badge label="Indisponible" fg={colors.textSoft} bg={colors.surface2} /> : null}
      </View>
      <View style={s.wrap}>
        {rights.adjust_stock ? <Button small variant="secondary" label="Il en reste…" accessibilityLabel={`Il en reste : ${item.name}`}
          disabled={busy} onPress={() => onAsk(asking === 'remaining' ? null : { item: item.id, action: 'remaining' })} /> : null}
        {rights.adjust_stock && item.stock != null ? <Button small variant="secondary" label="+ Réassort" accessibilityLabel={`Réassort : ${item.name}`}
          disabled={busy} onPress={() => onAsk(asking === 'restock' ? null : { item: item.id, action: 'restock' })} /> : null}
        {rights.unavailable ? <Button small variant={item.unavailable ? 'primary' : 'ghost'}
          label={item.unavailable ? 'De nouveau dispo' : 'Indisponible'} accessibilityLabel={`${item.unavailable ? 'De nouveau dispo' : 'Indisponible'} : ${item.name}`}
          loading={busy && !asking} disabled={busy} onPress={() => onAct(item.unavailable ? 'available' : 'unavailable')} /> : null}
        {rights.prices ? <Button small variant="ghost" label="Prix" accessibilityLabel={`Prix : ${item.name}`} disabled={busy}
          onPress={() => onAsk(asking === 'price' ? null : { item: item.id, action: 'price' })} /> : null}
        {rights.items ? <Button small variant="ghost" label="Modifier" accessibilityLabel={`Modifier ${item.name}`} disabled={busy} onPress={onEdit} /> : null}
      </View>
      {asking ? (
        <View style={[s.row, { alignItems: 'flex-end' }]}>
          <View style={{ flex: 1 }}>
            <Field label={`${ASK_LABEL[asking]} · ${item.name}`} value={value} onChangeText={setValue} autoFocus
              inputMode={asking === 'price' ? 'decimal' : 'numeric'} keyboardType={asking === 'price' ? 'decimal-pad' : 'number-pad'}
              placeholder={asking === 'price' ? String(item.price_chf) : asking === 'remaining' ? String(left ?? '') : '12'}
              onSubmitEditing={submit} />
          </View>
          <Button label="OK" loading={busy} onPress={submit} />
        </View>
      ) : null}
    </View>
  );
}

/**
 * « Carte et stock » sur l'écran de service (barman, organisateur) : il en reste, réassort, indisponible / de nouveau
 * dispo, prix, articles — chaque geste selon les droits donnés par l'organisateur, vérifiés par la base, notés au journal.
 */
export function StockPanel({ eventId }: { eventId: string }) {
  const { data, error: loadError, reload } = useQuery(() => barStaffItems(eventId), [eventId]);
  const [open, setOpen] = useState(false);
  const [ask, setAsk] = useState<Ask>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<BarItem | 'new' | null>(null);
  const terms = useTermsGate();
  const rights = data?.rights;
  if (!rights || !(rights.adjust_stock || rights.unavailable || rights.prices || rights.items)) {
    return loadError && open ? <ErrorText error={loadError} /> : null;
  }

  async function act(item: BarItem, action: ItemAction, amount?: number) {
    setBusy(item.id);
    setError(null);
    try {
      const next = await barItemAction(eventId, item.id, action, amount ?? null);
      setNotice(`${item.name} : ${stockLogText({ at: '', actor: null, item: item.name, kind: ACTION_KIND[action], qty: amount ?? null, amount: amount ?? null })}.`);
      setAsk(null);
      if (next) void reload();
    } catch (e) {
      setError(errorText(e, 'Le changement n’a pas pu être enregistré. Réessaie.'));
    } finally {
      setBusy(null);
    }
  }

  async function save(input: ItemInput): Promise<boolean> {
    setError(null);
    try {
      try {
        await barSaveItem(eventId, input);
      } catch (e) {
        if (!(errorCode(e) === 'terms_required' && (await terms.ensure()))) throw e;
        await barSaveItem(eventId, input);
      }
      setEditing(null);
      void reload();
      return true;
    } catch (e) {
      setError(errorText(e, 'L’article n’a pas pu être enregistré. Réessaie.'));
      return false;
    }
  }

  return (
    <Section title="Carte et stock" right={<Button small variant="ghost" label={open ? 'Fermer' : 'Ouvrir'}
      accessibilityLabel={open ? 'Fermer la carte et le stock' : 'Ouvrir la carte et le stock'} onPress={() => setOpen(!open)} />}>
      {open ? (
        <>
          <T muted size={13}>Compte ce qu’il reste, réassortis, ou marque un article indisponible : les invités le voient tout de suite.</T>
          {notice ? <T size={14} weight="semibold" color={colors.mint}>{notice}</T> : null}
          {(data?.items ?? []).filter((i) => i.active).map((item) => (
            <StockRow key={item.id} item={item} rights={rights} busy={busy === item.id} ask={ask} onAsk={setAsk}
              onAct={(action, amount) => void act(item, action, amount)} onEdit={() => setEditing(item)} />
          ))}
          <ErrorText error={error} />
          {rights.items && editing ? (
            <ItemForm key={editing === 'new' ? 'new' : editing.id} item={editing === 'new' ? undefined : editing}
              onCancel={() => setEditing(null)} onSave={save} />
          ) : null}
          {rights.items && !editing ? <Button variant="secondary" label="+ Ajouter un article" onPress={() => setEditing('new')} /> : null}
          {terms.sheet}
        </>
      ) : <T muted size={13}>Il en reste, réassort, indisponible{rights.prices ? ', prix' : ''}.</T>}
    </Section>
  );
}

const ACTION_KIND: Record<ItemAction, string> = {
  remaining: 'stock_set', restock: 'restock', unavailable: 'unavailable', available: 'available', price: 'price_set',
};

const st = StyleSheet.create({
  row: { gap: 8, padding: 10, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  off: { opacity: 0.75, borderStyle: 'dashed' },
  head: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  tile: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
});
