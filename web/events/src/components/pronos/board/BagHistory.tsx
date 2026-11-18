import type { ReactNode } from 'react';
import { Text, View } from 'react-native';

import { ErrorText, Skeleton } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { formatLongDay, relativeDay } from '@/lib/format';
import { rpc } from '@/lib/pronos';

import { card, NoValueNote, SectionHead } from '../reveal/Bits';
import { K, useStage } from '../reveal/fx';
import { monthName } from '../reveal/model';
import { label, N, num, round, text, web } from '../reveal/theme';

/**
 * « Ton sac » (maquette 1-sac) : le solde dans une jauge ronde, la prochaine remontée du lundi, ce que la saison a
 * rendu, comment ça marche, et SON historique (60 derniers mouvements, `prono_bag_history`) : « 🔒 toi seul le vois »,
 * jamais d'export, jamais la ligne d'un autre. Le rappel « aucune valeur » est obligatoire. Contenu seul : la liste
 * (W2) le pose dans sa feuille. Sans terrain : tous mes sacs. Patates éteintes : rien.
 */

type Bag = { balance: number; refill_at: string | null; max_stake: number; season?: { month: string; harvest_net: number } } | null;
type Move = { at: string; delta: number; reason: 'start' | 'refill' | 'plant' | 'unplant' | 'refund' | 'harvest'; prono: { id: string; question: string | null } | null };

const REASON: Record<Move['reason'], { icon: string; label: string; tone: 'plus' | 'back' | 'plain' }> = {
  start: { icon: '🎒', label: 'Sac de départ', tone: 'plus' },
  refill: { icon: '↻', label: 'Remontée du lundi', tone: 'plus' },
  plant: { icon: '🎉', label: 'Lancés', tone: 'plain' },
  unplant: { icon: '↩', label: 'Repris', tone: 'back' },
  refund: { icon: '↩', label: 'Rendus', tone: 'back' },
  harvest: { icon: '🧺', label: 'Tu ramasses', tone: 'plus' },
};

const refillFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: 'Europe/Zurich', weekday: 'long', day: 'numeric', month: 'short' });
const dayKey = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Zurich', year: 'numeric', month: '2-digit', day: '2-digit' });

export function BagHistory({ groupId, eventId }: { groupId?: string; eventId?: string }) {
  const terrain = groupId || eventId ? { group_id: groupId ?? null, event_id: eventId ?? null } : null;
  const { data, error, loading } = useQuery(async () => {
    const [bag, moves, cards] = await Promise.all([
      terrain ? rpc<Bag>('prono_bag', terrain) : Promise.resolve(null),
      rpc<Move[]>('prono_bag_history', terrain ?? {}),
      rpc<{ id: string; settled?: boolean }[]>('prono_list', terrain ?? {}).catch(() => []),
    ]);
    const settled = new Set((cards ?? []).filter((c) => c.settled).map((c) => c.id));
    return { bag, moves: moves ?? [], composted: composted(moves ?? [], settled) };
  }, [groupId, eventId]);
  const { root } = useStage((s) => {
    s.a('arc', [{ opacity: 0, transform: 'rotate(-30deg)' }, { opacity: 1, transform: 'none' }], 0, 700, 'cubic-bezier(.22,1,.36,1)');
  }, 800, [data ? 'ok' : 'wait']);
  if (loading && !data) return <View style={{ gap: 12 }}><Skeleton height={196} /><Skeleton height={92} /><Skeleton height={240} /></View>;
  if (!data) return <ErrorText error={error ?? null} />;
  const bag = data.bag;
  if (terrain && !bag) {
    return <Text style={[text(14, '500', N.t2), { textAlign: 'center', padding: 24 }]}>Les confettis arrivent bientôt.</Text>;
  }
  const days = groupByDay(data.moves);
  const full = bag ? bag.balance >= 100 : false;
  const share = bag ? Math.max(0, Math.min(1, bag.balance / 100)) : 0;
  return (
    <View ref={root} testID="prono-bag">
      {bag ? (
        <>
          <View style={{ width: 196, height: 196, alignSelf: 'center', marginTop: 28 }} role="img" aria-label={`${bag.balance} confettis sur 100`}>
            <Text style={[text(11, '700', N.t3), { position: 'absolute', top: -20, alignSelf: 'center' }]}>100</Text>
            <View style={web({ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, borderRadius: 999, backgroundColor: N.line2,
              WebkitMask: 'radial-gradient(circle,transparent 84px,#000 85px)', mask: 'radial-gradient(circle,transparent 84px,#000 85px)' })} />
            <K k="arc" style={web({ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, borderRadius: 999,
              backgroundImage: `conic-gradient(from 0deg,#CBBDFF,#7B6CF6 ${share * 100}%,transparent 0)`,
              WebkitMask: 'radial-gradient(circle,transparent 84px,#000 85px)', mask: 'radial-gradient(circle,transparent 84px,#000 85px)' })} />
            <View style={web({ position: 'absolute', left: 20, top: 20, right: 20, bottom: 20, borderRadius: 999,
              backgroundImage: 'radial-gradient(circle,rgba(123,108,246,.22),transparent 70%)' })} />
            <View style={{ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, alignItems: 'center', justifyContent: 'center' }}>
              <Text style={[num(64), { lineHeight: 66 }]}>{bag.balance}</Text>
              <Text style={[text(13, '600', N.t2), { marginTop: 6 }]}>🎊 dans ton sac</Text>
            </View>
          </View>
          <View style={{ alignItems: 'center', marginTop: 16 }}>
            <View style={{ height: 32, paddingHorizontal: 14, borderRadius: 16, justifyContent: 'center', backgroundColor: 'rgba(185,167,255,0.12)',
              borderWidth: 1, borderColor: 'rgba(185,167,255,0.3)' }}>
              <Text style={text(13, '700', N.lav)}>
                {full ? 'Ton sac est plein' : bag.refill_at ? `↻ Remonte à 100 ${refillFmt.format(new Date(bag.refill_at))} à 0 h` : '↻ Remonte à 100 lundi'}
              </Text>
            </View>
          </View>
          {bag.season ? (
            <View style={{ flexDirection: 'row', gap: 8, marginTop: 20 }}>
              <Tile title="Ramassés" value={`${bag.season.harvest_net > 0 ? '+' : bag.season.harvest_net < 0 ? '−' : ''}${Math.abs(bag.season.harvest_net)} 🎊`}
                sub={`nets en ${monthName(bag.season.month)}`} color={bag.season.harvest_net > 0 ? N.mint : N.t1} />
              <Tile title="Par prono" value={`1 à ${bag.max_stake ?? 20} 🎊`} sub="à lancer, ou 0" />
            </View>
          ) : null}
        </>
      ) : null}

      <SectionHead left="Comment ça marche" />
      <View style={[card, { paddingHorizontal: 14, paddingVertical: 4, borderRadius: 20 }]}>
        <How icon="🎊" first><Text style={text(14, '700')}>100 confettis</Text> au départ, un sac par groupe et par soirée.</How>
        <How icon="↻">Chaque <Text style={text(14, '700')}>lundi</Text>, ton sac remonte à 100 s’il est plus bas.</How>
        <How icon="🎉">Lance <Text style={text(14, '700')}>1 à 20</Text> 🎊 par prono. Ceux qui voient juste se partagent la piste.</How>
      </View>

      <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', marginTop: 24, paddingHorizontal: 4 }}>
        <Text style={label()}>Ton historique</Text>
        <Text style={text(12, '600', N.t2)}>🔒 toi seul le vois</Text>
      </View>
      {days.length ? days.map(([day, moves]) => (
        <View key={day}>
          <Text style={[text(13, '700', N.t2), { paddingTop: 18, paddingBottom: 6, paddingHorizontal: 2 }]}>{dayTitle(moves[0].at)}</Text>
          <View style={[card, { borderRadius: 20, overflow: 'hidden' }]}>
            {moves.map((m, i) => {
              const r = REASON[m.reason] ?? REASON.plant;
              const lost = m.reason === 'plant' && !!m.prono && data.composted.has(m.prono.id);
              const color = r.tone === 'plus' ? N.mint : r.tone === 'back' ? N.lav : N.t1;
              const sub = m.prono ? m.prono.question ?? 'Prono masqué' : m.reason === 'refill' ? 'Ton sac est revenu à 100' : m.reason === 'start' ? 'Bienvenue sur la piste' : '';
              return (
                <View key={`${m.at}-${i}`} style={[{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, paddingHorizontal: 14 },
                  i > 0 && { borderTopWidth: 1, borderColor: N.line }]} testID={`prono-bag-move-${m.reason}`}>
                  <View style={{ width: 36, height: 36, borderRadius: 18, backgroundColor: N.s3, alignItems: 'center', justifyContent: 'center' }}>
                    <Text style={{ fontSize: 16, color: N.t1 }}>{r.icon}</Text>
                  </View>
                  <View style={{ flex: 1, minWidth: 0 }}>
                    <Text style={text(15, '600')}>{r.label}{lost ? ' · partis au balai' : ''}</Text>
                    {sub ? <Text style={text(13, '500', N.t2)} numberOfLines={1}>{sub}</Text> : null}
                  </View>
                  <Text style={[num(15, color), { minWidth: 44, textAlign: 'right' }]}>{m.delta > 0 ? `+${m.delta}` : `−${Math.abs(m.delta)}`}</Text>
                </View>
              );
            })}
          </View>
        </View>
      )) : <Text style={[text(13, '500', N.t2), { paddingTop: 12, paddingHorizontal: 4 }]}>Rien encore : lance tes premiers confettis sur un prono.</Text>}

      <NoValueNote boxed />
    </View>
  );
}

function Tile({ title, value, sub, color = N.t1 }: { title: string; value: string; sub: string; color?: string }) {
  return (
    <View style={{ flex: 1, padding: 12, borderRadius: 16, backgroundColor: N.s3, borderWidth: 1, borderColor: N.line, minHeight: 92, justifyContent: 'space-between' }}>
      <Text style={label()}>{title}</Text>
      <View>
        <Text style={[num(20, color), { lineHeight: 24 }]}>{value}</Text>
        <Text style={text(12, '500', N.t2)}>{sub}</Text>
      </View>
    </View>
  );
}

function How({ icon, children, first }: { icon: string; children: ReactNode; first?: boolean }) {
  return (
    <View style={[{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52 }, !first && { borderTopWidth: 1, borderColor: N.line }]}>
      <View style={{ width: 32, height: 32, borderRadius: 10, backgroundColor: N.s3, alignItems: 'center', justifyContent: 'center' }}>
        <Text style={{ fontSize: 15, color: N.t1 }}>{icon}</Text>
      </View>
      <Text style={[text(14, '500', N.t2), { flex: 1, lineHeight: 19 }]}>{children}</Text>
    </View>
  );
}

/** Pronos réglés où je n'ai rien récolté ni récupéré : mes plantations y sont parties au compost. */
function composted(moves: Move[], settled: Set<string>): Set<string> {
  const back = new Set(moves.filter((m) => m.prono && (m.reason === 'harvest' || m.reason === 'refund')).map((m) => m.prono!.id));
  return new Set(moves.filter((m) => m.reason === 'plant' && m.prono && settled.has(m.prono.id) && !back.has(m.prono.id)).map((m) => m.prono!.id));
}

function groupByDay(moves: Move[]): [string, Move[]][] {
  const m = new Map<string, Move[]>();
  for (const x of moves) {
    const k = dayKey.format(new Date(x.at));
    m.set(k, [...(m.get(k) ?? []), x]);
  }
  return [...m.entries()];
}

function dayTitle(iso: string): string {
  const r = relativeDay(iso);
  return r === 'Aujourd’hui' || r === 'Hier' ? r : formatLongDay(iso);
}

/** Titre de la feuille (la liste W2 peut s'en servir) : « Ton sac ». */
export function BagTitle() {
  return <Text style={[round(28, 32), { textAlign: 'center' }]}>Ton sac</Text>;
}
