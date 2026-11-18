import { useState } from 'react';
import { Text, View } from 'react-native';

import { enter } from '@/lib/motion';
import type { Prono } from '@/lib/pronos';

import { card, Chip, FaceRing, FaceStack, NoValueNote, PinkButton, SectionHead, Shape } from './Bits';
import {
  axis, axisLabel, fates, gapText, isAxis, isUnanimous, laureates, myAnswerText, myFate, nameOf, OPTION_KINDS, potatoesOn, rarity,
  rarityText, rightText, rows, v2, type Fate, type V2,
} from './model';
import { Axis, OptionRow } from './Parts';
import { ShareSheet } from './ShareCard';
import { N, num, round, text, web } from './theme';

/**
 * Le résultat posé (maquettes 4-resultat, 4-resultat-nombre, 4-resultat-heure, 4-trophee) : qui a tranché, les
 * patates en attente pendant la contestation, la bonne réponse et sa rareté, ma carte (récolte, au compost, rendues),
 * la répartition, chaque joueur avec SA réponse et SA récolte (jamais de « +/− » entre deux personnes), l'axe pour un
 * nombre ou une heure, le trophée sans patates. Les cartes entrent en fondu ; « Réduire les animations » : rien ne bouge.
 * La fiche (W4) met autour : le bandeau de contestation, les réactions, « Voir le classement ». Tant que le prono n'est
 * pas réglé (`settled` faux), chaque récolte est dite « en attente ».
 */
export function ResultView({ prono }: { prono: Prono }) {
  const p = v2(prono);
  const [share, setShare] = useState(false);
  if (!p.result && p.state !== 'cancelled') return null;
  const pot = potatoesOn(p);
  const unanimous = isUnanimous(p);
  const meRight = !!p.my_answer?.winner;
  const award = p.kind === 'award';
  let i = 0;
  const next = () => enter('rise', i++);
  return (
    <View style={{ gap: 12 }} testID="prono-result">
      {p.result && !award ? <Decider p={p} /> : null}
      <Cancelled p={p} pot={pot} style={next()} />
      {award ? <Trophy p={p} style={next()} /> : null}
      {!award && p.result ? <Hero p={p} style={next()} /> : null}
      {!award && p.result && p.my_answer ? <Mine p={p} pot={pot} unanimous={unanimous} style={next()} /> : null}
      {!award && OPTION_KINDS.concat('person').includes(p.kind) && p.result ? (
        <View style={next()}>
          <SectionHead left="La répartition" right={pot && p.field ? `${p.field.total} 🥔 dans le champ` : undefined} />
          <View style={[card, { padding: 12, gap: 8 }]}>
            {rows(p).map((r, k) => <OptionRow key={r.key} row={r} total={Math.max(1, p.answers?.length ?? 0)} index={k} potatoes={pot} />)}
          </View>
        </View>
      ) : null}
      {!award && p.result ? <Winners p={p} style={next()} /> : null}
      {!award && p.result ? <Players p={p} pot={pot} style={next()} /> : null}
      <View style={{ gap: 10, marginTop: 10 }}>
        {meRight && !unanimous && !award ? (
          <PinkButton label="🔮 Partager « J’avais vu juste »" onPress={() => setShare(true)} testID="prono-result-share" />
        ) : null}
      </View>
      {pot && !award ? <BagLine p={p} /> : null}
      {share ? <ShareSheet prono={p} onClose={() => setShare(false)} /> : null}
    </View>
  );
}

function Decider({ p }: { p: V2 }) {
  if (p.kind === 'majority') {
    return <Text style={text(14, '500', N.t2)}>Tranché par la bande : la réponse la plus choisie l’emporte.</Text>;
  }
  const c = p.creator;
  const also = p.result?.by_player ? (c.me ? ' · tu as joué aussi' : ' · a joué aussi') : '';
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }} testID="prono-result-by">
      <FaceRing face={c} size={22} ring={N.bg} />
      <Text style={[text(14, '500', N.t2), { flex: 1 }]}>
        Tranché par <Text style={text(14, '600', N.t1)}>{c.me ? 'toi' : c.name}</Text>{also}
      </Text>
    </View>
  );
}

function Cancelled({ p, pot, style }: { p: V2; pot: boolean; style?: object }) {
  if (p.state !== 'cancelled') return null;
  return (
    <View style={[banner, style]}>
      <Text style={text(15, '600', N.t1)}>Prono annulé{p.cancel_reason ? ` : ${p.cancel_reason}` : ''}.</Text>
      <Text style={text(13, '500', N.t2)}>{pot ? 'Toutes les patates sont rendues.' : 'Aucun point n’est compté.'}</Text>
    </View>
  );
}

const banner = { padding: 14, borderRadius: 20, backgroundColor: 'rgba(255,255,255,0.04)', borderWidth: 1, borderColor: N.line, gap: 4 };

function Hero({ p, style }: { p: V2; style?: object }) {
  const r = rarity(p);
  if (isAxis(p.kind)) {
    const { real } = axis(p);
    return (
      <View style={[{ gap: 12 }, style]}>
        <View style={web({ padding: 16, borderRadius: 24, borderWidth: 1, borderColor: 'rgba(91,227,166,0.35)', backgroundColor: N.s1,
          backgroundImage: 'radial-gradient(120% 140% at 0% 0%,rgba(91,227,166,.22),rgba(91,227,166,.03) 60%)' })}>
          <Text style={[text(12, '700', N.mint), { letterSpacing: 1 }]}>{p.kind === 'when' ? 'C’EST ARRIVÉ À' : 'LE VRAI COMPTE'}</Text>
          <Text style={[num(60, N.mint), { marginTop: 8, lineHeight: 62 }]}>{real == null ? '—' : axisLabel(p.kind, real)}</Text>
          <Text style={[text(13, '500', N.t2), { marginTop: 8 }]}>
            {p.not_over ? 'Sans dépasser : le plus proche en dessous l’emporte.' : 'Le plus proche l’emporte.'}
          </Text>
        </View>
        <View style={[card, { paddingHorizontal: 16, paddingTop: 14, paddingBottom: 10 }]}>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginBottom: 6 }}>
            <Text style={text(12, '700', N.t2)}>LES RÉPONSES</Text>
            <Text style={text(12, '700', N.t2)}>🎯 le plus proche</Text>
          </View>
          <Axis p={p} intro />
        </View>
      </View>
    );
  }
  const good = rows(p).find((x) => x.right);
  const textWinners = (p.answers ?? []).filter((a) => a.winner).length;
  return (
    <View style={[web({ padding: 16, borderRadius: 24, borderWidth: 1, borderColor: 'rgba(91,227,166,0.35)', backgroundColor: N.s1, overflow: 'hidden',
      backgroundImage: 'radial-gradient(120% 120% at 0% 0%,rgba(91,227,166,.22),rgba(91,227,166,.04) 60%)' }), style]} testID="prono-result-hero">
      <Text style={[text(12, '700', N.mint), { letterSpacing: 1 }]}>{p.kind === 'text' ? 'LES BONNES RÉPONSES' : 'LA BONNE RÉPONSE'}</Text>
      {p.kind === 'text' ? (
        <Text style={[round(26, 30), { marginTop: 12 }]}>{textWinners ? `${textWinners} réponse${textWinners > 1 ? 's' : ''} retenue${textWinners > 1 ? 's' : ''}` : 'Aucune réponse retenue'}</Text>
      ) : (
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 14, marginTop: 12 }}>
          {good ? <Shape shape={good.shape} size={44} on /> : null}
          <Text style={[round(30, 34), { flex: 1 }]}>{rightText(p) || '—'}</Text>
        </View>
      )}
      <Chip tone="lemon" style={{ marginTop: 14 }}>🔮 {rarityText(r)}</Chip>
    </View>
  );
}

function Mine({ p, pot, unanimous, style }: { p: V2; pot: boolean; unanimous: boolean; style?: object }) {
  const f = myFate(p);
  const right = !!p.my_answer?.winner;
  const pending = !p.settled;
  const winners = (p.answers ?? []).filter((a) => a.winner && (a.stake ?? 0) > 0);
  const wPlanted = winners.reduce((s, a) => s + (a.stake ?? 0), 0);
  const potatoes = pot && f && f.stake > 0;
  return (
    <View style={[card, { padding: 16, borderColor: right ? 'rgba(91,227,166,0.3)' : N.line }, style]} testID="prono-result-mine">
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View style={{ width: 40, height: 40, borderRadius: 20, alignItems: 'center', justifyContent: 'center',
          backgroundColor: unanimous ? 'rgba(185,167,255,0.18)' : right ? N.mint : 'rgba(139,132,168,0.2)', borderWidth: right || unanimous ? 0 : 2, borderColor: N.miss }}>
          <Text style={text(19, '800', unanimous ? N.lav : right ? N.ink : N.missText)}>{unanimous ? '🤝' : right ? '✓' : '○'}</Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={text(17, '700')}>{unanimous ? 'Unanimes !' : right ? 'Tu avais vu juste' : 'Pas cette fois'}</Text>
          <Text style={[text(13, '500', N.t2), { marginTop: 3 }]} numberOfLines={2}>
            {potatoes && f?.kind === 'harvest' ? `Ta récolte${pending ? ' · en attente' : ''}` : `Ta réponse : ${myAnswerText(p)}`}
          </Text>
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          <FateValue f={potatoes ? f : null} points={right && !unanimous ? p.points : null} big />
          {potatoes && f?.kind === 'harvest' && pending ? <Text style={[text(12, '600', N.warn), { marginTop: 4 }]}>en attente</Text> : null}
        </View>
      </View>
      {potatoes && f?.kind === 'harvest' && winners.length > 1 && wPlanted ? (
        <View style={{ marginTop: 16 }} accessibilityLabel={`Ta part : ${f.stake} sur ${wPlanted} patates plantées sur la bonne réponse`}>
          <View style={{ flexDirection: 'row', height: 14, borderRadius: 7, overflow: 'hidden', gap: 2 }}>
            {winners.map((a) => (
              <View key={a.user.id} style={[{ flex: a.stake ?? 0 }, a.user.me ? web({ backgroundImage: 'linear-gradient(90deg,#2FB984,#5BE3A6)' })
                : { backgroundColor: 'rgba(91,227,166,0.28)' }]} />
            ))}
          </View>
          <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 8 }}>
            <Text style={text(13, '600', N.t2)}><Text style={text(13, '700')}>Toi {f.stake}</Text> sur {wPlanted} 🥔</Text>
            <Text style={text(13, '600', N.t2)}>plantées sur la bonne réponse</Text>
          </View>
          <Text style={[text(13, '500', N.t2), { marginTop: 10, lineHeight: 19 }]}>
            Le champ (<Text style={text(13, '700')}>{p.field?.total ?? '—'} 🥔</Text>) est partagé entre ceux qui ont vu juste, selon ce que
            chacun a planté : {f.stake} sur {wPlanted}, c’est <Text style={text(13, '700', N.mint)}>{f.harvest} 🥔</Text> pour toi.
          </Text>
        </View>
      ) : null}
      {potatoes && f?.kind === 'refund' && !unanimous ? (
        <Text style={[text(13, '500', N.t2), { marginTop: 10 }]}>
          {(p.answers ?? []).some((a) => a.winner) ? 'Moins de 2 joueurs avaient planté : tout le monde récupère ses patates.'
            : 'Personne n’avait vu juste : tout le monde récupère ses patates.'}
        </Text>
      ) : null}
    </View>
  );
}

/** À droite d'une carte ou d'une ligne : récolte (menthe), au compost (gris), rendues (lavande), ou les points. */
function FateValue({ f, points, big }: { f: Fate | null; points: number | null; big?: boolean }) {
  if (f && f.kind === 'harvest') {
    return <Text style={num(big ? 30 : 17, N.mint)}>+{f.harvest} 🥔</Text>;
  }
  if (f && f.kind === 'refund') {
    return (
      <View style={{ alignItems: 'flex-end' }}>
        {big ? <Text style={[text(11, '700', N.t2), { letterSpacing: 1, marginBottom: 5 }]}>RENDUES</Text> : null}
        <Text style={num(big ? 26 : 17, N.lav)}>{f.stake} 🥔</Text>
      </View>
    );
  }
  if (f && f.kind === 'compost') {
    return (
      <View style={{ alignItems: 'flex-end' }}>
        {big ? <Text style={[text(11, '700', N.t2), { letterSpacing: 1, marginBottom: 5 }]}>AU COMPOST</Text> : null}
        <Text style={num(big ? 26 : 17, N.missText)}>{f.stake} 🥔</Text>
      </View>
    );
  }
  if (points != null) return <Text style={num(big ? 22 : 15, N.mint)}>+{points} pt{points > 1 ? 's' : ''}</Text>;
  return null;
}

function Players({ p, pot, style }: { p: V2; pot: boolean; style?: object }) {
  const list = p.answers ?? [];
  if (!list.length) return null;
  const all = fates(p);
  const axisKind = isAxis(p.kind);
  const ax = axisKind ? axis(p) : null;
  const ordered = axisKind && ax ? ax.points.map((pt) => list.find((a) => a.user.id === pt.face.id)!).filter(Boolean)
    : [...list].sort((a, b) => Number(b.winner) - Number(a.winner) || (all.get(b.user.id)?.harvest ?? 0) - (all.get(a.user.id)?.harvest ?? 0)
      || (b.stake ?? 0) - (a.stake ?? 0));
  const shapeOf = (a: (typeof list)[number]) => rows(p).find((r) => (OPTION_KINDS.includes(p.kind) ? r.key === a.option_id : r.key === a.person?.id))?.shape;
  return (
    <View style={style}>
      <SectionHead left={axisKind ? 'Du plus proche au plus loin' : `Les joueurs · ${list.length}`} right={pot ? 'planté → récolte' : undefined} />
      <View style={[card, { paddingHorizontal: 14, paddingVertical: 4 }]}>
        {ordered.map((a, k) => {
          const f = all.get(a.user.id);
          const pt = ax?.points.find((x) => x.face.id === a.user.id);
          const sh = shapeOf(a);
          const answer = OPTION_KINDS.includes(p.kind) ? p.options.find((o) => o.id === a.option_id)?.label ?? '—'
            : p.kind === 'person' ? nameOf(a.person) : axisKind && pt ? axisLabel(p.kind, pt.value) : a.hidden ? 'Réponse masquée' : a.text ?? '—';
          return (
            <View key={a.user.id} testID={`prono-result-player-${k}`}
              style={[{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 62, borderTopWidth: k ? 1 : 0, borderColor: N.line },
                a.user.me && { marginHorizontal: -14, paddingHorizontal: 14, backgroundColor: 'rgba(185,167,255,0.07)' }]}>
              {pt ? <Text style={[num(14, a.winner ? N.mint : N.t2), { width: 18, textAlign: 'center' }]}>{pt.rank}</Text> : null}
              <View>
                <FaceRing face={a.user} size={pt ? 36 : 40} ring={N.s1} />
                {a.winner ? (
                  <View style={{ position: 'absolute', right: -3, bottom: -3, width: 17, height: 17, borderRadius: 9, backgroundColor: N.mint,
                    borderWidth: 2, borderColor: N.s1, alignItems: 'center', justifyContent: 'center' }}>
                    <Text style={text(9, '900', N.ink)}>✓</Text>
                  </View>
                ) : null}
              </View>
              <View style={{ flex: 1, minWidth: 0 }}>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
                  <Text style={text(16, '600')} numberOfLines={1}>{nameOf(a.user)}</Text>
                  {a.user.id === p.creator.id && p.result?.by_player ? (
                    <View style={{ height: 20, paddingHorizontal: 7, borderRadius: 999, backgroundColor: 'rgba(185,167,255,0.16)', justifyContent: 'center' }}>
                      <Text style={text(11, '700', N.lav)}>a tranché</Text>
                    </View>
                  ) : null}
                </View>
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 3 }}>
                  {sh ? <View style={web({ width: 10, height: 10, backgroundColor: N.t2, clipPath: sh.clip })} /> : null}
                  <Text style={text(13, '500', N.t2)} numberOfLines={1}>
                    {axisKind ? 'a dit ' : ''}{answer}{axisKind && pot ? ` · ${a.stake ?? 0} 🥔` : ''}
                  </Text>
                </View>
              </View>
              <View style={{ alignItems: 'flex-end' }}>
                {axisKind && pt ? (
                  <View style={{ height: 24, paddingHorizontal: 9, borderRadius: 999, justifyContent: 'center',
                    backgroundColor: a.winner ? 'rgba(91,227,166,0.16)' : 'rgba(255,255,255,0.07)', marginBottom: 4 }}>
                    <Text style={text(13, '700', a.winner ? N.mint : N.missText)}>{a.winner ? '🎯 ' : ''}{pt.gap === 0 ? 'pile' : `à ${gapText(p.kind, pt.gap)}`}</Text>
                  </View>
                ) : null}
                <PlayerFate f={pot ? f : undefined} winner={a.winner} points={p.points} pending={!p.settled} />
              </View>
            </View>
          );
        })}
      </View>
    </View>
  );
}

/** « LES GAGNANTS » : leurs visages (le texte exact sert aussi à la recette web). */
function Winners({ p, style }: { p: V2; style?: object }) {
  const list = p.winners ?? [];
  return (
    <View style={style} testID="prono-result-winners">
      <View style={{ marginTop: 24, marginBottom: 10, paddingHorizontal: 4 }}>
        <Text style={[text(12, '700', N.t2), { letterSpacing: 1 }]}>LES GAGNANTS</Text>
      </View>
      <View style={[card, { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 20 }]}>
        {list.length ? (
          <>
            <FaceStack faces={list} size={32} ring={N.s1} max={8} />
            <Text style={[text(14, '600'), { flex: 1 }]} numberOfLines={2}>
              {list.length === 1 ? `${nameOf(list[0])} ${list[0].me ? 'avais' : 'avait'} vu juste` : `${list.length} ont vu juste`}
            </Text>
          </>
        ) : <Text style={text(14, '500', N.t2)}>Personne n’avait vu juste.</Text>}
      </View>
    </View>
  );
}

function PlayerFate({ f, winner, points, pending }: { f?: Fate; winner: boolean; points: number; pending: boolean }) {
  if (f && f.kind === 'harvest') {
    return (
      <>
        <Text style={num(17, N.mint)}>{f.harvest} 🥔</Text>
        <Text style={text(12, '500', N.t2)}>{pending ? 'en attente' : 'récolte'} · {f.stake} plantées</Text>
      </>
    );
  }
  if (f && f.kind === 'compost') {
    return (
      <>
        <Text style={text(14, '600', N.missText)}>au compost</Text>
        <Text style={text(12, '500', N.t2)}>{f.stake} 🥔 plantées</Text>
      </>
    );
  }
  if (f && f.kind === 'refund') {
    return (
      <>
        <Text style={num(17, N.lav)}>{f.stake} 🥔</Text>
        <Text style={text(12, '500', N.t2)}>rendues</Text>
      </>
    );
  }
  return winner ? <Text style={num(15, N.mint)}>+{points} pt{points > 1 ? 's' : ''}</Text> : <Text style={text(13, '500', N.t2)}>—</Text>;
}

/** Trophée de la soirée : le ou la lauréat·e, ses voix seulement ; jamais de patates. */
function Trophy({ p, style }: { p: V2; style?: object }) {
  const { people, voters } = laureates(p);
  const win = people[0];
  return (
    <View style={[web({ alignItems: 'center', padding: 20, borderRadius: 24, borderWidth: 1, borderColor: 'rgba(255,226,122,0.35)', backgroundColor: N.s1,
      backgroundImage: 'radial-gradient(90% 70% at 50% 0%,rgba(255,226,122,.22),rgba(255,226,122,0) 70%)' }), style]} testID="prono-result-trophy"
      accessibilityLabel={win ? `${p.award_label ?? 'Trophée'} : ${nameOf(win)}` : undefined}>
      <Text style={[text(12, '800', N.lemon), { letterSpacing: 1.6 }]}>TROPHÉE DE LA SOIRÉE</Text>
      <Text style={[round(24, 28), { marginTop: 8, textAlign: 'center' }]}>{p.award_emoji ?? '🏆'} {p.award_label ?? 'Trophée'}</Text>
      {win ? (
        <>
          <View style={[{ marginTop: 16 }, web({ borderRadius: 999, boxShadow: '0 0 0 4px #FFE27A, 0 0 30px rgba(255,214,102,.6)' })]}>
            <FaceRing face={win} size={96} ring={N.s1} />
          </View>
          <Text style={[round(30, 34), { marginTop: 12 }]}>{nameOf(win)}</Text>
          <Text style={[text(14, '500', N.t2), { marginTop: 4, textAlign: 'center' }]}>
            {win.votes ? `choisi·e par ${win.votes} des ${voters} votants` : `${voters} votants`}
            {people.length > 1 ? ` · ex æquo avec ${people.slice(1).map(nameOf).join(', ')}` : ''}
          </Text>
        </>
      ) : <Text style={[text(14, '500', N.t2), { marginTop: 12 }]}>Il faut au moins 3 votants pour dévoiler le trophée.</Text>}
      <Text style={[text(12.5, '500', N.t2), { marginTop: 14, textAlign: 'center' }]}>
        {p.patates_on ? 'Pour la gloire : aucun trophée ne rapporte de patates.' : 'Pour la gloire, rien d’autre.'}
      </Text>
    </View>
  );
}

function BagLine({ p }: { p: V2 }) {
  const bag = p.bag;
  if (!bag) return null;
  const f = myFate(p);
  const waiting = !p.settled && f?.kind === 'harvest' ? f.harvest : 0;
  return (
    <View>
      <SectionHead left={p.group ? p.group.name : p.event ? p.event.title : 'Ton sac'} />
      <View style={[card, { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 20 }]} testID="prono-result-bag">
        <View style={{ width: 44, height: 44, borderRadius: 14, backgroundColor: 'rgba(255,226,122,0.12)', alignItems: 'center', justifyContent: 'center' }}>
          <Text style={{ fontSize: 24 }}>🥔</Text>
        </View>
        <View style={{ flex: 1 }}>
          <Text style={text(16, '700')}>Ton sac</Text>
          <Text style={text(13, '500', N.t2)}>Remonte à 100 lundi s’il est en dessous</Text>
        </View>
        <View style={{ alignItems: 'flex-end' }}>
          <Text style={num(24)}>{bag.balance} 🥔</Text>
          {waiting ? <Text style={text(13, '600', N.warn)}>+{waiting} en attente</Text> : null}
        </View>
      </View>
      <NoValueNote />
    </View>
  );
}
