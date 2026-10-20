import { Redirect } from 'expo-router';
import { useRef, useState } from 'react';
import { Pressable, View } from 'react-native';

import { Button, ErrorText, Input, Screen, s, Section, T } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { fetchTaxonomy, useQuery } from '@/lib/data';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

const palette = ['#FF7A59', '#D4F24A', '#F2C14A', '#7AD3C8', '#7AA7FF', '#B9A7FF', '#FF9ECF'];

type Kind = 'categories' | 'tags';
type Item = { id: string; name: string; color: string; archived: boolean };

function Editor({ kind, items, onChange }: { kind: Kind; items: Item[]; onChange: () => void }) {
  const [name, setName] = useState('');
  const [color, setColor] = useState(palette[0]!);
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const saving = useRef(false);

  async function run(operation: () => PromiseLike<{ error: { message: string } | null }>, onSuccess?: () => void) {
    if (saving.current) return;
    saving.current = true;
    setBusy(true);
    setError(null);
    try {
      const { error } = await operation();
      if (error) throw error;
      onSuccess?.();
      await onChange();
    } catch (error) {
      const message = error && typeof error === 'object' && 'message' in error ? String(error.message) : '';
      setError(message.includes('duplicate') ? 'Ce nom existe déjà.' : 'La modification n’a pas été enregistrée. Réessaie.');
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  const clean = (v: string) => (kind === 'tags' ? v.trim().replace(/^#/, '').toLowerCase() : v.trim());

  return (
    <>
      {items.map((it) => (
        <View key={it.id} style={[s.row, { opacity: it.archived ? 0.5 : 1 }]}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={`Changer la couleur de ${it.name}`}
            disabled={busy}
            onPress={() => run(() => supabase.from(kind).update({ color: palette[(palette.indexOf(it.color) + 1) % palette.length] }).eq('id', it.id))}
            style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }}
          >
            <View style={{ width: 28, height: 28, borderRadius: 14, backgroundColor: it.color }} />
          </Pressable>
          {editing === it.id ? (
            <>
              <Input accessibilityLabel={`Nouveau nom de ${it.name}`} value={editName} onChangeText={setEditName} maxLength={kind === 'tags' ? 40 : 60} style={{ flex: 1 }} autoFocus />
              <Button small label="OK" disabled={busy || !clean(editName)} onPress={() => run(() => supabase.from(kind).update({ name: clean(editName) }).eq('id', it.id), () => setEditing(null))} />
            </>
          ) : (
            <>
              <Pressable style={{ flex: 1 }} onPress={() => { setEditing(it.id); setEditName(it.name); }} accessibilityRole="button" accessibilityHint="Renommer">
                <T>{kind === 'tags' ? `#${it.name}` : it.name}{it.archived ? ' (archivé)' : ''}</T>
              </Pressable>
              <Button small variant="ghost" disabled={busy} label={it.archived ? 'Restaurer' : 'Archiver'} onPress={() => run(() => supabase.from(kind).update({ archived: !it.archived }).eq('id', it.id))} />
            </>
          )}
        </View>
      ))}
      <View style={s.wrap}>
        {palette.map((c) => (
          <Pressable
            key={c}
            accessibilityRole="button"
            accessibilityState={{ selected: c === color }}
            accessibilityLabel={`Couleur ${c}`}
            onPress={() => setColor(c)}
            style={{ width: 44, height: 44, alignItems: 'center', justifyContent: 'center' }}
          >
            <View style={{ width: 32, height: 32, borderRadius: 16, backgroundColor: c, borderWidth: 3, borderColor: c === color ? colors.text : 'transparent' }} />
          </Pressable>
        ))}
      </View>
      <View style={s.row}>
        <Input accessibilityLabel={kind === 'tags' ? 'Nouveau tag' : 'Nouvelle catégorie'} placeholder={kind === 'tags' ? 'Nouveau tag (ex. bar)' : 'Nouvelle catégorie'} value={name} onChangeText={setName} maxLength={kind === 'tags' ? 40 : 60} style={{ flex: 1 }} />
        <Button
          small
          label="Ajouter"
          disabled={busy || !clean(name)}
          onPress={() => {
            run(() => supabase.from(kind).insert({ name: clean(name), color, ...(kind === 'categories' ? { sort: items.length + 1 } : {}) }), () => setName(''));
          }}
        />
      </View>
      <ErrorText error={error} />
    </>
  );
}

export default function Taxonomy() {
  const { can } = useAuth();
  const isAdmin = can('taxonomy.manage');
  const { data, error, reload } = useQuery(() => fetchTaxonomy(true), []);
  if (!isAdmin) return <Redirect href="/" />;
  return (
    <Screen edges={[]}>
      <T muted size={13}>
        Un événement a une seule catégorie et plusieurs tags. Les membres s’abonnent aux deux. Archiver masque l’élément sans toucher aux événements existants.
      </T>
      <ErrorText error={error} />
      {error ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}
      {!data && !error ? <T muted>Chargement des catégories et des tags…</T> : null}
      <Section title="Catégories">{data ? <Editor kind="categories" items={data.categories} onChange={reload} /> : null}</Section>
      <Section title="Tags">{data ? <Editor kind="tags" items={data.tags} onChange={reload} /> : null}</Section>
    </Screen>
  );
}
