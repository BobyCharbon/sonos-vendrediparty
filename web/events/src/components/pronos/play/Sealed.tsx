import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { AvatarStack, BagChip, GlassCard, Seal, SealRow, SectionLabel, useReducedMotion } from '@/components/pronos/Kit';
import { formatTime } from '@/lib/format';
import { enter, pressTransition } from '@/lib/motion';
import type { Face } from '@/lib/pronos';

import { PATATES_NOTE } from './Plant';
import { C, rounded, webView, wide, withPatates, type PronoV2 } from './model';

/**
 * Réponse scellée (maquette 3-2) : le sceau héros (emoji du groupe, cadenas), une phrase, ma réponse FLOUTÉE qu'on voit
 * en maintenant le doigt (téléphone qui passe de main en main), « Changer » ; puis les sceaux des joueurs (« pas
 * encore » sans nom), le champ et le sac. Jamais la répartition par réponse avant la fin.
 */
export function SealedCard({ p, answer, onChange, compact }: { p: PronoV2; answer: string; onChange: () => void; compact?: boolean }) {
  const [peek, setPeek] = useState(false);
  const reduced = useReducedMotion();
  const until = formatTime(p.closes_at);
  const stake = withPatates(p) ? p.my_answer?.stake ?? 0 : 0;
  if (compact) {
    // Organisateur : une ligne (maquette 3-4), l'organisation prend la place.
    return (
      <GlassCard style={st.line}>
        <Seal emoji={p.group?.emoji ?? '🔮'} color={p.group?.color} size={56} />
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={rounded(17, '800')}>Ta réponse est scellée</Text>
          <Text style={st.help}>{stake ? `Avec ${stake} 🥔, cachée à tous` : 'Cachée à tous jusqu’à la fin'}</Text>
        </View>
        <Pressable accessibilityRole="button" onPress={onChange} style={({ pressed }) => [st.glassBtn, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
          <Text style={st.glassBtnText}>Changer</Text>
        </Pressable>
      </GlassCard>
    );
  }
  return (
    <GlassCard style={st.hero}>
      <View style={[st.sealWrap, enter('pop')]}>
        {reduced ? null : <View pointerEvents="none" style={[st.halo, st.breathe]} />}
        <Seal emoji={p.group?.emoji ?? '🔮'} color={p.group?.color} size={132} />
        <View style={st.lock}><Text style={{ fontSize: 18 }} accessibilityElementsHidden>🔒</Text></View>
      </View>
      <Text role="heading" aria-level={2} style={[rounded(30, '800'), { textAlign: 'center' }]}>Réponse scellée</Text>
      <Text style={[st.help, { textAlign: 'center', maxWidth: 320 }]}>
        Personne ne voit ta réponse, pas même l’organisateur. Tout se dévoile à la fin, pour tout le monde en même temps.
      </Text>
      <View style={st.actions}>
        <Pressable accessibilityRole="button" accessibilityLabel={`Ta réponse : ${answer}${stake ? `, ${stake} patates` : ''}`}
          accessibilityHint="Maintiens pour la voir" onPressIn={() => setPeek(true)} onPressOut={() => setPeek(false)} testID="prono-peek"
          style={st.peek}>
          <Text style={{ color: C.t2, fontSize: 18 }} accessibilityElementsHidden>👁</Text>
          {peek ? (
            <Text style={[rounded(16, '700'), { flex: 1 }]} numberOfLines={1}>{answer}{stake ? ` · ${stake} 🥔` : ''}</Text>
          ) : (
            <>
              <Text style={rounded(16, '700')}>Maintiens pour voir</Text>
              <Text style={[rounded(16, '700'), { flex: 1, opacity: 0.8 }, webView({ filter: 'blur(7px)' })]} numberOfLines={1} aria-hidden>{answer}</Text>
            </>
          )}
        </Pressable>
        <Pressable accessibilityRole="button" onPress={onChange} testID="prono-change"
          style={({ pressed }) => [st.glassBtn, { height: 52 }, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
          <Text style={st.glassBtnText}>Changer</Text>
        </Pressable>
      </View>
      <Text style={[st.small, { textAlign: 'center' }]}>
        {withPatates(p) ? 'Réponse et patates changeables' : 'Réponse changeable'} jusqu’à {until}.
      </Text>
    </GlassCard>
  );
}

/** « Les sceaux » : qui a joué (visages), puis « ? » pour ceux qui n'ont pas encore joué, sans nom. */
export function Seals({ p }: { p: PronoV2 }) {
  const n = p.answered.length;
  const missing = Math.max(0, p.players - n);
  return (
    <View style={{ gap: 10 }}>
      <SectionLabel right={`${n} ${n > 1 ? 'personnes ont joué' : 'personne a joué'}${missing ? `, ${missing} pas encore` : ''}`}>Les sceaux</SectionLabel>
      <GlassCard style={{ padding: 16, borderRadius: 24 }}>
        <SealRow faces={p.answered} total={p.players} me={!!p.my_answer} />
      </GlassCard>
    </View>
  );
}

/** Avant de jouer : « 5 réponses déjà scellées », visages qui se chevauchent. */
export function SealsTeaser({ faces }: { faces: Face[] }) {
  if (!faces.length) return null;
  const shown = faces.slice(-3);
  return (
    <GlassCard style={st.teaser}>
      <AvatarStack faces={shown} extra={faces.length - shown.length} />
      <View style={{ flex: 1, gap: 2 }}>
        <Text style={rounded(16, '700')}>
          {faces.length} {faces.length > 1 ? 'réponses déjà scellées' : 'réponse déjà scellée'}
        </Text>
        <Text style={st.help}>Cachées à tout le monde jusqu’à la fin.</Text>
      </View>
    </GlassCard>
  );
}

/** Le champ (total, joueurs, « Dont tes 10 ») et le sac, sous l'état scellé. */
export function FieldCard({ p }: { p: PronoV2 }) {
  if (!withPatates(p)) return null;
  const mine = p.my_answer?.stake ?? 0;
  const planters = p.field?.planters ?? 0;
  return (
    <View style={{ gap: 12 }}>
      <GlassCard style={st.fieldCard}>
        <View style={{ flexDirection: 'row', gap: 14, alignItems: 'center' }}>
          <View style={st.fieldIcon}><Text style={{ fontSize: 26 }} accessibilityElementsHidden>🥔</Text></View>
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={rounded(17, '800')}>
              {(p.field?.total ?? 0) > 0
                ? <><Text style={wide(17)}>{p.field?.total}</Text> 🥔 dans le champ · {planters} joueur{planters > 1 ? 's' : ''}</>
                : 'Le champ est encore vide'}
            </Text>
            <Text style={st.help}>{mine ? `Dont tes ${mine} 🥔. ` : ''}La répartition reste cachée jusqu’à la fin.</Text>
          </View>
        </View>
        {p.bag ? (
          <>
            <View style={st.sep} />
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
              <BagChip bag={p.bag} />
              <Text style={[st.help, { flex: 1, textAlign: 'right' }]}>Remonte à 100 🥔 lundi</Text>
            </View>
          </>
        ) : null}
      </GlassCard>
      <Text style={st.note}>ⓘ {PATATES_NOTE}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  hero: { alignItems: 'center', gap: 14, padding: 24, borderRadius: 28 },
  sealWrap: { width: 190, height: 170, alignItems: 'center', justifyContent: 'center' },
  halo: webView({ position: 'absolute', width: 190, height: 190, borderRadius: 95,
    backgroundImage: 'radial-gradient(circle, rgba(108,199,255,0.45), transparent 65%)' }),
  breathe: webView({
    animationKeyframes: [{ '0%': { opacity: 0.55 }, '50%': { opacity: 0.85 }, '100%': { opacity: 0.55 } }],
    animationDuration: '2400ms', animationTimingFunction: 'ease-in-out', animationIterationCount: 'infinite',
  }),
  lock: { position: 'absolute', right: 22, bottom: 8, width: 42, height: 42, borderRadius: 21, backgroundColor: '#160F2C', borderWidth: 3,
    borderColor: C.s1, alignItems: 'center', justifyContent: 'center' },
  actions: { flexDirection: 'row', gap: 10, alignSelf: 'stretch' },
  peek: webView({ flex: 1, flexDirection: 'row', alignItems: 'center', gap: 12, height: 52, paddingHorizontal: 16, borderRadius: 16,
    borderWidth: 1.5, borderStyle: 'dashed', borderColor: 'rgba(255,255,255,0.18)', overflow: 'hidden', userSelect: 'none' }),
  glassBtn: { minHeight: 44, paddingHorizontal: 18, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: C.glass,
    borderWidth: 1, borderColor: C.glassLine },
  glassBtnText: { color: C.t1, fontSize: 17, fontWeight: '700' },
  line: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 24 },
  teaser: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, borderRadius: 24 },
  fieldCard: { gap: 14, padding: 18, borderRadius: 24 },
  fieldIcon: webView({ width: 52, height: 52, borderRadius: 14, alignItems: 'center', justifyContent: 'center',
    backgroundImage: 'repeating-linear-gradient(135deg, #3A2A1C 0 6px, #2E2016 6px 12px)' }),
  sep: { height: 1, backgroundColor: C.line },
  help: { color: C.t2, fontSize: 15, lineHeight: 21 },
  small: { color: C.t3, fontSize: 13, lineHeight: 18 },
  note: { color: C.t3, fontSize: 12.5, lineHeight: 18, paddingHorizontal: 4 },
});
