import { useState } from 'react';
import { View } from 'react-native';

import { draftOf, parseItemDraft, type AgeMin, type BarItem, type ItemDraft, type ItemInput } from '@/lib/bar';

import { Button, Chip, ErrorText, Field, s, Section, T, ToggleRow } from '../ui';

const AGES: { key: AgeMin; label: string }[] = [{ key: 0, label: 'Aucun' }, { key: 16, label: '16+' }, { key: 18, label: '18+' }];

/** Ajouter ou modifier un article : nom, emoji, prix, stock (vide = illimité), maximum en attente (vide = sans limite), âge. */
export function ItemForm({ item, onSave, onCancel }: {
  item?: BarItem;
  /** true : enregistré (le formulaire se ferme). */
  onSave: (input: ItemInput) => Promise<boolean>;
  onCancel: () => void;
}) {
  const [draft, setDraft] = useState<ItemDraft>(() => draftOf(item));
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const set = (patch: Partial<ItemDraft>) => setDraft((d) => ({ ...d, ...patch }));

  async function submit() {
    const parsed = parseItemDraft(draft, item?.id);
    if ('error' in parsed) return setError(parsed.error);
    setError(null);
    setBusy(true);
    try {
      await onSave(parsed.input);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Section title={item ? `Modifier · ${item.name}` : 'Nouvel article'}>
      <Field label="Nom" value={draft.name} onChangeText={(name) => set({ name })} maxLength={40} placeholder="Vodka Red Bull" />
      <View style={[s.row, { alignItems: 'flex-start' }]}>
        <View style={{ width: 96 }}>
          <Field label="Emoji" value={draft.emoji} onChangeText={(emoji) => set({ emoji })} placeholder="🍸" />
        </View>
        <View style={{ flex: 1 }}>
          <Field label="Prix (CHF)" value={draft.price} onChangeText={(price) => set({ price })} inputMode="decimal" keyboardType="decimal-pad" placeholder="4.50" />
        </View>
      </View>
      <Field label="Stock acheté" hint="Vide = illimité." value={draft.stock} onChangeText={(stock) => set({ stock })}
        inputMode="numeric" keyboardType="number-pad" placeholder="Illimité" />
      <Field label="Maximum en attente par personne" hint="Commandés, pas encore servis. Dès qu’un verre est servi, on peut en recommander un. Vide = sans limite."
        value={draft.maxPending} onChangeText={(maxPending) => set({ maxPending })} inputMode="numeric" keyboardType="number-pad" placeholder="Sans limite" />
      <View style={{ gap: 6 }}>
        <T muted size={13} weight="medium">Âge minimum</T>
        <View style={s.wrap}>
          {AGES.map((a) => <Chip key={a.key} label={a.label} selected={draft.age === a.key} onPress={() => set({ age: a.key })} />)}
        </View>
      </View>
      {item ? (
        <ToggleRow label="Proposé aux invités" hint="Éteint : l’article disparaît de la carte (ce qui est commandé reste)."
          value={draft.active} onChange={(active) => set({ active })} />
      ) : null}
      <ErrorText error={error} />
      <View style={s.row}>
        <Button variant="secondary" label="Annuler" style={{ flex: 1 }} onPress={onCancel} />
        <Button label={item ? 'Enregistrer' : 'Ajouter l’article'} loading={busy} style={{ flex: 1 }} onPress={() => void submit()} />
      </View>
    </Section>
  );
}
