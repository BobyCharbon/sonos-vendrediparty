import type { ReactNode } from 'react';
import { Text, View } from 'react-native';

import type { Face } from '@/lib/pronos';

import { FaceRing } from '../reveal/Bits';
import { K, spring, useStage } from '../reveal/fx';
import { nameOf } from '../reveal/model';
import { N, num, text, web } from '../reveal/theme';

/**
 * Podium 2-1-3 qui monte (maquette 4-classement) : la 3e marche, puis la 2e, puis la 1re ; la couronne citron tombe
 * sur le premier avec un rebond et un éclat. « Réduire les animations » : tout est posé.
 */

export type PodiumSpot = { face: Face; rank: number; main: ReactNode; sub: string };

const SPOTS = [
  { at: 1, h: 100, w: 104, face: 56, t: 450 },
  { at: 0, h: 132, w: 120, face: 76, t: 700 },
  { at: 2, h: 76, w: 104, face: 56, t: 200 },
];

export function Podium({ spots, color = '#FF8FC0', replay }: { spots: PodiumSpot[]; color?: string; replay: string }) {
  const { root } = useStage((s) => {
    for (const spot of SPOTS) {
      const col = s.q(`col${spot.at}`);
      if (!col) continue;
      const step = col.querySelector<HTMLElement>('[data-k="step"]');
      const who = col.querySelector<HTMLElement>('[data-k="who"]');
      const rk = col.querySelector<HTMLElement>('[data-k="rk"]');
      s.a(step, [{ transform: 'scaleY(0)' }, { transform: 'scaleY(1)' }], spot.t, spring(0.5, 0.7));
      s.a(rk, [{ opacity: 0 }, { opacity: 1 }], spot.t + 200, 200);
      s.a(who, [{ transform: 'translateY(16px) scale(.7)', opacity: 0 }, { transform: 'none', opacity: 1 }], spot.t + 180, spring(0.35, 0.55));
    }
    s.a('crown', [{ transform: 'translateY(-46px) rotate(-14deg)', opacity: 0 }, { transform: 'translateY(-46px) rotate(-14deg)', opacity: 1, offset: 0.05 },
      { transform: 'none', opacity: 1 }], 1150, spring(0.4, 0.5));
    s.a('burst', [{ transform: 'scale(.3)', opacity: 0 }, { transform: 'scale(1.2)', opacity: 1, offset: 0.4 }, { transform: 'scale(1.5)', opacity: 0 }], 1250, 500);
  }, 1800, [replay, spots.length]);
  if (!spots.length) return null;
  const label = spots.map((s) => `${s.rank} ${nameOf(s.face)}`).join(', ');
  return (
    <View ref={root} accessibilityLabel={`Podium : ${label}`} testID="prono-podium"
      style={{ flexDirection: 'row', justifyContent: 'center', alignItems: 'flex-end', gap: 8, minHeight: 330, marginTop: 8 }}>
      {SPOTS.map((spot) => {
        const s = spots[spot.at];
        if (!s) return <View key={spot.at} style={{ width: spot.w }} />;
        const first = spot.at === 0;
        return (
          <K key={spot.at} k={`col${spot.at}`} style={{ width: spot.w, alignItems: 'center' }}>
            <K k="who" style={{ alignItems: 'center', marginBottom: 10 }}>
              {first ? (
                <>
                  <K k="burst" pointerEvents="none" style={web({ position: 'absolute', top: -30, left: '50%', width: 90, height: 90, marginLeft: -45, borderRadius: 999,
                    opacity: 0, backgroundImage: 'radial-gradient(closest-side,rgba(255,226,122,.6),rgba(255,226,122,0))' })} />
                  <K k="crown" style={{ position: 'absolute', top: -24, zIndex: 3 }}><Crown /></K>
                </>
              ) : null}
              <FaceRing face={s.face} size={spot.face} ring={N.bg} />
              <Text style={[text(15, '700'), { marginTop: 8, textAlign: 'center' }]} numberOfLines={1}>{nameOf(s.face)}</Text>
              <View style={{ marginTop: 4 }}>{s.main}</View>
              <Text style={[text(12, '500', N.t2), { marginTop: 3, textAlign: 'center' }]}>{s.sub}</Text>
            </K>
            <K k="step" style={web({ width: '100%', height: spot.h, borderTopLeftRadius: 18, borderTopRightRadius: 18, borderBottomLeftRadius: 6,
              borderBottomRightRadius: 6, overflow: 'hidden', alignItems: 'center', paddingTop: 10, transformOrigin: '50% 100%', borderWidth: 1,
              borderColor: N.line2, borderTopWidth: 2, borderTopColor: first ? N.lemon : color,
              backgroundImage: first ? 'linear-gradient(180deg,rgba(185,167,255,.30),rgba(185,167,255,.05))' : 'linear-gradient(180deg,rgba(185,167,255,.20),rgba(185,167,255,.04))',
              boxShadow: first ? 'inset 0 14px 26px -14px rgba(255,226,122,.55)' : 'none' })}>
              <K k="rk"><Text style={num(40, first ? N.lemon : 'rgba(244,241,255,0.92)')}>{s.rank}</Text></K>
            </K>
          </K>
        );
      })}
    </View>
  );
}

/** Couronne citron (dessinée en CSS : pas d'image). */
function Crown() {
  const clip = 'polygon(7.1% 33.3%, 28.6% 56.7%, 50% 13.3%, 71.4% 56.7%, 92.9% 33.3%, 84.5% 86.7%, 15.5% 86.7%)';
  const ball = (left: number, top: number, size: number, c: string) => (
    <View style={{ position: 'absolute', left: left - size / 2, top: top - size / 2, width: size, height: size, borderRadius: size / 2, backgroundColor: c }} />
  );
  return (
    <View aria-hidden style={web({ width: 42, height: 30, filter: 'drop-shadow(0 4px 10px rgba(255,200,80,.6))' })}>
      <View style={web({ position: 'absolute', left: 0, top: 0, width: 42, height: 30, clipPath: clip,
        backgroundImage: 'linear-gradient(180deg,#FFF3B8,#FFE27A 55%,#FFB347)' })} />
      <View style={{ position: 'absolute', left: 7, top: 23, width: 28, height: 3.5, borderRadius: 1.5, backgroundColor: '#E89A2E' }} />
      {ball(3, 9, 5.2, '#FFE27A')}
      {ball(21, 3.2, 5.6, '#FFF3B8')}
      {ball(39, 9, 5.2, '#FFE27A')}
    </View>
  );
}
