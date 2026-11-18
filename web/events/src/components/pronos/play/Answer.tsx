import { useEffect, useRef, useState, type ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Switch, Text, TextInput, View } from 'react-native';

import { Avatar } from '@/components/ui';
import { ChoicePill, GlassCard, SectionLabel, ShapeMark, useReducedMotion } from '@/components/pronos/Kit';
import { palette } from '@/lib/groups';
import { pressTransition, transition } from '@/lib/motion';
import type { Face } from '@/lib/pronos';

import { C, decimal, hhmm, meName, rounded, shapeAt, webView, whenAt, whenMinutes, wide, type Draft, type PronoV2 } from './model';

/**
 * La réponse, par type (maquettes 3-1, 3-3a à 3-3d) : pastilles à formes (la couleur de la FORME quand elle est
 * choisie), Oui / Non géants, Plus / Moins autour de la ligne, grand chiffre + molette à crans, heure en deux roues,
 * grille de visages, trophée, réponse libre, « Devine ce que pense la bande ». Rien n'est envoyé ici : la fiche scelle.
 */
export function AnswerPicker({ p, draft, onDraft, onOptout, busy }: {
  p: PronoV2; draft: Draft; onDraft: (d: Draft) => void; onOptout: (out: boolean) => void; busy: boolean;
}) {
  const set = (patch: Partial<Draft>) => onDraft({ ...draft, ...patch });
  switch (p.kind) {
    case 'yesno': return <YesNo p={p} value={draft.option_id ?? null} onPick={(option_id) => set({ option_id })} />;
    case 'overunder': return <OverUnder p={p} value={draft.option_id ?? null} onPick={(option_id) => set({ option_id })} />;
    case 'majority': return <Majority p={p} value={draft.option_id ?? null} onPick={(option_id) => set({ option_id })} />;
    case 'number': return <NumberAnswer p={p} value={draft.number ?? null} onValue={(number) => set({ number })} />;
    case 'when': return <WhenAnswer p={p} value={draft.at ?? null} onValue={(at) => set({ at })} />;
    case 'person': return <People p={p} value={draft.person_id ?? null} onPick={(person_id) => set({ person_id })} />;
    case 'award': return <Award p={p} value={draft.person_id ?? null} onPick={(person_id) => set({ person_id })} onOptout={onOptout} busy={busy} />;
    case 'text': return <FreeText p={p} value={draft.text ?? ''} onValue={(text) => set({ text })} />;
    default: return <Choices p={p} value={draft.option_id ?? null} onPick={(option_id) => set({ option_id })} />;
  }
}

// ───────── Choix : pastilles à formes ─────────

function Choices({ p, value, onPick }: { p: PronoV2; value: string | null; onPick: (id: string) => void }) {
  return (
    <View style={{ gap: 10 }} accessibilityRole="radiogroup">
      <SectionLabel right="un toucher">Ta réponse</SectionLabel>
      {p.options.map((o, i) => {
        const s = shapeAt(i);
        return (
          <View key={o.id} testID={`prono-choice-${i}`}>
            <ChoicePill label={o.label} shape={s.key} color={s.color} selected={value === o.id} onPress={() => onPick(o.id)} />
          </View>
        );
      })}
    </View>
  );
}

// ───────── Oui / Non ─────────

function YesNo({ p, value, onPick }: { p: PronoV2; value: string | null; onPick: (id: string) => void }) {
  const yes = p.options.find((o) => o.label.trim().toLowerCase() === 'oui') ?? p.options[0];
  const no = p.options.find((o) => o !== yes) ?? p.options[1];
  if (!yes || !no) return <Choices p={p} value={value} onPick={onPick} />;
  return (
    <View style={{ gap: 10 }}>
      <SectionLabel right="un toucher">Ta réponse</SectionLabel>
      <View style={st.duo} accessibilityRole="radiogroup">
        <BigTile testID="prono-choice-0" label={yes.label} on={value === yes.id} color={C.sky} onPress={() => onPick(yes.id)}
          glyph={<View style={[st.yesGlyph, value === yes.id && { backgroundColor: C.sky }]}><Text style={st.glyphText}>✓</Text></View>} />
        <BigTile testID="prono-choice-1" label={no.label} on={value === no.id} color={C.pink} onPress={() => onPick(no.id)}
          glyph={<View style={[st.noGlyph, value === no.id && { backgroundColor: C.pink }]}><Text style={[st.glyphText, value !== no.id && { color: C.pink }]}>✕</Text></View>} />
      </View>
    </View>
  );
}

function BigTile({ label, on, color, glyph, onPress, testID, height = 172, children }: {
  label: string; on: boolean; color: string; glyph: ReactNode; onPress: () => void; testID?: string; height?: number; children?: ReactNode;
}) {
  return (
    <Pressable testID={testID} accessibilityRole="radio" accessibilityLabel={label} accessibilityState={{ selected: on }} aria-checked={on}
      onPress={onPress}
      style={({ pressed }) => [st.tile, { height }, on && tileOn(color), transition('transform, border-color, box-shadow, background-color', 350, 'cubic-bezier(.34,1.56,.64,1)'),
        pressed && { transform: [{ scale: 0.97 }] }]}>
      {on ? <View style={[st.tick, { backgroundColor: color }]}><Text style={st.tickText}>✓</Text></View> : null}
      {glyph}
      {children}
      <Text style={[rounded(label.length > 6 ? 24 : 36, '900'), { textAlign: 'center' }]} numberOfLines={2}>{label}</Text>
    </Pressable>
  );
}

const tileOn = (color: string) => webView({
  borderColor: color, transform: 'scale(1.02)',
  backgroundImage: `linear-gradient(160deg, ${color}57, ${color}14)`, boxShadow: `0 0 0 5px ${color}24, 0 14px 44px ${color}55`,
});

// ───────── Plus / Moins autour de la ligne ─────────

function OverUnder({ p, value, onPick }: { p: PronoV2; value: string | null; onPick: (id: string) => void }) {
  const plus = p.options.find((o) => /^plus/i.test(o.label.trim())) ?? p.options[0];
  const minus = p.options.find((o) => o !== plus) ?? p.options[1];
  if (!plus || !minus || p.line == null) return <Choices p={p} value={value} onPick={onPick} />;
  const line = p.line;
  return (
    <View style={{ gap: 0 }} accessibilityRole="radiogroup">
      <SectionLabel right="un toucher">Ta réponse</SectionLabel>
      <View style={{ height: 10 }} />
      <LineButton testID="prono-choice-0" label={plus.label} hint={`${Math.floor(line) + 1} ou plus`} glyph="▲" color={C.amber}
        on={value === plus.id} onPress={() => onPick(plus.id)} />
      <View style={st.lineRow} accessibilityLabel={`La ligne : ${decimal(line)}`}>
        <View style={st.dash} />
        <View style={st.lineCap}><Text style={wide(34, C.lemon)}>{decimal(line)}</Text></View>
        <View style={st.dash} />
      </View>
      <LineButton testID="prono-choice-1" label={minus.label} hint={`${Math.floor(line)} ou moins`} glyph="▼" color={C.lav}
        on={value === minus.id} onPress={() => onPick(minus.id)} />
      <Text style={[st.small, { marginTop: 10 }]}>ⓘ Une demi-unité : il n’y a jamais d’égalité avec la ligne.</Text>
    </View>
  );
}

function LineButton({ label, hint, glyph, color, on, onPress, testID }: {
  label: string; hint: string; glyph: string; color: string; on: boolean; onPress: () => void; testID: string;
}) {
  return (
    <Pressable testID={testID} accessibilityRole="radio" accessibilityLabel={`${label}, ${hint}`} accessibilityState={{ selected: on }} aria-checked={on}
      onPress={onPress}
      style={({ pressed }) => [st.lineBtn, on && tileOn(color), pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
      <View style={[st.lineGlyph, { backgroundColor: on ? color : `${color}29` }]}>
        <Text style={{ color: on ? C.bg : color, fontSize: 20, fontWeight: '900' }}>{glyph}</Text>
      </View>
      <View style={{ flex: 1 }}>
        <Text style={rounded(22)}>{label}</Text>
        <Text style={st.help}>{hint}</Text>
      </View>
      <View style={[st.radio, on && { backgroundColor: color, borderColor: color }]}>{on ? <Text style={st.tickText}>✓</Text> : null}</View>
    </Pressable>
  );
}

// ───────── Devine ce que pense la bande ─────────

const EMOJI = /^(\p{Extended_Pictographic}(?:️|‍\p{Extended_Pictographic})*)\s*/u;
export const splitEmoji = (label: string) => {
  const m = EMOJI.exec(label.trim());
  return m ? { emoji: m[1], text: label.trim().slice(m[0].length) } : { emoji: null, text: label.trim() };
};

function Majority({ p, value, onPick }: { p: PronoV2; value: string | null; onPick: (id: string) => void }) {
  const tint = palette(p.group?.color);
  return (
    <View style={{ gap: 14 }}>
      <View style={[st.band, webView({ borderColor: `${tint.main}73`, backgroundImage: `linear-gradient(120deg, ${tint.main}2E, transparent)` })]}>
        <Text style={{ fontSize: 30 }} accessibilityElementsHidden>👥</Text>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={rounded(17, '800')}>Devine ce que pense la bande</Text>
          <Text style={st.help}>Ce n’est pas ton goût qui compte : choisis ce que la majorité va choisir.</Text>
        </View>
      </View>
      {p.options.length === 2 ? (
        <View style={st.duo} accessibilityRole="radiogroup">
          {p.options.map((o, i) => {
            const s = shapeAt(i);
            const { emoji, text } = splitEmoji(o.label);
            return (
              <BigTile key={o.id} testID={`prono-choice-${i}`} label={text || o.label} on={value === o.id} color={s.color} height={196}
                onPress={() => onPick(o.id)}
                glyph={<View style={st.cornerShape}><ShapeMark shape={s.key} color={s.color} size={32} filled={value === o.id} /></View>}>
                {emoji ? <Text style={{ fontSize: 58 }} accessibilityElementsHidden>{emoji}</Text> : null}
              </BigTile>
            );
          })}
          <View style={st.or} pointerEvents="none"><Text style={rounded(17, '800')}>ou</Text></View>
        </View>
      ) : <Choices p={p} value={value} onPick={onPick} />}
    </View>
  );
}

// ───────── Nombre : grand chiffre, − / +, molette à crans ─────────

const TICK = 14;

function NumberAnswer({ p, value, onValue }: { p: PronoV2; value: number | null; onValue: (n: number) => void }) {
  const [typing, setTyping] = useState(false);
  const [typed, setTyped] = useState(value != null ? decimal(value) : '');
  const tint = palette(p.group?.color);
  const v = value ?? 0;
  const max = Math.max(100, Math.ceil((Math.abs(v) + 50) / 50) * 50);
  const index = value == null ? null : Math.max(0, Math.min(max, Math.round(value)));
  return (
    <View style={{ gap: 14 }}>
      <SectionLabel right={p.not_over ? 'sans dépasser' : 'le plus proche'}>Ta réponse</SectionLabel>
      <View style={st.numRow}>
        <Step label="Moins un" glyph="−" onPress={() => onValue(Math.max(0, Math.round(v) - 1))} />
        <Text style={[wide(value != null && Math.abs(value) >= 1000 ? 64 : 96), st.bigNum,
          webView({ backgroundImage: `linear-gradient(180deg, #FFFFFF 30%, ${tint.from})`, WebkitBackgroundClip: 'text', backgroundClip: 'text', color: 'transparent' })]}
          accessibilityLiveRegion="polite" accessibilityLabel={value == null ? 'Pas encore de nombre' : `Ton nombre : ${decimal(value)}`}>
          {value == null ? '?' : decimal(value)}
        </Text>
        <Step label="Plus un" glyph="+" onPress={() => onValue(Math.round(v) + 1)} />
      </View>
      <View style={st.dial} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        <Snap horizontal size={TICK} count={max + 1} index={index} onIndex={onValue}
          render={(i) => (
            <View style={{ alignItems: 'center', gap: 6 }}>
              <View style={{ width: i % 5 ? 2 : 3, height: i % 5 ? 14 : 24, borderRadius: 2, backgroundColor: i % 5 ? 'rgba(255,255,255,0.28)' : 'rgba(255,255,255,0.6)' }} />
              {i % 5 ? null : <Text style={[wide(12, C.t3), { width: 40, textAlign: 'center' }]}>{i}</Text>}
            </View>
          )} />
        <View pointerEvents="none" style={st.needle} />
        <View pointerEvents="none" style={[st.fade, { left: 0 }, webView({ backgroundImage: 'linear-gradient(90deg, #1A1433, transparent)' })]} />
        <View pointerEvents="none" style={[st.fade, { right: 0 }, webView({ backgroundImage: 'linear-gradient(270deg, #1A1433, transparent)' })]} />
      </View>
      {typing ? (
        <View style={st.typeRow}>
          <TextInput value={typed} onChangeText={setTyped} placeholder="Ton nombre" placeholderTextColor={C.t3} inputMode="decimal"
            keyboardType="numbers-and-punctuation" accessibilityLabel="Ton nombre" autoFocus style={st.typeInput}
            onSubmitEditing={() => { const n = Number(typed.replace(',', '.')); if (typed.trim() && Number.isFinite(n)) { onValue(n); setTyping(false); } }} />
          <Pressable accessibilityRole="button" style={st.smallBtn} disabled={!typed.trim() || !Number.isFinite(Number(typed.replace(',', '.')))}
            onPress={() => { onValue(Number(typed.replace(',', '.'))); setTyping(false); }}>
            <Text style={st.smallBtnText}>OK</Text>
          </Pressable>
        </View>
      ) : (
        <Pressable accessibilityRole="button" onPress={() => { setTyped(value != null ? decimal(value) : ''); setTyping(true); }} style={st.link}>
          <Text style={st.linkText}>⌨︎ Taper un nombre</Text>
        </Pressable>
      )}
      {p.not_over ? <NotOver example={v} /> : null}
    </View>
  );
}

function NotOver({ example }: { example: number }) {
  const n = Math.max(2, Math.round(example) || 15);
  return (
    <View style={st.notOver}>
      <View style={st.notOverIcon}><Text style={{ color: C.lemon, fontSize: 14, fontWeight: '900' }}>▼</Text></View>
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={{ color: C.lemon, fontSize: 15, fontWeight: '700' }}>Sans dépasser</Text>
        <Text style={st.help}>Le plus proche sans aller au-dessus l’emporte. Si c’est {n}, {n - 1} bat {n + 1}.</Text>
      </View>
    </View>
  );
}

function Step({ label, glyph, onPress }: { label: string; glyph: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={onPress}
      style={({ pressed }) => [st.step, pressTransition, pressed && { transform: [{ scale: 0.92 }] }]}>
      <Text style={{ color: C.t1, fontSize: 26, fontWeight: '600', marginTop: -2 }}>{glyph}</Text>
    </Pressable>
  );
}

/**
 * Défilement aimanté par cran (molette du nombre, roues de l'heure). Le cran au centre est la valeur ; une valeur
 * changée ailleurs (−, +, puce) fait défiler jusqu'à elle, sans boucle avec le défilement du doigt.
 */
function Snap({ horizontal, size, count, index, onIndex, render }: {
  horizontal?: boolean; size: number; count: number; index: number | null; onIndex: (i: number) => void; render: (i: number, on: boolean) => ReactNode;
}) {
  const ref = useRef<ScrollView>(null);
  const fromFinger = useRef<number | null>(null);
  const [box, setBox] = useState(0);
  const reduced = useReducedMotion();
  useEffect(() => {
    if (!box || index == null) return;
    if (fromFinger.current === index) { fromFinger.current = null; return; }
    ref.current?.scrollTo(horizontal ? { x: index * size, animated: !reduced } : { y: index * size, animated: !reduced });
  }, [index, box, horizontal, size, reduced]);
  const pad = Math.max(0, (box - size) / 2);
  return (
    <ScrollView ref={ref} horizontal={horizontal} showsHorizontalScrollIndicator={false} showsVerticalScrollIndicator={false}
      scrollEventThrottle={16}
      onLayout={(e) => setBox(horizontal ? e.nativeEvent.layout.width : e.nativeEvent.layout.height)}
      onScroll={(e) => {
        const off = horizontal ? e.nativeEvent.contentOffset.x : e.nativeEvent.contentOffset.y;
        const i = Math.max(0, Math.min(count - 1, Math.round(off / size)));
        if (i !== index) { fromFinger.current = i; onIndex(i); }
      }}
      contentContainerStyle={horizontal ? { paddingHorizontal: pad, alignItems: 'center' } : { paddingVertical: pad }}
      style={[{ flex: 1 }, webView({ scrollSnapType: horizontal ? 'x mandatory' : 'y mandatory', overscrollBehavior: 'contain' })]}>
      {Array.from({ length: count }, (_, i) => (
        <View key={i} style={[horizontal ? { width: size } : { height: size }, { alignItems: 'center', justifyContent: 'center' },
          webView({ scrollSnapAlign: 'center' })]}>
          {render(i, i === index)}
        </View>
      ))}
    </ScrollView>
  );
}

// ───────── Heure : grand « 22:40 », deux roues, puces rapides ─────────

const ROW = 44;
const MINUTES = Array.from({ length: 12 }, (_, i) => i * 5);

function WhenAnswer({ p, value, onValue }: { p: PronoV2; value: string | null; onValue: (iso: string) => void }) {
  const tint = palette(p.group?.color);
  const fallback = Math.round((whenMinutes(p.closes_at) ?? 22 * 60) / 30) * 30 % 1440;
  const mins = whenMinutes(value) ?? fallback;
  const h = Math.floor(mins / 60);
  const m = Math.round((mins % 60) / 5) * 5 % 60;
  const set = (hh: number, mm: number) => onValue(whenAt(p, hh * 60 + mm));
  const quick = [-60, -30, 0, 30].map((d) => (fallback + d + 1440) % 1440);
  const pad = (n: number) => String(n).padStart(2, '0');
  return (
    <View style={{ gap: 14 }}>
      <SectionLabel right="heure de Suisse">Ta réponse</SectionLabel>
      <Text style={[wide(78), { textAlign: 'center', opacity: value ? 1 : 0.55 }]} accessibilityLiveRegion="polite"
        accessibilityLabel={value ? `Ton heure : ${hhmm(value)}` : 'Pas encore d’heure'}>
        {pad(h)}:{pad(m)}
      </Text>
      <Text style={[st.help, { textAlign: 'center', marginTop: -8 }]}>L’heure la plus proche l’emporte{p.not_over ? ', sans dépasser' : ''}.</Text>
      <View style={st.wheels}>
        <View pointerEvents="none" style={[st.wheelBand, { backgroundColor: `${tint.main}29`, borderColor: `${tint.main}66` }]} />
        <View style={st.wheel} accessibilityLabel="Heures" importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
          <Snap size={ROW} count={24} index={h} onIndex={(i) => set(i, m)}
            render={(i, on) => <Text style={wide(on ? 30 : 24, on ? C.t1 : C.t3)}>{pad(i)}</Text>} />
        </View>
        <Text style={[wide(26), { alignSelf: 'center' }]}>:</Text>
        <View style={st.wheel} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
          <Snap size={ROW} count={12} index={m / 5} onIndex={(i) => set(h, MINUTES[i])}
            render={(i, on) => <Text style={wide(on ? 30 : 24, on ? C.t1 : C.t3)}>{pad(MINUTES[i])}</Text>} />
        </View>
      </View>
      <View style={st.chips}>
        {quick.map((q) => {
          const on = !!value && q === h * 60 + m;
          return (
            <Pressable key={q} accessibilityRole="button" accessibilityState={{ selected: on }} onPress={() => set(Math.floor(q / 60), q % 60)}
              style={({ pressed }) => [st.chip, on && { backgroundColor: `${tint.main}33`, borderColor: tint.main }, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
              <Text style={wide(16)}>{pad(Math.floor(q / 60))}:{pad(q % 60)}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

// ───────── Une personne : grille de visages ─────────

function People({ p, value, onPick }: { p: PronoV2; value: string | null; onPick: (id: string) => void }) {
  const faces = [...(p.candidates ?? [])].sort((a, b) => Number(!!a.me) - Number(!!b.me));
  return (
    <View style={{ gap: 12 }}>
      <SectionLabel right={`${faces.length} personnes${faces.some((f) => f.me) ? ', toi en dernier' : ''}`}>Ta réponse</SectionLabel>
      <FaceGrid faces={faces} value={value} onPick={onPick} color={palette(p.group?.color).main} />
    </View>
  );
}

function FaceGrid({ faces, value, onPick, color }: { faces: Face[]; value: string | null; onPick: (id: string) => void; color: string }) {
  return (
    <View style={st.faces} accessibilityRole="radiogroup">
      {faces.map((f, i) => {
        const on = value === f.id;
        return (
          <Pressable key={f.id} testID={`prono-choice-${i}`} accessibilityRole="radio" accessibilityLabel={meName(f)} accessibilityState={{ selected: on }}
            aria-checked={on} onPress={() => onPick(f.id)} style={({ pressed }) => [st.face, pressed && { opacity: 0.85 }]}>
            <View style={[st.faceRing, on && webView({ borderColor: color, transform: 'scale(1.12)', boxShadow: `0 0 0 3px ${C.bg}, 0 10px 30px ${color}88` }),
              transition('transform, border-color, box-shadow', 350, 'cubic-bezier(.34,1.56,.64,1)')]}>
              <Avatar id={f.id} name={f.name} photo={f.avatar_url} size={72} profile={false} />
              {on ? <View style={[st.faceTick, { backgroundColor: color }]}><Text style={st.tickText}>✓</Text></View> : null}
            </View>
            <Text numberOfLines={1} style={{ color: on ? color : f.me ? C.t2 : C.t1, fontSize: 15, fontWeight: '700', fontFamily: rounded(15).fontFamily }}>{meName(f)}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

// ───────── Trophée de la soirée ─────────

function Award({ p, value, onPick, onOptout, busy }: {
  p: PronoV2; value: string | null; onPick: (id: string) => void; onOptout: (out: boolean) => void; busy: boolean;
}) {
  const { emoji, text } = splitEmoji(p.award ?? '');
  const faces = (p.candidates ?? []).filter((f) => !f.me);
  const where = p.event?.title ?? p.group?.name ?? null;
  return (
    <View style={{ gap: 14 }}>
      <GlassCard style={st.medalCard}>
        <View pointerEvents="none" style={[StyleSheet.absoluteFill, webView({ borderRadius: 24,
          backgroundImage: 'repeating-conic-gradient(from 0deg at 50% 32%, rgba(255,226,122,0.11) 0deg 8deg, transparent 8deg 22deg)',
          maskImage: 'radial-gradient(circle at 50% 32%, black 0, transparent 70%)', WebkitMaskImage: 'radial-gradient(circle at 50% 32%, black 0, transparent 70%)' })]} />
        <View style={st.medal}><Text style={{ fontSize: 52 }} accessibilityElementsHidden>{emoji ?? '🏆'}</Text></View>
        <Text style={{ color: C.lemon, fontSize: 14, fontWeight: '700', textAlign: 'center' }}>🏆 Trophée de la soirée{where ? ` · ${where}` : ''}</Text>
        {text ? <Text style={[rounded(28, '800'), { textAlign: 'center' }]}>{text}</Text> : null}
        <Text style={[st.help, { textAlign: 'center' }]}>{p.question}</Text>
        <View style={st.medalTags}>
          <View style={st.mtag}><Text style={st.mtagText}>Pour l’honneur, sans patates</Text></View>
          <View style={st.mtag}><Text style={st.mtagText}>{p.answered.length} {p.answered.length > 1 ? 'ont voté' : 'a voté'}</Text></View>
        </View>
      </GlassCard>
      <SectionLabel right="une personne">Ton vote</SectionLabel>
      <FaceGrid faces={faces} value={value} onPick={onPick} color={C.lav} />
      <Pressable accessibilityRole="switch" accessibilityState={{ checked: !!p.optout, disabled: busy }} aria-checked={!!p.optout} disabled={busy}
        onPress={() => onOptout(!p.optout)} style={st.optout} testID="prono-optout">
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={{ color: C.t1, fontSize: 16, fontWeight: '700' }}>Ne pas me proposer</Text>
          <Text style={st.help}>Tu n’apparais plus dans la liste de ce trophée. Tu peux toujours voter.</Text>
        </View>
        <Switch value={!!p.optout} onValueChange={(out) => onOptout(out)} disabled={busy} trackColor={{ true: C.mint, false: 'rgba(255,255,255,0.16)' }}
          accessibilityElementsHidden importantForAccessibility="no" />
      </Pressable>
      <Text style={st.small}>ⓘ Le trophée se dévoile à la fin, s’il y a au moins 3 votes.</Text>
    </View>
  );
}

// ───────── Réponse libre ─────────

function FreeText({ p, value, onValue }: { p: PronoV2; value: string; onValue: (t: string) => void }) {
  return (
    <View style={{ gap: 14 }}>
      <SectionLabel right="en quelques mots">Ta réponse</SectionLabel>
      <GlassCard style={st.free}>
        <TextInput value={value} onChangeText={onValue} maxLength={80} multiline placeholder="Ta réponse" placeholderTextColor={C.t3}
          accessibilityLabel="Ta réponse" style={st.freeInput} />
        <View style={{ flexDirection: 'row', alignItems: 'center' }}>
          <Text style={[st.small, { flex: 1 }]}>Les réponses passent le filtre de Party</Text>
          <Text style={wide(14, C.t2)}>{value.length}/80</Text>
        </View>
      </GlassCard>
      <GlassCard style={st.who}>
        <View style={st.whoIcon}><Text style={{ color: C.lav, fontSize: 16, fontWeight: '900' }}>✓</Text></View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={rounded(16, '700')}>Qui coche les bonnes réponses ?</Text>
          <Text style={st.help}>{p.mine ? 'Toi' : p.creator.name}, à la fin. Toutes les réponses apparaissent alors en bulles, comme une discussion.</Text>
        </View>
      </GlassCard>
      <View style={{ gap: 10 }} importantForAccessibility="no-hide-descendants" accessibilityElementsHidden>
        {[180, 220, 140].map((w, i) => (
          <View key={w} style={[st.ghost, { width: w, alignSelf: i % 2 ? 'flex-end' : 'flex-start' }]}>
            <View style={[st.ghostBar, webView({ filter: 'blur(3px)' })]} />
          </View>
        ))}
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  duo: { flexDirection: 'row', gap: 12 },
  tile: webView({ flex: 1, borderRadius: 28, borderWidth: 2, borderColor: C.glassLine, backgroundColor: C.glass, alignItems: 'center',
    justifyContent: 'center', gap: 10, padding: 12, backdropFilter: 'blur(20px)' }),
  tick: { position: 'absolute', top: 12, right: 12, width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  tickText: { color: C.bg, fontSize: 14, fontWeight: '900' },
  yesGlyph: { width: 66, height: 66, borderRadius: 33, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(108,199,255,0.22)' },
  noGlyph: { width: 66, height: 66, borderRadius: 20, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,111,174,0.18)' },
  glyphText: { color: C.bg, fontSize: 30, fontWeight: '900' },
  lineRow: { flexDirection: 'row', alignItems: 'center', marginVertical: 8, marginHorizontal: -16 },
  dash: webView({ flex: 1, height: 0, borderTopWidth: 2, borderStyle: 'dashed', borderColor: 'rgba(255,226,122,0.7)' }),
  lineCap: webView({ paddingHorizontal: 22, height: 64, borderRadius: 999, borderWidth: 2, borderColor: C.lemon, alignItems: 'center', justifyContent: 'center',
    backgroundColor: '#1F1830', boxShadow: '0 0 24px rgba(255,226,122,0.35)' }),
  lineBtn: webView({ flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 78, borderRadius: 22, paddingHorizontal: 16, borderWidth: 2,
    borderColor: C.glassLine, backgroundColor: C.glass }),
  lineGlyph: { width: 52, height: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  radio: { width: 26, height: 26, borderRadius: 13, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', alignItems: 'center', justifyContent: 'center' },
  band: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 20, borderWidth: 1 },
  cornerShape: { position: 'absolute', top: 14, left: 14 },
  or: { position: 'absolute', left: '50%', top: '50%', width: 50, height: 50, marginLeft: -25, marginTop: -25, borderRadius: 25, backgroundColor: C.bg,
    alignItems: 'center', justifyContent: 'center' },
  numRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  bigNum: { flex: 1, textAlign: 'center', lineHeight: 110 },
  step: webView({ width: 52, height: 52, borderRadius: 26, alignItems: 'center', justifyContent: 'center', backgroundColor: C.glass, borderWidth: 1,
    borderColor: C.glassLine }),
  dial: { height: 76, borderRadius: 22, backgroundColor: C.s1, borderWidth: 1, borderColor: C.glassLine, overflow: 'hidden' },
  needle: webView({ position: 'absolute', left: '50%', top: 4, width: 4, height: 34, marginLeft: -2, borderRadius: 2, backgroundColor: C.accent,
    boxShadow: '0 0 12px rgba(255,79,154,0.8)' }),
  fade: { position: 'absolute', top: 0, bottom: 0, width: '24%' },
  typeRow: { flexDirection: 'row', gap: 10, alignItems: 'center' },
  typeInput: { flex: 1, height: 52, borderRadius: 16, paddingHorizontal: 16, backgroundColor: C.glass, color: C.t1, fontSize: 22, fontWeight: '700',
    borderWidth: 1, borderColor: C.glassLine },
  smallBtn: { minWidth: 64, height: 52, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: C.action },
  smallBtnText: { color: '#fff', fontSize: 16, fontWeight: '800' },
  link: { alignSelf: 'center', minHeight: 44, justifyContent: 'center', paddingHorizontal: 12 },
  linkText: { color: C.lav, fontSize: 15, fontWeight: '700' },
  notOver: { flexDirection: 'row', gap: 12, padding: 16, borderRadius: 20, borderWidth: 1, borderColor: 'rgba(255,226,122,0.45)',
    backgroundColor: 'rgba(255,226,122,0.08)' },
  notOverIcon: { width: 34, height: 34, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,226,122,0.16)' },
  wheels: { flexDirection: 'row', height: 176, borderRadius: 22, backgroundColor: C.s1, borderWidth: 1, borderColor: C.glassLine, overflow: 'hidden',
    paddingHorizontal: 16, gap: 8 },
  wheel: { flex: 1 },
  wheelBand: { position: 'absolute', left: 12, right: 12, top: 64, height: 48, borderRadius: 14, borderWidth: 1 },
  chips: { flexDirection: 'row', gap: 8 },
  chip: { flex: 1, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: C.glass, borderWidth: 1, borderColor: C.glassLine },
  faces: { flexDirection: 'row', flexWrap: 'wrap', rowGap: 14 },
  face: { width: '33.33%', alignItems: 'center', gap: 8, paddingVertical: 4 },
  faceRing: { borderRadius: 999, borderWidth: 3, borderColor: 'transparent' },
  faceTick: { position: 'absolute', right: -4, bottom: -4, width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center',
    borderWidth: 2, borderColor: C.bg },
  medalCard: { alignItems: 'center', gap: 8, padding: 22, borderRadius: 24, overflow: 'hidden' },
  medal: webView({ width: 112, height: 112, borderRadius: 56, alignItems: 'center', justifyContent: 'center',
    backgroundImage: 'radial-gradient(circle at 40% 35%, #FFF8D6, #FFE27A 55%, #E9A93A)',
    boxShadow: '0 0 0 6px rgba(255,226,122,0.18), 0 0 0 14px rgba(255,226,122,0.08), 0 18px 50px rgba(233,169,58,0.45)' }),
  medalTags: { flexDirection: 'row', gap: 8, flexWrap: 'wrap', justifyContent: 'center', marginTop: 4 },
  mtag: { height: 30, paddingHorizontal: 12, borderRadius: 999, justifyContent: 'center', backgroundColor: C.glass, borderWidth: 1, borderColor: C.glassLine },
  mtagText: { color: C.t2, fontSize: 13, fontWeight: '600' },
  optout: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 20, backgroundColor: C.glass, borderWidth: 1, borderColor: C.glassLine },
  free: { padding: 18, borderRadius: 24, gap: 10 },
  freeInput: webView({ minHeight: 70, color: C.t1, fontSize: 26, lineHeight: 32, fontWeight: '800', fontFamily: rounded(26).fontFamily, outlineStyle: 'none',
    caretColor: C.accent }),
  who: { flexDirection: 'row', gap: 12, padding: 16, borderRadius: 20 },
  whoIcon: { width: 34, height: 34, borderRadius: 11, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(185,167,255,0.16)' },
  ghost: { height: 40, borderRadius: 20, borderWidth: 1, borderStyle: 'dashed', borderColor: 'rgba(255,255,255,0.14)', justifyContent: 'center', paddingHorizontal: 16 },
  ghostBar: { height: 12, borderRadius: 6, backgroundColor: 'rgba(255,255,255,0.18)' },
  help: { color: C.t2, fontSize: 15, lineHeight: 21 },
  small: { color: C.t3, fontSize: 13, lineHeight: 18 },
});
