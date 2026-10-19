import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { EventCard } from '@/components/EventCard';
import { Button, Chip, Empty, ErrorText, Input, s, Segmented, T, Title } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { fetchEventList, fetchTaxonomy, useQuery } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';
import { colors, fonts, radius } from '@/lib/theme';

type Tab = 'upcoming' | 'polls' | 'mine' | 'past';
type Filter = { kind: 'all' } | { kind: 'subscribed' } | { kind: 'category'; id: string } | { kind: 'tag'; id: string };

export default function Home() {
  const me = useMe();
  const { isAdmin } = useAuth();
  const [tab, setTab] = useState<Tab>('upcoming');
  const [filter, setFilter] = useState<Filter>({ kind: 'all' });
  const [search, setSearch] = useState('');

  const { data, error, loading, reload } = useQuery(async () => {
    const [events, taxonomy, tagSubs, catSubs] = await Promise.all([
      fetchEventList(),
      fetchTaxonomy(),
      supabase.from('tag_subscriptions').select('tag_id').eq('user_id', me.id),
      supabase.from('category_subscriptions').select('category_id').eq('user_id', me.id),
    ]);
    return {
      events,
      loadedAt: Date.now(),
      ...taxonomy,
      subscribedTags: new Set(must(tagSubs).map((r) => r.tag_id as string)),
      subscribedCategories: new Set(must(catSubs).map((r) => r.category_id as string)),
    };
  }, [me.id]);

  const tagsById = useMemo(() => new Map((data?.tags ?? []).map((t) => [t.id, t])), [data?.tags]);

  const visible = useMemo(() => {
    if (!data) return [];
    const now = data.loadedAt - 6 * 3600_000; // un événement reste « à venir » 6 h après son début
    return data.events
      .filter((e) => {
        const started = e.starts_at ? new Date(e.starts_at).getTime() : null;
        switch (tab) {
          case 'upcoming':
            return e.status === 'published' && e.date_mode === 'fixed' && started !== null && started >= now;
          case 'polls':
            return e.status === 'published' && e.date_mode === 'poll';
          case 'mine':
            return e.created_by === me.id && e.status !== 'published';
          case 'past':
            return (e.status === 'published' || e.status === 'cancelled') && started !== null && started < now;
        }
      })
      .filter((e) => {
        const query = search.trim().toLocaleLowerCase('fr');
        if (!query) return true;
        const tagNames = e.event_tags.map(({ tag_id }) => tagsById.get(tag_id)?.name ?? '');
        return [e.title, e.description, e.location_name, e.category?.name, ...tagNames]
          .filter(Boolean).join(' ').toLocaleLowerCase('fr').includes(query);
      })
      .filter((e) => {
        switch (filter.kind) {
          case 'all':
            return true;
          case 'subscribed':
            return (
              (e.category_id && data.subscribedCategories.has(e.category_id)) ||
              e.event_tags.some((t) => data.subscribedTags.has(t.tag_id))
            );
          case 'category':
            return e.category_id === filter.id;
          case 'tag':
            return e.event_tags.some((t) => t.tag_id === filter.id);
        }
      })
      .sort((a, b) => (tab === 'past' ? (b.starts_at ?? '').localeCompare(a.starts_at ?? '') : 0));
  }, [data, tab, filter, search, tagsById, me.id]);

  const pendingCount = data?.events.filter((e) => e.status === 'pending').length ?? 0;
  const isSel = (f: Filter) => JSON.stringify(f) === JSON.stringify(filter);

  return (
    <SafeAreaView style={s.screen} edges={['top']}>
      <ScrollView
        style={{ flex: 1, minHeight: 0 }}
        contentContainerStyle={[s.content, { paddingBottom: 24 }]}
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={reload} tintColor={colors.accent} />}
      >
        <View style={s.rowBetween}>
          <View style={{ flex: 1, minWidth: 0 }}>
            <Title size={28}>
              Les sorties du groupe
            </Title>
            <T muted size={13}>Salut {me.display_name} !</T>
          </View>
        </View>

        <Input
          accessibilityLabel="Rechercher un événement"
          placeholder="Rechercher une sortie, un lieu, un tag…"
          value={search}
          onChangeText={setSearch}
          returnKeyType="search"
        />

        <Segmented<Tab>
          value={tab}
          onChange={setTab}
          options={[
            { key: 'upcoming', label: 'À venir' },
            { key: 'polls', label: 'Sondages' },
            { key: 'mine', label: 'Propositions' },
            { key: 'past', label: 'Passés' },
          ]}
        />

        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
          <Chip label="Tout" selected={isSel({ kind: 'all' })} onPress={() => setFilter({ kind: 'all' })} />
          <Chip label="Mes abonnements" selected={isSel({ kind: 'subscribed' })} onPress={() => setFilter({ kind: 'subscribed' })} />
          {data?.categories.map((c) => (
            <Chip
              key={c.id}
              label={c.name}
              color={c.color}
              selected={isSel({ kind: 'category', id: c.id })}
              onPress={() => setFilter({ kind: 'category', id: c.id })}
            />
          ))}
        </ScrollView>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 6 }}>
          {data?.tags.map((t) => (
            <Chip
              key={t.id}
              label={`#${t.name}`}
              color={t.color}
              selected={isSel({ kind: 'tag', id: t.id })}
              onPress={() => setFilter(isSel({ kind: 'tag', id: t.id }) ? { kind: 'all' } : { kind: 'tag', id: t.id })}
            />
          ))}
        </ScrollView>

        {isAdmin && pendingCount > 0 ? (
          <Pressable
            accessibilityRole="link"
            onPress={() => router.push('/admin')}
            style={{ backgroundColor: colors.lavenderDim, padding: 14, borderRadius: radius.md }}
          >
            <T size={14}>
              <T weight="bold" size={14}>{pendingCount} proposition(s)</T> attendent ta validation ›
            </T>
          </Pressable>
        ) : null}

        <ErrorText error={error} />
        {error ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}
        {loading && !data ? <T muted>Chargement des événements…</T> : null}
        {data && visible.length === 0 ? (
          <View style={{ gap: 8, paddingVertical: 20 }}>
            <Empty>
              {search.trim() ? 'Aucun événement ne correspond à ta recherche.'
                : filter.kind === 'subscribed' ? 'Aucune sortie pour tes abonnements pour le moment.'
                : filter.kind !== 'all' ? 'Aucun événement avec ce filtre pour le moment.'
                : tab === 'mine' ? 'Tes brouillons et propositions en attente apparaîtront ici.'
                : tab === 'polls' ? 'Aucune date à choisir pour le moment.'
                : tab === 'past' ? 'Les sorties passées apparaîtront ici.'
                : 'Le groupe attend sa première sortie. Lance une idée !'}
            </Empty>
            {filter.kind === 'subscribed' ? (
              <Button label="Choisir mes abonnements" variant="secondary" onPress={() => router.push('/settings/subscriptions')} />
            ) : null}
            {search.trim() || filter.kind !== 'all' ? (
              <Button label="Effacer la recherche et les filtres" variant="ghost" onPress={() => { setSearch(''); setFilter({ kind: 'all' }); }} />
            ) : null}
          </View>
        ) : null}
        {visible.map((e) => (
          <EventCard key={e.id} event={e} me={me.id} tagsById={tagsById} />
        ))}
      </ScrollView>

      <Pressable
        accessibilityRole="button"
        accessibilityLabel="Proposer un événement"
        onPress={() => router.push('/event/new')}
        style={{
          alignSelf: 'flex-end', marginHorizontal: 16, marginTop: 8, marginBottom: 12,
          height: 52, paddingHorizontal: 22, borderRadius: radius.md,
          backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center',
        }}
      >
        <T color={colors.onAccent} style={{ fontFamily: fonts.bold, fontSize: 15 }}>+ Proposer</T>
      </Pressable>
    </SafeAreaView>
  );
}
