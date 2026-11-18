import { router } from 'expo-router';
import { useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { Avatar, Button } from '@/components/ui';
import { GlassCard, PrimaryButton, Seal, SectionLabel } from '@/components/pronos/Kit';
import { ResultView } from '@/components/pronos/reveal/ResultView';
import { RevealStage } from '@/components/pronos/reveal/RevealStage';
import { formatTime } from '@/lib/format';
import { answerLabel, resultLabel, type Prono } from '@/lib/pronos';

import { AnswerPicker } from './Answer';
import { ContestAsk, ContestBanner, ContestSheet, ContestVote } from './Contest';
import { AnswerShape, Plant } from './Plant';
import { FieldCard, SealedCard, Seals, SealsTeaser } from './Sealed';
import {
  answerBody, C, draftFrom, draftLabel, draftReady, hhmm, meName, OPTION_KINDS, rounded, webView, withPatates, type Draft, type PronoV2,
} from './model';

type Act = (fn: string, args: Record<string, unknown>) => Promise<boolean>;

/**
 * Prono ouvert : la réponse (par type), les patates, « Sceller ma réponse » ; puis l'état scellé (« Changer » rouvre
 * la réponse ET les patates). `pick` : choix présélectionné venu de la liste (?pick=<option_id>), jamais envoyé seul.
 */
export function Play({ p, pick, busy, act }: { p: PronoV2; pick?: string | null; busy: boolean; act: Act }) {
  const [editing, setEditing] = useState(!p.my_answer);
  const [draft, setDraft] = useState<Draft>(() => draftFrom(p, p.my_answer ? null : pick));
  const [planted, setPlanted] = useState(p.my_answer?.stake ?? 0);
  if (!p.can_answer) return <Text style={st.help}>Ce prono ne t’est pas ouvert.</Text>;

  if (p.my_answer && !editing) {
    const mine = draftFrom(p);
    return (
      <View style={{ gap: 22 }}>
        <SealedCard p={p} answer={draftLabel(p, mine)} compact={p.mine}
          onChange={() => { setDraft(mine); setPlanted(p.my_answer?.stake ?? 0); setEditing(true); }} />
        <Seals p={p} />
        <FieldCard p={p} />
      </View>
    );
  }

  const label = draftLabel(p, draft);
  const index = OPTION_KINDS.includes(p.kind) ? p.options.findIndex((o) => o.id === draft.option_id) : -1;
  const patates = withPatates(p);
  async function seal() {
    if (await act('prono_answer', { id: p.id, answer: answerBody(p, draft, patates ? planted : 0) })) setEditing(false);
  }
  return (
    <View style={{ gap: 22 }}>
      <AnswerPicker p={p} draft={draft} onDraft={setDraft} busy={busy} onOptout={(out) => void act('prono_optout', { id: p.id, out })} />
      <SealsTeaser faces={p.answered.filter((f) => !f.me)} />
      {patates ? (
        <Plant p={p} value={planted} onValue={setPlanted} full={p.kind === 'choice'} answer={{ label, index: index >= 0 ? index : null }} />
      ) : null}
      <View style={st.sealBar}>
        {label ? (
          <View style={st.summary} accessibilityLabel={`${label}${patates ? `, avec ${planted} confettis` : ''}`}>
            <AnswerShape index={index >= 0 ? index : null} />
            <Text style={{ color: C.t1, fontSize: 16, fontWeight: '700' }} numberOfLines={1}>{label}</Text>
            {patates ? <Text style={st.help}>{planted ? `avec ${planted} 🎊` : 'sans confettis'}</Text> : null}
          </View>
        ) : null}
        <View testID="prono-seal">
          <PrimaryButton label={p.kind === 'award' ? 'Sceller mon vote' : 'Sceller ma réponse'} disabled={!draftReady(p, draft)} loading={busy}
            onPress={() => void seal()} />
        </View>
        <Text style={[st.small, { textAlign: 'center' }]}>
          {p.kind === 'award' ? 'Ton vote reste caché, tu peux le changer jusqu’à la fin.' : 'Tu pourras changer jusqu’à la fin.'}
        </Text>
        {p.my_answer ? (
          <Pressable accessibilityRole="button" onPress={() => setEditing(false)} style={st.keep}>
            <Text style={{ color: C.lav, fontSize: 15, fontWeight: '700' }}>Garder ma réponse scellée</Text>
          </Pressable>
        ) : null}
      </View>
    </View>
  );
}

/** Fermé, résultat attendu (joueurs) : ma réponse scellée, les sceaux, le champ. */
export function Waiting({ p }: { p: PronoV2 }) {
  const mine = p.my_answer ? draftLabel(p, draftFrom(p)) : null;
  return (
    <View style={{ gap: 22 }}>
      <GlassCard style={st.wait}>
        <Seal emoji={p.group?.emoji ?? '🔮'} color={p.group?.color} size={72} />
        <View style={{ flex: 1, gap: 4 }}>
          <Text style={rounded(19, '800')}>
            {p.kind === 'majority' || p.kind === 'award' ? 'Réponses fermées' : `En attente du résultat de ${p.creator.name}`}
          </Text>
          <Text style={st.help}>
            {p.revealed ? 'Les réponses sont dévoilées ci-dessous.' : 'Les réponses restent cachées jusqu’au résultat.'}
            {mine ? ` Ta réponse : ${mine}.` : ' Tu n’as pas joué.'}
          </Text>
        </View>
      </GlassCard>
      <Seals p={p} />
      <FieldCard p={p} />
    </View>
  );
}

/** Le résultat en mots, pour la contestation. */
export function resultText(p: PronoV2): string {
  if (p.kind === 'when') return p.result?.time ? hhmm(p.result.time) : '';
  if (p.kind === 'text') return 'les réponses cochées';
  return resultLabel(p as unknown as Prono);
}

const SEEN = (id: string) => `party-prono-reveal:${id}`;
function seen(id: string): boolean {
  try { return typeof localStorage !== 'undefined' && localStorage.getItem(SEEN(id)) === '1'; } catch { return false; }
}
function markSeen(id: string) {
  try { localStorage.setItem(SEEN(id), '1'); } catch { /* navigation privée : le dévoilement se rejouera */ }
}

/**
 * Terminé : le dévoilement (W5) ne se joue qu'une fois par personne et par prono (mémoire du navigateur), puis le
 * résultat ; autour, la contestation (bandeau, « Contester », vote des joueurs) et le classement du groupe.
 */
export function Finished({ p, busy, act, call }: {
  p: PronoV2; busy: boolean; act: Act; call: (fn: string, args: Record<string, unknown>) => Promise<string | null>;
}) {
  const [done, setDone] = useState(() => seen(p.id));
  const [contest, setContest] = useState(false);
  const c = p.contest ?? null;
  const prono = p as unknown as Prono;
  return (
    <View style={{ gap: 22 }} testID="prono-reveal">
      {done && c && (c.open || c.contested) ? <ContestBanner c={c} /> : null}
      {done ? <ResultView prono={prono} /> : (
        // Fenêtre au-dessus de toute la page : sinon les réactions et la ligne « Proposé par » de la fiche passaient
        // par-dessus le panneau plein écran (empilement des calques du défilement).
        <Modal visible transparent animationType="none" onRequestClose={() => { markSeen(p.id); setDone(true); }}>
          <RevealStage prono={prono} onDone={() => { markSeen(p.id); setDone(true); }} />
        </Modal>
      )}
      {done && c?.can_contest && !c.contested ? <ContestAsk onOpen={() => setContest(true)} /> : null}
      {done && c?.contested ? <ContestVote p={p} c={c} result={resultText(p)} busy={busy} onVote={(fair) => void act('prono_contest_vote', { id: p.id, fair })} /> : null}
      {done && p.group ? <Button variant="secondary" label="🏅 Voir le classement" onPress={() => router.push(`/group/${p.group?.id}/pronos?tab=board`)} /> : null}
      <ContestSheet open={contest} organizer={p.mine ? 'Toi' : p.creator.name} onClose={() => setContest(false)}
        onSend={(reason) => call('prono_contest', { id: p.id, reason })} />
    </View>
  );
}

/** Réponses dévoilées à la fermeture (dévoilement « à la fin », résultat pas encore donné) ; libre : « Signaler ». */
export function Answers({ p, onReport }: { p: PronoV2; onReport: (author: string) => void }) {
  return (
    <View style={{ gap: 10 }}>
      <SectionLabel>Les réponses</SectionLabel>
      {(p.answers ?? []).map((a) => (
        <View key={a.user.id} style={st.answer}>
          <Avatar id={a.user.id} name={a.user.name} photo={a.user.avatar_url} size={40} profile={false} />
          <View style={{ flex: 1 }}>
            <Text style={{ color: C.t1, fontSize: 16, fontWeight: '700' }}>
              {p.kind === 'when' ? whenText((a as unknown as { answer_at?: string | null }).answer_at) : answerLabel(p as unknown as Prono, a)}
            </Text>
            <Text style={st.small}>{meName(a.user)}</Text>
          </View>
          {p.kind === 'text' && !a.user.me && !a.hidden ? (
            <Pressable accessibilityRole="button" accessibilityLabel={`Signaler la réponse de ${a.user.name}`} onPress={() => onReport(a.user.id)} style={st.report}>
              <Text style={{ color: C.t2, fontSize: 14, fontWeight: '600' }}>Signaler</Text>
            </Pressable>
          ) : null}
        </View>
      ))}
    </View>
  );
}

const whenText = (iso: string | null | undefined) => (iso ? formatTime(iso) : '—');

const st = StyleSheet.create({
  sealBar: webView({ position: 'sticky', bottom: 0, gap: 10, marginHorizontal: -16, paddingHorizontal: 16, paddingTop: 18, paddingBottom: 12,
    backgroundImage: 'linear-gradient(180deg, rgba(21,16,42,0), rgba(21,16,42,0.62) 30%, rgba(21,16,42,0.95))' }),
  summary: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8 },
  keep: { alignSelf: 'center', minHeight: 44, justifyContent: 'center', paddingHorizontal: 12 },
  wait: { flexDirection: 'row', alignItems: 'center', gap: 16, padding: 18, borderRadius: 24 },
  answer: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, padding: 10, borderRadius: 18, backgroundColor: C.glass,
    borderWidth: 1, borderColor: C.glassLine },
  report: { minHeight: 44, paddingHorizontal: 12, justifyContent: 'center' },
  help: { color: C.t2, fontSize: 15, lineHeight: 21 },
  small: { color: C.t3, fontSize: 13, lineHeight: 18 },
});
