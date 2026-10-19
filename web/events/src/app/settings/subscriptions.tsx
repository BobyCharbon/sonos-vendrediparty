import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { Button, Chip, ErrorText, Screen, s, Section, T } from '@/components/ui';
import { useMe } from '@/lib/auth';
import { fetchTaxonomy, useQuery } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';
import type { NewEventScope } from '@/lib/types';

const scopeHint: Record<NewEventScope, string> = {
  all: 'Tu es prévenu de TOUS les nouveaux événements. Tes abonnements servent au filtre « Mes abonnements ».',
  subscribed: 'Tu es prévenu seulement des nouveaux événements qui ont une de tes catégories ou un de tes tags.',
  none: 'Tu n’es prévenu d’aucun nouvel événement. Les annonces admin restent actives.',
};

export default function Subscriptions() {
  const me = useMe();
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const { data, error, setData, reload } = useQuery(async () => {
    const [taxonomy, tags, cats, prefs] = await Promise.all([
      fetchTaxonomy(),
      supabase.from('tag_subscriptions').select('tag_id').eq('user_id', me.id),
      supabase.from('category_subscriptions').select('category_id').eq('user_id', me.id),
      supabase.from('notification_prefs').select('new_event').eq('user_id', me.id).single(),
    ]);
    return {
      ...taxonomy,
      tagIds: new Set(must(tags).map((r) => r.tag_id as string)),
      categoryIds: new Set(must(cats).map((r) => r.category_id as string)),
      scope: (must(prefs) as { new_event: NewEventScope }).new_event,
    };
  }, [me.id]);

  if (!data) return (
    <Screen edges={[]}>
      {error ? <><ErrorText error={error} /><Button label="Réessayer" onPress={reload} /></> : <T muted>Chargement des abonnements…</T>}
    </Screen>
  );

  async function save(operation: () => PromiseLike<{ error: { message: string } | null }>, onSuccess: () => void) {
    if (savingRef.current) return;
    savingRef.current = true;
    setSaving(true);
    setSaveError(null);
    try {
      const { error } = await operation();
      if (error) throw error;
      onSuccess();
    } catch {
      setSaveError('Tes préférences n’ont pas été enregistrées. Vérifie ta connexion et réessaie.');
    } finally {
      savingRef.current = false;
      setSaving(false);
    }
  }

  // Le choix s'affiche une fois enregistré pour ne pas annoncer un faux succès.
  async function toggle(kind: 'tag' | 'category', id: string) {
    if (!data) return;
    const isTag = kind === 'tag';
    const set = new Set(isTag ? data.tagIds : data.categoryIds);
    const on = set.has(id);
    if (on) set.delete(id);
    else set.add(id);
    const table = isTag ? 'tag_subscriptions' : 'category_subscriptions';
    const col = isTag ? 'tag_id' : 'category_id';
    await save(
      () => on ? supabase.from(table).delete().eq('user_id', me.id).eq(col, id) : supabase.from(table).insert({ user_id: me.id, [col]: id }),
      () => setData({ ...data, ...(isTag ? { tagIds: set } : { categoryIds: set }) }),
    );
  }

  async function setScope(scope: NewEventScope) {
    if (!data) return;
    await save(
      () => supabase.from('notification_prefs').update({ new_event: scope }).eq('user_id', me.id),
      () => setData({ ...data, scope }),
    );
  }

  return (
    <Screen edges={[]}>
      <T muted>Abonne-toi aux catégories et aux tags qui t’intéressent.</T>
      <T muted size={13}>En mode « Mes abonnements », une catégorie OU un tag suffit. Les annonces admin concernent toujours tout le groupe.</T>
      <ErrorText error={saveError ?? error} />
      {saving ? <T muted size={13}>Enregistrement…</T> : null}

      <Section title="Catégories">
        <View style={s.wrap}>
          {data.categories.map((c) => (
            <Chip key={c.id} label={c.name} color={c.color} selected={data.categoryIds.has(c.id)} disabled={saving} onPress={() => toggle('category', c.id)} />
          ))}
        </View>
      </Section>

      <Section title="Tags">
        <View style={s.wrap}>
          {data.tags.map((t) => (
            <Chip key={t.id} label={`#${t.name}`} color={t.color} selected={data.tagIds.has(t.id)} disabled={saving} onPress={() => toggle('tag', t.id)} />
          ))}
        </View>
      </Section>

      <Section title="Me prévenir des nouveaux événements">
        <View style={s.wrap}>
          <Chip label="Tous" selected={data.scope === 'all'} disabled={saving} onPress={() => setScope('all')} />
          <Chip label="Mes abonnements seulement" selected={data.scope === 'subscribed'} disabled={saving} onPress={() => setScope('subscribed')} />
          <Chip label="Jamais" selected={data.scope === 'none'} disabled={saving} onPress={() => setScope('none')} />
        </View>
        <T muted size={13}>{scopeHint[data.scope]}</T>
      </Section>
      <Button variant="secondary" label="Autres réglages de notifications" onPress={() => router.push('/settings/notifications')} />
    </Screen>
  );
}
