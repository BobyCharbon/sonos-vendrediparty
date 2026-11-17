import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Text, View } from 'react-native';

import { PillButton, TopBar } from '@/components/agenda/Bits';
import { BoardView, PronoCardView } from '@/components/pronos/Bits';
import { ConfirmButton, ErrorText, Loading, Screen, Segmented, T } from '@/components/ui';
import { useQuery, useSignal } from '@/lib/data';
import { formatShort, plural } from '@/lib/format';
import { fetchMyGroups, groupName } from '@/lib/groups';
import { newProno, openProno, rpc, type Board, type PronoCard } from '@/lib/pronos';
import { colors } from '@/lib/theme';

/**
 * Pronos d'un groupe (maquette du 17.11, écrans 1 et 6) : la liste (à jouer, en cours, terminés) et le classement aux
 * points, remis à zéro par qui gère le groupe. Réservé aux membres du groupe (la base vérifie).
 */
export default function GroupPronos() {
  const { id, tab } = useLocalSearchParams<{ id: string; tab?: string }>();
  const [view, setView] = useState<'list' | 'board'>(tab === 'board' ? 'board' : 'list');
  const { data, error, loading, reload } = useQuery(async () => {
    const [groups, list, board] = await Promise.all([fetchMyGroups(), rpc<PronoCard[]>('prono_list', { group_id: id }), rpc<Board>('prono_board', { group_id: id })]);
    return { group: groups.find((g) => g.id === id) ?? null, list, board };
  }, [id]);
  useSignal(id ? [`pronos:${id}`] : [], reload);
  const push = (path: string) => router.push(path as never);
  if (loading && !data) return <Loading />;
  const name = data?.group ? groupName(data.group) : 'Groupe';

  return (
    <Screen contentStyle={{ gap: 12, paddingBottom: 48 }}>
      <Stack.Screen options={{ headerShown: false, title: `Pronos · ${name}` }} />
      <TopBar back={name} fallback={`/group/${id}`} title="🔮 Pronos"
        right={<PillButton label="＋ Nouveau" tone="accent" testID="prono-new" onPress={() => newProno({ group: id }, push)} />} />
      <Segmented options={[{ key: 'list', label: 'Pronos' }, { key: 'board', label: 'Classement' }]} value={view} onChange={(v) => setView(v as 'list' | 'board')} />
      <ErrorText error={error ?? null} />
      {view === 'list' ? (
        data?.list.length ? data.list.map((p, i) => <PronoCardView key={p.id} p={p} index={i} showPlace={false} onPress={() => openProno(p.id, push)} />) : (
          <View style={{ alignItems: 'center', gap: 8, padding: 24, borderRadius: 20, backgroundColor: colors.surface }}>
            <Text style={{ fontSize: 40 }}>🔮</Text>
            <T weight="bold">Aucun prono dans ce groupe</T>
            <T muted size={13} style={{ textAlign: 'center' }}>Pose la première question : tout le groupe sera prévenu.</T>
          </View>
        )
      ) : data ? (
        <View style={{ gap: 10 }}>
          <T size={13} muted>{data.board.since ? `Depuis le ${formatShort(data.board.since)}` : 'Depuis le début'} · {plural(data.board.pronos, 'prono')}</T>
          <BoardView board={data.board} />
          {data.board.manage && data.board.rows.length ? (
            <ConfirmButton small label="Remettre le classement à zéro" confirmLabel="Oui, repartir de zéro"
              onConfirm={async () => { await rpc('prono_board_reset', { group_id: id }); reload(); }} />
          ) : null}
        </View>
      ) : null}
    </Screen>
  );
}
