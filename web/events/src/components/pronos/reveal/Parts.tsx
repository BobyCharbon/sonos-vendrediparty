import { useState } from 'react';
import { Text, View, type LayoutChangeEvent } from 'react-native';

import { FaceRing, FaceStack, Shape } from './Bits';
import { K, spring, useStage } from './fx';
import { axis, axisLabel, axisScale, gapText, type Row, type V2 } from './model';
import { N, num, text, web } from './theme';

/**
 * Pièces des réponses, partagées par le dévoilement (animées par la scène) et le résultat (posées) : la ligne d'une
 * réponse avec sa barre et ses visages, et l'axe « le plus proche » (nombre, heure).
 */

const STACK = 24;
const stackWidth = (n: number) => (n ? STACK + 4 + (Math.min(n, 7) - 1) * STACK * 0.78 + (n > 7 ? 22 : 0) : 0);

/** Une réponse : forme, libellé, compte et %, barre qui porte les visages au bout. */
export function OptionRow({ row, total, big, potatoes, settled = true, index, stage }: {
  row: Row; total: number; big?: boolean; potatoes?: boolean; settled?: boolean; index: number; stage?: boolean;
}) {
  const pct = total ? Math.round((row.count * 100) / total) : 0;
  const right = row.right && settled;
  const dim = settled && !row.right;
  return (
    <K k="opt" testID={`prono-reveal-row-${index}`}
      accessibilityLabel={`${row.label} : ${row.count} sur ${total}${right ? ', bonne réponse' : ''}`}
      style={[web({ borderRadius: 20, paddingHorizontal: 14, paddingTop: big ? 18 : 10, paddingBottom: big ? 20 : 12,
        backgroundColor: right ? 'rgba(91,227,166,0.12)' : dim ? 'rgba(255,255,255,0.025)' : 'rgba(255,255,255,0.05)',
        borderWidth: right ? 2 : 1, borderColor: right ? N.mint : dim ? 'rgba(255,255,255,0.06)' : 'rgba(255,255,255,0.10)',
        boxShadow: right ? '0 0 0 6px rgba(91,227,166,.08), 0 12px 40px -10px rgba(91,227,166,.55)' : 'none',
        transform: right && stage ? 'scale(1.03)' : 'none' })]}
      data={{ r: right ? '1' : '0' }}>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 32 }}>
        <View>
          <K k="shape" style={{ opacity: dim ? 0.45 : 1 }}><Shape shape={row.shape} /></K>
          {right ? <K k="shapeOn" style={{ position: 'absolute', left: 0, top: 0 }}><Shape shape={row.shape} on /></K> : null}
        </View>
        <K k="olabel" style={{ flex: 1 }}>
          <Text style={text(big ? 26 : 17, '700', dim ? N.t2 : N.t1)} numberOfLines={1}>{row.label}</Text>
        </K>
        <K k="count" style={{ flexDirection: 'row', alignItems: 'baseline', gap: 6 }}>
          {potatoes ? <Text style={text(13, '600', N.t2)}>{row.planted} 🥔 ·</Text> : null}
          <Text style={num(22, dim ? N.t2 : N.t1)}>{row.count}</Text>
          <Text style={text(13, '600', N.t2)}>{pct} %</Text>
        </K>
      </View>
      <K k="track" style={{ height: 10, marginTop: 8, borderRadius: 5, backgroundColor: 'rgba(255,255,255,0.07)', opacity: dim ? 0.7 : 1 }}>
        <K k="fill" style={web({ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(row.count * 100) / Math.max(1, total)}%`,
          minWidth: stackWidth(row.faces.length), borderRadius: 5, flexDirection: 'row', justifyContent: 'flex-end', alignItems: 'center',
          backgroundImage: right ? 'linear-gradient(90deg,#2FB984,#5BE3A6)' : 'linear-gradient(90deg,rgba(185,167,255,.35),rgba(185,167,255,.7))' })}>
          {row.faces.length ? (
            <View style={{ marginVertical: -8 }}>
              <FaceStack faces={row.faces} size={STACK} ring={right ? '#123a33' : '#15112a'} k={stage ? 'dest' : undefined} />
            </View>
          ) : null}
        </K>
      </K>
      {right ? (
        <K k="okb" style={{ position: 'absolute', right: 12, top: -12, height: 22, paddingHorizontal: 9, borderRadius: 999, backgroundColor: N.mint,
          justifyContent: 'center' }}>
          <Text style={text(12, '800', N.ink)}>✓ Bonne réponse</Text>
        </K>
      ) : null}
    </K>
  );
}

/** Une réponse libre (dévoilement et résultat) : le visage, le texte, la coche des bonnes réponses. */
export function TextRow({ face, body, right, stage }: { face: V2['answered'][number]; body: string; right: boolean; stage?: boolean }) {
  return (
    <K k="opt" data={{ r: right ? '1' : '0' }} style={{ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingHorizontal: 14, borderRadius: 18,
      backgroundColor: right ? 'rgba(91,227,166,0.12)' : 'rgba(255,255,255,0.04)', borderWidth: right ? 2 : 1,
      borderColor: right ? N.mint : 'rgba(255,255,255,0.08)' }} accessibilityLabel={`${face.me ? 'Toi' : face.name} : ${body}${right ? ', bonne réponse' : ''}`}>
      <View {...(stage ? ({ dataSet: { dest: face.id } } as object) : {})}><FaceRing face={face} size={32} ring={N.s1} /></View>
      <View style={{ flex: 1 }}>
        <Text style={text(16, '700', right ? N.t1 : N.t2)} numberOfLines={2}>{body}</Text>
        <Text style={text(12.5, '500', N.t2)}>{face.me ? 'Toi' : face.name}</Text>
      </View>
      {right ? <Text style={text(14, '800', N.mint)}>✓</Text> : null}
    </K>
  );
}

const LH = 36;
const TOP = 42;

/**
 * L'axe « le plus proche » (maquettes 4-resultat-nombre / -heure) : la vraie valeur en menthe, chaque réponse posée à
 * sa place (couloirs pour ne pas se chevaucher), les écarts du ou des plus proches en menthe, le mien en pointillés.
 * `intro` : l'entrée propre au résultat (la vraie valeur tombe, les réponses se posent, les écarts se tracent).
 */
export function Axis({ p, intro, stage }: { p: V2; intro?: boolean; stage?: boolean }) {
  const [w, setW] = useState(0);
  const { real, points } = axis(p);
  const { root } = useStage((s) => {
    if (!intro) return;
    const sp = spring(0.3, 0.55);
    s.a('ax-real', [{ transform: 'scaleY(0)' }, { transform: 'scaleY(1)' }], 150, 420);
    s.a('ax-tag', [{ opacity: 0, transform: 'translateX(-50%) translateY(6px) scale(.7)' }, { opacity: 1, transform: 'translateX(-50%) scale(1)' }], 350, sp);
    const dots = s.qa('ax-dot').sort((a, b) => Number(b.dataset.g) - Number(a.dataset.g));
    dots.forEach((d, i) => s.a(d, [{ opacity: 0, transform: 'translateY(-26px) scale(.6)' }, { opacity: 1, transform: 'none' }], 520 + i * 55, spring(0.4, 0.62)));
    const tG = 520 + dots.length * 55 + 150;
    s.qa('ax-gap').forEach((g) => s.a(g, [{ transform: 'scaleX(0)' }, { transform: 'scaleX(1)' }], tG, 380));
    s.qa('ax-glab').forEach((g) => s.a(g, [{ opacity: 0 }, { opacity: 1 }], tG + 300, 220));
  }, 2200, [p.id, w > 0, !!intro]);
  if (real == null || !points.length) return null;
  const kind = p.kind;
  const sc = axisScale(kind, [...points.map((x) => x.value), real]);
  const pad = 22;
  const X = (v: number) => pad + ((v - sc.min) / Math.max(1e-9, sc.max - sc.min)) * Math.max(1, w - pad * 2);
  const lanes: number[] = [];
  const placed = [...points].sort((a, b) => a.value - b.value).map((pt) => {
    const x = X(pt.value);
    let l = 0;
    while (lanes[l] !== undefined && x - lanes[l] < 31) l++;
    lanes[l] = x;
    return { pt, x, lane: l };
  });
  const axisY = TOP + Math.max(1, lanes.length) * LH + 8;
  const H = axisY + 34;
  const xr = X(real);
  const onLayout = (e: LayoutChangeEvent) => setW(Math.round(e.nativeEvent.layout.width));
  return (
    <View ref={root} onLayout={onLayout} style={{ height: H, position: 'relative' }}
      accessibilityLabel={`Les réponses sur un axe : la vraie valeur est ${axisLabel(kind, real)}`}>
      {w ? (
        <>
          <K k="ax-real" style={web({ position: 'absolute', left: xr - 1.5, top: TOP - 6, width: 3, height: axisY - TOP + 14, borderRadius: 2,
            backgroundImage: 'linear-gradient(180deg,#5BE3A6,rgba(91,227,166,.25))', boxShadow: '0 0 14px rgba(91,227,166,.7)', transformOrigin: '50% 0' })} />
          <K k="ax-tag" style={web({ position: 'absolute', left: xr, top: 0, transform: 'translateX(-50%)', height: 24, paddingHorizontal: 9,
            borderRadius: 999, backgroundColor: N.mint, justifyContent: 'center', zIndex: 3 })}>
            <Text style={num(13, N.ink)} numberOfLines={1}>{axisLabel(kind, real)}</Text>
          </K>
          <View style={{ position: 'absolute', left: 10, right: 10, top: axisY - 1, height: 2, borderRadius: 1, backgroundColor: 'rgba(255,255,255,0.18)' }} />
          {sc.ticks.map((t) => (
            <View key={t} style={{ position: 'absolute', left: X(t) - 30, width: 60, top: axisY - 4, alignItems: 'center' }}>
              <View style={{ width: 1.5, height: 8, backgroundColor: 'rgba(255,255,255,0.3)' }} />
              <Text style={[text(12, '600', N.t2), { marginTop: 4, textAlign: 'center' }]} numberOfLines={1}>{axisLabel(kind, t)}</Text>
            </View>
          ))}
          {placed.map(({ pt, x, lane }) => {
            const y = axisY - 22 - lane * LH;
            const show = pt.winner || pt.face.me;
            const x1 = Math.min(x, xr);
            const gw = Math.abs(x - xr);
            const fromRight = x < xr;
            return (
              <View key={pt.face.id} style={{ position: 'absolute', left: 0, top: 0, right: 0, bottom: 0 }} pointerEvents="none">
                {show && gw > 16 ? (
                  <>
                    <K k="ax-gap" style={web({ position: 'absolute', left: x1, width: gw, top: y - (pt.winner ? 1.5 : 1), height: pt.winner ? 3 : 2,
                      transformOrigin: fromRight ? '100% 50%' : '0 50%',
                      backgroundImage: pt.winner ? 'none' : 'repeating-linear-gradient(90deg,rgba(201,196,221,.7) 0 4px,transparent 4px 7px)',
                      backgroundColor: pt.winner ? N.mint : 'transparent' })} />
                    {gw >= 44 ? (
                      <K k="ax-glab" style={web({ position: 'absolute', left: x1 + gw / 2, top: y - 17, transform: 'translateX(-50%)',
                        backgroundColor: N.s1, paddingHorizontal: 4, paddingVertical: 2, borderRadius: 4 })}>
                        <Text style={text(11, '700', pt.winner ? N.mint : N.missText)}>{gapText(kind, pt.gap)}</Text>
                      </K>
                    ) : null}
                  </>
                ) : null}
                <View style={{ position: 'absolute', left: x, top: y, width: 1, height: axisY - y, backgroundColor: 'rgba(255,255,255,0.12)' }} />
                <View style={{ position: 'absolute', left: x - 16, top: y - 16 }}
                  {...({ dataSet: { k: 'ax-dot', g: String(pt.gap), ...(stage ? { dest: pt.face.id } : {}) } } as object)}>
                  <FaceRing face={pt.face} size={28} ring={N.s1} glow={pt.winner ? N.mint : undefined} />
                  {pt.winner ? <Text style={{ position: 'absolute', right: -8, top: -9, fontSize: 13 }}>🎯</Text> : null}
                </View>
              </View>
            );
          })}
        </>
      ) : null}
    </View>
  );
}
