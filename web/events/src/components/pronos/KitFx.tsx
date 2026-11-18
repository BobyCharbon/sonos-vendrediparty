import { createElement, useEffect, useRef, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View, type StyleProp, type TextStyle, type ViewStyle } from 'react-native';

import { MAX_PLANT, PATATE } from '@/lib/pronos';

import { alpha, GROUP_FX_COLORS, pronoFont, pronoMotion, usePronoTheme, useReducedMotion, web } from './KitTheme';

/**
 * Effets du kit des Pronos (web) : confettis (bonne réponse seulement), paillettes dorées (trophée), projecteur,
 * chiffre qui roule, curseur « Planter des patates ». Tout est coupé par « Réduire les animations ».
 * À importer depuis '@/components/pronos/Kit'.
 */

const fx = StyleSheet.create({
  fallL: web({ animationKeyframes: [{ '0%': { transform: 'translate3d(0,-40px,0) rotate(0deg)', opacity: 1 }, '80%': { opacity: 1 },
    '100%': { transform: 'translate3d(-60px,880px,0) rotate(-560deg)', opacity: 0 } }], animationTimingFunction: 'cubic-bezier(.25,.6,.5,1)', animationFillMode: 'both' }),
  fallR: web({ animationKeyframes: [{ '0%': { transform: 'translate3d(0,-40px,0) rotate(0deg)', opacity: 1 }, '80%': { opacity: 1 },
    '100%': { transform: 'translate3d(70px,880px,0) rotate(620deg)', opacity: 0 } }], animationTimingFunction: 'cubic-bezier(.25,.6,.5,1)', animationFillMode: 'both' }),
  fallS: web({ animationKeyframes: [{ '0%': { transform: 'translate3d(0,-40px,0) rotate(0deg)', opacity: 1 }, '80%': { opacity: 1 },
    '100%': { transform: 'translate3d(10px,880px,0) rotate(400deg)', opacity: 0 } }], animationTimingFunction: 'cubic-bezier(.25,.6,.5,1)', animationFillMode: 'both' }),
  twinkle: web({ animationKeyframes: [{ '0%': { transform: 'translateY(0) scale(.2)', opacity: 0 }, '30%': { transform: 'translateY(-10px) scale(1)', opacity: 1 },
    '100%': { transform: 'translateY(-60px) scale(.4)', opacity: 0 } }], animationTimingFunction: pronoMotion.quint, animationFillMode: 'both' }),
  drop: web({ animationKeyframes: [{ '0%': { transform: 'translateY(-36px) rotate(-30deg)', opacity: 0 }, '40%': { opacity: 1 },
    '100%': { transform: 'translateY(0) rotate(-12deg)', opacity: 0 } }], animationDuration: '380ms', animationTimingFunction: pronoMotion.spring, animationFillMode: 'both' }),
});

/** Pseudo-hasard stable (même pluie à chaque rendu). */
const rnd = (i: number, salt: number) => {
  const x = Math.sin(i * 127.1 + salt * 311.7) * 43758.5453;
  return x - Math.floor(x);
};

/**
 * Confettis aux 6 couleurs de Party (seulement pour une bonne réponse) ; `variant="sparkle"` : paillettes dorées (trophée).
 * Se pose par-dessus son parent (position absolue, ne capte aucun toucher). `run` : les relancer en changeant de clé.
 */
export function Confetti({ run, variant = 'confetti', count, onDone }: { run: boolean; variant?: 'confetti' | 'sparkle'; count?: number; onDone?: () => void }) {
  const reduced = useReducedMotion();
  const n = count ?? (variant === 'sparkle' ? 26 : 70);
  useEffect(() => {
    if (!run || !onDone) return;
    const t = setTimeout(onDone, reduced ? 0 : 3000);
    return () => clearTimeout(t);
  }, [run, onDone, reduced]);
  if (!run || reduced) return null;
  return (
    <View pointerEvents="none" aria-hidden style={[StyleSheet.absoluteFill, { overflow: 'hidden', zIndex: 30 }]}>
      {Array.from({ length: n }, (_, i) => {
        if (variant === 'sparkle') {
          return (
            <Text key={i} style={[{ position: 'absolute', left: `${rnd(i, 1) * 100}%`, top: `${15 + rnd(i, 2) * 70}%`, fontSize: 10 + rnd(i, 3) * 14,
              color: i % 3 ? '#FFE27A' : '#FFF3B8' }, fx.twinkle, web({ animationDuration: `${1200 + rnd(i, 4) * 900}ms`, animationDelay: `${rnd(i, 5) * 900}ms`,
              textShadow: '0 0 8px rgba(255,226,122,.8)' })]}>✦</Text>
          );
        }
        const kind = i % 3 === 0 ? fx.fallL : i % 3 === 1 ? fx.fallR : fx.fallS;
        const w = 6 + rnd(i, 3) * 5;
        return (
          <View key={i} style={[{ position: 'absolute', left: `${rnd(i, 1) * 100}%`, top: -20, width: w, height: i % 4 === 0 ? w : w * 1.8,
            borderRadius: i % 4 === 0 ? w : 2, backgroundColor: GROUP_FX_COLORS[i % GROUP_FX_COLORS.length] }, kind,
            web({ animationDuration: `${1700 + rnd(i, 4) * 1100}ms`, animationDelay: `${rnd(i, 5) * 450}ms` })]} />
        );
      })}
    </View>
  );
}

/** Projecteur lavande (dévoilement) : faisceau depuis le haut, apparaît en fondu. */
export function Spotlight({ on, color = '#B9A7FF', style }: { on: boolean; color?: string; style?: StyleProp<ViewStyle> }) {
  const reduced = useReducedMotion();
  return (
    <View pointerEvents="none" aria-hidden style={[StyleSheet.absoluteFill, { opacity: on ? 1 : 0 },
      web({ backgroundImage: `radial-gradient(55% 45% at 50% 0%, ${alpha(color, 0.38)}, transparent 72%), conic-gradient(from 160deg at 50% -10%, transparent 0deg, ${alpha(color, 0.16)} 14deg, transparent 28deg, transparent 332deg, ${alpha(color, 0.16)} 346deg, transparent 360deg)`,
        transitionProperty: 'opacity', transitionDuration: reduced ? '150ms' : '500ms', transitionTimingFunction: pronoMotion.quint }), style]} />
  );
}

/** Chiffre qui roule de `from` à `value` (300 ms) : récolte « +18 », sac. Chiffres tabulaires. */
export function NumberRoll({ value, from = 0, duration = 300, sign, suffix, style }: {
  value: number; from?: number; duration?: number; sign?: boolean; suffix?: ReactNode; style?: StyleProp<TextStyle>;
}) {
  const reduced = useReducedMotion();
  const [shown, setShown] = useState(from);
  const start = useRef(from);
  useEffect(() => {
    if (reduced) return;
    const a = start.current;
    let raf = 0;
    const t0 = performance.now();
    const tick = (t: number) => {
      const k = Math.min(1, (t - t0) / duration);
      const eased = 1 - (1 - k) ** 3;
      setShown(Math.round(a + (value - a) * eased));
      if (k < 1) raf = requestAnimationFrame(tick);
      else start.current = value;
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, duration, reduced]);
  const n = reduced ? value : shown;
  return (
    <Text accessibilityLabel={`${sign && value > 0 ? 'plus ' : ''}${value}`} style={[pronoFont.num, style]}>
      {sign && n > 0 ? '+' : n < 0 ? '−' : ''}{Math.abs(n)}{suffix}
    </Text>
  );
}

const CHIPS = [{ n: 0, label: 'Sans' }, { n: 5, label: '5' }, { n: 10, label: '10' }, { n: 20, label: '20' }];

/**
 * « Planter des patates » : grand chiffre + 🥔, curseur 0–20 au pas de 1 (vrai curseur du navigateur : clavier et lecteur
 * d'écran), puces Sans / 5 / 10 / 20 (une 🥔 tombe dans le chiffre). `available` = sac + ce qui est déjà planté ici :
 * au-delà, rien n'est possible. `caption` s'affiche sous le chiffre (« plantées sur ▲ Suisse »).
 */
export function PatateSlider({ value, onChange, max = MAX_PLANT, available, showNumber = true, caption, testID = 'prono-plant' }: {
  value: number; onChange: (n: number) => void; max?: number; available?: number | null; showNumber?: boolean; caption?: ReactNode; testID?: string;
}) {
  const c = usePronoTheme();
  const reduced = useReducedMotion();
  const [drops, setDrops] = useState(0);
  const limit = Math.max(0, Math.min(max, available ?? max));
  const set = (n: number) => onChange(Math.max(0, Math.min(limit, Math.round(n))));
  const p = `${(Math.min(value, max) / max) * 100}%`;
  const input = createElement('input', {
    type: 'range', min: 0, max, step: 1, value, 'data-testid': `${testID}-range`,
    'aria-label': 'Patates à planter', 'aria-valuetext': value ? `${value} patate${value > 1 ? 's' : ''}` : 'Sans patates',
    onChange: (e: { target: { value: string } }) => set(Number(e.target.value)),
    style: { position: 'absolute', inset: 0, width: '100%', height: 44, margin: 0, opacity: 0, cursor: 'pointer', zIndex: 2 },
  });
  return (
    <View testID={testID}>
      {showNumber ? (
        <View style={{ alignItems: 'center', marginTop: 18 }}>
          <View style={{ flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, height: 76 }}>
            <Text style={[pronoFont.num, { color: c.potatoInk, fontSize: 68, lineHeight: 76 }]}>{value}</Text>
            <View>
              <Text style={{ fontSize: 44, transform: [{ rotate: '-12deg' }] }}>{PATATE}</Text>
              {drops && !reduced ? <Text key={drops} aria-hidden style={[{ position: 'absolute', left: 0, top: 0, fontSize: 44 }, fx.drop]}>{PATATE}</Text> : null}
            </View>
          </View>
          {caption ? <View style={{ marginTop: 2 }}>{typeof caption === 'string' ? <Text style={[pronoFont.text, { color: c.t2, fontSize: 14.5 }]}>{caption}</Text> : caption}</View> : null}
        </View>
      ) : null}
      <View style={{ marginTop: 20, marginHorizontal: 6, height: 44 }}>
        <View style={{ position: 'absolute', left: 0, right: 0, top: 17, height: 10, borderRadius: 5, backgroundColor: alpha(c.scheme === 'light' ? '#1D1530' : '#F4F1FF', 0.1) }} />
        <View style={[{ position: 'absolute', left: 0, top: 17, height: 10, borderRadius: 5, width: p as `${number}%` },
          web({ backgroundImage: 'linear-gradient(90deg, #F5C27A, #FF9F5A)', boxShadow: '0 0 16px -2px rgba(255,159,90,.6)' })]} />
        <View pointerEvents="none" style={[{ position: 'absolute', top: 2, left: p as `${number}%`, marginLeft: -20, width: 40, height: 40, borderRadius: 20,
          backgroundColor: '#FFF6E6', alignItems: 'center', justifyContent: 'center' },
          web({ boxShadow: `0 0 0 4px ${alpha(c.potato, 0.3)}, 0 6px 16px rgba(0,0,0,.45)` }),
          reduced ? null : web({ transitionProperty: 'left', transitionDuration: '250ms', transitionTimingFunction: pronoMotion.spring })]}>
          <Text style={{ fontSize: 21 }}>{PATATE}</Text>
        </View>
        {input}
      </View>
      <View style={{ flexDirection: 'row', justifyContent: 'space-between', marginTop: 6, marginHorizontal: 6 }} aria-hidden>
        {[0, 5, 10, 15, 20].filter((n) => n <= max).map((n) => (
          <Text key={n} style={[pronoFont.semibold, { width: 20, textAlign: 'center', color: c.t3, fontSize: 12 }]}>{n}</Text>
        ))}
      </View>
      <View style={{ flexDirection: 'row', gap: 8, marginTop: 14 }}>
        {CHIPS.filter((x) => x.n <= max).map((x, i) => {
          const on = value === x.n;
          const off = x.n > limit;
          return (
            <Pressable key={x.n} testID={`${testID}-${x.n}`} accessibilityRole="button" disabled={off}
              accessibilityLabel={x.n ? `${x.n} patates` : 'Sans patates'} accessibilityState={{ selected: on, disabled: off }}
              onPress={() => { set(x.n); if (x.n) setDrops((d) => d + 1); }}
              style={({ pressed }) => [{ flex: i === 0 ? 1.25 : 1, height: 44, borderRadius: 14, borderWidth: 1, alignItems: 'center', justifyContent: 'center',
                backgroundColor: c.glass, borderColor: c.glassLine },
              reduced ? null : web({ transitionProperty: 'transform, background-color', transitionDuration: '300ms', transitionTimingFunction: pronoMotion.spring }),
              on && { backgroundColor: c.potato, borderColor: c.potato }, off && { opacity: 0.4 }, pressed && { transform: [{ scale: 0.95 }] }]}>
              <Text style={[x.n ? pronoFont.num : pronoFont.bold, { fontSize: 15, color: on ? c.onPotato : c.t1 }]}>{x.label}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}
