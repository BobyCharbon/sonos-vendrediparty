import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { loop } from '@/components/GroupBits';
import { Avatar, T } from '@/components/ui';
import { plural } from '@/lib/format';
import { enter, pressTransition } from '@/lib/motion';
import { placeLine, pointsLabel, stateLine, type Board, type Face, type PronoCard as Card } from '@/lib/pronos';
import { colors, font, radius } from '@/lib/theme';

/**
 * Pièces communes des Pronos (maquette du 17.11) : carte de liste (état, visages de ceux qui ont joué, gagnants),
 * pastille d'état, boîte « réponse cachée », rangée de visages, podium et lignes du classement.
 */

type WebStyle = ViewStyle & Record<string, unknown>;
const web = (style: WebStyle) => style as ViewStyle;

export const LAV = '#B9A7FF';
export const LEMON = '#FFE27A';

const CHIPS = {
  open: { bg: 'rgba(185,167,255,0.16)', fg: LAV },
  closed: { bg: 'rgba(255,179,71,0.16)', fg: colors.coral },
  done: { bg: 'rgba(91,227,166,0.16)', fg: colors.mint },
  cancelled: { bg: colors.fill, fg: colors.muted },
  accent: { bg: colors.action, fg: colors.onAction },
};

export function StateChip({ tone, label, style }: { tone: keyof typeof CHIPS; label: string; style?: StyleProp<ViewStyle> }) {
  const c = CHIPS[tone];
  return (
    <View style={[st.chip, { backgroundColor: c.bg }, style]}>
      <Text style={{ color: c.fg, fontSize: 12, ...font.bold, letterSpacing: 0.2 }}>{label}</Text>
    </View>
  );
}

export function cardChip(p: Card): { tone: keyof typeof CHIPS; label: string } {
  if (p.state === 'open') return p.answered ? { tone: 'open', label: '🔒 Réponse cachée · tu as joué' } : { tone: 'accent', label: '🔮 À toi de jouer' };
  if (p.state === 'closed') return p.mine ? { tone: 'closed', label: '⏳ Donne le résultat' } : { tone: 'closed', label: '⏳ Résultat attendu' };
  if (p.state === 'done') return p.won ? { tone: 'done', label: '🏆 Tu avais vu juste' } : { tone: 'done', label: '🏆 Terminé' };
  return { tone: 'cancelled', label: 'Annulé' };
}

/** Visages qui se chevauchent (qui a joué, les gagnants). */
export function Faces({ faces, size = 26, ring = colors.surface }: { faces: Face[]; size?: number; ring?: string }) {
  return (
    <View style={{ flexDirection: 'row' }} accessibilityLabel={faces.map((f) => (f.me ? 'toi' : f.name)).join(', ')}>
      {faces.map((f, i) => (
        <View key={f.id} style={{ marginLeft: i ? -size * 0.3 : 0, borderRadius: 999, borderWidth: 2, borderColor: ring }}>
          <Avatar id={f.id} name={f.name} photo={f.avatar_url} size={size} profile={false} />
        </View>
      ))}
    </View>
  );
}

/** Carte d'un prono dans une liste. */
export function PronoCardView({ p, onPress, index = 0, showPlace = true }: { p: Card; onPress: () => void; index?: number; showPlace?: boolean }) {
  const chip = cardChip(p);
  const winners = p.winners ?? [];
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${p.question}, ${chip.label}`} testID={`prono-card-${p.id}`} onPress={onPress}
      style={({ pressed }) => [st.card, p.state === 'open' && !p.answered && st.cardHot, enter('rise', index), pressTransition,
        pressed && { transform: [{ scale: 0.98 }], opacity: 0.92 }]}>
      <View style={st.cardTop}>
        <StateChip tone={chip.tone} label={chip.label} />
        <T size={12} muted>{stateLine(p)}</T>
      </View>
      <T weight="bold" size={17} style={{ lineHeight: 22 }}>{p.question}</T>
      {showPlace ? <T size={13} muted numberOfLines={1}>{placeLine(p)} · {pointsLabel(p.points)}</T> : null}
      {p.state === 'done' && winners.length ? (
        <View style={st.row}>
          <Faces faces={winners} />
          <T size={13} weight="semibold" style={{ flex: 1 }}>
            {winners.length === 1 ? `${winners[0].me ? 'Toi' : winners[0].name} avai${winners[0].me ? 's' : 't'} vu juste`
              : `${plural(p.winners_count ?? winners.length, 'gagnant')}`} · +{p.points}
          </T>
        </View>
      ) : p.state === 'done' ? (
        <T size={13} muted>Personne n’avait vu juste.</T>
      ) : (
        <View style={st.row}>
          {p.faces.length ? <Faces faces={p.faces} /> : null}
          <T size={13} muted style={{ flex: 1 }}>{p.answered_count} sur {p.players} ont joué</T>
        </View>
      )}
      {p.state === 'open' ? (
        <View style={st.track}><View style={[st.fill, { width: `${Math.min(100, (p.answered_count / Math.max(1, p.players)) * 100)}%` }, enter('grow', index)]} /></View>
      ) : null}
    </Pressable>
  );
}

/** « Ta réponse reste cachée… » : cadenas qui flotte. */
export function SealBox({ title, children }: { title: string; children: ReactNode }) {
  return (
    <View style={st.seal}>
      <View style={[st.lock, loop('floaty')]}><Text style={{ fontSize: 20 }}>🔒</Text></View>
      <View style={{ flex: 1, gap: 2 }}>
        <T weight="bold" size={15}>{title}</T>
        <T size={13} muted>{children}</T>
      </View>
    </View>
  );
}

/** Rappel « pour l'honneur » (revue de conformité). */
export function HonourNote({ points }: { points?: number }) {
  return (
    <View style={st.honour}>
      <Text style={{ fontSize: 18 }}>🏅</Text>
      <T size={13} color={colors.textSoft} style={{ flex: 1 }}>
        <Text style={{ color: colors.text, ...font.bold }}>Pour l’honneur. </Text>
        {points ? `Une bonne réponse = ${pointsLabel(points)} au classement du groupe. ` : 'Des points au classement du groupe, rien d’autre. '}
        Aucun argent, aucune mise, aucun lot.
      </T>
    </View>
  );
}

const PODIUM = [
  { place: 2, h: 70, bg: 'linear-gradient(180deg,#E8E4F5,#B1A8CF)' },
  { place: 1, h: 96, bg: 'linear-gradient(180deg,#FFEA9C,#FFB347)' },
  { place: 3, h: 54, bg: 'linear-gradient(180deg,#FFC2A8,#FF7A59)' },
];

/** Classement du groupe : podium des trois premiers puis la liste, aux points seulement. */
export function BoardView({ board }: { board: Board }) {
  if (!board.rows.length) {
    return (
      <View style={st.emptyBoard}>
        <Text style={{ fontSize: 34 }}>🏅</Text>
        <T weight="bold">Pas encore de points</T>
        <T muted size={13} style={{ textAlign: 'center' }}>Le classement se remplit à chaque résultat donné.</T>
      </View>
    );
  }
  const top = [board.rows[1], board.rows[0], board.rows[2]];
  return (
    <View style={{ gap: 8 }}>
      <View style={st.podium}>
        {PODIUM.map((spot, i) => {
          const r = top[i];
          if (!r) return <View key={spot.place} style={{ width: 96 }} />;
          return (
            <View key={spot.place} style={{ width: 96, alignItems: 'center', gap: 6 }}>
              <View style={[spot.place === 1 && st.crown, enter('pop', i + 1)]}>
                <Avatar id={r.user.id} name={r.user.name} photo={r.user.avatar_url} size={50} profile={false} />
              </View>
              <T size={13} weight="bold" numberOfLines={1}>{r.user.me ? 'Toi' : r.user.name}{spot.place === 1 ? ' 👑' : ''}</T>
              <View style={[st.step, { height: spot.h }, web({ backgroundImage: spot.bg }), enter('rise', i + 1)]}>
                <Text style={st.stepText}>{spot.place}</Text>
              </View>
            </View>
          );
        })}
      </View>
      {board.rows.map((r, i) => (
        <View key={r.user.id} style={[st.lrow, r.user.me && st.lrowMe, enter('rise', i)]}>
          <Text style={st.rank}>{i + 1}</Text>
          <Avatar id={r.user.id} name={r.user.name} photo={r.user.avatar_url} size={34} profile={false} />
          <View style={{ flex: 1 }}>
            <T weight="semibold">{r.user.me ? 'Toi' : r.user.name}</T>
            <T size={12} muted>{r.right} bonne{r.right > 1 ? 's' : ''} réponse{r.right > 1 ? 's' : ''} sur {r.played}</T>
          </View>
          <Text style={st.pts}>{r.points}</Text>
        </View>
      ))}
    </View>
  );
}

const st = StyleSheet.create({
  chip: { alignSelf: 'flex-start', height: 24, paddingHorizontal: 9, borderRadius: 12, justifyContent: 'center' },
  card: { backgroundColor: colors.surface, borderRadius: radius.lg, padding: 14, gap: 8, borderWidth: 1, borderColor: colors.line },
  cardHot: { borderColor: 'rgba(255,79,154,0.55)', shadowColor: colors.accent, shadowOpacity: 0.3, shadowRadius: 16, shadowOffset: { width: 0, height: 0 } },
  cardTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  track: { height: 6, borderRadius: 3, backgroundColor: colors.fill, overflow: 'hidden' },
  fill: web({ height: 6, borderRadius: 3, backgroundImage: `linear-gradient(90deg, ${LAV}, ${colors.accent})`, backgroundColor: colors.accent }),
  seal: { flexDirection: 'row', gap: 12, alignItems: 'center', padding: 14, borderRadius: 16, backgroundColor: 'rgba(185,167,255,0.10)',
    borderWidth: 1, borderColor: 'rgba(185,167,255,0.35)' },
  lock: web({ width: 42, height: 42, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: '#7B6CF6',
    backgroundImage: 'linear-gradient(135deg,#CBBDFF,#7B6CF6)' }),
  honour: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', padding: 12, borderRadius: 14, backgroundColor: 'rgba(91,227,166,0.09)',
    borderWidth: 1, borderColor: 'rgba(91,227,166,0.3)' },
  emptyBoard: { alignItems: 'center', gap: 6, padding: 24, borderRadius: radius.lg, backgroundColor: colors.surface },
  podium: { flexDirection: 'row', alignItems: 'flex-end', justifyContent: 'center', gap: 10, marginVertical: 10 },
  crown: { borderRadius: 999, borderWidth: 3, borderColor: LEMON, shadowColor: LEMON, shadowOpacity: 0.6, shadowRadius: 14, shadowOffset: { width: 0, height: 0 } },
  step: { width: 96, borderTopLeftRadius: 14, borderTopRightRadius: 14, borderBottomLeftRadius: 4, borderBottomRightRadius: 4,
    alignItems: 'center', justifyContent: 'center' },
  stepText: { color: colors.bg, fontSize: 26, ...font.display },
  lrow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 10, borderRadius: 14, backgroundColor: colors.surface },
  lrowMe: { borderWidth: 1.5, borderColor: colors.accent },
  rank: { width: 22, color: colors.muted, fontSize: 15, ...font.display },
  pts: { color: LEMON, fontSize: 17, ...font.bold },
});
