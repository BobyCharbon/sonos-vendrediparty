import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import type { Prono } from '@/lib/pronos';

import { Chip, FaceRing, FaceStack, GlassButton, TerrainChip } from './Bits';
import { Announce, confetti, EASE, FxLayer, K, Roll, spring, useStage, type StageCtx } from './fx';
import {
  axis, axisLabel, isAxis, isUnanimous, myAnswerText, myFate, potatoesOn, rarity, rarityText, rightText, rows, terrainChip, v2, type V2,
} from './model';
import { Axis, OptionRow, TextRow } from './Parts';
import { ShareSheet } from './ShareCard';
import { band, N, num, round, terrainLook, text, web } from './theme';
import { TrophyStage } from './TrophyStage';

/**
 * Le dévoilement (maquette 4-devoilement, chronologie en ms dans son en-tête) : les sceaux craquent toutes les 60 ms,
 * le projecteur cherche, 500 ms de temps mort, la bonne réponse s'allume en menthe, les visages tombent sur leur
 * réponse, les barres poussent, « Seuls 2 sur 8 l'avaient vu », puis ma carte : la récolte compte régulièrement de 0
 * à N, confettis SEULEMENT si j'ai vu juste. « Pas cette fois » : gris, « au compost », rien qui bouge en plus.
 * « Unanimes ! » : lavande, tout est rendu, la vague des visages, pas de confettis. Trophée : TrophyStage.
 * « Passer » ou un toucher n'importe où : l'état final. « Réduire les animations » : l'état final directement.
 * Panneau plein écran (position fixed) par-dessus la fiche, qui garde sa hauteur derrière.
 */
export function RevealStage({ prono, onDone }: { prono: Prono; onDone: () => void }) {
  const p = v2(prono);
  if (p.kind === 'award') return <TrophyStage p={p} onDone={onDone} />;
  return <ResultStage p={p} onDone={onDone} />;
}

const T = { seal0: 60, sealGap: 60, sweep: 600, light: 1100, fly: 1120, flyGap: 35, bar: 1420, barGap: 70, counts: 1650, rare: 1800,
  card: 1950, roll: 2100, rollDur: 450, conf: 2150, acts: 2600, END: 3500 };
const MAX_SEALS = 8;

function ResultStage({ p, onDone }: { p: V2; onDone: () => void }) {
  const [share, setShare] = useState(false);
  const look = terrainLook(p.group);
  const seals = p.answered.slice(0, MAX_SEALS);
  const extraSeals = p.answered.length - seals.length;
  const list = rows(p);
  const total = Math.max(1, p.answers?.length ?? p.answered.length);
  const r = rarity(p);
  const unanimous = isUnanimous(p);
  const pot = potatoesOn(p);
  const fate = myFate(p);
  const played = !!p.my_answer;
  const meRight = !!p.my_answer?.winner;
  const axisKind = isAxis(p.kind);
  const party = meRight && !unanimous;

  const { root, ended, skip } = useStage((s) => build(s, { unanimous, party, axisKind }), T.END, [p.id, p.result?.at ?? '']);

  const value = cardValue(p, fate, meRight, unanimous, pot);
  const say = `Bonne réponse : ${rightText(p) || 'voir le détail'}. ${!played ? 'Tu n’as pas joué.' : meRight
    ? `Tu avais vu juste${value.n != null ? `, ${value.say}` : ''}.` : `Pas cette fois${value.n != null ? `, ${value.say}` : ''}.`}`;

  return (
    <View ref={root} testID="prono-reveal-stage" accessibilityViewIsModal aria-modal role="dialog" aria-label="Le résultat"
      style={web({ position: 'fixed', left: 0, right: 0, top: 0, bottom: 0, zIndex: 1000, backgroundColor: N.stage, overflow: 'hidden' })}>
      <Announce>{say}</Announce>
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 230 }}>
        <View style={{ width: '100%', maxWidth: 520, alignSelf: 'center', minHeight: '100%' }}>
          <StageCover look={look} />
          <View pointerEvents="none" style={web({ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, filter: 'blur(14px)', zIndex: 3 })}>
            <K k="beam" style={web({ position: 'absolute', left: 0, right: 0, top: 0, height: 400, transformOrigin: '50% 0', opacity: 0,
              clipPath: 'polygon(46% 0,54% 0,96% 100%,4% 100%)',
              backgroundImage: 'linear-gradient(180deg,rgba(185,167,255,0) 0%,rgba(185,167,255,.16) 55%,rgba(200,186,255,.32) 100%)' })} />
          </View>
          <K k="lamp" pointerEvents="none" style={web({ position: 'absolute', left: '50%', top: 40, width: 120, height: 26, marginLeft: -60,
            borderRadius: 999, zIndex: 3, opacity: 0.3, backgroundImage: 'radial-gradient(closest-side,rgba(220,210,255,.85),rgba(185,167,255,0))' })} />

          <View style={{ zIndex: 20, height: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12 }}>
            <GlassButton round label="‹" a11y="Retour à la fiche" onPress={onDone} testID="prono-reveal-back" />
            <TerrainChip group={p.group} title={terrainChip(p)} />
            {ended ? <View style={{ width: 44 }} /> : <K k="passer"><GlassButton label="Passer" onPress={skip} testID="prono-reveal-skip" /></K>}
          </View>

          <View style={{ zIndex: 4, alignItems: 'center', paddingHorizontal: 30, paddingTop: 10 }}>
            <K k="band" style={web({ transform: 'rotate(-3deg)', marginBottom: 14 })}>
              <View style={web({ paddingHorizontal: 14, paddingTop: 6, paddingBottom: 5, borderRadius: 6, backgroundImage: 'linear-gradient(135deg,#D9CEFF,#A08FFF)',
                boxShadow: 'inset 0 0 0 1px rgba(255,255,255,.25), 0 6px 30px -6px rgba(123,108,246,.9)' })}>
                <Text style={band}>LE RÉSULTAT</Text>
              </View>
            </K>
            <K k="q"><Text role="heading" aria-level={1} style={[round(28), { textAlign: 'center', maxWidth: 360 }]}>{p.question}</Text></K>
            <View style={{ height: 36, marginTop: 18, flexDirection: 'row', gap: 8, justifyContent: 'center' }}>
              {seals.map((f) => (
                <View key={f.id} style={{ width: 36, height: 36 }}>
                  <K k="sface" data={{ p: f.id }} style={{ position: 'absolute', left: 0, top: 0, opacity: 0 }}>
                    <FaceRing face={f} size={32} ring={N.stage} />
                  </K>
                  <K k="seal" pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, opacity: 0 }}>
                    <SealHalf side="l" look={look} me={!!f.me} />
                    <SealHalf side="r" look={look} me={!!f.me} />
                  </K>
                  <K k="lock" style={{ position: 'absolute', right: -4, bottom: -3, width: 16, height: 16, borderRadius: 8, backgroundColor: N.stage,
                    alignItems: 'center', justifyContent: 'center', opacity: 0 }}><Text style={{ fontSize: 9 }}>🔒</Text></K>
                  <K k="flash" style={{ position: 'absolute', left: -2, top: -2, right: -2, bottom: -2, borderRadius: 999, borderWidth: 2, borderColor: N.lav, opacity: 0 }} />
                </View>
              ))}
              {extraSeals > 0 ? <Text style={[text(13, '700', N.t2), { alignSelf: 'center' }]}>+{extraSeals}</Text> : null}
            </View>
            <K k="meta" style={{ height: 36, marginTop: -36, flexDirection: 'row', alignItems: 'center', justifyContent: 'center' }}>
              <Text style={text(13, '500', N.t2)}>
                <Text style={text(13, '700')}>{p.answered.length}</Text> {p.answered.length > 1 ? 'ont joué' : 'a joué'}
                {pot && p.field ? <> · <Text style={text(13, '700')}>{p.field.total} 🎊</Text> sur la piste</> : null}
              </Text>
            </K>
          </View>

          <K k="opts" style={{ zIndex: 4, marginTop: 18, marginHorizontal: 16, gap: 10 }}>
            <K k="spot" pointerEvents="none" style={web({ position: 'absolute', left: -30, right: -30, top: 0, height: 130, borderRadius: 999, opacity: 0,
              mixBlendMode: 'screen', backgroundImage: 'radial-gradient(closest-side,rgba(200,186,255,.55),rgba(185,167,255,0))' })} />
            <K k="spot2" pointerEvents="none" style={web({ position: 'absolute', left: -30, right: -30, top: 0, height: 130, borderRadius: 999, opacity: 0,
              mixBlendMode: 'screen', backgroundImage: 'radial-gradient(closest-side,rgba(91,227,166,.30),rgba(91,227,166,0))' })} />
            {list.length ? list.map((row, i) => <OptionRow key={row.key} row={row} total={total} index={i} stage big={unanimous && list.length <= 2} />) : null}
            {axisKind ? <AxisBlock p={p} /> : null}
            {p.kind === 'text' ? (p.answers ?? []).map((a) => (
              <TextRow key={a.user.id} face={a.user} body={a.hidden ? 'Réponse masquée' : a.text ?? '—'} right={a.winner} stage />
            )) : null}
          </K>

          {unanimous ? (
            <K k="rare" style={{ alignItems: 'center', marginTop: 26, gap: 8, paddingHorizontal: 24 }}>
              <Text style={{ fontSize: 46 }}>🤝</Text>
              <Text style={[round(44, 48), web({ backgroundImage: 'linear-gradient(90deg,#CBBDFF,#FFFFFF,#CBBDFF)', WebkitBackgroundClip: 'text',
                backgroundClip: 'text', color: 'transparent' }) as object]}>Unanimes !</Text>
              <Text style={[text(15, '500', N.t2), { textAlign: 'center' }]}>
                {pot ? 'Tout le monde récupère ses confettis.' : 'Tout le monde avait vu juste.'}
              </Text>
            </K>
          ) : (
            <K k="rare" style={{ alignItems: 'center', marginTop: 14, gap: 10 }}>
              <Chip tone="lemon" big style={{ alignSelf: 'center' }}>🔮 {rarityText(r)}</Chip>
              {p.winners?.length ? (
                <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} testID="prono-reveal-winners">
                  <Text style={[text(12, '700', N.t2), { letterSpacing: 1 }]}>LES GAGNANTS</Text>
                  <FaceStack faces={p.winners} size={24} ring={N.stage} />
                </View>
              ) : null}
            </K>
          )}

          {!ended ? (
            <Pressable accessible={false} focusable={false} onPress={skip} testID="prono-reveal-tap"
              style={{ position: 'absolute', left: 0, right: 0, top: 56, bottom: 0, zIndex: 10 }} />
          ) : null}
        </View>
      </ScrollView>

      <MeCard p={p} played={played} meRight={meRight} unanimous={unanimous} value={value} ended={ended}
        onShare={() => setShare(true)} onDone={onDone} />
      <FxLayer style={{ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, zIndex: 30, overflow: 'hidden' }} />
      {share ? <ShareSheet prono={p} onClose={() => setShare(false)} /> : null}
    </View>
  );
}

/** Les animations de la scène, dans l'ordre de la chronologie. */
function build(s: StageCtx, o: { unanimous: boolean; party: boolean; axisKind: boolean }) {
  const { a, q, qa, root } = s;
  const sp = spring;
  breathe(s);
  a('band', [{ transform: 'rotate(-9deg) scale(1.35)', opacity: 0 }, { transform: 'rotate(-3deg) scale(1)', opacity: 1 }], 0, sp(0.35, 0.55));
  a('q', [{ opacity: 0, transform: 'translateY(10px)' }, { opacity: 1, transform: 'none' }], 40, 380);
  a('meta', [{ opacity: 0 }, { opacity: 1 }], T.fly + 300, 300);

  // Les sceaux craquent ; le visage dessous apparaît.
  const seals = qa('seal');
  const faces = qa('sface');
  const locks = qa('lock');
  const flashes = qa('flash');
  seals.forEach((seal, i) => {
    const t = T.seal0 + i * T.sealGap;
    const [l, r] = Array.from(seal.children) as HTMLElement[];
    a(seal, [{ opacity: 1, transform: 'rotate(0)' }, { opacity: 1, transform: 'rotate(-6deg)', offset: 0.33 }, { opacity: 1, transform: 'rotate(6deg)', offset: 0.66 },
      { opacity: 1, transform: 'rotate(0)' }], Math.max(0, t - 80), 80, 'linear');
    a(l, [{ transform: 'none', opacity: 1 }, { transform: 'translate(-7px,6px) rotate(-28deg)', opacity: 0 }], t, 240);
    a(r, [{ transform: 'none', opacity: 1 }, { transform: 'translate(7px,6px) rotate(28deg)', opacity: 0 }], t, 240);
    a(locks[i], [{ opacity: 1, transform: 'none' }, { opacity: 0, transform: 'translateY(8px) scale(.6)' }], t, 180);
    a(flashes[i], [{ opacity: 0.9, transform: 'scale(.8)' }, { opacity: 0, transform: 'scale(1.8)' }], t, 260);
    a(faces[i], [{ transform: 'scale(.5)', opacity: 0 }, { transform: 'scale(1)', opacity: 1, offset: 0.4 }, { transform: 'scale(1)', opacity: 1 }], t + 20, 500);
  });

  // Le projecteur balaie de la première à la dernière réponse, puis se pose sur la bonne.
  const box = q('opts');
  const opts = qa('opt');
  const right = root.querySelector<HTMLElement>('[data-k="opt"][data-r="1"]') ?? (o.axisKind ? q('axis') : null);
  const targets = opts.length ? opts : [q('axis')].filter(Boolean) as HTMLElement[];
  if (box && targets.length) {
    const mid = (el: HTMLElement) => el.getBoundingClientRect().top - box.getBoundingClientRect().top + el.offsetHeight / 2 - 65;
    const path = [mid(targets[0]), mid(targets[targets.length - 1]), mid(right ?? targets[0])];
    const spot = q('spot');
    a(spot, [{ transform: `translateY(${path[0] - 40}px) scaleX(.7)`, opacity: 0 }, { transform: `translateY(${path[0]}px) scaleX(1)`, opacity: 1, offset: 0.12 },
      { transform: `translateY(${path[1]}px) scaleX(1)`, opacity: 1, offset: 0.5 }, { transform: `translateY(${path[2]}px) scaleX(.9)`, opacity: 1 }],
    T.sweep, T.light - T.sweep, EASE.inOut);
    a(spot, [{ opacity: 1, transform: `translateY(${path[2]}px) scaleX(.9)` }, { opacity: 0, transform: `translateY(${path[2]}px) scaleX(.9)` }], T.light, 300,
      EASE.out, 'forwards');
    a('spot2', [{ transform: `translateY(${path[2]}px) scale(1.3)`, opacity: 0 }, { transform: `translateY(${path[2]}px) scale(1)`, opacity: 1, offset: 0.3 },
      { transform: `translateY(${path[2]}px) scale(1)`, opacity: 0.55 }], T.light, 900);
    const top = box.getBoundingClientRect().top - (q('beam')?.getBoundingClientRect().top ?? 0);
    const h = (y: number) => Math.max(0.2, (top + y + 65) / 400);
    a('beam', [{ transform: `scaleY(${h(path[0])})`, opacity: 0 }, { transform: `scaleY(${h(path[0])})`, opacity: 1, offset: 0.12 },
      { transform: `scaleY(${h(path[1])})`, opacity: 1, offset: 0.5 }, { transform: `scaleY(${h(path[2])})`, opacity: 1 }], T.sweep, T.light - T.sweep, EASE.inOut);
    a('beam', [{ opacity: 1, transform: `scaleY(${h(path[2])})` }, { opacity: 0.4, offset: 0.4, transform: `scaleY(${h(path[2])})` },
      { opacity: 0, transform: `scaleY(${h(path[2])})` }], T.light, 1500, EASE.out, 'forwards');
    a('lamp', [{ opacity: 0 }, { opacity: 1 }], T.sweep - 100, 200);
    a('lamp', [{ opacity: 1 }, { opacity: 0.3 }], T.light, 1200, EASE.out, 'forwards');
  }

  // La bonne réponse s'allume, les autres s'éteignent.
  opts.forEach((el) => {
    const good = el.dataset.r === '1';
    if (good) {
      a(el, [{ transform: 'scale(1)', borderColor: 'rgba(255,255,255,.10)', backgroundColor: 'rgba(255,255,255,.05)', boxShadow: '0 0 0 0 rgba(91,227,166,0)' },
        { transform: 'scale(1.03)', borderColor: '#5BE3A6', backgroundColor: 'rgba(91,227,166,.12)',
          boxShadow: '0 0 0 6px rgba(91,227,166,.08),0 12px 40px -10px rgba(91,227,166,.55)' }], T.light, sp(0.35, 0.6));
      a(el.querySelector<HTMLElement>('[data-k="okb"]'), [{ transform: 'scale(.3)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], T.light + 60, sp(0.3, 0.5));
      a(el.querySelector<HTMLElement>('[data-k="shapeOn"]'), [{ opacity: 0 }, { opacity: 1 }], T.light, 200);
    } else {
      a(el, [{ backgroundColor: 'rgba(255,255,255,.05)', borderColor: 'rgba(255,255,255,.10)' },
        { backgroundColor: 'rgba(255,255,255,.025)', borderColor: 'rgba(255,255,255,.06)' }], T.light, 220);
      a(el.querySelector<HTMLElement>('[data-k="shape"]'), [{ opacity: 1 }, { opacity: 0.45 }], T.light, 220);
      a(el.querySelector<HTMLElement>('[data-k="olabel"] > *'), [{ color: N.t1 }, { color: N.t2 }], T.light, 220);
      a(el.querySelector<HTMLElement>('[data-k="track"]'), [{ opacity: 1 }, { opacity: 0.7 }], T.light, 220);
    }
  });
  if (o.axisKind) {
    a('ax-real', [{ transform: 'scaleY(0)' }, { transform: 'scaleY(1)' }], T.light, 420);
    a('ax-tag', [{ opacity: 0, transform: 'translateX(-50%) translateY(6px) scale(.7)' }, { opacity: 1, transform: 'translateX(-50%) scale(1)' }], T.light + 200, sp(0.3, 0.55));
    a('hero', [{ opacity: 0, transform: 'translateY(8px)' }, { opacity: 1, transform: 'none' }], T.light, sp(0.4, 0.9));
    qa('ax-gap').forEach((g) => a(g, [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], T.counts, 380));
    qa('ax-glab').forEach((g) => a(g, [{ opacity: 0 }, { opacity: 1 }], T.counts + 300, 220));
  }

  // Chaque visage quitte la rangée et tombe sur SA réponse.
  const from = new Map(faces.map((f) => [f.dataset.p ?? '', f]));
  const used = new Set<HTMLElement>();
  Array.from(root.querySelectorAll<HTMLElement>('[data-dest]')).forEach((dest, i) => {
    const src = from.get(dest.dataset.dest ?? '');
    const t = T.fly + i * T.flyGap;
    if (!src) {
      a(dest, [{ opacity: 0, transform: 'scale(.6)' }, { opacity: 1, transform: 'none' }], t, sp(0.45, 0.72));
      return;
    }
    const s0 = src.getBoundingClientRect();
    const d0 = dest.getBoundingClientRect();
    const dx = s0.left + s0.width / 2 - (d0.left + d0.width / 2);
    const dy = s0.top + s0.height / 2 - (d0.top + d0.height / 2);
    used.add(src);
    a(src, [{ opacity: 1 }, { opacity: 0 }], t, 120, EASE.out, 'forwards');
    a(dest, [{ transform: `translate(${dx}px,${dy}px) scale(1.4)`, opacity: 0 }, { transform: `translate(${dx}px,${dy}px) scale(1.4)`, opacity: 1, offset: 0.05 },
      { transform: 'none', opacity: 1 }], t, sp(0.45, 0.72));
  });

  faces.forEach((f) => { if (!used.has(f)) a(f, [{ opacity: 1 }, { opacity: 0 }], T.fly, 160, EASE.out, 'forwards'); });

  // Les barres poussent (léger dépassement), les comptes arrivent.
  qa('fill').forEach((f, j) => {
    a(f, [{ opacity: 0 }, { opacity: 1 }], T.fly, 200);
    a(f, [{ width: '0px' }, { width: getComputedStyle(f).width }], T.bar + j * T.barGap, sp(0.5, 0.62));
  });
  qa('count').forEach((c, j) => a(c, [{ opacity: 0, transform: 'translateY(6px)' }, { opacity: 1, transform: 'none' }], T.counts + j * 40, 260));
  a('rare', [{ transform: 'scale(.6)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], T.rare, sp(0.35, 0.55));

  // Ma carte.
  a('mecard', [{ transform: 'translateY(40px)', opacity: 0 }, { transform: 'none', opacity: 1 }], T.card, sp(0.45, 0.8));
  a('acts', [{ opacity: 0 }, { opacity: 1 }], T.acts, 300);
  a('wait', [{ opacity: 0 }, { opacity: 1 }], T.acts, 300);
  a('passer', [{ opacity: 1 }, { opacity: 0 }], T.acts, 300);
  if (o.unanimous) {
    root.querySelectorAll<HTMLElement>('[data-k="opt"][data-r="1"] [data-dest]').forEach((d, i) => {
      a(d, [{ translate: '0 0' }, { translate: '0 -10px' }, { translate: '0 0' }], 2150 + i * 70, 300, EASE.inOut);
    });
  }
  if (o.party) confetti(root.querySelector<HTMLElement>('[data-fx]'), a, { start: T.conf, count: 90, seed: 11 });
}

/** La couverture respire (7 s), coupée par « Réduire les animations ». */
function breathe(s: StageCtx) {
  s.loop(s.q('cv1'), [{ transform: 'translate(0,0)' }, { transform: 'translate(60px,30px)' }], { duration: 7000, iterations: Infinity, direction: 'alternate', easing: 'ease-in-out' });
  s.loop(s.q('cv2'), [{ transform: 'translate(0,0)' }, { transform: 'translate(-70px,40px)' }], { duration: 6000, iterations: Infinity, direction: 'alternate', easing: 'ease-in-out' });
}

function StageCover({ look }: { look: ReturnType<typeof terrainLook> }) {
  return (
    <View pointerEvents="none" aria-hidden style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 300, overflow: 'hidden' }}>
      <K k="cv1" style={web({ position: 'absolute', width: 280, height: 280, left: -70, top: -120, borderRadius: 999, backgroundColor: look.to, opacity: 0.55, filter: 'blur(60px)' })} />
      <K k="cv2" style={web({ position: 'absolute', width: 240, height: 240, right: -40, top: -110, borderRadius: 999, backgroundColor: N.lav2, opacity: 0.55, filter: 'blur(60px)' })} />
      <Text style={[{ position: 'absolute', right: -40, top: 20, fontSize: 190, opacity: 0.12 }, web({ transform: 'rotate(-12deg)' }) as object]}>{look.emoji}</Text>
      <View style={web({ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, backgroundImage: `linear-gradient(180deg, ${N.stage}00 0%, ${N.stage} 96%)` })} />
    </View>
  );
}

function SealHalf({ side, look, me }: { side: 'l' | 'r'; look: ReturnType<typeof terrainLook>; me: boolean }) {
  const clip = side === 'l' ? 'polygon(0 0,52% 0,44% 22%,57% 42%,45% 60%,56% 80%,49% 100%,0 100%)'
    : 'polygon(52% 0,100% 0,100% 100%,49% 100%,56% 80%,45% 60%,57% 42%,44% 22%)';
  return (
    <View style={web({ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, borderRadius: 999, alignItems: 'center', justifyContent: 'center',
      clipPath: clip, backgroundImage: `radial-gradient(70% 70% at 30% 25%,rgba(255,255,255,.55),rgba(255,255,255,0) 60%),linear-gradient(145deg,${look.from},${look.to} 75%)`,
      boxShadow: `0 0 0 2px ${N.stage}${me ? `,0 0 0 4px ${N.t1}` : ''},inset 0 -3px 6px rgba(40,0,40,.45),inset 0 1px 0 rgba(255,255,255,.5)` })}>
      <Text style={{ fontSize: 17 }}>{look.emoji}</Text>
    </View>
  );
}

/** Nombre et heure : la vraie valeur en grand, puis l'axe. */
function AxisBlock({ p }: { p: V2 }) {
  const { real } = axis(p);
  return (
    <View style={{ gap: 12 }}>
      <K k="hero" style={web({ padding: 16, borderRadius: 24, borderWidth: 1, borderColor: 'rgba(91,227,166,0.35)', backgroundColor: N.s1,
        backgroundImage: 'radial-gradient(120% 140% at 0% 0%,rgba(91,227,166,.22),rgba(91,227,166,.03) 60%)' })}>
        <Text style={[text(12, '700', N.mint), { letterSpacing: 1 }]}>{p.kind === 'when' ? 'C’EST ARRIVÉ À' : 'LE VRAI COMPTE'}</Text>
        <Text style={[num(52, N.mint), { marginTop: 6 }]}>{real == null ? '—' : axisLabel(p.kind, real)}</Text>
      </K>
      <K k="axis" style={{ backgroundColor: N.s1, borderRadius: 24, borderWidth: 1, borderColor: N.line, paddingHorizontal: 16, paddingTop: 14, paddingBottom: 10 }}>
        <Axis p={p} stage />
      </K>
    </View>
  );
}

type Value = { n: number | null; tone: 'mint' | 'miss' | 'lav'; label: string; say: string; roll: boolean; unit: 'potato' | 'points' };

/** Ce que ma carte affiche à droite : récolte, au compost, rendues, ou les points (pour l'honneur). */
function cardValue(p: V2, fate: ReturnType<typeof myFate>, meRight: boolean, unanimous: boolean, pot: boolean): Value {
  if (pot && fate && fate.stake > 0) {
    if (fate.kind === 'refund') return { n: fate.stake, tone: 'lav', label: 'Rendus', say: `${fate.stake} confettis rendus`, roll: false, unit: 'potato' };
    if (fate.kind === 'harvest') {
      return { n: fate.harvest, tone: 'mint', label: 'Tu ramasses', roll: true, unit: 'potato',
        say: `tu ramasses ${fate.harvest} confettis${p.settled ? '' : ', en attente 12 heures'}` };
    }
    if (fate.kind === 'compost') return { n: fate.stake, tone: 'miss', label: 'Au balai', say: `${fate.stake} confettis au balai`, roll: false, unit: 'potato' };
  }
  if (meRight && !unanimous) return { n: p.points, tone: 'mint', label: 'Au classement', say: `${p.points} points au classement`, roll: true, unit: 'points' };
  return { n: null, tone: 'miss', label: '', say: '', roll: false, unit: 'points' };
}

function MeCard({ p, played, meRight, unanimous, value, ended, onShare, onDone }: {
  p: V2; played: boolean; meRight: boolean; unanimous: boolean; value: Value; ended: boolean; onShare: () => void; onDone: () => void;
}) {
  const edge = !played ? N.line2 : unanimous ? N.lav : meRight ? N.mint : N.miss;
  const pending = value.unit === 'potato' && value.tone === 'mint' && !p.settled;
  const color = value.tone === 'mint' ? N.mint : value.tone === 'lav' ? N.lav : N.missText;
  const title = !played ? 'Tu n’as pas joué' : unanimous ? 'Vu juste, comme tous' : meRight ? 'Tu avais vu juste' : 'Pas cette fois';
  const sub = !played ? 'Le prochain, c’est le tien.' : unanimous ? (value.unit === 'potato' ? 'Personne ne perd rien.' : 'Toute la bande avait vu juste.')
    : meRight ? (value.unit === 'potato' && p.my_answer?.stake ? `Tu en avais lancé ${p.my_answer.stake} 🎊` : `Ta réponse : ${myAnswerText(p)}`)
      : `Ta réponse : ${myAnswerText(p)}. La bonne : ${rightText(p) || '—'}.`;
  return (
    <K k="mecard" role="status" testID="prono-reveal-me"
      style={web({ position: 'absolute', left: 12, right: 12, bottom: 26, zIndex: 25, maxWidth: 496, marginHorizontal: 'auto', borderRadius: 24,
        padding: 14, overflow: 'hidden', backgroundColor: N.glass, borderWidth: 1, borderColor: N.line2, backdropFilter: 'blur(24px)',
        WebkitBackdropFilter: 'blur(24px)', boxShadow: '0 20px 50px -10px rgba(0,0,0,.6)' })}>
      <View style={{ position: 'absolute', left: 0, right: 0, top: 0, height: 2, backgroundColor: edge }} />
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
        <View style={{ width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center',
          backgroundColor: !played ? 'rgba(255,255,255,0.08)' : unanimous ? 'rgba(185,167,255,0.18)' : meRight ? N.mint : 'rgba(139,132,168,0.2)',
          borderWidth: played && !meRight && !unanimous ? 2 : 0, borderColor: N.miss }}>
          <Text style={text(20, '800', meRight && !unanimous ? N.ink : unanimous ? N.lav : N.missText)}>
            {!played ? '·' : unanimous ? '🤝' : meRight ? '✓' : '○'}
          </Text>
        </View>
        <View style={{ flex: 1, minWidth: 0 }}>
          <Text style={text(17, '700')} numberOfLines={1}>{title}</Text>
          <Text style={[text(13, '500', N.t2), { marginTop: 3 }]} numberOfLines={2}>{sub}</Text>
        </View>
        {value.n != null ? (
          <View style={{ alignItems: 'flex-end' }}>
            <Text style={[text(11, '700', value.tone === 'mint' ? N.mint : N.t2), { letterSpacing: 1, textTransform: 'uppercase', marginBottom: 5 }]}>{value.label}</Text>
            <View style={{ flexDirection: 'row', alignItems: 'baseline' }}>
              {value.roll ? <Roll to={value.n} delay={T.roll} duration={T.rollDur} done={ended} style={num(30, color)} />
                : <Text style={num(30, color)}>{value.n}</Text>}
              <Text style={num(value.unit === 'potato' ? 30 : 15, color)}>{value.unit === 'potato' ? ' 🎊' : ` pt${value.n > 1 ? 's' : ''}`}</Text>
            </View>
          </View>
        ) : null}
      </View>
      {pending ? (
        <K k="wait" style={{ flexDirection: 'row', alignItems: 'center', gap: 6, marginTop: 10 }}>
          <Text style={text(13, '500', N.t2)}>⏳ En attente 12 h, le temps de contester</Text>
        </K>
      ) : null}
      <K k="acts" style={{ flexDirection: 'row', gap: 8, marginTop: 12 }}>
        {meRight && !unanimous ? <GlassButton label="🔮 Partager" onPress={onShare} style={{ flex: 1 }} testID="prono-reveal-share" />
          : <GlassButton label="Réactions 😂" onPress={onDone} style={{ flex: 1 }} />}
        <GlassButton label="Voir tout ›" onPress={onDone} style={{ flex: 1 }} testID="prono-reveal-done" />
      </K>
    </K>
  );
}
