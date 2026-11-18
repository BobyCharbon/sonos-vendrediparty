import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AvatarStack, Countdown, KindIcon, kindLabel, SealRow } from '@/components/pronos/Kit';
import { Avatar } from '@/components/ui';
import { plural, relativeDay } from '@/lib/format';
import { enter, pressTransition } from '@/lib/motion';
import { errorText, nativePronos, rpc } from '@/lib/pronos';

import { answerText, C, clock, contextLine, coverOf, inTime, label, num, round, shape, untilLine, useNow, web, withPatates, type Detail, type ListCard } from './model';

/**
 * Carte d'un prono dans « Mes pronos » et la page du groupe (maquette 1-liste) : couverture du groupe (64), question,
 * champ de patates, aperçu jouable (pastilles à formes, Oui / Non, visages) qui ouvre la fiche avec le choix
 * présélectionné (jamais de réponse directe : on choisit les patates sur la fiche), sceaux, compte à rebours, résultat.
 */

type Push = (path: string) => void;

/** Ouvrir la fiche, choix présélectionné (`?pick=`) ; app iPhone : écran natif. */
export function openPick(id: string, pick: string | null, push: Push): void {
  const native = nativePronos();
  if (native) native.open(id);
  else push(pick ? `/prono/${id}?pick=${encodeURIComponent(pick)}` : `/prono/${id}`);
}

export function PronoCard({ p, d, index = 0, push, showContext = true, onChanged }: {
  p: ListCard; d?: Detail; index?: number; push: Push; showContext?: boolean; onChanged?: () => void;
}) {
  const pat = withPatates(p);
  const playable = p.state === 'open' && !p.answered;
  const done = p.state === 'done' || p.state === 'cancelled';
  const now = useNow();
  const urgent = playable && new Date(p.closes_at).getTime() - now < 60_000;
  const won = done && p.won;
  const open = () => openPick(p.id, null, push);
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={`${p.question}, ${stateWords(p)}`} testID={`prono-card-${p.id}`} onPress={open}
      style={({ pressed }) => [st.card, urgent && st.urgent, won && st.won, enter('rise', index), pressTransition,
        pressed && { transform: [{ scale: 0.97 }] }]}>
      {showContext ? <CardCover p={p} /> : (
        <View style={st.kindLine}>
          <KindIcon kind={p.kind} />
          <Text style={[label, { color: C.pinkInk }]}>{kindLabel(p.kind)}</Text>
          <Text style={st.by}>· par {p.creator.me ? 'toi' : p.creator.name}</Text>
        </View>
      )}
      <View style={st.body}>
        <Text style={round(22, 26)}>{p.question}</Text>
        <Meta p={p} d={d} pat={pat} />
        {playable ? <Preview p={p} d={d} push={push} /> : null}
        {!playable && !done ? <Sealed p={p} d={d} pat={pat} push={push} onChanged={onChanged} /> : null}
        {done ? <Outcome p={p} d={d} pat={pat} /> : null}
      </View>
      <Foot p={p} d={d} pat={pat} now={now} />
    </Pressable>
  );
}

function stateWords(p: ListCard): string {
  if (p.state === 'open') return p.answered ? 'réponse scellée' : 'à jouer';
  if (p.state === 'closed') return 'fermé, résultat attendu';
  if (p.state === 'cancelled') return 'annulé';
  return p.won ? 'tu avais vu juste' : 'terminé';
}

// ───────── Couverture ─────────
export function CardCover({ p, height = 64 }: { p: ListCard; height?: number }) {
  const { pal, emoji } = coverOf(p);
  return (
    <View style={[st.cover, { height }, web({ backgroundImage: `linear-gradient(135deg, ${pal.from}, ${pal.to})`, backgroundColor: pal.to })]}>
      <Text aria-hidden style={st.fili}>{emoji}</Text>
      <View style={[st.coverFade, web({ backgroundImage: `linear-gradient(to bottom, transparent, ${C.s1})` })]} />
      <View style={st.ctx}><Text numberOfLines={1} style={st.ctxText}>{contextLine(p)}</Text></View>
      <View style={st.kind}><KindIcon kind={p.kind} /><Text style={st.kindText}>{kindLabel(p.kind)}</Text></View>
    </View>
  );
}

function Meta({ p, d, pat }: { p: ListCard; d?: Detail; pat: boolean }) {
  const bits: ReactNode[] = [];
  const field = d?.field?.total ?? p.field_total;
  const planters = d?.field?.planters ?? p.planters;
  if (pat && field != null) bits.push(<Text key="f" style={st.metaText}>🥔 <Text style={st.metaB}>{field}</Text> dans le champ</Text>);
  if (pat && planters != null) bits.push(<Text key="p" style={st.metaText}>{plural(planters, 'planteur')}</Text>);
  if (p.kind === 'award') bits.push(<Text key="h" style={st.metaText}>Pour l’honneur</Text>, <Text key="v" style={st.metaText}>dévoilé dès 3 votes</Text>);
  else if (p.kind === 'majority') bits.push(<Text key="m" style={st.metaText}>La réponse la plus choisie l’emporte</Text>);
  else if (p.kind === 'number' || p.kind === 'when') bits.push(<Text key="n" style={st.metaText}>le plus proche l’emporte</Text>);
  if (d?.not_over) bits.push(<Text key="o" style={st.metaText}>sans dépasser</Text>);
  if (!pat && p.kind !== 'award') bits.push(<Text key="pt" style={st.metaText}>{plural(p.points, 'pt')}</Text>);
  return (
    <View style={st.meta}>
      {bits.map((b, i) => (i ? [<View key={`d${i}`} style={st.dot} />, b] : b))}
    </View>
  );
}

// ───────── À jouer : aperçu jouable ─────────
export function Preview({ p, d, push }: { p: ListCard; d?: Detail; push: Push }) {
  const pick = (choice: string | null) => openPick(p.id, choice, push);
  if (!d) return null;
  if (p.kind === 'yesno' && d.options.length >= 2) {
    const yes = d.options.find((o) => /^oui$/i.test(o.label)) ?? d.options[0];
    const no = d.options.find((o) => /^non$/i.test(o.label)) ?? d.options[1];
    return (
      <View style={st.yn}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Oui : ouvrir la fiche avec Oui choisi`} testID="prono-pick-yes" onPress={() => pick(yes.id)}
          style={({ pressed }) => [st.ynBtn, st.yes, pressTransition, pressed && st.pressed]}>
          <Text style={[st.ynText, { color: C.mint }]}>✓  Oui</Text>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={`Non : ouvrir la fiche avec Non choisi`} testID="prono-pick-no" onPress={() => pick(no.id)}
          style={({ pressed }) => [st.ynBtn, st.no, pressTransition, pressed && st.pressed]}>
          <Text style={[st.ynText, { color: C.pinkInk }]}>✕  Non</Text>
        </Pressable>
      </View>
    );
  }
  if (d.options.length && ['choice', 'majority', 'overunder', 'yesno'].includes(p.kind)) {
    const many = d.options.length > 3;
    const shown = many ? d.options.slice(0, 2) : d.options;
    return (
      <View style={st.opts}>
        {shown.map((o, i) => {
          const sh = shape(i);
          return (
            <Pressable key={o.id} accessibilityRole="button" accessibilityLabel={`${sh.name}, ${o.label} : ouvrir la fiche avec ce choix`}
              testID={`prono-pick-${i}`} onPress={() => pick(o.id)} style={({ pressed }) => [st.opt, pressTransition, pressed && st.pressed]}>
              <Text aria-hidden style={{ color: sh.color, fontSize: 12 }}>{sh.glyph}</Text>
              <Text numberOfLines={1} style={st.optText}>{o.label}</Text>
            </Pressable>
          );
        })}
        {many ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Voir les ${d.options.length} réponses`} onPress={() => pick(null)}
            style={({ pressed }) => [st.opt, pressTransition, pressed && st.pressed]}>
            <Text style={[st.optText, { color: C.t2 }]}>+{d.options.length - 2}</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }
  if ((p.kind === 'person' || p.kind === 'award') && d.candidates?.length) {
    const people = d.candidates.filter((c) => !(p.kind === 'award' && c.me));
    const shown = people.slice(0, people.length > 6 ? 5 : 6);
    return (
      <View style={st.faces}>
        {shown.map((c) => (
          <Pressable key={c.id} accessibilityRole="button" accessibilityLabel={`${c.me ? 'Toi' : c.name} : ouvrir la fiche avec ce choix`}
            onPress={() => pick(c.id)} style={({ pressed }) => [st.face, pressTransition, pressed && st.pressed]}>
            <Avatar id={c.id} name={c.name} photo={c.avatar_url} size={44} profile={false} />
            <Text numberOfLines={1} style={st.faceName}>{c.me ? 'Toi' : c.name.split(' ')[0]}</Text>
          </Pressable>
        ))}
        {people.length > shown.length ? (
          <Pressable accessibilityRole="button" accessibilityLabel={`Voir les ${people.length} personnes`} onPress={() => pick(null)}
            style={({ pressed }) => [st.face, pressTransition, pressed && st.pressed]}>
            <View style={st.faceMore}><Text style={[st.faceName, { fontSize: 15 }]}>+{people.length - shown.length}</Text></View>
            <Text style={st.faceName}>Tous</Text>
          </Pressable>
        ) : null}
      </View>
    );
  }
  return (
    <Pressable accessibilityRole="button" accessibilityLabel="Donner ma réponse" onPress={() => pick(null)}
      style={({ pressed }) => [st.glassBtn, pressTransition, pressed && st.pressed]}>
      <Text style={st.glassText}>{p.kind === 'when' ? '◷  Choisir une heure' : p.kind === 'number' ? '#  Donner mon nombre' : '✎  Donner ma réponse'}</Text>
    </Pressable>
  );
}

// ───────── En attente : ma réponse scellée ─────────
function Sealed({ p, d, pat, push, onChanged }: { p: ListCard; d?: Detail; pat: boolean; push: Push; onChanged?: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const mine = d?.my_answer ? answerText(d, d.my_answer) : '';
  const stake = d?.my_answer?.stake ?? p.my_stake ?? 0;
  const planted = pat && stake > 0 ? `${stake} 🥔 plantées` : null;
  const happen = !!d?.can_happen;
  let sub: string;
  if (p.state === 'open') sub = ['Scellée', planted].filter(Boolean).join(' · ');
  else if (happen) sub = 'Tu organises : touche dès que c’est arrivé.';
  else if (p.mine) sub = 'Tu organises : donne le résultat.';
  else sub = ['Scellée', planted, `${p.creator.name} donne le résultat`].filter(Boolean).join(' · ');
  const happened = async () => {
    setBusy(true); setErr(null);
    try { await rpc('prono_result', { id: p.id, body: { time: new Date().toISOString() } }); onChanged?.(); }
    catch (e) { setErr(errorText(e)); }
    finally { setBusy(false); }
  };
  return (
    <View style={{ gap: 12, marginTop: 14 }}>
      <View style={st.sealed}>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={st.sealedT}>{p.answered ? <>Ta réponse : <Text style={num(15)}>{mine || '…'}</Text></> : 'Tu n’as pas joué'}</Text>
          <Text style={st.sealedS}>{sub}</Text>
        </View>
        {p.state === 'open' ? (
          <Pressable accessibilityRole="button" accessibilityLabel="Modifier ma réponse" onPress={() => openPick(p.id, null, push)}
            style={({ pressed }) => [st.edit, pressTransition, pressed && st.pressed]}>
            <Text style={{ color: C.lav, fontWeight: '700', fontSize: 15 }}>Modifier</Text>
          </Pressable>
        ) : null}
      </View>
      {happen ? (
        <Pressable accessibilityRole="button" accessibilityLabel="C’est arrivé !" testID="prono-happened" disabled={busy} onPress={() => void happened()}
          style={({ pressed }) => [st.mintBtn, pressTransition, (pressed || busy) && st.pressed]}>
          <Text style={{ color: C.bg, fontWeight: '800', fontSize: 17 }}>🚪 C’est arrivé !</Text>
        </Pressable>
      ) : p.state === 'closed' && p.mine ? (
        <Pressable accessibilityRole="button" accessibilityLabel="Donner le résultat" onPress={() => openPick(p.id, null, push)}
          style={({ pressed }) => [st.glassBtn, { marginTop: 0 }, pressTransition, pressed && st.pressed]}>
          <Text style={st.glassText}>⏳  Donner le résultat</Text>
        </Pressable>
      ) : null}
      {err ? <Text style={{ color: C.pinkInk, fontSize: 13 }}>{err}</Text> : null}
    </View>
  );
}

// ───────── Terminés ─────────
function Outcome({ p, d, pat }: { p: ListCard; d?: Detail; pat: boolean }) {
  const stake = d?.my_answer?.stake ?? p.my_stake ?? 0;
  if (p.state === 'cancelled') {
    return (
      <View style={st.verdict}>
        <Text style={st.neutral}>Prono annulé</Text>
        {pat && stake > 0 ? <Text style={st.lavPill}>↩ {stake} 🥔</Text> : null}
      </View>
    );
  }
  if (p.kind === 'award') return <AwardWinner p={p} d={d} />;
  const unanimous = d?.unanimous ?? p.unanimous;
  const right = d ? answerText(d, d.result) : '';
  const winner = p.winners?.[0] ?? null;
  const counted = d?.options.filter((o) => o.count != null && o.count > 0) ?? [];
  const total = counted.reduce((n, o) => n + (o.count ?? 0), 0);
  const harvest = d?.my_answer?.harvest ?? p.my_harvest;
  return (
    <View>
      {right ? (
        <View style={st.result}>
          {!unanimous && counted.length ? <Text style={[label, { marginBottom: 8 }]}>La bonne réponse</Text> : null}
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
            <View style={[st.rightAns, !p.won && p.answered && st.rightNeutral]}>
              <View style={[st.ok, !p.won && p.answered && { backgroundColor: C.miss }]}><Text style={{ color: C.bg, fontSize: 11, fontWeight: '900' }}>✓</Text></View>
              <Text style={{ color: C.t1, fontWeight: '700', fontSize: 15 }}>{right}</Text>
            </View>
            {unanimous ? (
              <View style={{ flex: 1, minWidth: 140 }}>
                <Text style={[round(17, 21), { color: C.lav }]}>🤝 Unanimes !</Text>
                <Text style={st.small}>{`Les ${p.answered_count} avaient vu juste.`}</Text>
              </View>
            ) : (p.kind === 'number' || p.kind === 'when') && winner ? (
              <Text style={[st.small, { flex: 1, textAlign: 'right' }]}>Le plus proche :{'\n'}<Text style={{ color: C.t1, fontWeight: '700' }}>{winner.me ? 'Toi' : winner.name}</Text></Text>
            ) : null}
          </View>
          {!unanimous && counted.length > 1 && total ? <Distribution d={d!} total={total} /> : null}
        </View>
      ) : null}
      <View style={st.verdict}>
        {unanimous ? (
          <>
            <Text style={st.neutral}>{pat && stake ? 'Tes patates sont rendues' : 'Tout le monde avait vu juste'}</Text>
            {pat && stake ? <Text style={st.lavPill}>↩ {stake} 🥔</Text> : null}
          </>
        ) : p.won ? (
          <>
            <View style={{ flex: 1 }}>
              <Text style={[round(19, 24), { color: C.mint }]}>🔮 Tu l’avais vu !</Text>
              {d?.rarity ? <Text style={st.small}><Text style={{ color: C.gold }}>★ </Text>{rarityLine(d.rarity)}</Text> : null}
            </View>
            {pat && harvest != null ? <Text style={[num(28), { color: C.mint }]}>+{harvest}<Text style={{ fontSize: 22 }}> 🥔</Text></Text>
              : !pat ? <Text style={[num(22), { color: C.mint }]}>+{p.points} pt{p.points > 1 ? 's' : ''}</Text> : null}
          </>
        ) : p.answered ? (
          <>
            <View style={{ flex: 1 }}>
              <Text style={[round(19, 24), { color: C.miss }]}>Pas cette fois</Text>
              {d?.my_answer ? <Text style={st.small}>Ta réponse : {answerText(d, d.my_answer)}</Text> : null}
            </View>
            {pat && stake > 0 ? <Text style={[num(20), { color: C.miss }]}>{stake} 🥔<Text style={st.compost}> au compost</Text></Text> : null}
          </>
        ) : (
          <Text style={st.neutral}>Tu n’as pas joué</Text>
        )}
      </View>
    </View>
  );
}

export function rarityLine(r: { right: number; of: number }): string {
  if (r.right <= 1) return `Seul·e à l’avoir vu sur ${r.of}`;
  return r.right / Math.max(1, r.of) <= 0.34 ? `Seuls ${r.right} sur ${r.of} l’avaient vu` : `${r.right} sur ${r.of} l’avaient vu`;
}

function Distribution({ d, total }: { d: Detail; total: number }) {
  const parts = d.options.map((o, i) => ({ o, sh: shape(i), n: o.count ?? 0 }));
  return (
    <View accessibilityLabel={`Répartition : ${parts.map((x) => `${x.o.label} ${x.n}`).join(', ')}`}>
      <View style={st.dist}>
        {parts.filter((x) => x.n).map((x) => (
          <View key={x.o.id} style={[{ flex: x.n / total, height: 6, borderRadius: 3, backgroundColor: x.o.correct ? C.mint : `${x.sh.color}66` }, enter('grow')]} />
        ))}
      </View>
      <View style={st.distL}>
        {parts.map((x) => (
          <Text key={x.o.id} style={[st.small, x.o.correct && { color: C.mint, fontWeight: '700' }]}>
            <Text style={{ color: x.o.correct ? C.mint : x.sh.color }}>{x.sh.glyph}</Text> {x.o.label} {x.n}
          </Text>
        ))}
      </View>
    </View>
  );
}

function AwardWinner({ p, d }: { p: ListCard; d?: Detail }) {
  const w = d?.result?.person ?? p.winners?.[0] ?? null;
  if (!w) return <Text style={[st.small, { marginTop: 10 }]}>Pas assez de votes pour dévoiler le trophée.</Text>;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16, marginTop: 12 }}>
      <View>
        <View style={st.crowned}><Avatar id={w.id} name={w.name} photo={w.avatar_url} size={60} profile={false} /></View>
        <Text aria-hidden style={st.crown}>👑</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={[label, { color: C.gold }]}>{p.award ?? d?.award ?? 'Trophée'}</Text>
        <Text style={round(26, 30)}>{w.me ? 'Toi' : w.name}</Text>
        <Text style={st.small}>{d?.rarity ? `${d.rarity.right} des ${d.rarity.of} · ` : ''}pour l’honneur</Text>
      </View>
    </View>
  );
}

// ───────── Pied ─────────
function Foot({ p, d, pat, now }: { p: ListCard; d?: Detail; pat: boolean; now: number }) {
  const verb = p.kind === 'award' ? 'voté' : 'joué';
  const shown = p.faces.slice(0, 3);
  let left: ReactNode;
  if (p.state === 'done' && pat && p.won && d?.contest?.open) {
    left = <Text style={st.footText}>Versées {inTime(d.contest.until, now)} · le temps de contester</Text>;
  } else if (p.answered && (p.state === 'open' || p.state === 'closed')) {
    left = <SealRow faces={p.faces} total={p.answered_count} me={p.answered} />;
  } else {
    left = (
      <View style={st.who}>
        {shown.length ? <AvatarStack faces={shown} extra={Math.max(0, p.answered_count - shown.length)} /> : null}
        <Text style={st.footText}><Text style={{ color: C.t1, fontWeight: '700' }}>{p.answered_count}</Text>{` ${p.answered_count > 1 ? 'ont' : 'a'} ${verb}`}</Text>
      </View>
    );
  }
  const reactions = (d?.reactions ?? []).filter((r) => r.count > 0).slice(0, 2);
  let right: ReactNode;
  if (p.state === 'open') {
    right = new Date(p.closes_at).getTime() - now < 24 * 3600_000
      ? <Countdown closesAt={p.closes_at} />
      : <View style={st.cd}><Text style={st.cdText}>🗓  {untilLine(p.closes_at)}</Text></View>;
  } else if (p.state === 'closed') {
    right = <View style={st.cd}><Text style={st.cdText}>🔒  Fermé{d?.result?.time ? ` · ${clock(d.result.time)}` : ''}</Text></View>;
  } else if (reactions.length) {
    right = <View style={st.cd}><Text style={st.cdText}>{reactions.map((r) => `${r.emoji} ${r.count}`).join(' · ')}</Text></View>;
  } else {
    right = <View style={st.cd}><Text style={st.cdText}>{relativeDay(p.closes_at)}</Text></View>;
  }
  return <View style={st.foot}>{left}{right}</View>;
}

const st = StyleSheet.create({
  card: web({ borderRadius: 24, backgroundColor: C.s1, borderWidth: 1, borderColor: C.line, overflow: 'hidden',
    boxShadow: '0 1px 0 rgba(255,255,255,.04) inset, 0 18px 40px -24px rgba(0,0,0,.8)' }),
  urgent: web({ borderColor: 'rgba(255,79,154,0.6)', boxShadow: '0 0 0 1px rgba(255,79,154,.35), 0 0 32px -8px rgba(255,79,154,.55)' }),
  won: web({ borderColor: 'rgba(91,227,166,0.55)', boxShadow: '0 0 30px -10px rgba(91,227,166,.5)' }),
  pressed: { opacity: 0.88, transform: [{ scale: 0.97 }] },
  cover: { position: 'relative', overflow: 'hidden', flexDirection: 'row', justifyContent: 'space-between', alignItems: 'flex-start', padding: 12 },
  fili: web({ position: 'absolute', right: -14, top: -26, fontSize: 112, lineHeight: 112, opacity: 0.22, transform: 'rotate(-14deg)', filter: 'saturate(.6)' }),
  coverFade: { position: 'absolute', left: 0, right: 0, bottom: 0, height: 34 },
  ctx: web({ zIndex: 1, height: 26, paddingHorizontal: 10, borderRadius: 13, justifyContent: 'center', maxWidth: '62%',
    backgroundColor: C.chipDark, backdropFilter: 'blur(12px)' }),
  ctxText: { color: '#fff', fontSize: 13, fontWeight: '600' },
  kind: { zIndex: 1, height: 26, paddingHorizontal: 10, borderRadius: 13, flexDirection: 'row', alignItems: 'center', gap: 5,
    backgroundColor: 'rgba(255,255,255,0.88)' },
  kindText: { color: '#1D1530', fontSize: 12, fontWeight: '700' },
  body: { paddingHorizontal: 18, paddingTop: 2, paddingBottom: 16 },
  kindLine: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingHorizontal: 18, paddingTop: 16, paddingBottom: 6 },
  by: { color: C.t2, fontSize: 13, fontWeight: '600' },
  meta: { marginTop: 6, flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 6 },
  metaText: { color: C.t2, fontSize: 13, lineHeight: 18, fontWeight: '500' },
  metaB: { color: C.t1, fontWeight: '700' },
  dot: { width: 3, height: 3, borderRadius: 2, backgroundColor: C.t3 },
  yn: { flexDirection: 'row', gap: 10, marginTop: 14 },
  ynBtn: { flex: 1, height: 52, borderRadius: 16, borderWidth: 1, alignItems: 'center', justifyContent: 'center' },
  yes: web({ borderColor: 'rgba(91,227,166,0.35)', backgroundImage: 'linear-gradient(160deg, rgba(91,227,166,.20), rgba(91,227,166,.08))' }),
  no: web({ borderColor: 'rgba(255,79,154,0.35)', backgroundImage: 'linear-gradient(160deg, rgba(255,79,154,.20), rgba(255,79,154,.08))' }),
  ynText: { ...round(19, 22), color: undefined },
  opts: { flexDirection: 'row', gap: 8, marginTop: 14 },
  opt: { flex: 1, minWidth: 0, height: 48, paddingHorizontal: 10, borderRadius: 14, flexDirection: 'row', alignItems: 'center',
    justifyContent: 'center', gap: 7, backgroundColor: C.s3, borderWidth: 1, borderColor: C.line2 },
  optText: { color: C.t1, fontSize: 15, fontWeight: '600', flexShrink: 1 },
  faces: { flexDirection: 'row', gap: 10, marginTop: 14, flexWrap: 'wrap' },
  face: { width: 52, alignItems: 'center', gap: 5, minHeight: 44 },
  faceName: { color: C.t2, fontSize: 12, fontWeight: '600', maxWidth: 52 },
  faceMore: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: C.s3,
    borderWidth: 1, borderStyle: 'dashed', borderColor: C.line2 },
  glassBtn: { marginTop: 14, height: 48, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: C.s3,
    borderWidth: 1, borderColor: C.line2 },
  glassText: { color: C.t1, fontSize: 15, fontWeight: '700' },
  sealed: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 16, backgroundColor: C.s3, borderWidth: 1, borderColor: C.line },
  sealedT: { color: C.t1, fontSize: 16, fontWeight: '700' },
  sealedS: { color: C.t2, fontSize: 13, lineHeight: 18, fontWeight: '500' },
  edit: { height: 44, paddingHorizontal: 14, borderRadius: 12, justifyContent: 'center', backgroundColor: 'rgba(185,167,255,0.14)' },
  mintBtn: web({ height: 52, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: C.mint,
    backgroundImage: 'linear-gradient(160deg,#7BF0BD,#3FCF8E)', boxShadow: '0 12px 26px -14px rgba(91,227,166,.9)' }),
  result: { marginTop: 14, padding: 14, borderRadius: 16, backgroundColor: C.s3, borderWidth: 1, borderColor: C.line, gap: 10 },
  rightAns: { flexDirection: 'row', alignItems: 'center', gap: 8, height: 44, paddingHorizontal: 12, borderRadius: 14,
    borderWidth: 1.5, borderColor: C.mint, backgroundColor: 'rgba(91,227,166,0.08)', alignSelf: 'flex-start' },
  rightNeutral: { borderColor: C.line2, backgroundColor: C.s3 },
  ok: { width: 20, height: 20, borderRadius: 10, backgroundColor: C.mint, alignItems: 'center', justifyContent: 'center' },
  dist: { flexDirection: 'row', gap: 3, marginTop: 2 },
  distL: { flexDirection: 'row', flexWrap: 'wrap', columnGap: 12, rowGap: 4, marginTop: 8 },
  small: { color: C.t2, fontSize: 13, lineHeight: 18, fontWeight: '500' },
  verdict: { marginTop: 14, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 12 },
  neutral: { color: C.t2, fontSize: 15, fontWeight: '600', flex: 1 },
  compost: { fontSize: 13, fontWeight: '600', ...({ fontStretch: '100%' } as object) },
  lavPill: { color: C.lav, fontSize: 15, fontWeight: '800', paddingHorizontal: 12, paddingVertical: 5, borderRadius: 999,
    borderWidth: 1, borderColor: 'rgba(185,167,255,0.35)', overflow: 'hidden' },
  crowned: web({ borderRadius: 999, boxShadow: `0 0 0 3px ${C.s1}, 0 0 0 5px ${C.gold}, 0 10px 30px -6px rgba(255,226,122,.55)` }),
  crown: web({ position: 'absolute', left: 18, top: -20, fontSize: 24, transform: 'rotate(-8deg)' }),
  foot: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 10, borderTopWidth: 1, borderTopColor: C.line,
    marginHorizontal: 18, paddingTop: 12, paddingBottom: 14, minHeight: 56 },
  who: { flexDirection: 'row', alignItems: 'center', gap: 10, flexShrink: 1 },
  footText: { color: C.t2, fontSize: 13, fontWeight: '600', flexShrink: 1 },
  cd: { height: 32, paddingHorizontal: 12, borderRadius: 999, justifyContent: 'center', borderWidth: 1, borderColor: C.line2 },
  cdText: { color: C.t2, fontSize: 13, fontWeight: '700' },
});
