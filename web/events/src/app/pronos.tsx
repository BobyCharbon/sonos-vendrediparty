import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { goBack, TopBar } from '@/components/agenda/Bits';
import { BagHero, terrainsOf, useBags } from '@/components/pronos/list/BagHero';
import { AllPlayed, NoPronos } from '@/components/pronos/list/EmptyState';
import { byClose, soon, tabOf, terrainOf, useNow, withPatates, type ListCard, type Tab } from '@/components/pronos/list/model';
import { PronoCard } from '@/components/pronos/list/PronoCard';
import { HonourLine, SectionTitle, Tabs } from '@/components/pronos/list/Tabs';
import { useDetails } from '@/components/pronos/list/useDetails';
import { ErrorText, Loading, Screen } from '@/components/ui';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { pressTransition } from '@/lib/motion';
import { nativePronos, newProno, rpc } from '@/lib/pronos';

/**
 * « Mes pronos » (Réglages › Autres apps, maquette 1-liste du 18.11) : le sac en vedette (patates, si la base les
 * allume) et les sacs de mes autres groupes, le rappel « aucune valeur », puis trois onglets : À jouer (la fin la plus
 * proche d'abord : « Ça ferme bientôt » puis « Plus tard »), En attente (scellés encore ouverts, fermés sans résultat),
 * Terminés. Un toucher sur une pastille ouvre la fiche avec ce choix présélectionné : on ne répond jamais d'ici.
 */
export default function PronosHome() {
  const me = useMe();
  const native = nativePronos();
  const params = useLocalSearchParams<{ tab?: string }>();
  useEffect(() => {
    if (native?.list) { native.list(); goBack('/account'); }
  }, [native]);
  const { data, error, loading, reload } = useQuery(() => rpc<ListCard[]>('prono_list'), []);
  useSignal([`user:${me.id}`], reload);
  const push = (path: string) => router.push(path as never);
  const list = useMemo(() => data ?? [], [data]);

  const groups = useMemo(() => {
    const play = list.filter((p) => tabOf(p) === 'play').sort(byClose);
    const wait = list.filter((p) => tabOf(p) === 'wait').sort(byClose);
    const done = list.filter((p) => tabOf(p) === 'done');
    return { play, wait, done };
  }, [list]);
  const [tab, setTab] = useState<Tab>(params.tab === 'wait' || params.tab === 'done' ? params.tab : 'play');
  const shown = groups[tab];
  const details = useDetails(shown);

  const terrains = useMemo(() => terrainsOf(list, terrainOf), [list]);
  const bags = useBags(terrains);
  const [bag, setBag] = useState('');
  const patates = list.some(withPatates);
  const now = useNow();

  const sections: { title: string; items: ListCard[] }[] = tab === 'play'
    ? [{ title: 'Ça ferme bientôt', items: shown.filter((p) => soon(p, now)) }, { title: 'Plus tard', items: shown.filter((p) => !soon(p, now)) }]
    : tab === 'wait'
      ? [{ title: 'Scellés · tu peux encore changer', items: shown.filter((p) => p.state === 'open') },
        { title: 'Fermés · on attend le résultat', items: shown.filter((p) => p.state === 'closed') }]
      : [{ title: 'Cette semaine', items: shown.filter((p) => now - new Date(p.closes_at).getTime() < 7 * 86_400_000) },
        { title: 'Plus tôt', items: shown.filter((p) => now - new Date(p.closes_at).getTime() >= 7 * 86_400_000) }];

  const summary = groups.play.length
    ? <><Text style={st.b}>{groups.play.length} à jouer</Text>{groups.wait.length ? ` · ${groups.wait.length} en attente` : ''}</>
    : list.length ? <><Text style={st.b}>Tout est joué</Text>{groups.wait.length ? ` · ${groups.wait.length} en attente` : ''}</>
      : 'Devine, scelle ta réponse, attends le dévoilement.';

  let index = 0;
  return (
    <Screen contentStyle={{ gap: 14, paddingBottom: 48 }}>
      <Stack.Screen options={{ headerShown: false, title: 'Pronos' }} />
      <TopBar back="Réglages" fallback="/account" title="Pronos" subtitle={<Text style={st.sub}>{summary}</Text>}
        titleRight={(
          <Pressable accessibilityRole="button" accessibilityLabel="Nouveau prono" testID="prono-new" onPress={() => newProno({}, push)}
            style={({ pressed }) => [st.plus, pressTransition, pressed && { transform: [{ scale: 0.94 }] }]}>
            <Text style={st.plusText}>＋</Text>
          </Pressable>
        )} />
      {loading && !data ? <Loading /> : null}
      <ErrorText error={error ?? null} />

      {patates ? <BagHero terrains={terrains} bags={bags} selected={bag} onSelect={setBag} list={list} push={push} /> : null}

      {data && !list.length ? <NoPronos onNew={() => newProno({}, push)} /> : null}

      {list.length ? (
        <>
          <Tabs value={tab} onChange={setTab} tabs={[
            { key: 'play', label: 'À jouer', count: groups.play.length, hot: true },
            { key: 'wait', label: 'En attente', count: groups.wait.length },
            { key: 'done', label: 'Terminés' },
          ]} />
          {tab === 'play' && !shown.length ? (
            <AllPlayed next={groups.wait.find((p) => p.state === 'open') ?? null} onWait={() => setTab('wait')} />
          ) : null}
          {tab !== 'play' && !shown.length ? (
            <Text style={st.empty}>{tab === 'wait' ? 'Rien en attente : tes pronos joués apparaîtront ici.' : 'Aucun prono terminé pour l’instant.'}</Text>
          ) : null}
          {sections.map((s) => (s.items.length ? (
            <View key={s.title} style={{ gap: 14 }}>
              <SectionTitle>{s.title}</SectionTitle>
              {s.items.map((p) => <PronoCard key={p.id} p={p} d={details[p.id]} index={index++} push={push} onChanged={reload} />)}
            </View>
          ) : null))}
        </>
      ) : null}
      {data && !patates ? <HonourLine /> : null}
    </Screen>
  );
}

const st = StyleSheet.create({
  sub: { color: '#A79FC7', fontSize: 15, lineHeight: 20, fontWeight: '500' },
  b: { color: '#F4F1FF', fontWeight: '700' },
  plus: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: '#D42A76',
    shadowColor: '#FF4F9A', shadowOpacity: 0.7, shadowRadius: 12, shadowOffset: { width: 0, height: 8 } },
  plusText: { color: '#fff', fontSize: 22, fontWeight: '700', lineHeight: 24 },
  empty: { color: '#A79FC7', fontSize: 15, textAlign: 'center', paddingVertical: 24 },
});
