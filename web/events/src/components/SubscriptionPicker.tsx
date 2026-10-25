import { useRef, useState } from 'react';
import { View } from 'react-native';

import { Button, Chip, ErrorText, s, T } from '@/components/ui';
import { useMe } from '@/lib/auth';
import { fetchTaxonomy, useQuery } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';

type Kind = 'tag' | 'category';

/** Catégories et tags suivis : servent aux alertes « Selon mes abonnements » et au filtre de la liste des événements. */
export function SubscriptionPicker({ disabled = false }: { disabled?: boolean }) {
  const me = useMe();
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const { data, error, setData, reload } = useQuery(async () => {
    const [taxonomy, tags, cats] = await Promise.all([
      fetchTaxonomy(),
      supabase.from('tag_subscriptions').select('tag_id').eq('user_id', me.id),
      supabase.from('category_subscriptions').select('category_id').eq('user_id', me.id),
    ]);
    return {
      ...taxonomy,
      tagIds: new Set(must(tags).map((r) => r.tag_id as string)),
      categoryIds: new Set(must(cats).map((r) => r.category_id as string)),
    };
  }, [me.id]);

  if (!data) return error
    ? <><ErrorText error={error} /><Button label="Réessayer" small variant="secondary" onPress={reload} /></>
    : <T muted size={13}>Chargement des catégories et des tags…</T>;

  // Le choix s'affiche une fois enregistré pour ne pas annoncer un faux succès.
  async function toggle(kind: Kind, id: string) {
    if (!data || savingRef.current) return;
    const isTag = kind === 'tag';
    const next = new Set(isTag ? data.tagIds : data.categoryIds);
    const on = next.has(id);
    if (on) next.delete(id);
    else next.add(id);
    const table = isTag ? 'tag_subscriptions' : 'category_subscriptions';
    const col = isTag ? 'tag_id' : 'category_id';
    savingRef.current = true;
    setSaving(true);
    setSaveError(null);
    try {
      const { error } = on
        ? await supabase.from(table).delete().eq('user_id', me.id).eq(col, id)
        : await supabase.from(table).insert({ user_id: me.id, [col]: id });
      if (error) throw error;
      setData({ ...data, ...(isTag ? { tagIds: next } : { categoryIds: next }) });
    } catch {
      setSaveError('Ton choix n’a pas été enregistré. Vérifie ta connexion et réessaie.');
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  const locked = disabled || saving;
  const count = data.categoryIds.size + data.tagIds.size;
  return (
    <View style={{ gap: 10 }}>
      <ErrorText error={saveError} />
      <T weight="semibold">Catégories suivies</T>
      <View style={s.wrap}>
        {data.categories.map((c) => (
          <Chip key={c.id} label={c.name} color={c.color} selected={data.categoryIds.has(c.id)} disabled={locked} onPress={() => toggle('category', c.id)} />
        ))}
      </View>
      <T weight="semibold">Tags suivis</T>
      <View style={s.wrap}>
        {data.tags.map((t) => (
          <Chip key={t.id} label={`#${t.name}`} color={t.color} selected={data.tagIds.has(t.id)} disabled={locked} onPress={() => toggle('tag', t.id)} />
        ))}
      </View>
      <T muted size={13}>{saving ? 'Enregistrement…' : count === 0
        ? 'Tu ne suis encore rien : touche une catégorie ou un tag pour le suivre.'
        : `Tu suis ${count} ${count > 1 ? 'sujets' : 'sujet'}. Un événement qui a au moins une de ces catégories OU un de ces tags compte comme « abonnement ».`}</T>
    </View>
  );
}
