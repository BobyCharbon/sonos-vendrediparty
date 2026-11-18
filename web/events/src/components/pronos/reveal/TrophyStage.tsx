import { useState } from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';

import { rpc } from '@/lib/pronos';

import { FaceRing, GlassButton, PinkButton, TerrainChip } from './Bits';
import { Announce, EASE, FxLayer, glitter, K, spring, useStage } from './fx';
import { laureates, nameOf, terrainChip, type V2 } from './model';
import { band, N, round, text, web } from './theme';

/**
 * Trophée de la soirée (maquette 4-trophee) : le projecteur cherche, le sceau doré frissonne puis craque, le visage
 * du ou de la lauréat·e, le halo, des paillettes dorées qui MONTENT (jamais de confettis : réservés à une bonne
 * réponse). Seul le nombre de voix du ou de la gagnant·e est dit (« 7 des 12 »). Jamais de patates.
 */

const T = { cat: 250, beam: 600, shake: 1450, crack: 1800, name: 2000, votes: 2200, glit: 2300, acts: 3000, END: 3800 };

export function TrophyStage({ p, onDone }: { p: V2; onDone: () => void }) {
  const { people, voters } = laureates(p);
  const win = people[0] ?? null;
  const tie = people.slice(1);
  const [clapped, setClapped] = useState(() => !!p.reactions?.find((r) => r.emoji === '👏')?.mine);
  const cat = p.award_label ?? 'Trophée de la soirée';
  const emoji = p.award_emoji ?? '🏆';
  const { root, ended, skip } = useStage((s) => {
    const { a, q } = s;
    a('band', [{ transform: 'rotate(-9deg) scale(1.35)', opacity: 0 }, { transform: 'rotate(-3deg) scale(1)', opacity: 1 }], 0, spring(0.35, 0.55));
    a('em', [{ transform: 'scale(.2)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], T.cat, spring(0.3, 0.5));
    a('cat', [{ transform: 'translateY(10px)', opacity: 0 }, { transform: 'none', opacity: 1 }], T.cat + 50, 380);
    a('beam', [{ transform: 'rotate(0deg)', opacity: 0 }, { transform: 'rotate(15deg)', opacity: 1, offset: 0.2 }, { transform: 'rotate(-15deg)', opacity: 1, offset: 0.6 },
      { transform: 'rotate(8deg)', opacity: 1, offset: 0.85 }, { transform: 'rotate(0deg) scaleX(.8)', opacity: 1 }], T.beam, T.crack - T.beam, EASE.inOut);
    a('beam', [{ opacity: 1, transform: 'rotate(0deg) scaleX(.8)' }, { opacity: 0, transform: 'rotate(0deg) scaleX(.8)' }], T.crack, 300, EASE.out, 'forwards');
    a('beam2', [{ opacity: 0, transform: 'scaleX(.6)' }, { opacity: 1, transform: 'scaleX(1)' }], T.crack, spring(0.5, 0.8));
    a('floor', [{ opacity: 0, transform: 'scale(.4)' }, { opacity: 1, transform: 'scale(1)' }], T.crack, 500);
    a('seal', [{ transform: 'rotate(0)', opacity: 1 }, { transform: 'rotate(-4deg)', opacity: 1, offset: 0.2 }, { transform: 'rotate(4deg)', opacity: 1, offset: 0.4 },
      { transform: 'rotate(-4deg)', opacity: 1, offset: 0.6 }, { transform: 'rotate(4deg)', opacity: 1, offset: 0.8 }, { transform: 'rotate(0)', opacity: 1 }], T.shake, 300, 'linear');
    a('sl', [{ transform: 'none', opacity: 1 }, { transform: 'translate(-26px,20px) rotate(-30deg)', opacity: 0 }], T.crack, 300);
    a('sr', [{ transform: 'none', opacity: 1 }, { transform: 'translate(26px,20px) rotate(30deg)', opacity: 0 }], T.crack, 300);
    a('face', [{ transform: 'scale(.6)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], T.crack + 20, spring(0.4, 0.55));
    a('halo', [{ transform: 'scale(.7)', opacity: 0 }, { transform: 'scale(1)', opacity: 1 }], T.crack + 80, spring(0.45, 0.6));
    a('name', [{ transform: 'translateY(14px)', opacity: 0 }, { transform: 'none', opacity: 1 }], T.name, spring(0.45, 0.8));
    a('votes', [{ opacity: 0 }, { opacity: 1 }], T.votes, 300);
    a('acts', [{ opacity: 0 }, { opacity: 1 }], T.acts, 300);
    a('foot', [{ opacity: 0 }, { opacity: 1 }], T.acts, 300);
    a('passer', [{ opacity: 1 }, { opacity: 0 }], T.acts, 300);
    s.loop(q('halo-spin'), [{ transform: 'rotate(0deg)' }, { transform: 'rotate(360deg)' }], { duration: 12000, iterations: Infinity });
    glitter(s.root.querySelector<HTMLElement>('[data-fx]'), a, { start: T.glit, count: 40, bottom: 500 });
  }, T.END, [p.id, p.result?.at ?? '']);

  const say = win ? `Trophée de la soirée, ${cat} : ${nameOf(win)}${win.votes ? `, choisi·e par ${win.votes} des ${voters} votants` : ''}.`
    : 'Trophée de la soirée : pas encore de lauréat.';
  async function clap() {
    setClapped((c) => !c);
    try { await rpc('prono_react', { id: p.id, emoji: '👏' }); } catch { setClapped((c) => !c); }
  }

  return (
    <View ref={root} testID="prono-reveal-stage" accessibilityViewIsModal aria-modal role="dialog" aria-label="Trophée de la soirée"
      style={web({ position: 'fixed', left: 0, right: 0, top: 0, bottom: 0, zIndex: 1000, backgroundColor: N.stage, overflow: 'hidden' })}>
      <Announce>{say}</Announce>
      <View pointerEvents="none" style={web({ position: 'absolute', left: 0, right: 0, top: 0, bottom: 0, zIndex: 1,
        backgroundImage: 'radial-gradient(110% 70% at 50% 42%,transparent 40%,rgba(0,0,0,.75))' })} />
      <ScrollView style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 170 }}>
        <View style={{ width: '100%', maxWidth: 520, alignSelf: 'center' }}>
          <View pointerEvents="none" style={web({ position: 'absolute', left: 0, right: 0, top: 0, height: 620, filter: 'blur(16px)', zIndex: 2 })}>
            <K k="beam" style={web({ position: 'absolute', left: '50%', top: 60, width: 360, marginLeft: -180, height: 470, transformOrigin: '50% 0', opacity: 0,
              clipPath: 'polygon(46% 0,54% 0,86% 100%,14% 100%)',
              backgroundImage: 'linear-gradient(180deg,rgba(255,240,200,0),rgba(220,210,255,.18) 60%,rgba(220,210,255,.30))' })} />
            <K k="beam2" style={web({ position: 'absolute', left: '50%', top: 60, width: 360, marginLeft: -180, height: 470, transformOrigin: '50% 0',
              clipPath: 'polygon(46% 0,54% 0,86% 100%,14% 100%)',
              backgroundImage: 'linear-gradient(180deg,rgba(255,240,200,0),rgba(255,236,170,.22) 60%,rgba(255,226,122,.38))' })} />
          </View>
          <K k="floor" pointerEvents="none" style={web({ position: 'absolute', left: '50%', top: 452, width: 300, height: 44, marginLeft: -150, borderRadius: 999,
            zIndex: 2, backgroundImage: 'radial-gradient(closest-side,rgba(255,226,122,.55),rgba(255,226,122,0))' })} />

          <View style={{ zIndex: 20, height: 56, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', paddingHorizontal: 12 }}>
            <GlassButton round label="‹" a11y="Retour à la fiche" onPress={onDone} testID="prono-reveal-back" />
            <TerrainChip group={p.group} title={terrainChip(p)} />
            {ended ? <View style={{ width: 44 }} /> : <K k="passer"><GlassButton label="Passer" onPress={skip} testID="prono-reveal-skip" /></K>}
          </View>

          <View style={{ zIndex: 3, alignItems: 'center', paddingTop: 10 }}>
            <K k="band" style={web({ transform: 'rotate(-3deg)' })}>
              <View style={web({ paddingHorizontal: 14, paddingTop: 6, paddingBottom: 5, borderRadius: 6, backgroundImage: 'linear-gradient(135deg,#FFEA9C,#FFB347)',
                boxShadow: '0 6px 30px -6px rgba(255,179,71,.8)' })}>
                <Text style={band}>TROPHÉE DE LA SOIRÉE</Text>
              </View>
            </K>
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, marginTop: 16, paddingHorizontal: 20 }}>
              <K k="em"><Text style={{ fontSize: 40 }}>{emoji}</Text></K>
              <K k="cat" style={{ flexShrink: 1 }}><Text role="heading" aria-level={1} style={round(30, 34)}>{cat}</Text></K>
            </View>
          </View>

          <View style={{ zIndex: 3, height: 300, marginTop: 6 }} role="img" aria-label={say}>
            <View style={{ position: 'absolute', left: '50%', top: 44, width: 136, height: 136, marginLeft: -68 }}>
              <K k="halo" style={{ position: 'absolute', left: -10, top: -10, right: -10, bottom: -10 }}>
                <K k="halo-spin" style={web({ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, borderRadius: 999,
                  backgroundImage: 'conic-gradient(from 0deg,#FFEA9C,#FFB347,#FFF6CC,#FFB347,#FFEA9C)',
                  WebkitMask: 'radial-gradient(closest-side,transparent calc(100% - 6px),#000 calc(100% - 5px))',
                  mask: 'radial-gradient(closest-side,transparent calc(100% - 6px),#000 calc(100% - 5px))', filter: 'drop-shadow(0 0 18px rgba(255,214,102,.75))' })} />
              </K>
              <K k="face" style={{ position: 'absolute', left: 0, top: 0 }}>
                {win ? <FaceRing face={win} size={132} ring={N.stage} /> : <View style={{ width: 136, height: 136 }} />}
              </K>
              <K k="seal" pointerEvents="none" style={{ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, opacity: 0 }}>
                <GoldHalf k="sl" side="l" />
                <GoldHalf k="sr" side="r" />
              </K>
            </View>
            <View style={{ position: 'absolute', left: 0, right: 0, top: 200, alignItems: 'center', paddingHorizontal: 16 }}>
              <K k="name"><Text style={[round(40, 44), { textAlign: 'center' }]} numberOfLines={1}>{win ? nameOf(win) : 'Pas encore'}</Text></K>
              <K k="votes">
                <Text style={[text(15, '500', N.t2), { marginTop: 8, textAlign: 'center' }]}>
                  {win ? (win.votes ? `choisi·e par ${win.votes} des ${voters} votants` : `${voters} votants`) : 'Il faut au moins 3 votants.'}
                  {tie.length ? ` · ex æquo avec ${tie.map(nameOf).join(', ')}` : ''}
                </Text>
              </K>
            </View>
          </View>

          <K k="foot" style={{ alignItems: 'center', paddingHorizontal: 24, zIndex: 3 }}>
            <Text style={[text(13, '500', N.t2), { textAlign: 'center' }]}>
              {p.patates_on ? 'Pour la gloire : aucun trophée ne rapporte de confettis.' : 'Pour la gloire, rien d’autre.'}
            </Text>
          </K>

          {!ended ? (
            <Pressable accessible={false} focusable={false} onPress={skip} style={{ position: 'absolute', left: 0, right: 0, top: 56, bottom: 0, zIndex: 10 }} />
          ) : null}
        </View>
      </ScrollView>
      <K k="acts" style={web({ position: 'absolute', left: 16, right: 16, bottom: 30, zIndex: 25, flexDirection: 'row', gap: 10, maxWidth: 488,
        marginHorizontal: 'auto' })}>
        <PinkButton label={clapped ? '👏 Applaudi' : '👏 Applaudir'} onPress={() => void clap()} style={{ flex: 1 }} testID="prono-reveal-clap" />
        <GlassButton label="Voir tout ›" onPress={onDone} style={{ flex: 1, height: 52 }} testID="prono-reveal-done" />
      </K>
      <FxLayer style={{ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, zIndex: 30, overflow: 'hidden' }} />
    </View>
  );
}

function GoldHalf({ k, side }: { k: string; side: 'l' | 'r' }) {
  const clip = side === 'l' ? 'polygon(0 0,52% 0,44% 22%,57% 42%,45% 60%,56% 80%,49% 100%,0 100%)'
    : 'polygon(52% 0,100% 0,100% 100%,49% 100%,56% 80%,45% 60%,57% 42%,44% 22%)';
  return (
    <K k={k} style={web({ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0, borderRadius: 999, alignItems: 'center', justifyContent: 'center',
      clipPath: clip, boxShadow: 'inset 0 -6px 14px rgba(120,60,0,.45), inset 0 2px 0 rgba(255,255,255,.6)',
      backgroundImage: 'radial-gradient(60% 60% at 32% 26%,rgba(255,255,255,.6),rgba(255,255,255,0) 60%),linear-gradient(145deg,#FFEA9C,#F2A93B 70%,#C77E1A)' })}>
      <Text style={{ fontSize: 52 }}>🏆</Text>
    </K>
  );
}
