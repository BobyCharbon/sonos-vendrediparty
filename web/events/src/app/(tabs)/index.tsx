import { router } from 'expo-router';
import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, RefreshControl, ScrollView, StyleSheet, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { EventCard } from '@/components/EventCard';
import { SignedIn } from '@/components/SignedIn';
import { HomeHeader, HomePills } from '@/components/HomeHeader';
import { Button, Chip, Empty, ErrorText, Input, Reveal, s, Skeleton, T } from '@/components/ui';
import { useImportantUnread } from '@/lib/activityBadge';
import { useAuth, useMe } from '@/lib/auth';
import { type Attendance, fetchAttendance } from '@/lib/attendance';
import { inTab, type ListTab } from '@/lib/eventTime';
import { fetchEventList, fetchTaxonomy, needsAnswer, useQuery, useRealtime } from '@/lib/data';
import { plural } from '@/lib/format';
import { must, supabase } from '@/lib/supabase';
import { duration, ease, enter, pressTransition, transition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

type Tab = ListTab;
type PillKey = Exclude<Tab, 'pending'> | 'filters';
type Filter = { kind: 'all' } | { kind: 'subscribed' } | { kind: 'category'; id: string } | { kind: 'tag'; id: string };

export default function Home() {
  const me = useMe();
  const { can } = useAuth();
  const isAdmin = can('events.approve');
  // App iPhone et droit « Utiliser l'assistant IA » : l'événement se décrit à voix haute dans un écran natif.
  const native = (globalThis as { PartyNative?: { ai?: { createEvent?: () => void } } }).PartyNative;
  // « + Proposer » seulement avec le droit de créer (campagne des bots : Membres et Guests remplissaient tout pour rien).
  const canPropose = can('events.create');
  const aiEvent = can('ai.use') && can('events.create') && native?.ai?.createEvent ? () => native.ai!.createEvent!() : null;
  const [tab, setTab] = useState<Tab>('upcoming');
  const [filter, setFilter] = useState<Filter>({ kind: 'all' });
  const [search, setSearch] = useState('');
  const [searchOpen, setSearchOpen] = useState(false);
  const [filtersOpen, setFiltersOpen] = useState(false);
  // « + Proposer » s’efface en descendant dans la liste et revient dès qu’on remonte (comme Mail ou Photos).
  const [fabAway, setFabAway] = useState(false);
  const lastY = useRef(0);

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
  // Temps réel (retour du 08.11) : ajouté à un groupe, invité, événement publié ou modifié → la liste suit sans recharger.
  useRealtime('events-list', [
    { table: 'events' },
    { table: 'event_invites', filter: `user_id=eq.${me.id}` },
    { table: 'member_group_members', filter: `user_id=eq.${me.id}` },
    { table: 'event_groups' },
    { table: 'rsvps', filter: `user_id=eq.${me.id}` },
  ], reload);

  // Pastille des présents : totaux exacts même quand la liste des participants est cachée. Lue APRÈS l'affichage des cartes
  // (avant : une étape réseau de plus avant la première carte) ; les cartes comptent les réponses en attendant.
  const eventIds = (data?.events ?? []).map((e) => e.id).join(',');
  const [attendance, setAttendance] = useState<Map<string, Attendance>>(new Map());
  useEffect(() => {
    let current = true;
    if (eventIds) void fetchAttendance(eventIds.split(',')).then((a) => { if (current) setAttendance(a); });
    return () => { current = false; };
  }, [eventIds, data?.loadedAt]);

  const tagsById = useMemo(() => new Map((data?.tags ?? []).map((t) => [t.id, t])), [data?.tags]);

  const visible = useMemo(() => {
    if (!data) return [];
    return data.events
      // « Brouillons » range aussi mes propositions en attente de validation (plus d'onglet « En attente »).
      .filter((e) => inTab(e, tab, me.id, data.loadedAt) || (tab === 'drafts' && inTab(e, 'pending', me.id, data.loadedAt)))
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

  // « À venir » : d’abord les sorties où tu es présent, puis les autres par date.
  const awaiting = (e: (typeof visible)[number]) => !!data && needsAnswer(e, me.id, data.loadedAt);
  const going = (e: (typeof visible)[number]) => e.rsvps.some((r) => r.user_id === me.id && r.status === 'yes' && !r.waitlisted);
  const goingList = tab === 'upcoming' ? visible.filter(going) : [];
  const rest = tab === 'upcoming' ? visible.filter((e) => !going(e)) : visible;
  const unvotedPolls = data?.events.filter((e) => e.date_mode === 'poll' && awaiting(e)).length ?? 0;
  // Sondages qui attendent mon vote : bandeau en tête de liste (hors onglet Sondages et pendant une recherche),
  // compte rouge sur « Sondages ».
  const openPolls = tab === 'polls' || !data || search.trim() ? [] : data.events.filter((e) => e.date_mode === 'poll' && awaiting(e));
  const pollBanner = openPolls.length === 0 ? null : openPolls.length === 1
    ? { only: openPolls[0].id, title: `Nouveau sondage : ${openPolls[0].title}`, body: 'Choisis les dates qui t’arrangent.',
      label: `Nouveau sondage : ${openPolls[0].title}. Choisis les dates qui t’arrangent. Voter` }
    : { only: null, title: `${openPolls.length} sondages attendent ton vote`, body: openPolls.map((e) => e.title).join(' · '),
      label: `${openPolls.length} sondages attendent ton vote. Voter` };
  const important = useImportantUnread(data?.loadedAt);
  const filterName = filter.kind === 'subscribed' ? 'Mes abonnements'
    : filter.kind === 'category' ? data?.categories.find((c) => c.id === filter.id)?.name
    : filter.kind === 'tag' ? `#${data?.tags.find((t) => t.id === filter.id)?.name ?? ''}` : null;
  const filterLabel = filterName ? `Filtre : ${filterName}` : 'Filtres';
  const isSel = (f: Filter) => JSON.stringify(f) === JSON.stringify(filter);

  return (
    <SafeAreaView style={s.screen} edges={['left', 'right']}>
      <ScrollView
        style={{ flex: 1, minHeight: 0 }}
        contentContainerStyle={[s.content, { paddingBottom: 96 }]}
        refreshControl={<RefreshControl refreshing={loading && !!data} onRefresh={reload} tintColor={colors.accent} />}
        scrollEventThrottle={32}
        onScroll={(e) => {
          const y = e.nativeEvent.contentOffset.y;
          const dy = y - lastY.current;
          if (Math.abs(dy) < FAB_SCROLL_SLOP) return;
          lastY.current = y;
          const away = dy > 0 && y > FAB_SCROLL_START;
          if (away !== fabAway) setFabAway(away);
        }}
      >
        <HomeHeader
          searchOpen={searchOpen}
          onToggleSearch={() => { if (searchOpen) setSearch(''); setSearchOpen(!searchOpen); }}
          important={important}
          onBell={() => router.push('/activity')}
        />

        {searchOpen ? (
          <Input
            accessibilityLabel="Rechercher un événement"
            placeholder="Rechercher un événement, un lieu, un tag…"
            value={search}
            onChangeText={setSearch}
            returnKeyType="search"
            autoFocus
          />
        ) : null}

        <HomePills<PillKey>
          items={[
            { key: 'upcoming', label: 'À venir', selected: tab === 'upcoming' },
            { key: 'polls', label: 'Sondages', count: unvotedPolls, selected: tab === 'polls' },
            { key: 'drafts', label: 'Brouillons', selected: tab === 'drafts' },
            { key: 'past', label: 'Passés', selected: tab === 'past' },
            { key: 'filters', label: filterLabel, selected: filter.kind !== 'all', outline: filtersOpen },
          ]}
          onPress={(k) => (k === 'filters' ? setFiltersOpen(!filtersOpen) : setTab(k))}
        />

        {filtersOpen ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} style={{ marginHorizontal: -16, flexGrow: 0 }} contentContainerStyle={{ gap: 6, paddingHorizontal: 16 }}>
          <Chip label="Tout" selected={isSel({ kind: 'all' })} onPress={() => setFilter({ kind: 'all' })} />
          <Chip label="Mes abonnements" selected={isSel({ kind: 'subscribed' })} onPress={() => setFilter({ kind: 'subscribed' })} />
          {data?.categories.map((c) => (
            <Chip
              key={c.id}
              label={c.name}
              color={c.color}
              selected={isSel({ kind: 'category', id: c.id })}
              onPress={() => setFilter(isSel({ kind: 'category', id: c.id }) ? { kind: 'all' } : { kind: 'category', id: c.id })}
            />
          ))}
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
        ) : null}

        {pollBanner ? (
          <Pressable accessibilityRole="button" testID="poll-banner"
            accessibilityLabel={pollBanner.label}
            onPress={() => (pollBanner.only ? router.push(`/event/${pollBanner.only}`) : setTab('polls'))}
            style={({ pressed }) => [st.banner, enter('drop'), pressTransition, pressed && { opacity: 0.8 }]}>
            <View style={st.bannerIcon}><T size={18}>🗳️</T></View>
            <View style={{ flex: 1, minWidth: 0 }}>
              <T size={15} weight="bold">{pollBanner.title}</T>
              <T size={13} color={colors.textSoft}>{pollBanner.body}</T>
            </View>
            <View style={st.bannerCta}><T size={13} weight="bold" color={colors.onAction}>Voter</T></View>
          </Pressable>
        ) : null}

        {!can('events.view') ? (
          <SignedIn note="Tu vois ici les événements publics et ceux où on t’invite. Les jeux et la musique sont ouverts avec ton compte." />
        ) : null}

        {isAdmin && pendingCount > 0 ? (
          <Pressable
            accessibilityRole="link"
            onPress={() => router.push('/admin')}
            style={{ backgroundColor: colors.lavenderDim, padding: 14, borderRadius: radius.md }}
          >
            <T size={14}>
              <T weight="bold" size={14}>{plural(pendingCount, 'proposition')}</T> {pendingCount > 1 ? 'attendent' : 'attend'} ta validation ›
            </T>
          </Pressable>
        ) : null}

        <ErrorText error={error} />
        {error ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}
        {loading && !data ? <ListSkeleton /> : null}
        {data && visible.length === 0 ? (
          <Reveal kind="fade" style={{ gap: 8, paddingVertical: 20 }}>
            <Empty>
              {search.trim() ? 'Aucun événement ne correspond à ta recherche.'
                : filter.kind === 'subscribed' ? 'Aucun événement pour tes abonnements pour le moment.'
                : filter.kind !== 'all' ? 'Aucun événement avec ce filtre pour le moment.'
                : tab === 'drafts' ? 'Tes brouillons, tes propositions en attente de validation et celles à retravailler apparaîtront ici.'
                : tab === 'polls' ? 'Aucune date à choisir pour le moment.'
                : tab === 'past' ? 'Les événements passés apparaîtront ici.'
                : 'Le groupe attend son premier événement. Lance une idée !'}
            </Empty>
            {filter.kind === 'subscribed' ? (
              <Button label="Choisir mes abonnements" variant="secondary" onPress={() => router.push('/settings/notifications?topics=1')} />
            ) : null}
            {search.trim() || filter.kind !== 'all' ? (
              <Button label="Effacer la recherche et les filtres" variant="ghost" onPress={() => { setSearch(''); setFilter({ kind: 'all' }); }} />
            ) : null}
          </Reveal>
        ) : null}
        {goingList.length ? (
          <View style={{ gap: 10 }}>
            <T size={13} weight="bold" color={colors.mint} style={st.label}>TU Y VAS</T>
            {goingList.map((e, i) => (
              <EventCard key={e.id} index={i} event={e} me={me.id} tagsById={tagsById} onChanged={reload} quickRsvp now={data!.loadedAt} attendance={attendance.get(e.id)} />
            ))}
          </View>
        ) : null}
        {goingList.length && rest.length ? <T size={13} weight="bold" color={colors.muted} style={[st.label, { marginTop: 6 }]}>À VENIR</T> : null}
        {rest.map((e, i) => (
          <EventCard key={e.id} index={goingList.length + i} event={e} me={me.id} tagsById={tagsById} onChanged={reload} quickRsvp={tab === 'polls' || tab === 'upcoming'} now={data!.loadedAt} attendance={attendance.get(e.id)} />
        ))}
      </ScrollView>

      {canPropose || aiEvent ? (
      <View pointerEvents="box-none" style={st.fabWrap}>
        {/* Effacé : hors de l'arbre d'accessibilité aussi (VoiceOver « activer » touchait ce qu'il y a derrière). */}
        <View pointerEvents={fabAway ? 'none' : 'box-none'} aria-hidden={fabAway || undefined} accessibilityElementsHidden={fabAway}
          importantForAccessibility={fabAway ? 'no-hide-descendants' : 'auto'}
          style={[st.fabColumn, transition('transform, opacity', duration.base, ease.out),
          fabAway && { opacity: 0, transform: [{ translateY: 24 }, { scale: 0.9 }] }]}>
        {aiEvent ? (
          <Pressable
            accessibilityRole="button"
            accessibilityLabel="Créer un événement avec l'IA, en le décrivant à voix haute"
            focusable={!fabAway}
            tabIndex={fabAway ? -1 : 0}
            onPress={aiEvent}
            style={({ pressed }) => [st.fab, st.fabAI, pressed && { opacity: 0.85 }]}
          >
            <T color={colors.text} style={{ ...font.bold, fontSize: 15 }}>✨ Avec l’IA</T>
          </Pressable>
        ) : null}
        {canPropose ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel="Proposer un événement"
          focusable={!fabAway}
            tabIndex={fabAway ? -1 : 0}
          onPress={() => router.push('/event/new')}
          style={({ pressed }) => [st.fab, enter('pop'), pressTransition, pressed && { opacity: 0.9, transform: [{ scale: 0.94 }] }]}
        >
          <T color={colors.onAccent} style={{ ...font.bold, fontSize: 15 }}>+ Proposer</T>
        </Pressable>
        ) : null}
        </View>
      </View>
      ) : null}
    </SafeAreaView>
  );
}

/** Défilement minimal (px) avant de montrer ou cacher « + Proposer », et zone du haut où il reste toujours visible. */
const FAB_SCROLL_SLOP = 8;
const FAB_SCROLL_START = 120;

/** Cartes fantômes pendant le premier chargement : la liste garde sa forme, rien ne saute à l’arrivée. */
function ListSkeleton() {
  return (
    <View accessibilityLabel="Chargement des événements…" accessibilityRole="progressbar" style={{ gap: 14 }}>
      {[0, 1, 2].map((i) => (
        <View key={i} style={[st.ghost, { opacity: 1 - i * 0.25 }]}>
          <Skeleton width={56} height={64} radius={radius.md} />
          <View style={{ flex: 1, gap: 10, paddingTop: 4 }}>
            <Skeleton width={90} height={18} radius={radius.pill} />
            <Skeleton width="80%" height={20} />
            <Skeleton width="55%" />
          </View>
        </View>
      ))}
    </View>
  );
}

const st = StyleSheet.create({
  ghost: { flexDirection: 'row', gap: 14, padding: 14, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.surface },
  label: { letterSpacing: 0.6 },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 12, backgroundColor: colors.accentDim, padding: 12,
    borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.accent },
  bannerIcon: { width: 40, height: 40, borderRadius: 20, backgroundColor: 'rgba(255,79,154,0.18)', alignItems: 'center', justifyContent: 'center' },
  bannerCta: { paddingHorizontal: 14, minHeight: 36, borderRadius: 18, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center' },
  fabWrap: { position: 'absolute', left: 0, right: 0, bottom: 16, alignItems: 'center' },
  fabColumn: { width: '100%', maxWidth: 640, alignItems: 'flex-end', paddingRight: 16, gap: 10 },
  fabAI: { backgroundColor: colors.surface2, borderWidth: 1, borderColor: colors.accent },
  fab: {
    height: 52, paddingHorizontal: 22, borderRadius: radius.pill,
    backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center',
    shadowColor: '#000', shadowOpacity: 0.45, shadowRadius: 16, shadowOffset: { width: 0, height: 6 },
  },
});
