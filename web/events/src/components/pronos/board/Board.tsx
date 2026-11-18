import { useState } from 'react';
import { Pressable, Text, View } from 'react-native';

import { ConfirmButton, ErrorText, Skeleton } from '@/components/ui';
import { useQuery, useSignal } from '@/lib/data';
import { formatShort, plural } from '@/lib/format';
import { rpc, type Board as BoardData, type Face } from '@/lib/pronos';

import { card, FaceRing, NoValueNote, SectionHead } from '../reveal/Bits';
import { K, spring, useStage } from '../reveal/fx';
import { daysLeftInMonth, monthName, nameOf, shiftMonth, thisMonth } from '../reveal/model';
import { label, N, num, round, text, web } from '../reveal/theme';
import { Podium } from './Podium';

/**
 * Classement d'un groupe. « season » (maquette 4-classement) : la saison du mois, à la récolte nette (versé − planté
 * des pronos réglés dans le mois), la justesse en stat, ▲▼ depuis la veille, podium 2-1-3, titres honorifiques ; jamais
 * au sac. « points » : l'ancien classement aux points, restylé (mêmes mots, remise à zéro par qui gère le groupe).
 * Patates éteintes (la base renvoie null) : la saison laisse la place aux points.
 */
export function Board({ groupId, mode }: { groupId: string; mode: 'season' | 'points' }) {
  return mode === 'season' ? <SeasonBoard groupId={groupId} /> : <PointsBoard groupId={groupId} />;
}

type SeasonRow = { user: Face; harvest_net: number; right: number; played: number; rank: number; move: number | null };
type Season = { month: string; rows: SeasonRow[]; me: SeasonRow | null } | null;
type Bag = { balance: number; refill_at: string | null; max_stake: number; season?: { month: string; harvest_net: number } } | null;

const netText = (n: number) => (n > 0 ? `+${n}` : n < 0 ? `−${-n}` : '0');
const netColor = (n: number) => (n > 0 ? N.mint : n < 0 ? N.missText : N.t1);
const pct = (r: { right: number; played: number }) => (r.played ? Math.round((r.right * 100) / r.played) : 0);

function SeasonBoard({ groupId }: { groupId: string }) {
  const now = thisMonth();
  const [month, setMonth] = useState(now);
  const [end, setEnd] = useState(now);
  const { data, error, loading, reload } = useQuery(async () => {
    const [season, bag] = await Promise.all([
      rpc<Season>('prono_season', { group_id: groupId, month }),
      rpc<Bag>('prono_bag', { group_id: groupId, event_id: null }).catch(() => null),
    ]);
    return { season, bag };
  }, [groupId, month]);
  useSignal(groupId ? [`pronos:${groupId}`] : [], reload);
  if (loading && !data) return <View style={{ gap: 10 }}><Skeleton height={36} /><Skeleton height={300} /><Skeleton height={200} /></View>;
  if (data && data.season === null) return <PointsBoard groupId={groupId} />;
  const rows = data?.season?.rows ?? [];
  const current = month === now;
  const days = daysLeftInMonth();
  const months = [shiftMonth(end, -2), shiftMonth(end, -1), end];
  const short = (m: string) => {
    const n = monthName(m);
    return m === month ? n.charAt(0).toUpperCase() + n.slice(1) : `${n.charAt(0).toUpperCase()}${n.slice(1, 4)}.`;
  };
  return (
    <View testID="prono-season">
      <Text style={label()}>Classement · saison</Text>
      <Text role="heading" aria-level={2} style={[round(32, 36), { marginTop: 8 }]}>Saison de {monthName(month)}</Text>
      <Text style={[text(14, '500', N.t2), { marginTop: 6 }]}>
        {current ? `En cours · encore ${plural(days, 'jour')}` : 'Terminée'}
      </Text>
      <View role="tablist" aria-label="Mois" style={{ flexDirection: 'row', gap: 8, marginTop: 16, flexWrap: 'wrap' }}>
        <MonthChip label="‹" a11y="Mois plus anciens" onPress={() => setEnd(shiftMonth(end, -3))} />
        {months.map((m) => <MonthChip key={m} label={short(m)} on={m === month} onPress={() => setMonth(m)} testID={`prono-season-month-${m.slice(0, 7)}`} />)}
        {end < now ? <MonthChip label="›" a11y="Mois plus récents" onPress={() => setEnd(shiftMonth(end, 3) > now ? now : shiftMonth(end, 3))} /> : null}
      </View>
      <ErrorText error={error ?? null} />
      {rows.length ? (
        <>
          <Podium replay={`${month}:${rows.length}`} spots={rows.slice(0, 3).map((r) => ({
            face: r.user, rank: r.rank, sub: `${r.right} juste${r.right > 1 ? 's' : ''} sur ${r.played}`,
            main: <Text style={num(16, netColor(r.harvest_net))}>{netText(r.harvest_net)} 🥔</Text>,
          }))} />
          <Titles rows={rows} />
          <SectionHead left="Toute la saison" right="récolte nette" />
          <SeasonRows rows={rows} replay={`${month}:${rows.length}`} />
        </>
      ) : (
        <View style={[card, { alignItems: 'center', gap: 6, padding: 24, marginTop: 16 }]} testID="prono-season-empty">
          <Text style={{ fontSize: 34 }}>🌱</Text>
          <Text style={text(16, '700')}>Pas encore de récolte en {monthName(month)}</Text>
          <Text style={[text(13, '500', N.t2), { textAlign: 'center' }]}>Le classement se remplit à chaque prono réglé.</Text>
        </View>
      )}
      <View style={{ marginTop: 12, padding: 14, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: N.line }}>
        <Text style={[text(13, '500', N.t2), { lineHeight: 19 }]}>
          <Text style={text(13, '700')}>Comment on classe ? </Text>
          À la récolte nette de la saison : ce que tes pronos t’ont rendu, moins ce que tu as planté. Ton sac n’y compte pas.
          {current ? ` Nouvelle saison le 1er ${monthName(shiftMonth(now, 1))}.` : ''}
        </Text>
      </View>
      {data?.bag ? (
        <View style={[card, { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 20, marginTop: 12 }]} testID="prono-season-bag">
          <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: 'rgba(255,226,122,0.12)', alignItems: 'center', justifyContent: 'center' }}>
            <Text style={{ fontSize: 24 }}>🥔</Text>
          </View>
          <View style={{ flex: 1 }}>
            <Text style={text(16, '700')}>Ton sac</Text>
            <Text style={text(13, '500', N.t2)}>Remonte à 100 lundi s’il est en dessous</Text>
          </View>
          <Text style={num(24)}>{data.bag.balance} 🥔</Text>
        </View>
      ) : null}
      <NoValueNote />
    </View>
  );
}

function MonthChip({ label: l, on, onPress, a11y, testID }: { label: string; on?: boolean; onPress: () => void; a11y?: string; testID?: string }) {
  return (
    <Pressable accessibilityRole="tab" accessibilityState={{ selected: !!on }} aria-selected={!!on} accessibilityLabel={a11y ?? l} onPress={onPress} testID={testID}
      style={({ pressed }) => [{ height: 44, minWidth: 44, paddingHorizontal: 14, borderRadius: 999, alignItems: 'center', justifyContent: 'center', borderWidth: 1,
        backgroundColor: on ? N.t1 : 'rgba(255,255,255,0.07)', borderColor: on ? N.t1 : N.line }, pressed && { opacity: 0.85 }]}>
      <Text style={text(14, '600', on ? N.ink : N.t1)}>{l}</Text>
    </Pressable>
  );
}

/** Titres honorifiques du mois, tirés de la saison (justesse, bonnes réponses, pronos joués) : jamais au sac. */
function Titles({ rows }: { rows: SeasonRow[] }) {
  if (rows.length < 2) return null;
  const best = <T,>(f: (r: SeasonRow) => T, list = rows) => list.reduce((a, b) => (f(b) > f(a) ? b : a), list[0]);
  const seers = rows.filter((r) => r.played >= 3);
  const items = [
    seers.length ? { e: '🔮', t: 'Voyant·e du mois', r: best(pct, seers), s: (r: SeasonRow) => `${pct(r)} % de justesse` } : null,
    { e: '🎯', t: 'Le plus de justes', r: best((r) => r.right), s: (r: SeasonRow) => `${plural(r.right, 'juste')}` },
    { e: '🙋', t: 'Toujours partant·e', r: best((r) => r.played), s: (r: SeasonRow) => `${plural(r.played, 'prono joué', 'pronos joués')}` },
  ].filter(Boolean) as { e: string; t: string; r: SeasonRow; s: (r: SeasonRow) => string }[];
  return (
    <View>
      <SectionHead left="Les titres du mois" />
      <View style={{ flexDirection: 'row', gap: 11 }}>
        {items.map((it, i) => (
          <View key={it.t} style={[card, { flex: 1, borderRadius: 20, paddingHorizontal: 10, paddingVertical: 12, minHeight: 136 }, enterStyle(i)]}>
            <Text style={{ fontSize: 24 }}>{it.e}</Text>
            <Text style={[text(13, '700', N.t2), { marginTop: 6, minHeight: 32 }]}>{it.t}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 8 }}>
              <FaceRing face={it.r.user} size={22} ring={N.s1} />
              <Text style={[text(15, '700'), { flexShrink: 1 }]} numberOfLines={1}>{nameOf(it.r.user)}</Text>
            </View>
            <Text style={[text(12, '500', N.t2), { marginTop: 6 }]}>{it.s(it.r)}</Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const enterStyle = (i: number) => web({ animationKeyframes: [{ from: { opacity: 0, transform: 'translateY(12px)' }, to: { opacity: 1, transform: 'none' } }],
  animationDuration: '420ms', animationDelay: `${1250 + i * 60}ms`, animationFillMode: 'backwards', animationTimingFunction: 'cubic-bezier(.22,1,.36,1)' });

function SeasonRows({ rows, replay }: { rows: SeasonRow[]; replay: string }) {
  const { root } = useStage((s) => {
    s.qa('srow').forEach((r, i) => {
      const mv = Number(r.dataset.mv || 0);
      s.a(r, [{ transform: `translateY(${mv * 60}px)` }, { transform: 'none' }], 1450 + i * 20, spring(0.55, 0.82));
      s.a(r.querySelector<HTMLElement>('[data-k="mv"]'), [{ transform: 'scale(.3)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], 1830 + i * 20, spring(0.3, 0.5));
    });
  }, 2600, [replay]);
  return (
    <View ref={root} style={[card, { paddingHorizontal: 8, paddingVertical: 4 }]}>
      {rows.map((r, i) => {
        const mv = r.move ?? 0;
        return (
          <K key={r.user.id} k="srow" data={{ mv: String(mv) }} testID={`prono-season-row-${i}`}
            accessibilityLabel={`${r.rank}, ${nameOf(r.user)}, ${netText(r.harvest_net)} patates, ${r.right} justes sur ${r.played}${mv > 0 ? `, monte de ${mv}` : mv < 0 ? `, descend de ${-mv}` : ''}`}
            style={[{ flexDirection: 'row', alignItems: 'center', gap: 10, height: 60, paddingHorizontal: 8, backgroundColor: N.s1, zIndex: 10 + mv },
              i > 0 && { borderTopWidth: 1, borderColor: N.line },
              r.user.me && web({ borderRadius: 16, backgroundColor: '#251d45', boxShadow: 'inset 0 0 0 1.5px rgba(185,167,255,.45)', zIndex: 40, borderTopWidth: 0 })]}>
            <Text style={[num(16, N.t2), { width: 22, textAlign: 'center' }]}>{r.rank}</Text>
            <K k="mv" style={{ width: 30, flexDirection: 'row', alignItems: 'center', gap: 2 }}>
              {mv ? <View style={web({ width: 9, height: 9, backgroundColor: mv > 0 ? N.mint : N.t2,
                clipPath: mv > 0 ? 'polygon(50% 5%, 95% 90%, 5% 90%)' : 'polygon(50% 95%, 5% 10%, 95% 10%)' })} /> : null}
              <Text style={text(12, '700', mv > 0 ? N.mint : N.t2)}>{mv ? Math.abs(mv) : '–'}</Text>
            </K>
            <FaceRing face={r.user} size={36} ring={N.s1} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={text(16, '600')} numberOfLines={1}>{nameOf(r.user)}</Text>
              <Text style={[text(12.5, '500', N.t2), { marginTop: 3 }]}>{r.right}/{r.played} justes · {pct(r)} %</Text>
            </View>
            <Text style={num(17, netColor(r.harvest_net))}>{netText(r.harvest_net)} 🥔</Text>
          </K>
        );
      })}
    </View>
  );
}

/** L'ancien classement aux points, restylé : mêmes mots (« 1 bonne réponse sur 1 »), remise à zéro par qui gère. */
function PointsBoard({ groupId }: { groupId: string }) {
  const { data, error, loading, reload } = useQuery(() => rpc<BoardData>('prono_board', { group_id: groupId }), [groupId]);
  useSignal(groupId ? [`pronos:${groupId}`] : [], reload);
  if (loading && !data) return <View style={{ gap: 10 }}><Skeleton height={300} /><Skeleton height={200} /></View>;
  if (!data) return <ErrorText error={error ?? null} />;
  return (
    <View testID="prono-board" style={{ gap: 10 }}>
      <Text style={text(13, '500', N.t2)}>{data.since ? `Depuis le ${formatShort(data.since)}` : 'Depuis le début'} · {plural(data.pronos, 'prono')}</Text>
      {!data.rows.length ? (
        <View style={[card, { alignItems: 'center', gap: 6, padding: 24 }]}>
          <Text style={{ fontSize: 34 }}>🏅</Text>
          <Text style={text(16, '700')}>Pas encore de points</Text>
          <Text style={[text(13, '500', N.t2), { textAlign: 'center' }]}>Le classement se remplit à chaque résultat donné.</Text>
        </View>
      ) : (
        <>
          <Podium replay={`points:${data.rows.length}:${data.since ?? ''}`} spots={data.rows.slice(0, 3).map((r, i) => ({
            face: r.user, rank: i + 1, sub: `${r.right} juste${r.right > 1 ? 's' : ''} sur ${r.played}`,
            main: <Text style={num(16, N.lemon)}>{plural(r.points, 'point')}</Text>,
          }))} />
          <View style={[card, { paddingHorizontal: 8, paddingVertical: 4 }]}>
            {data.rows.map((r, i) => (
              <View key={r.user.id} testID={`prono-board-row-${i}`}
                style={[{ flexDirection: 'row', alignItems: 'center', gap: 12, height: 60, paddingHorizontal: 8 }, i > 0 && { borderTopWidth: 1, borderColor: N.line },
                  r.user.me && web({ borderRadius: 16, backgroundColor: '#251d45', boxShadow: 'inset 0 0 0 1.5px rgba(185,167,255,.45)', borderTopWidth: 0 })]}>
                <Text style={[num(16, N.t2), { width: 22, textAlign: 'center' }]}>{i + 1}</Text>
                <FaceRing face={r.user} size={36} ring={N.s1} />
                <View style={{ flex: 1, minWidth: 0 }}>
                  <Text style={text(16, '600')} numberOfLines={1}>{nameOf(r.user)}</Text>
                  <Text style={[text(12.5, '500', N.t2), { marginTop: 3 }]}>
                    {r.right} bonne{r.right > 1 ? 's' : ''} réponse{r.right > 1 ? 's' : ''} sur {r.played}
                  </Text>
                </View>
                <Text style={num(17, N.lemon)}>{r.points}</Text>
              </View>
            ))}
          </View>
        </>
      )}
      {data.manage && data.rows.length ? (
        <ConfirmButton small label="Remettre le classement à zéro" confirmLabel="Oui, repartir de zéro"
          onConfirm={async () => { await rpc('prono_board_reset', { group_id: groupId }); reload(); }} />
      ) : null}
    </View>
  );
}
