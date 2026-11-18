import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { GroupTile } from '@/components/GroupBits';
import { Icon } from '@/components/HomeHeader';
import { Board } from '@/components/pronos/board/Board';
import { PrimaryButton } from '@/components/pronos/Kit';
import { NoValue } from '@/components/pronos/list/BagHero';
import { GroupEmpty } from '@/components/pronos/list/EmptyState';
import { byClose, C, fetchBag, num, round, sacPath, tabOf, web, withPatates, type ListCard } from '@/components/pronos/list/model';
import { PronoCard } from '@/components/pronos/list/PronoCard';
import { PronoRow, RowList } from '@/components/pronos/list/PronoRow';
import { HonourLine, SectionTitle, Tabs } from '@/components/pronos/list/Tabs';
import { useDetails } from '@/components/pronos/list/useDetails';
import { ErrorText, Loading } from '@/components/ui';
import { useQuery, useSignal } from '@/lib/data';
import { plural } from '@/lib/format';
import { fetchMyGroups, groupName, palette } from '@/lib/groups';
import { enter, pressTransition } from '@/lib/motion';
import { newProno, rpc } from '@/lib/pronos';

const BACK = ['M15 18l-6-6 6-6'];
const DONE_SHOWN = 3;

/**
 * Pronos d'un groupe (maquette 1-groupe du 18.11) : couverture du groupe, « Nouveau prono », le classement en deux
 * onglets « Saison 🥔 » (récolte nette du mois, si les patates sont allumées) et « Points », puis les pronos : à jouer
 * (cartes jouables), en attente et terminés (rangées). Réservé aux membres du groupe (la base vérifie).
 * `?tab=board` (« Voir le classement » après un dévoilement) ouvre les Points ; `?tab=season` la saison.
 */
export default function GroupPronos() {
  const { id, tab } = useLocalSearchParams<{ id: string; tab?: string }>();
  const insets = useSafeAreaInsets();
  const { data, error, loading, reload } = useQuery(async () => {
    const [groups, list, bag] = await Promise.all([fetchMyGroups(), rpc<ListCard[]>('prono_list', { group_id: id }), fetchBag({ kind: 'group', id })]);
    return { group: groups.find((g) => g.id === id) ?? null, list, bag };
  }, [id]);
  useSignal(id ? [`pronos:${id}`] : [], reload);
  const push = (path: string) => router.push(path as never);
  const list = useMemo(() => data?.list ?? [], [data]);
  const play = useMemo(() => list.filter((p) => tabOf(p) === 'play').sort(byClose), [list]);
  const wait = useMemo(() => list.filter((p) => tabOf(p) === 'wait').sort(byClose), [list]);
  const done = useMemo(() => list.filter((p) => tabOf(p) === 'done'), [list]);
  const details = useDetails(useMemo(() => [...play, ...wait, ...done], [play, wait, done]));
  const patates = list.some(withPatates) || data?.bag?.patates_on === true;
  const [mode, setMode] = useState<'season' | 'points'>(tab === 'board' ? 'points' : 'season');
  const [allDone, setAllDone] = useState(false);

  if (loading && !data) return <Loading />;
  const g = data?.group ?? null;
  const name = g ? groupName(g) : 'Groupe';
  const color = g?.color ?? 'lavender';
  const pal = palette(color);
  const bag = patates ? data?.bag ?? null : null;
  const back = () => (router.canGoBack() ? router.back() : router.replace(`/group/${id}`));
  const running = play.length + wait.filter((p) => p.state === 'open').length;
  let index = 0;

  return (
    <View style={{ flex: 1, backgroundColor: C.bg }}>
      <Stack.Screen options={{ headerShown: false, title: `Pronos · ${name}` }} />
      <ScrollView contentContainerStyle={{ paddingBottom: 48 }} testID="group-pronos-page">
        <View style={[st.hero, { paddingTop: insets.top + 8 }, web({ backgroundImage: `linear-gradient(135deg, ${pal.from}, ${pal.to})`, backgroundColor: pal.to })]}>
          <Text aria-hidden style={st.heroFili}>{g?.emoji ?? '🔮'}</Text>
          <View style={[st.heroFade, web({ backgroundImage: `linear-gradient(to bottom, transparent, ${C.bg} 92%)` })]} />
          <View style={st.bar}>
            <Pressable accessibilityRole="button" accessibilityLabel={`Retour à ${name}`} onPress={back}
              style={({ pressed }) => [st.glassBtn, pressTransition, pressed && st.pressed]}>
              <Icon paths={BACK} />
            </Pressable>
            {bag ? (
              <Pressable accessibilityRole="button" accessibilityLabel={`Ton sac : ${bag.balance} patates. Voir l’historique`} testID="prono-bag"
                onPress={() => push(sacPath({ kind: 'group', id }))} style={({ pressed }) => [st.glassBtn, st.bagBtn, pressTransition, pressed && st.pressed]}>
                <Text style={[num(16), { color: '#fff' }]}>{bag.balance}</Text><Text style={{ fontSize: 16 }}>🥔</Text>
              </Pressable>
            ) : null}
          </View>
        </View>

        <View style={st.body}>
          {g ? <View style={[st.tile, enter('pop')]}><GroupTile group={g} size={72} /></View> : null}
          <View style={{ gap: 2 }}>
            <Text role="heading" aria-level={1} style={round(28, 32)}>{name}</Text>
            <Text style={st.subtitle}>
              {['Pronos', g ? plural(g.members, 'membre') : null, list.length ? (running ? `${running} en cours` : 'rien en cours') : 'aucun pour l’instant'].filter(Boolean).join(' · ')}
            </Text>
          </View>
          <PrimaryButton label="＋  Nouveau prono" onPress={() => newProno({ group: id }, push)} testID="prono-new" />
          <ErrorText error={error ?? null} />

          {data && !list.length ? (
            <GroupEmpty color={color} onTemplate={(t) => push(`/prono/new?group=${id}&template=${encodeURIComponent(t)}`)}
              onBlank={() => newProno({ group: id }, push)} />
          ) : null}

          {patates ? (
            <View style={{ gap: 12 }}>
              <Tabs sticky={false} value={mode} onChange={setMode}
                tabs={[{ key: 'season', label: 'Saison 🥔' }, { key: 'points', label: 'Points' }]} />
              <Board groupId={id} mode={mode} />
            </View>
          ) : (
            <View style={{ gap: 12 }}>
              <SectionTitle>Classement</SectionTitle>
              <Board groupId={id} mode="points" />
            </View>
          )}

          {play.length ? (
            <View style={{ gap: 14 }}>
              <SectionTitle>À jouer · {play.length}</SectionTitle>
              {play.map((p) => <PronoCard key={p.id} p={p} d={details[p.id]} index={index++} push={push} showContext={false} onChanged={reload} />)}
            </View>
          ) : null}
          {wait.length ? (
            <View style={{ gap: 12 }}>
              <SectionTitle>En attente · {wait.length}</SectionTitle>
              <RowList>{wait.map((p) => <PronoRow key={p.id} p={p} d={details[p.id]} push={push} index={index++} />)}</RowList>
            </View>
          ) : null}
          {done.length ? (
            <View style={{ gap: 12 }}>
              <SectionTitle right={done.length > DONE_SHOWN && !allDone ? (
                <Pressable accessibilityRole="button" onPress={() => setAllDone(true)} style={st.link}>
                  <Text style={{ color: C.lav, fontSize: 15, fontWeight: '600' }}>Tout voir</Text>
                </Pressable>
              ) : null}>Terminés</SectionTitle>
              <RowList>{(allDone ? done : done.slice(0, DONE_SHOWN)).map((p) => <PronoRow key={p.id} p={p} d={details[p.id]} push={push} index={index++} />)}</RowList>
            </View>
          ) : null}
          {patates ? <NoValue /> : data ? <HonourLine /> : null}
        </View>
      </ScrollView>
    </View>
  );
}

const st = StyleSheet.create({
  hero: { height: 300, marginBottom: -120, overflow: 'hidden', paddingHorizontal: 16 },
  heroFili: web({ position: 'absolute', right: -50, top: 10, fontSize: 230, lineHeight: 230, opacity: 0.2, transform: 'rotate(-14deg)' }),
  heroFade: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 160 },
  bar: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', zIndex: 2 },
  glassBtn: web({ height: 44, minWidth: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(14,10,31,0.32)',
    backdropFilter: 'blur(16px)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.22)' }),
  bagBtn: { flexDirection: 'row', gap: 6, paddingHorizontal: 14 },
  pressed: { transform: [{ scale: 0.95 }], opacity: 0.9 },
  body: { paddingHorizontal: 16, gap: 18, maxWidth: 640, width: '100%', alignSelf: 'center' },
  tile: web({ alignSelf: 'flex-start', borderRadius: 24, boxShadow: `0 0 0 3px ${C.bg}` }),
  subtitle: { color: C.t2, fontSize: 15, lineHeight: 20, fontWeight: '500' },
  link: { minHeight: 44, justifyContent: 'center' },
});
