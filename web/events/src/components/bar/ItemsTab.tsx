import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { barChf, barSaveItem, errorCode, errorText, type BarItem, type BarOverview, type ItemInput } from '@/lib/bar';
import { colors, radius } from '@/lib/theme';

import { useTermsGate } from '../TermsSheet';
import { Badge, Button, ErrorText, Section, T } from '../ui';
import { BarHours } from './BarHours';
import { ItemForm } from './ItemForm';
import { Stepper } from './Stepper';

/** Une ligne : prix, âge, maximum ; le chiffre du stepper = ce qu'il reste (stock − servis − réservés). */
function ItemRow({ item, busy, onEdit, onStock }: { item: BarItem; busy: boolean; onEdit: () => void; onStock: (stock: number) => void }) {
  const meta = [barChf(item.price_chf), item.max_pending != null ? `max ${item.max_pending}` : null, item.active ? null : 'retiré de la carte']
    .filter(Boolean).join(' · ');
  const left = item.available ?? 0;
  return (
    <View style={st.row}>
      <Pressable accessibilityRole="button" accessibilityLabel={`Modifier ${item.name}`} onPress={onEdit}
        style={({ pressed }) => [st.main, pressed && { opacity: 0.7 }]}>
        <View style={st.tile}><Text style={{ fontSize: 20 }}>{item.emoji || '🍹'}</Text></View>
        <View style={{ flex: 1, minWidth: 0, gap: 2 }}>
          <T weight="semibold" size={15} numberOfLines={2} color={item.active ? colors.text : colors.muted}>{item.name}</T>
          <View style={st.meta}>
            <T muted size={12}>{meta}</T>
            {item.age_min ? <Badge label={`${item.age_min}+`} fg={colors.onCoral} bg={colors.coral} /> : null}
          </View>
          <T size={12} weight="semibold" color={colors.accent}>Modifier ›</T>
        </View>
      </Pressable>
      {item.stock == null ? <Badge label="Illimité" fg={colors.onAccent} bg={colors.lavender} />
        : <Stepper label={`stock de ${item.name}`} value={left} min={left - item.stock} disabled={busy}
            onChange={(n) => onStock(item.stock! + (n - left))} />}
    </View>
  );
}

/** Onglet « Articles » : ouverture des commandes, précommande, fermeture ; la carte ; ajouter / modifier un article. */
export function ItemsTab({ eventId, overview, onOverview, reload }: {
  eventId: string; overview: BarOverview; onOverview: (o: BarOverview) => void; reload: () => void;
}) {
  const [editing, setEditing] = useState<BarItem | 'new' | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [warning, setWarning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // Nom d'article : contenu vu des invités (base : require_terms) → CGU d'abord, puis un seul nouvel essai.
  const terms = useTermsGate();

  async function save(input: ItemInput): Promise<boolean> {
    setError(null);
    setBusy(input.id ?? 'new');
    try {
      let saved;
      try {
        saved = await barSaveItem(eventId, input);
      } catch (e) {
        if (!(errorCode(e) === 'terms_required' && (await terms.ensure()))) throw e;
        saved = await barSaveItem(eventId, input);
      }
      setWarning(saved.overbooked > 0 ? `« ${saved.name} » surréservé de ${saved.overbooked} : annule des réservations dans Direct.` : null);
      reload();
      return true;
    } catch (e) {
      setError(errorCode(e) === 'terms_required' ? 'Accepte les conditions d’utilisation pour enregistrer un article.'
        : errorText(e, 'L’article n’a pas pu être enregistré. Réessaie.'));
      return false;
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <BarHours key={`${overview.closes_at}|${overview.preorder_until}`} eventId={eventId} overview={overview} onOverview={onOverview} />
      {warning ? <T size={14} weight="semibold" color={colors.coral} style={st.warn}>{warning}</T> : null}
      <Section title="Articles">
        {overview.items.length === 0 ? <T muted size={14}>Pas encore d’article : ajoute ce que tu as acheté.</T> : null}
        {overview.items.map((item) => (
          <ItemRow key={item.id} item={item} busy={busy === item.id} onEdit={() => setEditing(item)}
            onStock={(stock) => void save({ id: item.id, name: item.name, emoji: item.emoji, stock: Math.max(0, stock) })} />
        ))}
        {overview.items.length ? <T muted size={12}>Le chiffre = ce qu’il reste. « max 3 » = 3 en attente au plus par personne.</T> : null}
      </Section>
      <ErrorText error={error} />
      {editing ? (
        <ItemForm key={editing === 'new' ? 'new' : editing.id} item={editing === 'new' ? undefined : editing} onCancel={() => setEditing(null)}
          onSave={async (input) => {
            const ok = await save(input);
            if (ok) setEditing(null);
            return ok;
          }} />
      ) : (
        <Button variant="secondary" label="+ Ajouter un article" onPress={() => setEditing('new')} />
      )}
      {terms.sheet}
    </>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  main: { flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 44, minWidth: 0 },
  tile: { width: 44, height: 44, borderRadius: radius.sm, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
  meta: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  warn: { padding: 12, borderRadius: radius.md, backgroundColor: colors.coralDim },
});
