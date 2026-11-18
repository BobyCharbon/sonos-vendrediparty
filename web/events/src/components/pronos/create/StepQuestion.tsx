import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { KindIcon, kindLabel } from '@/components/pronos/Kit';
import { enter, pressTransition } from '@/lib/motion';

import { awardOf, DOWN, KINDS, lineLabel, MAX_QUESTION, questionProblem, SHAPES, shownQuestion, switchKind, UNITS, UP,
  type Award, type Draft } from './model';
import { PreviewCard, type Place } from './PreviewCard';
import { Block, body, C, noOutline, Chip, ChipRow, digits, Footer, rounded, StepNav, StepScreen, Txt, web } from './ui';

/**
 * Étape 2 « La question » (maquettes 2-2) : l'aperçu en direct de la carte en haut, le type de réponse (changer de type
 * garde la question), la question, puis ce que le type demande (réponses à formes, ligne en demi-unité, « sans dépasser »,
 * trophée), et « Comment on tranche ? ». Trophée : la question est écrite par Party.
 */
export function StepQuestion({ d, setD, awards, place, onBack, onNext }: {
  d: Draft; setD: (d: Draft) => void; awards: Award[]; place: Place; onBack: () => void; onNext: () => void;
}) {
  const problem = questionProblem(d);
  const set = (patch: Partial<Draft>) => setD({ ...d, ...patch });
  return (
    <StepScreen nav={<StepNav step={2} title="Question" icon="‹" onBack={onBack} backLabel="Retour aux modèles" />}
      footer={<Footer label="Continuer →" onPress={onNext} disabled={!!problem} testID="prono-next" />}>
      <View style={{ gap: 12 }}>
        <View style={st.liveRow}>
          <View style={[st.dot, enter('pulse')]} />
          <Txt size={14} weight="700" color={C.t1} style={{ letterSpacing: 1.2 }}>APERÇU EN DIRECT</Txt>
          <Txt size={14} color={C.t2} style={{ marginLeft: 'auto' }} numberOfLines={1}>ce que verront {place.label === 'Invités' ? 'les invités' : place.label}</Txt>
        </View>
        <PreviewCard d={d} awards={awards} place={place} />
      </View>

      <Block label="TYPE DE RÉPONSE" index={1}>
        <ChipRow>
          {KINDS.map((k) => (
            <Chip key={k.kind} label={kindLabel(k.kind)} icon={<KindIcon kind={k.kind} />} on={d.kind === k.kind}
              onPress={() => setD(switchKind(d, k.kind))} testID={`prono-type-${k.kind}`} />
          ))}
        </ChipRow>
      </Block>

      {d.kind === 'award' ? <AwardEditor d={d} set={set} awards={awards} /> : (
        <Block label="TA QUESTION" index={2}>
          <View style={st.qBox}>
            <TextInput value={d.question} onChangeText={(v) => set({ question: v })} multiline maxLength={MAX_QUESTION}
              placeholder="Qui marque le premier but samedi ?" placeholderTextColor={C.t3} accessibilityLabel="La question" testID="prono-question"
              style={[rounded, st.qInput, noOutline]} />
            <Txt size={14} color={C.t2} style={{ alignSelf: 'flex-end' }}>{d.question.length} / {MAX_QUESTION}</Txt>
          </View>
        </Block>
      )}

      {d.kind === 'choice' || d.kind === 'majority' ? <OptionsEditor d={d} set={set} /> : null}
      {d.kind === 'overunder' ? <LineEditor d={d} set={set} /> : null}
      {d.kind === 'number' || d.kind === 'when' ? (
        <Block label="QUI L’EMPORTE" index={3}>
          <Pressable accessibilityRole="switch" accessibilityState={{ checked: d.notOver }} aria-checked={d.notOver} testID="prono-not-over"
            onPress={() => set({ notOver: !d.notOver })} style={st.switchRow}>
            <View style={{ flex: 1, gap: 2 }}>
              <Txt size={17} weight="600">Sans dépasser</Txt>
              <Txt size={13} color={C.t2}>{d.kind === 'number'
                ? 'Le plus proche SOUS le vrai nombre l’emporte (comme au Juste Prix).'
                : 'L’heure la plus proche AVANT le moment venu l’emporte.'}</Txt>
            </View>
            <View style={[st.switch, d.notOver && st.switchOn]}><View style={[st.knob, d.notOver && { transform: [{ translateX: 20 }] }]} /></View>
          </Pressable>
          <Txt size={13} color={C.t2}>{d.notOver ? 'Si tout le monde a dépassé, personne n’a vu juste.' : 'Le plus proche l’emporte ; égalité : partagé.'}</Txt>
        </Block>
      ) : null}
      {d.kind === 'person' ? <Note>On choisit quelqu’un parmi ceux qui jouent. Chacun peut voter pour n’importe qui, sauf les personnes bloquées.</Note> : null}
      {d.kind === 'text' ? <Note>Chacun écrit sa réponse. À la fin, tu lis tout et tu coches celles qui sont justes. Pour l’honneur seulement.</Note> : null}
      {d.kind === 'majority' ? <Note>Devine ce que choisira la majorité : la réponse la plus choisie l’emporte, toute seule à la fin. Égalité : tout est rendu.</Note> : null}

      {d.kind !== 'award' && d.kind !== 'majority' ? (
        <Block label="COMMENT ON TRANCHE ?" right="Facultatif" index={4}>
          <TextInput value={d.rules} onChangeText={(v) => set({ rules: v })} maxLength={200} multiline accessibilityLabel="Comment on tranche"
            placeholder="Ex. : d’après le site officiel du match" placeholderTextColor={C.t3} testID="prono-rules"
            style={[body, st.rules, noOutline]} />
          {d.ruleHint && d.rules.trim() !== d.ruleHint ? (
            <Pressable accessibilityRole="button" accessibilityLabel={`Reprendre : ${d.ruleHint}`} onPress={() => set({ rules: d.ruleHint ?? '' })}
              style={({ pressed }) => [st.hint, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
              <Txt size={15} weight="600" color={C.lavText}>✦ {d.ruleHint}</Txt>
            </Pressable>
          ) : null}
          <Txt size={14} color={C.t2}>Écris-le avant que la bande joue : ensuite, on peut seulement le compléter.</Txt>
        </Block>
      ) : null}
      {problem && d.question.trim().length >= 5 ? <Txt size={14} color={C.amber}>{problem}</Txt> : null}
    </StepScreen>
  );
}

function Note({ children }: { children: string }) {
  return <View style={st.note}><Txt size={14} color={C.t2}>{children}</Txt></View>;
}

function OptionsEditor({ d, set }: { d: Draft; set: (p: Partial<Draft>) => void }) {
  const opts = d.options;
  return (
    <Block label="LES RÉPONSES" right={`${opts.length} sur 8`} index={3}>
      {opts.map((o, i) => (
        <View key={i} style={[st.opt, enter('rise', i)]}>
          <View style={[st.shape, { backgroundColor: `${SHAPES[i].color}29` }]} accessibilityLabel={SHAPES[i].name}>
            <Text style={{ color: SHAPES[i].color, fontSize: 20 }}>{SHAPES[i].glyph}</Text>
          </View>
          <TextInput value={o} onChangeText={(v) => set({ options: opts.map((x, j) => (j === i ? v : x)) })} maxLength={60}
            placeholder={`Réponse ${i + 1}`} placeholderTextColor={C.t3} accessibilityLabel={`Choix ${i + 1}`} testID={`prono-option-${i}`}
            style={[body, st.optInput, noOutline]} />
          {opts.length > 2 ? (
            <Pressable accessibilityRole="button" accessibilityLabel={`Retirer la réponse ${i + 1}`} hitSlop={6}
              onPress={() => set({ options: opts.filter((_, j) => j !== i) })} style={st.remove}>
              <Txt size={18} color={C.t3}>✕</Txt>
            </Pressable>
          ) : null}
        </View>
      ))}
      {opts.length < 8 ? (
        <Pressable accessibilityRole="button" testID="prono-add-option" onPress={() => set({ options: [...opts, ''] })}
          style={({ pressed }) => [st.add, pressTransition, pressed && { opacity: 0.7 }]}>
          <Txt size={18} weight="600" color={C.lavText}>＋  Ajouter une réponse</Txt>
        </Pressable>
      ) : null}
    </Block>
  );
}

function LineEditor({ d, set }: { d: Draft; set: (p: Partial<Draft>) => void }) {
  const auto = (line: number, unit: string) => `Plus ou moins de ${lineLabel(line)} ${unit} ?`;
  // La question suit la ligne et l'unité tant qu'elle n'a pas été réécrite à la main.
  const follow = (line: number, unit: string) => {
    const q = !d.question.trim() || d.question === auto(d.line, d.unit) || /^Plus ou moins de [\d,]+ /.test(d.question) ? auto(line, unit) : d.question;
    set({ line, unit, question: q });
  };
  const base = Math.floor(d.line);
  const ticks = [base - 2, base - 1, base, base + 1, base + 2, base + 3].filter((n) => n >= 0);
  return (
    <Block label="LA LIGNE" right="en demi-unité" index={3}>
      <View style={st.lineCard}>
        <View style={st.lineTop}>
          <Pressable accessibilityRole="button" accessibilityLabel="Un de moins" disabled={d.line <= 0.5} testID="prono-line-minus"
            onPress={() => follow(Math.max(0.5, d.line - 1), d.unit)} style={({ pressed }) => [st.step, pressed && { transform: [{ scale: 0.92 }] }, d.line <= 0.5 && { opacity: 0.4 }]}>
            <Txt size={30} weight="500">−</Txt>
          </Pressable>
          <View style={{ alignItems: 'center' }} accessibilityLabel={`Ligne : ${lineLabel(d.line)} ${d.unit}`}>
            <Text style={[digits, { fontSize: 64, lineHeight: 70, color: C.t1 }]}>{lineLabel(d.line)}</Text>
            <Txt size={17} color={C.t2}>{d.unit}</Txt>
          </View>
          <Pressable accessibilityRole="button" accessibilityLabel="Un de plus" testID="prono-line-plus"
            onPress={() => follow(Math.min(999.5, d.line + 1), d.unit)} style={({ pressed }) => [st.step, pressed && { transform: [{ scale: 0.92 }] }]}>
            <Txt size={30} weight="500">+</Txt>
          </Pressable>
        </View>
        <View style={st.track}>
          <View style={[st.half, web({ backgroundImage: 'linear-gradient(90deg, rgba(77,155,255,0.06), rgba(77,155,255,0.35))' })]}>
            <Txt size={14} weight="700" color="#8FBFFF" style={{ marginLeft: 'auto' }}>{DOWN.glyph} Moins</Txt>
          </View>
          <View style={st.mark} />
          <View style={[st.half, web({ backgroundImage: 'linear-gradient(90deg, rgba(255,95,162,0.35), rgba(255,95,162,0.06))' })]}>
            <Txt size={14} weight="700" color="#FF8FC0">{UP.glyph} Plus</Txt>
          </View>
        </View>
        <View style={st.ticks}>{ticks.map((n) => <Text key={n} style={[digits, { fontSize: 14, color: C.t2 }]}>{n}</Text>)}</View>
      </View>
      <Txt size={14} color={C.t2}>Toujours une demi-unité : jamais d’égalité possible.</Txt>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
        {UNITS.map((u) => <Chip key={u} label={u} on={d.unit === u} onPress={() => follow(d.line, u)} />)}
      </View>
    </Block>
  );
}

function AwardEditor({ d, set, awards }: { d: Draft; set: (p: Partial<Draft>) => void; awards: Award[] }) {
  const chosen = awardOf(d, awards);
  return (
    <>
      <Block label="LE TROPHÉE" right="que du positif" index={2}>
        <View style={st.awards}>
          {awards.map((a) => {
            const on = a.id === chosen.id;
            return (
              <Pressable key={a.id} accessibilityRole="radio" accessibilityState={{ selected: on }} aria-checked={on} accessibilityLabel={a.label}
                testID={`prono-award-${a.id}`} onPress={() => set({ award: a.id })}
                style={({ pressed }) => [st.award, on && st.awardOn, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
                <View style={st.awardIcon}><Text style={{ fontSize: 26 }}>{a.emoji}</Text></View>
                <Txt size={16} weight="700">{a.label}</Txt>
                {on ? <View style={st.awardTick}><Txt size={14} weight="800" color="#1D1530">✓</Txt></View> : null}
              </Pressable>
            );
          })}
        </View>
      </Block>
      <Block label="LA QUESTION" index={3}>
        <View style={st.qBox}>
          <Text style={[rounded, { fontSize: 22, lineHeight: 26, color: C.t1 }]}>{shownQuestion(d, awards)}</Text>
          <Txt size={14} color={C.t2}>🔒 Écrite par Party pour chaque trophée</Txt>
        </View>
      </Block>
      <Block label="COMMENT ÇA MARCHE" index={4}>
        <View style={st.how}>
          {[
            ['🗳️', 'Chacun vote pour une personne,', ' jamais pour soi.'],
            ['🔒', 'Votes cachés', ' jusqu’au dévoilement, 3 votes au moins.'],
            ['🏅', 'Seul le ou la gagnant·e est annoncé·e,', ' jamais les autres scores.'],
            ['🙋', 'Chacun peut se retirer', ' de la liste des nommés.'],
          ].map(([icon, strong, rest], i) => (
            <View key={icon} style={[st.howRow, i > 0 && { borderTopWidth: 1, borderTopColor: C.line }]}>
              <View style={st.howIcon}><Text style={{ fontSize: 18 }}>{icon}</Text></View>
              <Txt size={16} color={C.t2} style={{ flex: 1 }}><Text style={{ color: C.t1, fontWeight: '700' }}>{strong}</Text>{rest}</Txt>
            </View>
          ))}
        </View>
      </Block>
    </>
  );
}

const st = StyleSheet.create({
  liveRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  dot: web({ width: 10, height: 10, borderRadius: 5, backgroundColor: C.mint, boxShadow: `0 0 8px ${C.mint}` }),
  qBox: web({ gap: 8, padding: 16, borderRadius: 16, backgroundColor: C.glass, borderWidth: 1.5, borderColor: 'rgba(185,167,255,0.5)',
    boxShadow: '0 0 0 4px rgba(185,167,255,0.12)' }),
  qInput: { fontSize: 20, lineHeight: 25, color: C.t1, minHeight: 50, padding: 0 },
  opt: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 58, paddingLeft: 10, paddingRight: 6, borderRadius: 18,
    backgroundColor: C.glass, borderWidth: 1, borderColor: C.line },
  shape: { width: 36, height: 36, borderRadius: 10, alignItems: 'center', justifyContent: 'center' },
  optInput: { flex: 1, fontSize: 17, fontWeight: '600', color: C.t1, minHeight: 44, padding: 0 },
  remove: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  add: { minHeight: 58, borderRadius: 18, borderWidth: 1.5, borderStyle: 'dashed', borderColor: 'rgba(255,255,255,0.22)', justifyContent: 'center', paddingHorizontal: 18 },
  note: { padding: 14, borderRadius: 16, backgroundColor: 'rgba(185,167,255,0.08)', borderWidth: 1, borderColor: 'rgba(185,167,255,0.22)' },
  switchRow: { flexDirection: 'row', alignItems: 'center', gap: 12, padding: 14, borderRadius: 18, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line, minHeight: 64 },
  switch: { width: 51, height: 31, borderRadius: 16, backgroundColor: 'rgba(255,255,255,0.16)', padding: 2 },
  switchOn: { backgroundColor: C.lavDeep },
  knob: web({ width: 27, height: 27, borderRadius: 14, backgroundColor: '#fff', transitionProperty: 'transform', transitionDuration: '200ms' }),
  rules: { minHeight: 56, padding: 16, borderRadius: 16, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line, fontSize: 17, color: C.t1 },
  hint: { alignSelf: 'flex-start', minHeight: 44, justifyContent: 'center', paddingHorizontal: 16, borderRadius: 16,
    backgroundColor: 'rgba(185,167,255,0.10)', borderWidth: 1, borderColor: 'rgba(185,167,255,0.35)' },
  lineCard: { padding: 18, gap: 16, borderRadius: 24, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line },
  lineTop: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between' },
  step: { width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.06)',
    borderWidth: 1, borderColor: C.lineStrong },
  track: { flexDirection: 'row', alignItems: 'center', height: 22 },
  half: { flex: 1, height: 22, borderRadius: 11, justifyContent: 'center', paddingHorizontal: 10, flexDirection: 'row', alignItems: 'center' },
  mark: web({ width: 4, height: 30, borderRadius: 2, marginHorizontal: 6, backgroundColor: C.lav, boxShadow: `0 0 10px ${C.lav}` }),
  ticks: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 8 },
  awards: { flexDirection: 'row', flexWrap: 'wrap', gap: 12 },
  award: { flexBasis: '47%', flexGrow: 1, minHeight: 110, padding: 14, gap: 10, borderRadius: 22, backgroundColor: C.glass, borderWidth: 2, borderColor: C.line },
  awardOn: web({ borderColor: C.lemon, boxShadow: '0 0 0 4px rgba(255,226,122,0.16)' }),
  awardIcon: { width: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(255,255,255,0.08)', alignItems: 'center', justifyContent: 'center' },
  awardTick: { position: 'absolute', top: -10, right: -10, width: 30, height: 30, borderRadius: 15, backgroundColor: C.lemon,
    alignItems: 'center', justifyContent: 'center', borderWidth: 3, borderColor: C.bg },
  how: { borderRadius: 24, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line, paddingHorizontal: 16 },
  howRow: { flexDirection: 'row', alignItems: 'flex-start', gap: 14, paddingVertical: 14 },
  howIcon: { width: 36, height: 36, borderRadius: 10, backgroundColor: 'rgba(255,255,255,0.06)', alignItems: 'center', justifyContent: 'center' },
});
