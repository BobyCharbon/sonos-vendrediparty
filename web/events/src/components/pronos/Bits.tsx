import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import {
  alpha, AvatarStack, Countdown, CoverBand, FieldLine, PatateBadge, PronoAvatar, pronoFont, pronoMotion, Seal, SealRow, useAnim,
  usePronoTheme, useReducedMotion, web,
} from '@/components/pronos/Kit';
import { plural } from '@/lib/format';
import { awardLabel, NO_VALUE, pointsLabel, showPatates, type Board, type Face, type PronoCard as Card } from '@/lib/pronos';

/** Rappel « Les patates n'ont aucune valeur… » (le composant vit dans Kit.tsx). */
export { NoValueNote } from '@/components/pronos/Kit';

/**
 * Pièces communes des Pronos, au style C « Néon club » (v2, 18.11) : carte de liste (couverture du groupe, question en
 * ui-rounded, sceaux de ceux qui ont joué, compte à rebours), pastille d'état, boîte « réponse scellée », rangée de
 * visages, podium et lignes du classement aux points. Les nouvelles pièces sont dans Kit.tsx.
 */

export const LAV = '#B9A7FF';
export const LEMON = '#FFE27A';

type Tone = 'open' | 'closed' | 'done' | 'cancelled' | 'accent';

export function StateChip({ tone, label, style }: { tone: Tone; label: string; style?: StyleProp<ViewStyle> }) {
  const c = usePronoTheme();
  const t = {
    open: { bg: alpha(c.lavA, 0.16), fg: c.lav, bd: alpha(c.lavA, 0.3) },
    closed: { bg: alpha(c.amber, 0.14), fg: c.amberInk, bd: alpha(c.amber, 0.35) },
    done: { bg: alpha(c.mint, 0.14), fg: c.mintInk, bd: alpha(c.mint, 0.4) },
    cancelled: { bg: c.s3, fg: c.t2, bd: c.line },
    accent: { bg: c.pinkFill, fg: '#FFFFFF', bd: c.pinkFill },
  }[tone];
  return (
    <View style={[st.chip, { backgroundColor: t.bg, borderColor: t.bd }, style]}>
      <Text style={[pronoFont.bold, { color: t.fg, fontSize: 12, letterSpacing: 0.2 }]}>{label}</Text>
    </View>
  );
}

export function cardChip(p: Card): { tone: Tone; label: string } {
  if (p.state === 'open') return p.answered ? { tone: 'open', label: '🔒 Réponse scellée · tu as joué' } : { tone: 'accent', label: '🔮 À toi de jouer' };
  if (p.state === 'closed') return p.mine ? { tone: 'closed', label: '⏳ Donne le résultat' } : { tone: 'closed', label: '⏳ Résultat attendu' };
  if (p.state === 'done') return p.won ? { tone: 'done', label: '🔮 Tu l’avais vu' } : { tone: 'done', label: '🏆 Terminé' };
  return { tone: 'cancelled', label: 'Annulé' };
}

/** Visages qui se chevauchent (qui a joué, les gagnants). */
export function Faces({ faces, size = 26, ring }: { faces: Face[]; size?: number; ring?: string }) {
  return <AvatarStack faces={faces} size={size} max={faces.length} ring={ring} />;
}

/** Carte d'un prono dans une liste (maquette 1-liste) : couverture, question, champ ou points, sceaux, compte à rebours. */
export function PronoCardView({ p, onPress, index = 0, showPlace = true }: { p: Card; onPress: () => void; index?: number; showPlace?: boolean }) {
  const c = usePronoTheme();
  const reduced = useReducedMotion();
  const rise = useAnim('rise', Math.min(index, 6) * pronoMotion.stagger);
  const chip = cardChip(p);
  const patates = showPatates(p);
  const award = p.kind === 'award';
  const winners = p.winners ?? [];
  const others = Math.max(0, p.answered_count - p.faces.length);
  const missed = p.state === 'done' && p.answered && !p.won;
  const glow = p.state === 'open' && !p.answered && p.closes_soon ? 'urgent' : p.state === 'done' && p.won ? 'won' : null;
  const verb = award ? 'ont voté' : 'ont joué';
  const context = showPlace ? (p.group ? `${p.group.emoji} ${p.group.name}` : p.event ? `📅 ${p.event.title}` : null) : null;
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${p.question}, ${chip.label}`} testID={`prono-card-${p.id}`} onPress={onPress}
      style={({ pressed }) => [st.card, { backgroundColor: c.s1, borderColor: c.line }, web({ boxShadow: c.cardShadow }),
        glow === 'urgent' && web({ borderColor: alpha(c.pink, 0.5), boxShadow: `0 0 0 1px ${alpha(c.pink, 0.18)}, 0 22px 50px -22px ${alpha(c.pink, 0.75)}` }),
        glow === 'won' && web({ borderColor: alpha(c.mint, 0.42), boxShadow: `0 0 0 1px ${alpha(c.mint, 0.12)}, 0 22px 50px -26px ${alpha(c.mint, 0.6)}` }),
        rise, reduced ? null : web({ transitionProperty: 'transform', transitionDuration: '350ms', transitionTimingFunction: pronoMotion.spring }),
        pressed && { transform: [{ scale: 0.97 }] }]}>
      <CoverBand group={p.group} event={p.event} cover={p.cover} context={context} kind={p.kind}
        style={missed ? web({ filter: 'saturate(.25) brightness(.85)' }) : p.state === 'done' ? web({ filter: 'saturate(.75)' }) : undefined} />
      <View style={st.body}>
        <Text style={[pronoFont.round, st.q, { color: c.t1 }]}>
          {award && p.award_emoji ? `${p.award_emoji} ` : ''}{award ? awardLabel(p, false) || p.question : p.question}
        </Text>
        <View style={st.meta}>
          {patates && p.field_total != null ? <FieldLine total={p.field_total} /> : (
            <Text style={[pronoFont.text, { color: c.t2, fontSize: 13 }]}>
              Pour l’honneur · {award ? 'dévoilé dès 3 votes' : pointsLabel(p.points)}
            </Text>
          )}
        </View>
      </View>
      <View style={[st.foot, { borderTopColor: c.line }]}>
        {p.state === 'done' && winners.length ? (
          <View style={st.who}>
            <AvatarStack faces={winners} extra={Math.max(0, (p.winners_count ?? winners.length) - winners.length)} />
            <Text numberOfLines={1} style={[pronoFont.semibold, { color: c.t2, fontSize: 13, flexShrink: 1 }]}>
              {winners.length === 1 && (p.winners_count ?? 1) === 1
                ? `${winners[0].me ? 'Tu l’avais' : `${winners[0].name} l’avait`} vu`
                : `${plural(p.winners_count ?? winners.length, 'a vu juste', 'ont vu juste')}`}
            </Text>
          </View>
        ) : p.state === 'done' || p.state === 'cancelled' ? (
          <Text style={[pronoFont.semibold, { color: c.t2, fontSize: 13, flex: 1 }]}>
            {p.state === 'cancelled' ? 'Annulé · tout est rendu' : award ? 'Trophée dévoilé' : 'Personne n’avait vu juste'}
          </Text>
        ) : (
          <View style={st.who}>
            {p.answered && !award ? <SealRow faces={p.faces} total={p.answered_count} me color={p.cover?.color ?? p.group?.color} max={4} />
              : p.faces.length ? <AvatarStack faces={p.faces} extra={others} /> : null}
            {!p.answered || award ? (
              <Text numberOfLines={1} style={[pronoFont.semibold, { color: c.t2, fontSize: 13, flexShrink: 1 }]}>
                {p.answered_count ? <Text style={[pronoFont.bold, { color: c.t1 }]}>{p.answered_count} </Text> : null}
                {p.answered_count ? verb : 'Personne n’a encore joué'}
              </Text>
            ) : null}
          </View>
        )}
        {p.state === 'open' || (p.state === 'closed' && !p.mine) ? <Countdown variant="chip" closesAt={p.closes_at} />
          : p.state === 'closed' ? <StateChip tone="accent" label="⏳ Donne le résultat" />
            : p.state === 'done' && p.won && patates && p.my_harvest ? <PatateBadge n={p.my_harvest} tone="win" sign />
              : p.state === 'done' ? <StateChip tone={p.won ? 'done' : 'cancelled'} label={p.won ? '🔮 Tu l’avais vu' : 'Terminé'} /> : null}
      </View>
    </Pressable>
  );
}

/** « Ta réponse est scellée… » : sceau + texte (réponse cachée jusqu'à la fin). */
export function SealBox({ title, children }: { title: string; children: ReactNode }) {
  const c = usePronoTheme();
  return (
    <View style={[st.seal, { backgroundColor: c.s3, borderColor: c.line }]}>
      <Seal emoji="🔒" color="lavender" size={40} lock={false} label="Réponse scellée" />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={[pronoFont.bold, { color: c.t1, fontSize: 15, lineHeight: 20 }]}>{title}</Text>
        <Text style={[pronoFont.text, { color: c.t2, fontSize: 13, lineHeight: 18 }]}>{children}</Text>
      </View>
    </View>
  );
}

/** Rappel « pour l'honneur » (revue de conformité). */
export function HonourNote({ points }: { points?: number }) {
  const c = usePronoTheme();
  return (
    <View style={[st.honour, { backgroundColor: alpha(c.mint, 0.09), borderColor: alpha(c.mint, 0.3) }]}>
      <Text style={{ fontSize: 18 }}>🏅</Text>
      <Text style={[pronoFont.text, { flex: 1, color: c.t2, fontSize: 13, lineHeight: 18 }]}>
        <Text style={[pronoFont.bold, { color: c.t1 }]}>Pour l’honneur. </Text>
        {points ? `Une bonne réponse = ${pointsLabel(points)} au classement du groupe. ` : 'Des points au classement du groupe, rien d’autre. '}
        {NO_VALUE}
      </Text>
    </View>
  );
}

// Podium 3-2-1 (maquette 4-classement) : 3e à gauche, 1er au centre, 2e à droite.
const PODIUM = [
  { place: 3, h: 92, top: '#FF8FC0', avatar: 64 },
  { place: 1, h: 168, top: '#FFE27A', avatar: 96 },
  { place: 2, h: 132, top: '#FF8FC0', avatar: 72 },
];

/** Classement du groupe aux points : podium des trois premiers puis la liste (ma ligne en avant). */
export function BoardView({ board }: { board: Board }) {
  const c = usePronoTheme();
  if (!board.rows.length) {
    return (
      <View style={[st.emptyBoard, { backgroundColor: c.s1, borderColor: c.line }]}>
        <Text style={{ fontSize: 34 }}>🏅</Text>
        <Text style={[pronoFont.roundBold, { color: c.t1, fontSize: 17 }]}>Pas encore de points</Text>
        <Text style={[pronoFont.text, { color: c.t2, fontSize: 13, textAlign: 'center' }]}>Le classement se remplit à chaque résultat donné.</Text>
      </View>
    );
  }
  const top = [board.rows[2], board.rows[0], board.rows[1]];
  return (
    <View style={{ gap: 12 }}>
      <View style={st.podium}>
        {PODIUM.map((spot, i) => {
          const r = top[i];
          if (!r) return <View key={spot.place} style={{ flex: 1 }} />;
          return (
            <PodiumSpot key={spot.place} spot={spot} name={r.user.me ? 'Toi' : r.user.name} face={r.user} index={i}
              value={`${r.points} pt${r.points > 1 ? 's' : ''}`} sub={`${r.right} juste${r.right > 1 ? 's' : ''} sur ${r.played}`} />
          );
        })}
      </View>
      <View style={[st.rows, { backgroundColor: c.s1, borderColor: c.line }]}>
        {board.rows.map((r, i) => (
          <View key={r.user.id} style={[st.lrow, i > 0 && { borderTopWidth: 1, borderTopColor: c.line },
            r.user.me && [{ backgroundColor: alpha(c.lavB, 0.16), borderColor: alpha(c.lavA, 0.5), borderWidth: 1.5, borderRadius: 18 }]]}>
            <Text style={[pronoFont.num, { width: 24, color: c.t2, fontSize: 17 }]}>{i + 1}</Text>
            <PronoAvatar face={r.user} size={40} ring={r.user.me ? c.lavA : undefined} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text numberOfLines={1} style={[pronoFont.roundBold, { color: c.t1, fontSize: 17 }]}>{r.user.me ? 'Toi' : r.user.name}</Text>
              <Text style={[pronoFont.text, { color: c.t2, fontSize: 13 }]}>
                {r.right} bonne{r.right > 1 ? 's' : ''} réponse{r.right > 1 ? 's' : ''} sur {r.played}
              </Text>
            </View>
            <Text style={[pronoFont.num, { color: c.goldInk, fontSize: 19 }]}>{r.points}<Text style={[pronoFont.semibold, { fontSize: 13, color: c.t2 }]}> pt{r.points > 1 ? 's' : ''}</Text></Text>
          </View>
        ))}
      </View>
    </View>
  );
}

function PodiumSpot({ spot, name, face, value, sub, index }: {
  spot: (typeof PODIUM)[number]; name: string; face: Face; value: string; sub: string; index: number;
}) {
  const c = usePronoTheme();
  const pop = useAnim('pop', 120 + index * 120);
  const rise = useAnim('rise', index * 80);
  const first = spot.place === 1;
  return (
    <View style={{ flex: 1, alignItems: 'center' }}>
      {first ? <Text aria-hidden style={{ fontSize: 30, marginBottom: -10, zIndex: 2 }}>👑</Text> : null}
      <View style={[pop, first && web({ borderRadius: 999, boxShadow: `0 0 0 3px ${LEMON}, 0 0 28px ${alpha(LEMON, 0.55)}` })]}>
        <PronoAvatar face={face} size={spot.avatar} />
      </View>
      <Text numberOfLines={1} style={[pronoFont.roundBold, { color: c.t1, fontSize: 17, marginTop: 8 }]}>{name}</Text>
      <Text style={[pronoFont.num, { color: c.goldInk, fontSize: 19 }]}>{value}</Text>
      <Text style={[pronoFont.text, { color: c.t2, fontSize: 12.5, marginBottom: 8 }]}>{sub}</Text>
      <View style={[{ alignSelf: 'stretch', height: spot.h - spot.avatar / 2, minHeight: 64, borderTopLeftRadius: 16, borderTopRightRadius: 16,
        borderBottomLeftRadius: 4, borderBottomRightRadius: 4, borderWidth: 1, borderColor: c.line, borderTopWidth: 3, borderTopColor: spot.top,
        alignItems: 'center', paddingTop: 8 }, web({ backgroundImage: `linear-gradient(180deg, ${c.s1b}, ${c.bg})` }), rise]}>
        <Text style={[pronoFont.num, { color: first ? c.goldInk : c.t1, fontSize: 44, lineHeight: 50 }]}>{spot.place}</Text>
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  chip: { alignSelf: 'flex-start', height: 26, paddingHorizontal: 10, borderRadius: 13, justifyContent: 'center', borderWidth: 1 },
  card: { borderRadius: 24, borderWidth: 1, overflow: 'hidden' },
  body: { paddingTop: 2, paddingHorizontal: 18, paddingBottom: 14 },
  q: { fontSize: 22, lineHeight: 26, letterSpacing: -0.2 },
  meta: { marginTop: 6, flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' },
  foot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, borderTopWidth: 1, marginHorizontal: 18,
    paddingTop: 12, paddingBottom: 14, minHeight: 56 },
  who: { flexDirection: 'row', alignItems: 'center', gap: 10, flex: 1, minWidth: 0 },
  seal: { flexDirection: 'row', gap: 12, alignItems: 'center', padding: 12, paddingLeft: 14, borderRadius: 16, borderWidth: 1 },
  honour: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', padding: 12, borderRadius: 14, borderWidth: 1 },
  emptyBoard: { alignItems: 'center', gap: 6, padding: 24, borderRadius: 24, borderWidth: 1 },
  podium: { flexDirection: 'row', alignItems: 'flex-end', gap: 12, marginTop: 10 },
  rows: { borderRadius: 24, borderWidth: 1, padding: 6 },
  lrow: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingVertical: 10, paddingHorizontal: 12 },
});
