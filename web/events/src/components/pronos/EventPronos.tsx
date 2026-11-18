import { router } from 'expo-router';
import { useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Countdown } from '@/components/pronos/Kit';
import { NoValue } from '@/components/pronos/list/BagHero';
import { byClose, C, fetchBag, num, round, sacPath, tabOf, web, withPatates, type ListCard } from '@/components/pronos/list/model';
import { openPick, Preview } from '@/components/pronos/list/PronoCard';
import { PronoRow } from '@/components/pronos/list/PronoRow';
import { useDetails } from '@/components/pronos/list/useDetails';
import { useQuery, useSignal } from '@/lib/data';
import { plural } from '@/lib/format';
import { enter, pressTransition } from '@/lib/motion';
import { newProno, rpc } from '@/lib/pronos';

const ROWS = 3;

/**
 * « Pronos de la soirée » sur la fiche d'un événement publié (maquette 1-evenement du 18.11) : le prono le plus urgent
 * en vedette (jouable d'un toucher : la fiche s'ouvre avec ce choix), les autres en rangées, le sac de la soirée (si les
 * patates sont allumées) avec le rappel « aucune valeur », « Voir les N pronos » et « ＋ Ajouter ».
 */
export function EventPronos({ eventId }: { eventId: string }) {
  const { data, reload } = useQuery(async () => {
    const [list, bag] = await Promise.all([
      rpc<ListCard[]>('prono_list', { event_id: eventId }).catch((): ListCard[] => []),
      fetchBag({ kind: 'event', id: eventId }),
    ]);
    return { list, bag };
  }, [eventId]);
  useSignal([`pronos:${eventId}`], reload);
  const push = (path: string) => router.push(path as never);
  const [all, setAll] = useState(false);
  const list = useMemo(() => data?.list ?? [], [data]);
  const ordered = useMemo(() => {
    const order = { play: 0, wait: 1, done: 2 } as const;
    return [...list].sort((a, b) => order[tabOf(a)] - order[tabOf(b)] || byClose(a, b));
  }, [list]);
  const featured = ordered[0] && tabOf(ordered[0]) === 'play' ? ordered[0] : null;
  const rest = ordered.filter((p) => p !== featured);
  const details = useDetails(ordered);
  const patates = list.some(withPatates) || data?.bag?.patates_on === true;
  const bag = patates ? data?.bag ?? null : null;
  const players = list.reduce((n, p) => Math.max(n, p.players), 0);
  const shown = all ? rest : rest.slice(0, ROWS);

  return (
    <View style={[st.card, enter('rise')]} testID="event-pronos">
      <View style={st.head}>
        <View style={st.badge}><Text style={{ fontSize: 20 }}>🔮</Text></View>
        <View style={{ flex: 1 }}>
          <Text role="heading" aria-level={2} style={round(17, 22)}>Pronos de la soirée</Text>
          <Text style={st.sub}>{list.length ? `${plural(list.length, 'prono')} · ${plural(players, 'joueur')}` : 'Devine, scelle, dévoile'}</Text>
        </View>
        {bag ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Ton sac de la soirée : ${bag.balance} patates`} testID="prono-bag"
            onPress={() => push(sacPath({ kind: 'event', id: eventId }))} style={({ pressed }) => [st.bagChip, pressTransition, pressed && st.pressed]}>
            <Text style={[num(15), { color: C.t1 }]}>{bag.balance}</Text><Text style={{ fontSize: 15 }}>🥔</Text>
          </Pressable>
        ) : null}
      </View>

      {featured ? (
        <Pressable accessibilityRole="button" accessibilityLabel={featured.question} testID={`prono-card-${featured.id}`}
          onPress={() => openPick(featured.id, null, push)} style={({ pressed }) => [st.featured, pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
          <View style={{ flexDirection: 'row', gap: 12, alignItems: 'flex-start' }}>
            <Text style={[round(17, 21), { flex: 1 }]}>{featured.question}</Text>
            <Countdown closesAt={featured.closes_at} />
          </View>
          <Text style={st.sub}>
            {withPatates(featured) && featured.field_total != null ? `🥔 ${featured.field_total} dans le champ · ` : ''}
            {`${featured.answered_count} ${featured.answered_count > 1 ? 'ont' : 'a'} ${featured.kind === 'award' ? 'voté' : 'joué'}`}
          </Text>
          <Preview p={featured} d={details[featured.id]} push={push} />
        </Pressable>
      ) : null}

      {shown.length ? (
        <View style={{ marginHorizontal: -16 }}>
          {shown.map((p, i) => <PronoRow key={p.id} p={p} d={details[p.id]} push={push} compact index={i} />)}
        </View>
      ) : null}

      {!list.length ? (
        <Text style={[st.sub, { fontSize: 15, lineHeight: 21 }]}>Qui arrive en dernier ? Qui remporte le blind test ? Les réponses restent scellées jusqu’au dévoilement.</Text>
      ) : null}

      <View style={st.foot}>
        {rest.length > ROWS && !all ? (
          <Pressable accessibilityRole="button" onPress={() => setAll(true)} style={st.link}>
            <Text style={{ color: C.lav, fontSize: 15, fontWeight: '600' }}>Voir les {list.length} pronos ›</Text>
          </Pressable>
        ) : <View />}
        <Pressable accessibilityRole="button" accessibilityLabel="Nouveau prono pour la soirée" testID="event-prono-new"
          onPress={() => newProno({ event: eventId }, push)} style={({ pressed }) => [st.add, pressTransition, pressed && st.pressed]}>
          <Text style={{ color: C.t1, fontSize: 15, fontWeight: '700' }}>＋ Ajouter</Text>
        </Pressable>
      </View>
      {patates ? <NoValue /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  card: web({ borderRadius: 24, padding: 16, gap: 14, backgroundColor: C.s1, borderWidth: 1, borderColor: 'rgba(185,167,255,0.4)',
    boxShadow: '0 1px 0 rgba(255,255,255,.04) inset, 0 18px 40px -24px rgba(0,0,0,.8)' }),
  head: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 48 },
  badge: web({ width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center',
    backgroundImage: 'linear-gradient(135deg, #CBBDFF, #7B6CF6)', boxShadow: '0 8px 20px -8px rgba(123,108,246,.8)' }),
  sub: { color: C.t2, fontSize: 13, lineHeight: 18, fontWeight: '500' },
  bagChip: { height: 36, minWidth: 44, paddingHorizontal: 14, borderRadius: 18, flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: C.s3, borderWidth: 1, borderColor: C.line2 },
  pressed: { opacity: 0.85, transform: [{ scale: 0.96 }] },
  featured: { borderRadius: 16, padding: 14, gap: 6, backgroundColor: C.s3, borderWidth: 1, borderColor: 'rgba(255,79,154,0.35)' },
  foot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, borderTopWidth: 1, borderTopColor: C.line,
    paddingTop: 12, marginHorizontal: -16, paddingHorizontal: 16 },
  link: { minHeight: 44, justifyContent: 'center' },
  add: { height: 44, paddingHorizontal: 18, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: C.s3,
    borderWidth: 1, borderColor: C.line2 },
});
