import { Stack } from 'expo-router';
import type { ReactNode } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { TopBar } from '@/components/agenda/Bits';
import { BagHistory } from '@/components/pronos/board';
import { ErrorText, Loading, Screen } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { formatLongDay } from '@/lib/format';
import { fetchMyGroups, groupName, palette } from '@/lib/groups';
import { enter } from '@/lib/motion';
import { rpc } from '@/lib/pronos';

import { bagArgs, C, label, monthName, NO_VALUE, num, round, web, type Bag, type ListCard } from './model';

type Season = { month: string; me?: { harvest_net?: number; right?: number; played?: number } | null };

/**
 * « Ton sac » (maquette 1-sac) : un sac par groupe ou par soirée. Solde dans une jauge ronde jusqu'à 100, prochaine
 * remontée (lundi 0 h), plantées en cours, récolte de la saison, justesse ; « Comment ça marche » ; l'historique, à soi
 * SEUL (jamais d'export, jamais de comparaison entre deux personnes) ; rappel « aucune valeur ».
 */
export function SacScreen({ group, event }: { group?: string; event?: string }) {
  const terrain = group ? { kind: 'group' as const, id: group } : event ? { kind: 'event' as const, id: event } : null;
  const { data, error, loading } = useQuery(async () => {
    if (!terrain) return null;
    const [bag, list, groups, season] = await Promise.all([
      rpc<Bag | null>('prono_bag', bagArgs(terrain)),
      rpc<ListCard[]>('prono_list', bagArgs(terrain)).catch((): ListCard[] => []),
      group ? fetchMyGroups().catch(() => []) : Promise.resolve([]),
      group ? rpc<Season | null>('prono_season', { group_id: group }).catch(() => null) : Promise.resolve(null),
    ]);
    const g = groups.find((x) => x.id === group) ?? null;
    const name = g ? groupName(g) : list.find((p) => p.event)?.event?.title ?? 'La soirée';
    return { bag, list, name, emoji: g?.emoji ?? '🎉', color: g?.color ?? 'lavender', season };
  }, [group, event]);

  if (loading && !data) return <Loading />;
  const bag = data?.bag ?? null;
  const pal = palette(data?.color);
  const pending = (data?.list ?? []).filter((p) => p.answered && (p.state === 'open' || p.state === 'closed') && (p.my_stake ?? 0) > 0);
  const planted = pending.reduce((n, p) => n + (p.my_stake ?? 0), 0);
  const harvest = bag?.season?.harvest_net ?? data?.season?.me?.harvest_net ?? 0;
  const me = data?.season?.me;
  const pct = Math.min(100, Math.max(0, bag?.balance ?? 0));

  return (
    <Screen contentStyle={{ gap: 18, paddingBottom: 48 }}>
      <Stack.Screen options={{ headerShown: false, title: 'Ton sac' }} />
      <TopBar back="Pronos" fallback={group ? `/group/${group}/pronos` : '/pronos'} />
      <ErrorText error={error ?? null} />
      {data && bag ? (
        <>
          <View style={{ alignItems: 'center', gap: 6 }}>
            <View style={st.terrain}>
              <View style={[st.terrainEm, web({ backgroundImage: `linear-gradient(135deg, ${pal.from}, ${pal.to})` })]}><Text style={{ fontSize: 15 }}>{data.emoji}</Text></View>
              <Text numberOfLines={1} style={{ color: C.t1, fontSize: 15, fontWeight: '600' }}>{data.name}</Text>
            </View>
            <Text role="heading" aria-level={1} style={round(30, 34)}>Ton sac</Text>
          </View>

          <View style={[st.ringWrap, enter('pop')]} accessibilityLabel={`${bag.balance} confettis dans ton sac, sur 100`}>
            <View style={[st.ring, web({ backgroundImage: `conic-gradient(${pal.from} 0%, ${pal.to} ${pct}%, rgba(255,255,255,0.14) ${pct}% 100%)` })]}>
              <View style={st.ringIn}>
                <Text style={[num(60), { color: C.t1 }]}>{bag.balance}</Text>
                <Text style={{ color: C.t2, fontSize: 13, fontWeight: '600' }}>🎊 dans ton sac</Text>
              </View>
            </View>
          </View>

          <View style={st.refill}>
            <Text style={{ color: C.lav, fontSize: 15, fontWeight: '700', textAlign: 'center' }}>
              {bag.balance >= 100 ? 'Ton sac est plein' : `↻ Remonte à 100 ${bag.refill_at ? `${formatLongDay(bag.refill_at).toLowerCase()} à 0 h` : 'lundi à 0 h'}`}
            </Text>
          </View>

          <View style={st.tiles}>
            <Tile k="Lancés" v={`${planted} 🎊`} s={`dans ${pending.length} prono${pending.length > 1 ? 's' : ''}`} />
            <Tile k="Ramassés" v={`${harvest > 0 ? '+' : ''}${harvest} 🎊`} s={`en ${monthName(bag.season?.month ?? data.season?.month)}`} tone={harvest > 0 ? C.mint : undefined} />
            {me?.played ? <Tile k="Justesse" v={`${me.right ?? 0}/${me.played}`} s="vues justes" /> : null}
          </View>

          <View style={{ gap: 10 }}>
            <Text style={label}>Comment ça marche</Text>
            <View style={st.box}>
              <How icon="🎊" text={<><B>100 confettis</B> au départ, un sac par groupe et par soirée.</>} />
              <How icon="↻" text={<>Chaque <B>lundi</B>, ton sac remonte à 100 s’il est plus bas.</>} />
              <How icon="🪩" text={<>Lance <B>1 à 20 🎊</B> par prono. Ceux qui voient juste se partagent la piste.</>} last />
            </View>
          </View>

          <View style={{ gap: 10 }}>
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              <Text style={label}>Ton historique</Text>
              <Text style={{ color: C.t2, fontSize: 13, fontWeight: '600' }}>🔒 toi seul le vois</Text>
            </View>
            <BagHistory groupId={group} eventId={event} />
          </View>

          <View style={st.noValue}>
            <Text aria-hidden style={{ fontSize: 20 }}>🎊</Text>
            <View style={{ flex: 1, gap: 4 }}>
              <Text style={{ color: C.t1, fontSize: 14, lineHeight: 20, fontWeight: '600' }}>{NO_VALUE}</Text>
              <Text style={{ color: C.t2, fontSize: 13, lineHeight: 18 }}>Juste pour le plaisir de voir juste entre amis.</Text>
            </View>
          </View>
        </>
      ) : data ? (
        <Text style={{ color: C.t2, fontSize: 15, textAlign: 'center', paddingVertical: 24 }}>Pas de confettis ici : ces pronos se jouent pour l’honneur.</Text>
      ) : null}
    </Screen>
  );
}

function B({ children }: { children: ReactNode }) {
  return <Text style={{ color: C.t1, fontWeight: '700' }}>{children}</Text>;
}

function Tile({ k, v, s, tone }: { k: string; v: string; s: string; tone?: string }) {
  return (
    <View style={st.tile}>
      <Text style={label}>{k}</Text>
      <Text style={[num(22), { color: tone ?? C.t1 }]}>{v}</Text>
      <Text style={{ color: C.t2, fontSize: 13 }}>{s}</Text>
    </View>
  );
}

function How({ icon, text, last }: { icon: string; text: ReactNode; last?: boolean }) {
  return (
    <View style={[st.how, !last && { borderBottomWidth: 1, borderBottomColor: C.line }]}>
      <View style={st.howIcon}><Text style={{ fontSize: 15, color: C.t1 }}>{icon}</Text></View>
      <Text style={{ flex: 1, color: C.t2, fontSize: 15, lineHeight: 20 }}>{text}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  terrain: { flexDirection: 'row', alignItems: 'center', gap: 8, height: 36, paddingLeft: 4, paddingRight: 14, borderRadius: 18,
    backgroundColor: C.s3, borderWidth: 1, borderColor: C.line2, maxWidth: '90%' },
  terrainEm: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  ringWrap: { alignItems: 'center' },
  ring: { width: 196, height: 196, borderRadius: 98, padding: 14 },
  ringIn: { flex: 1, borderRadius: 84, backgroundColor: C.s1, alignItems: 'center', justifyContent: 'center', gap: 6 },
  refill: { alignSelf: 'center', paddingHorizontal: 16, paddingVertical: 8, borderRadius: 999, backgroundColor: 'rgba(185,167,255,0.12)',
    borderWidth: 1, borderColor: 'rgba(185,167,255,0.3)' },
  tiles: { flexDirection: 'row', gap: 10 },
  tile: { flex: 1, minHeight: 92, padding: 12, gap: 6, borderRadius: 16, backgroundColor: C.s3, borderWidth: 1, borderColor: C.line },
  box: { borderRadius: 20, backgroundColor: C.s3, borderWidth: 1, borderColor: C.line, paddingHorizontal: 14 },
  how: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48, paddingVertical: 10 },
  howIcon: { width: 32, height: 32, borderRadius: 10, alignItems: 'center', justifyContent: 'center', backgroundColor: C.s1 },
  noValue: { flexDirection: 'row', gap: 12, padding: 16, borderRadius: 16, backgroundColor: 'rgba(185,167,255,0.08)',
    borderWidth: 1, borderColor: 'rgba(185,167,255,0.25)' },
});
