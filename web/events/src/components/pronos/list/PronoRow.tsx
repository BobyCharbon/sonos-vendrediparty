import type { ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { Countdown, KindIcon } from '@/components/pronos/Kit';
import { enter, pressTransition } from '@/lib/motion';

import { answerText, C, round, web, withPatates, type Detail, type ListCard } from './model';
import { openPick, rarityLine } from './PronoCard';

/**
 * Rangée compacte d'un prono (maquettes 1-groupe « En attente » / « Terminés », 72 de haut, et 1-evenement, 56) :
 * pastille d'état (sceau, ✓ menthe, forme du type), question, ligne d'état, montant ou fin à droite.
 */
export function PronoRow({ p, d, push, compact = false, index = 0 }: {
  p: ListCard; d?: Detail; push: (path: string) => void; compact?: boolean; index?: number;
}) {
  const pat = withPatates(p);
  const stake = d?.my_answer?.stake ?? p.my_stake ?? 0;
  const harvest = d?.my_answer?.harvest ?? p.my_harvest;
  const unanimous = d?.unanimous ?? p.unanimous;
  const mine = d?.my_answer ? answerText(d, d.my_answer) : '';
  const done = p.state === 'done' || p.state === 'cancelled';
  const playable = p.state === 'open' && !p.answered;

  let icon = <KindIcon kind={p.kind} />;
  let tone = C.s3;
  if (p.answered && !done) { icon = <Text style={{ fontSize: 16 }}>🔒</Text>; tone = 'rgba(185,167,255,0.18)'; }
  else if (done && p.state === 'cancelled') icon = <Text style={{ color: C.miss, fontSize: 15 }}>⊘</Text>;
  else if (done && unanimous) icon = <Text style={{ fontSize: 18 }}>🤝</Text>;
  else if (done && p.won) { icon = <Text style={{ color: C.mint, fontSize: 18, fontWeight: '900' }}>✓</Text>; tone = 'rgba(91,227,166,0.14)'; }
  else if (done && p.kind === 'award') icon = <Text style={{ fontSize: 18 }}>🏆</Text>;

  const sub: string[] = [];
  if (playable) sub.push(p.kind === 'award' ? 'Vote pour le trophée' : `${p.answered_count} ${p.answered_count > 1 ? 'ont' : 'a'} joué`);
  else if (!done) {
    sub.push('Scellé');
    if (mine) sub.push(mine);
    if (pat && stake) sub.push(`${stake} 🥔`);
    if (p.state === 'closed') sub.push(p.mine ? 'à toi de trancher' : `${p.creator.me ? 'toi' : p.creator.name} tranche`);
  } else if (p.state === 'cancelled') sub.push('Annulé');
  else {
    const right = d ? answerText(d, d.result) : '';
    if (right) sub.push(right);
    if (unanimous) sub.push('Unanimes ! tout est rendu');
    else if (p.won && d?.rarity) sub.push(`★ ${rarityLine(d.rarity)}`);
    else if (!p.won && p.answered && mine) sub.push(`ta réponse : ${mine}`);
  }

  let right: ReactNode = null;
  if (playable) right = <Text style={{ color: C.pinkInk, fontSize: 13, fontWeight: '700' }}>{p.kind === 'award' ? 'À voter' : 'À jouer'}</Text>;
  else if (compact && !done && mine) right = <Text style={{ color: C.t2, fontSize: 13, fontWeight: '700' }}>🔒 {mine}</Text>;
  else if (p.state === 'open') right = <Countdown closesAt={p.closes_at} />;
  else if (p.state === 'closed') right = <View style={st.pill}><Text style={st.pillText}>🔒</Text></View>;
  else if (unanimous && pat && stake) right = <View style={[st.pill, st.lav]}><Text style={[st.pillText, { color: C.lav }]}>↩ {stake} 🥔</Text></View>;
  else if (p.won && pat && harvest != null) right = <View style={[st.pill, st.mint]}><Text style={[st.pillText, { color: C.mint }]}>+{harvest} 🥔</Text></View>;
  else if (p.won && !pat) right = <View style={[st.pill, st.mint]}><Text style={[st.pillText, { color: C.mint }]}>+{p.points} pt{p.points > 1 ? 's' : ''}</Text></View>;
  else if (done && pat && p.answered && stake && p.state === 'done') {
    right = <View style={st.pill}><Text style={[st.pillText, { color: C.miss }]}>{stake} 🥔</Text><Text style={{ color: C.miss, fontSize: 11 }}>au compost</Text></View>;
  }

  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${p.question}. ${sub.join(', ')}`} testID={`prono-card-${p.id}`}
      onPress={() => openPick(p.id, null, push)}
      style={({ pressed }) => [st.row, compact && st.rowCompact, enter('rise', index), pressTransition, pressed && { opacity: 0.85 }]}>
      <View style={[st.icon, compact && st.iconCompact, { backgroundColor: tone }]}>{icon}</View>
      <View style={{ flex: 1, gap: 2 }}>
        <Text numberOfLines={2} style={compact ? { color: C.t1, fontSize: 15, lineHeight: 19, fontWeight: '600' } : round(16, 20)}>{p.question}</Text>
        {!compact && sub.length ? <Text numberOfLines={2} style={st.sub}>{sub.join(' · ')}</Text> : null}
      </View>
      {right}
    </Pressable>
  );
}

export function RowList({ children }: { children: ReactNode }) {
  return <View style={st.list}>{children}</View>;
}

const st = StyleSheet.create({
  list: web({ borderRadius: 24, backgroundColor: C.s1, borderWidth: 1, borderColor: C.line, overflow: 'hidden',
    boxShadow: '0 1px 0 rgba(255,255,255,.04) inset, 0 18px 40px -24px rgba(0,0,0,.8)' }),
  row: { minHeight: 72, flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 16, paddingVertical: 12,
    borderBottomWidth: 1, borderBottomColor: C.line },
  rowCompact: { minHeight: 56, paddingVertical: 10, gap: 12 },
  icon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center', borderWidth: 1, borderColor: C.line },
  iconCompact: { width: 32, height: 32, borderRadius: 10 },
  sub: { color: C.t2, fontSize: 13, lineHeight: 18, fontWeight: '500' },
  pill: { minHeight: 32, paddingHorizontal: 12, paddingVertical: 4, borderRadius: 16, alignItems: 'center', justifyContent: 'center',
    borderWidth: 1, borderColor: C.line2, backgroundColor: C.s3 },
  pillText: { color: C.t2, fontSize: 14, fontWeight: '800', fontVariant: ['tabular-nums'] },
  mint: { borderColor: 'rgba(91,227,166,0.4)', backgroundColor: 'rgba(91,227,166,0.1)' },
  lav: { borderColor: 'rgba(185,167,255,0.4)', backgroundColor: 'rgba(185,167,255,0.1)' },
});
