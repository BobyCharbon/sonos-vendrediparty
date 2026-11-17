import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Platform, Pressable, Share, StyleSheet, Text, View } from 'react-native';

import { DateTimeField } from '@/components/DateTimeField';
import { goBack, TopBar } from '@/components/agenda/Bits';
import { Faces, HonourNote, LEMON, SealBox, StateChip } from '@/components/pronos/Bits';
import { ReportSheet } from '@/components/ReportSheet';
import { useTermsGate } from '@/components/TermsSheet';
import { Avatar, Button, ConfirmButton, ErrorText, Input, Loading, Screen, T } from '@/components/ui';
import { useQuery, useSignal } from '@/lib/data';
import { formatShort, parseLocalDateTime, plural, toLocalInput } from '@/lib/format';
import type { ReportTarget } from '@/lib/moderation';
import { enter, pressTransition } from '@/lib/motion';
import {
  answerLabel, errorText, isTerms, nativePronos, placeLine, pointsLabel, resultLabel, rpc, stateLine, type Face, type Prono,
} from '@/lib/pronos';
import { colors, font, radius } from '@/lib/theme';

type WebStyle = Record<string, unknown>;
const web = (style: WebStyle) => style as object;

/**
 * Un prono (maquette du 17.11, écrans 3 à 5) : jouer d'un toucher (réponse cachée, modifiable jusqu'à la fin), donner
 * le résultat (organisateur, une fois fermé), puis le dévoilement : bonne réponse, répartition avec les visages,
 * gagnants et leurs points. Pour l'honneur seulement. Dans l'app iPhone, l'écran natif prend le relais.
 */
export default function PronoScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const native = nativePronos();
  useEffect(() => {
    if (native && id) { native.open(id); goBack('/'); }
  }, [native, id]);
  const { data, error, loading, reload } = useQuery(() => rpc<Prono>('prono_get', { id }), [id]);
  useSignal(id ? [`prono:${id}`] : [], reload);
  // La réponse d'une action remplace l'affichage jusqu'à la relecture suivante (temps réel, retour) : la plus récente gagne.
  const [acted, setP] = useState<{ prono: Prono; base: Prono | null | undefined } | null>(null);
  const p = acted && acted.base === data ? acted.prono : (data ?? acted?.prono ?? null);
  const terms = useTermsGate('Avant de jouer');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<(ReportTarget & { author?: string }) | null>(null);

  async function act(fn: string, args: Record<string, unknown>): Promise<boolean> {
    setBusy(true);
    setErr(null);
    try {
      setP({ prono: await rpc<Prono>(fn, args), base: data });
      return true;
    } catch (e) {
      if (isTerms(e) && (await terms.ensure())) return act(fn, args);
      setErr(errorText(e));
      return false;
    } finally {
      setBusy(false);
    }
  }

  if (loading && !p) return <Loading />;
  if (!p) {
    return (
      <Screen contentStyle={{ gap: 12 }}>
        <Stack.Screen options={{ headerShown: false }} />
        <TopBar back="Pronos" fallback="/pronos" title="Prono introuvable" />
        <T muted>Ce prono n’existe plus, ou il ne t’est pas ouvert.</T>
        <ErrorText error={error ?? null} />
      </Screen>
    );
  }

  return (
    <Screen contentStyle={{ gap: 14, paddingBottom: 48 }}>
      <Stack.Screen options={{ headerShown: false, title: p.question }} />
      <TopBar back={p.group ? p.group.name : 'Pronos'} fallback={p.group ? `/group/${p.group.id}/pronos` : '/pronos'} />
      <Head p={p} />
      {p.state === 'open' ? <Play p={p} busy={busy} onAnswer={(answer) => void act('prono_answer', { id: p.id, answer })} /> : null}
      {p.state === 'closed' ? <Closed p={p} busy={busy} onResult={(body) => act('prono_result', { id: p.id, body })} /> : null}
      {p.state === 'done' ? <Done p={p} /> : null}
      {p.state === 'cancelled' ? <T muted>Ce prono a été annulé : aucun point n’est compté.</T> : null}
      <ErrorText error={err} />
      {p.revealed && p.state !== 'done' && p.answers ? <Answers p={p} onReport={(author) => setReport({ kind: 'prono', id: p.id, label: 'cette réponse', author })} /> : null}
      {p.mine ? <Organizer p={p} busy={busy} act={act} /> : (
        <Button small variant="ghost" label="Signaler ce prono" onPress={() => setReport({ kind: 'prono', id: p.id, label: 'ce prono' })} />
      )}
      <T muted size={12} style={{ textAlign: 'center' }}>Proposé par {p.creator.me ? 'toi' : p.creator.name} · {formatShort(p.created_at)}</T>
      <ReportSheet target={report} onClose={() => setReport(null)}
        send={report?.author ? (reason, comment) => rpc('prono_report_answer', { id: p.id, author: report.author, reason, comment: comment || null }).then(() => undefined) : undefined} />
      {terms.sheet}
    </Screen>
  );
}

function Head({ p }: { p: Prono }) {
  const tone = p.state === 'open' ? 'open' : p.state === 'closed' ? 'closed' : p.state === 'done' ? 'done' : 'cancelled';
  return (
    <View style={{ gap: 8 }}>
      <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
        <StateChip tone={tone} label={p.state === 'open' ? (p.revealed ? 'Ouvert' : `🔒 Réponses cachées · ${stateLine(p).toLowerCase()}`) : `${stateLine(p)}`} />
        <T size={13} muted>{placeLine(p)}</T>
      </View>
      <Text role="heading" aria-level={1} style={st.question}>{p.question}</Text>
      <T size={13} muted>{pointsLabel(p.points)} pour une bonne réponse{p.kind === 'number' ? ' · le plus proche gagne' : ''}</T>
    </View>
  );
}

// ───────── Jouer ─────────

function Play({ p, busy, onAnswer }: { p: Prono; busy: boolean; onAnswer: (a: Record<string, unknown>) => void }) {
  const mine = p.my_answer;
  const [num, setNum] = useState(mine?.number != null ? String(mine.number) : '');
  const [text, setText] = useState(mine?.text ?? '');
  if (!p.can_answer) return <T muted>Ce prono ne t’est pas ouvert.</T>;
  const until = p.reveal === 'close' ? 'la fin des pronos' : 'le résultat';
  return (
    <View style={{ gap: 10 }}>
      {p.kind === 'choice' ? p.options.map((o, i) => (
        <Choice key={o.id} on={mine?.option_id === o.id} label={o.label} index={i} disabled={busy} onPress={() => onAnswer({ option_id: o.id })} />
      )) : null}
      {p.kind === 'person' ? (
        <View style={st.people}>
          {(p.candidates ?? []).map((c, i) => (
            <PersonChoice key={c.id} face={c} on={mine?.person_id === c.id} index={i} disabled={busy} onPress={() => onAnswer({ person_id: c.id })} />
          ))}
        </View>
      ) : null}
      {p.kind === 'number' ? (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Input value={num} onChangeText={setNum} placeholder="Ton nombre" inputMode="decimal" keyboardType="numbers-and-punctuation"
            accessibilityLabel="Ton nombre" style={{ flex: 1, fontSize: 22 }} />
          <Button label={mine ? 'Changer' : 'Valider'} loading={busy} disabled={!num.trim() || Number.isNaN(Number(num.replace(',', '.')))}
            onPress={() => onAnswer({ number: Number(num.replace(',', '.')) })} />
        </View>
      ) : null}
      {p.kind === 'text' ? (
        <View style={{ gap: 8 }}>
          <Input value={text} onChangeText={setText} placeholder="Ta réponse" maxLength={80} accessibilityLabel="Ta réponse" />
          <Button label={mine ? 'Changer ma réponse' : 'Valider'} loading={busy} disabled={!text.trim() || text.trim() === mine?.text}
            onPress={() => onAnswer({ text: text.trim() })} />
        </View>
      ) : null}
      <SealBox title={mine ? 'Ta réponse est enregistrée et cachée' : 'Ta réponse restera cachée'}>
        Personne ne la voit avant {until}, pas même {p.mine ? 'toi en tant qu’organisateur' : p.creator.name}. Tu peux changer
        jusqu’au {formatShort(p.closes_at)}.
      </SealBox>
      <Played p={p} />
    </View>
  );
}

function Choice({ on, label, index, disabled, onPress }: { on: boolean; label: string; index: number; disabled: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="radio" accessibilityState={{ selected: on, disabled }} aria-checked={on} disabled={disabled} onPress={onPress}
      testID={`prono-choice-${index}`}
      style={({ pressed }) => [st.choice, on && st.choiceOn, enter('rise', index), pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
      <T weight="bold" size={17} style={{ flex: 1 }}>{label}</T>
      {on ? <View style={[st.tick, enter('pop')]}><Text style={{ color: '#fff', ...font.bold }}>✓</Text></View> : null}
    </Pressable>
  );
}

function PersonChoice({ face, on, index, disabled, onPress }: { face: Face; on: boolean; index: number; disabled: boolean; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="radio" accessibilityLabel={face.me ? 'Toi' : face.name} accessibilityState={{ selected: on }} aria-checked={on}
      disabled={disabled} onPress={onPress}
      style={({ pressed }) => [st.person, on && st.choiceOn, enter('pop', index), pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
      <Avatar id={face.id} name={face.name} photo={face.avatar_url} size={48} profile={false} />
      <T size={13} weight="semibold" numberOfLines={1}>{face.me ? 'Toi' : face.name}</T>
    </Pressable>
  );
}

function Played({ p }: { p: Prono }) {
  const missing = Math.max(0, p.players - p.answered.length);
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
      {p.answered.length ? <Faces faces={p.answered.slice(-8)} ring={colors.bg} /> : null}
      <T size={13} muted style={{ flex: 1 }}>
        {p.answered.length ? `${plural(p.answered.length, 'personne a joué', 'personnes ont joué')}` : 'Personne n’a encore joué'}
        {missing ? ` · ${missing} pas encore` : ''}
      </T>
    </View>
  );
}

// ───────── Fermé : résultat ─────────

function Closed({ p, busy, onResult }: { p: Prono; busy: boolean; onResult: (b: Record<string, unknown>) => Promise<boolean> }) {
  const [opt, setOpt] = useState<string | null>(null);
  const [person, setPerson] = useState<string | null>(null);
  const [num, setNum] = useState('');
  const [winners, setWinners] = useState<Set<string>>(new Set());
  if (!p.mine) {
    return (
      <View style={{ gap: 10 }}>
        <SealBox title={`En attente du résultat de ${p.creator.name}`}>
          {p.revealed ? 'Les réponses sont dévoilées ci-dessous.' : 'Les réponses restent cachées jusqu’au résultat.'}
          {p.my_answer ? ` Ta réponse : ${answerLabel(p, p.my_answer)}.` : ' Tu n’as pas joué.'}
        </SealBox>
        <Played p={p} />
      </View>
    );
  }
  if (!p.answered.length) {
    return <T muted>Personne n’a joué : tu peux annuler ce prono ou rouvrir les pronos en déplaçant la fin.</T>;
  }
  const ready = p.kind === 'choice' ? !!opt : p.kind === 'person' ? !!person : p.kind === 'number' ? num.trim() !== '' && !Number.isNaN(Number(num.replace(',', '.'))) : true;
  const body = p.kind === 'choice' ? { option_id: opt } : p.kind === 'person' ? { person_id: person }
    : p.kind === 'number' ? { number: Number(num.replace(',', '.')) } : { winners: [...winners] };
  return (
    <View style={{ gap: 10 }}>
      <Text style={st.ask}>Quel est le résultat&nbsp;?</Text>
      <T size={13} muted>{plural(p.answered.length, 'personne a joué', 'personnes ont joué')}. Tout le monde verra le résultat et les gagnants dès que tu valides.</T>
      {p.kind === 'choice' ? p.options.map((o, i) => (
        <Pressable key={o.id} accessibilityRole="radio" accessibilityState={{ selected: opt === o.id }} aria-checked={opt === o.id} onPress={() => setOpt(o.id)}
          testID={`prono-result-${i}`} style={({ pressed }) => [st.res, opt === o.id && st.resOn, pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
          <View style={[st.dot, opt === o.id && st.dotOn]}>{opt === o.id ? <Text style={{ color: colors.bg, ...font.bold }}>✓</Text> : null}</View>
          <T weight="bold" style={{ flex: 1 }}>{o.label}</T>
          {o.count != null ? <T size={13} muted>{plural(o.count, 'réponse')}</T> : null}
        </Pressable>
      )) : null}
      {p.kind === 'person' ? (
        <View style={st.people}>
          {(p.candidates ?? []).map((c, i) => <PersonChoice key={c.id} face={c} on={person === c.id} index={i} disabled={busy} onPress={() => setPerson(c.id)} />)}
        </View>
      ) : null}
      {p.kind === 'number' ? (
        <Input value={num} onChangeText={setNum} placeholder="Le vrai résultat" inputMode="decimal" accessibilityLabel="Le vrai résultat" style={{ fontSize: 22 }} />
      ) : null}
      {p.kind === 'text' ? (p.answers ?? []).map((a) => {
        const on = winners.has(a.user.id);
        return (
          <Pressable key={a.user.id} accessibilityRole="checkbox" accessibilityState={{ checked: on }} aria-checked={on}
            onPress={() => setWinners((w) => { const n = new Set(w); if (on) n.delete(a.user.id); else n.add(a.user.id); return n; })}
            style={({ pressed }) => [st.res, on && st.resOn, pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
            <View style={[st.box, on && st.dotOn]}>{on ? <Text style={{ color: colors.bg, ...font.bold }}>✓</Text> : null}</View>
            <Avatar id={a.user.id} name={a.user.name} photo={a.user.avatar_url} size={30} profile={false} />
            <View style={{ flex: 1 }}>
              <T weight="bold">{a.hidden ? 'Réponse masquée' : a.text}</T>
              <T size={12} muted>{a.user.me ? 'Toi' : a.user.name}</T>
            </View>
          </Pressable>
        );
      }) : null}
      <Button label={p.kind === 'text' ? `🎉 Dévoiler · ${plural(winners.size, 'gagnant')}` : '🎉 Dévoiler le résultat'} disabled={!ready} loading={busy}
        onPress={() => void onResult(body)} />
    </View>
  );
}

// ───────── Dévoilement ─────────

function Done({ p }: { p: Prono }) {
  const me = p.my_answer;
  const label = resultLabel(p);
  const total = Math.max(1, p.answers?.length ?? 0);
  return (
    <View style={{ gap: 14, alignItems: 'stretch' }} testID="prono-reveal">
      <View style={st.revealTop}>
        <View style={[st.trophy, enter('pop')]}><Text style={{ fontSize: 44 }}>🏆</Text></View>
        {label ? <Text style={[st.answer, enter('rise', 2)]}>{label}&nbsp;!</Text> : null}
        <T size={14} muted style={{ textAlign: 'center' }}>
          {me ? (me.winner ? <Text style={{ color: LEMON, ...font.bold }}>Tu avais vu juste · +{pointsLabel(p.points)}</Text> : `Ta réponse : ${answerLabel(p, me)}`) : 'Tu n’as pas joué.'}
        </T>
      </View>
      {p.kind === 'choice' ? p.options.map((o, i) => {
        const who = (p.answers ?? []).filter((a) => a.option_id === o.id).map((a) => a.user);
        return <Bar key={o.id} label={o.label} faces={who} count={o.count ?? who.length} total={total} good={!!o.correct} index={i} />;
      }) : null}
      {p.kind === 'person' ? groupBy(p, (a) => a.person?.id ?? '').map(([key, rows], i) => (
        <Bar key={key} label={rows[0].person ? (rows[0].person.me ? 'Toi' : rows[0].person.name) : '—'} faces={rows.map((r) => r.user)} count={rows.length}
          total={total} good={p.result?.person?.id === key} index={i} />
      )) : null}
      {p.kind === 'number' || p.kind === 'text' ? (p.answers ?? []).map((a, i) => (
        <View key={a.user.id} style={[st.res, a.winner && st.resWin, enter('rise', i)]}>
          <Avatar id={a.user.id} name={a.user.name} photo={a.user.avatar_url} size={30} profile={false} />
          <T weight="bold" style={{ flex: 1 }}>{answerLabel(p, a)}</T>
          <T size={12} muted>{a.user.me ? 'Toi' : a.user.name}</T>
          {a.winner ? <Text style={{ fontSize: 16 }}>🏆</Text> : null}
        </View>
      )) : null}
      <T size={13} weight="bold" color={colors.muted} style={{ textAlign: 'center', letterSpacing: 0.8 }}>LES GAGNANTS</T>
      {p.winners?.length ? (
        <View style={st.wins}>
          {p.winners.map((w, i) => (
            <View key={w.id} style={[{ alignItems: 'center', gap: 4, width: 74 }, enter('pop', i + 3)]}>
              <View style={st.winRing}><Avatar id={w.id} name={w.name} photo={w.avatar_url} size={52} profile={false} /></View>
              <T size={13} weight="bold" numberOfLines={1}>{w.me ? 'Toi' : w.name}</T>
              <Text style={{ color: LEMON, fontSize: 12, ...font.bold }}>+{p.points}</Text>
            </View>
          ))}
        </View>
      ) : <T muted style={{ textAlign: 'center' }}>Personne n’avait vu juste.</T>}
      {p.group ? <Button variant="secondary" label="🏅 Voir le classement" onPress={() => router.push(`/group/${p.group?.id}/pronos?tab=board`)} /> : null}
    </View>
  );
}

function groupBy(p: Prono, key: (a: NonNullable<Prono['answers']>[number]) => string) {
  const m = new Map<string, NonNullable<Prono['answers']>>();
  for (const a of p.answers ?? []) m.set(key(a), [...(m.get(key(a)) ?? []), a]);
  return [...m.entries()].sort((a, b) => b[1].length - a[1].length);
}

function Bar({ label, faces, count, total, good, index }: { label: string; faces: Face[]; count: number; total: number; good: boolean; index: number }) {
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }} accessibilityLabel={`${label} : ${plural(count, 'réponse')}${good ? ', bonne réponse' : ''}`}>
      <T weight="semibold" numberOfLines={1} style={{ width: 84 }}>{label}</T>
      <View style={st.barTrack}>
        <View style={[st.barFill, { width: `${Math.max(count ? 12 : 0, (count / total) * 100)}%` },
          good ? web({ backgroundImage: 'linear-gradient(90deg,#5BE3A6,#22B07D)' }) : { backgroundColor: colors.surface2 }, enter('grow', index)]} />
        <View style={st.barFaces}><Faces faces={faces.slice(0, 6)} size={22} ring={good ? '#22B07D' : colors.surface2} /></View>
      </View>
      <T muted style={{ width: 22, textAlign: 'right' }}>{count}</T>
    </View>
  );
}

function Answers({ p, onReport }: { p: Prono; onReport: (author: string) => void }) {
  return (
    <View style={{ gap: 8 }}>
      <T size={13} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>LES RÉPONSES</T>
      {(p.answers ?? []).map((a) => (
        <View key={a.user.id} style={st.res}>
          <Avatar id={a.user.id} name={a.user.name} photo={a.user.avatar_url} size={30} profile={false} />
          <View style={{ flex: 1 }}>
            <T weight="bold">{answerLabel(p, a)}</T>
            <T size={12} muted>{a.user.me ? 'Toi' : a.user.name}</T>
          </View>
          {p.kind === 'text' && !a.user.me && !a.hidden ? <Button small variant="ghost" label="Signaler" onPress={() => onReport(a.user.id)} /> : null}
        </View>
      ))}
    </View>
  );
}

// ───────── Organisateur ─────────

function Organizer({ p, busy, act }: { p: Prono; busy: boolean; act: (fn: string, args: Record<string, unknown>) => Promise<boolean> }) {
  const [end, setEnd] = useState(toLocalInput(p.closes_at));
  const [copied, setCopied] = useState(false);
  const live = p.state === 'open' || p.state === 'closed';
  const url = p.link?.path && typeof location !== 'undefined' ? `${location.origin}${p.link.path}` : null;
  async function share() {
    if (!url) return;
    if (Platform.OS === 'web' && typeof navigator !== 'undefined' && 'share' in navigator) {
      await (navigator as Navigator).share({ title: 'Un prono pour toi', text: p.question, url }).catch(() => undefined);
    } else await Share.share({ message: `${p.question} ${url}` }).catch(() => undefined);
  }
  async function copy() {
    if (!url) return;
    await navigator.clipboard?.writeText(url).catch(() => undefined);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }
  if (!live) {
    return p.state === 'cancelled' || !p.answered.length
      ? <ConfirmButton label="Supprimer ce prono" confirmLabel="Oui, supprimer" onConfirm={() => void rpc('prono_delete', { id: p.id }).then(() => goBack('/pronos'))} />
      : null;
  }
  return (
    <View style={st.tools}>
      <T size={13} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>ORGANISATION</T>
      {p.state === 'open' ? (
        <View style={{ gap: 8 }}>
          <T size={14} weight="semibold">Lien pour inviter d’autres personnes</T>
          {url ? (
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Button small label="Partager" style={{ flex: 1 }} onPress={() => void share()} />
              <Button small variant="secondary" label={copied ? 'Copié ✓' : 'Copier'} style={{ flex: 1 }} onPress={() => void copy()} />
              <Button small variant="danger" label="Arrêter" onPress={() => void act('prono_set_link', { id: p.id, active: false })} />
            </View>
          ) : <Button small variant="secondary" label="🔗 Créer un lien" loading={busy} onPress={() => void act('prono_set_link', { id: p.id, active: true })} />}
          <T size={12} muted>Qui l’ouvre se connecte à Party, puis joue. Le lien s’arrête à la fin des pronos.</T>
        </View>
      ) : null}
      {p.can_move_end && !(p.reveal === 'close' && p.revealed) ? (
        <View style={{ gap: 8 }}>
          <DateTimeField label="Fin des pronos" value={end} onChangeText={setEnd} />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button small variant="secondary" label="Déplacer la fin" style={{ flex: 1 }} disabled={!parseLocalDateTime(end) || end === toLocalInput(p.closes_at)}
              onPress={() => { const iso = parseLocalDateTime(end); if (iso) void act('prono_update', { id: p.id, body: { closes_at: iso } }); }} />
            {p.state === 'open' ? <Button small variant="secondary" label="Fermer maintenant" style={{ flex: 1 }} onPress={() => void act('prono_close_now', { id: p.id })} /> : null}
          </View>
        </View>
      ) : null}
      {p.locked ? <T size={12} muted>Quelqu’un a joué : la question et les choix ne changent plus.</T> : null}
      <ConfirmButton label={p.state === 'closed' ? 'Pas de résultat (annuler le prono)' : 'Annuler le prono'} confirmLabel="Oui, annuler : aucun point"
        onConfirm={() => void act('prono_cancel', { id: p.id })} />
      <HonourNote points={p.points} />
    </View>
  );
}

const st = StyleSheet.create({
  question: { color: colors.text, fontSize: 28, lineHeight: 31, ...font.display, letterSpacing: -0.5 },
  ask: { color: colors.text, fontSize: 24, ...font.display, letterSpacing: -0.4 },
  choice: { flexDirection: 'row', alignItems: 'center', minHeight: 60, borderRadius: 18, paddingHorizontal: 16, backgroundColor: colors.surface,
    borderWidth: 2, borderColor: 'transparent' },
  choiceOn: web({ borderColor: colors.accent, backgroundColor: colors.surface,
    backgroundImage: 'linear-gradient(120deg, rgba(255,79,154,0.28), rgba(185,167,255,0.16))',
    boxShadow: '0 0 18px rgba(255,79,154,0.45)' }),
  tick: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.accent, alignItems: 'center', justifyContent: 'center' },
  people: { flexDirection: 'row', flexWrap: 'wrap', gap: 10 },
  person: { width: 92, alignItems: 'center', gap: 6, paddingVertical: 12, borderRadius: 18, backgroundColor: colors.surface, borderWidth: 2, borderColor: 'transparent' },
  res: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 8,
    backgroundColor: colors.surface, borderWidth: 2, borderColor: 'transparent' },
  resOn: web({ borderColor: colors.mint, backgroundImage: 'linear-gradient(120deg, rgba(91,227,166,0.18), transparent)' }),
  resWin: web({ borderColor: LEMON, backgroundImage: 'linear-gradient(120deg, rgba(255,226,122,0.16), transparent)' }),
  dot: { width: 26, height: 26, borderRadius: 13, borderWidth: 2, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  box: { width: 26, height: 26, borderRadius: 8, borderWidth: 2, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  dotOn: { backgroundColor: colors.mint, borderColor: colors.mint },
  revealTop: web({ alignItems: 'center', gap: 6, paddingVertical: 14, borderRadius: radius.lg,
    backgroundImage: 'radial-gradient(70% 70% at 50% 10%, rgba(255,226,122,0.22), transparent 70%)' }),
  trophy: web({ width: 84, height: 84, borderRadius: 26, alignItems: 'center', justifyContent: 'center', backgroundColor: '#FFB347',
    backgroundImage: 'linear-gradient(135deg,#FFEA9C,#FFB347)', boxShadow: '0 0 0 6px rgba(255,226,122,0.15), 0 14px 40px rgba(255,179,71,0.55)' }),
  answer: { color: colors.text, fontSize: 30, ...font.display, letterSpacing: -0.5, textAlign: 'center' },
  barTrack: { flex: 1, height: 32, borderRadius: 10, backgroundColor: colors.fill, overflow: 'hidden', justifyContent: 'center' },
  barFill: { position: 'absolute', left: 0, top: 0, bottom: 0, borderRadius: 10 },
  barFaces: { paddingLeft: 6 },
  wins: { flexDirection: 'row', flexWrap: 'wrap', justifyContent: 'center', gap: 10 },
  winRing: web({ borderRadius: 999, borderWidth: 3, borderColor: LEMON, boxShadow: '0 0 18px rgba(255,226,122,0.55)' }),
  tools: { gap: 12, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, marginTop: 8 },
});

