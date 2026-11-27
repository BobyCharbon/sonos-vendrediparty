import { useState } from 'react';
import { Modal, Pressable, StyleSheet, View } from 'react-native';

import { useQuery } from '@/lib/data';
import { addManualGuest, fetchManualGuests, removeManualGuest, setManualGuest, type ManualGuest } from '@/lib/manualGuests';
import { pressTransition, useChangedSinceMount } from '@/lib/motion';
import { rsvpChoices, rsvpOptions, setRsvpFor, waitingPlusOnes } from '@/lib/rsvp';
import { colors, font, radius } from '@/lib/theme';
import type { EventRow, Rsvp, RsvpStatus } from '@/lib/types';

import { SheetBackdrop } from './SheetGesture';
import { Avatar, Button, ConfirmButton, ErrorText, Input, Reveal, Rows, s, Section, T } from './ui';

const MAX_SUGGESTIONS = 6;
const SHORT: Record<RsvpStatus, string> = { yes: 'Oui', maybe: '?', no: 'Non' };

type Props = {
  event: Pick<EventRow, 'id' | 'allow_maybe'>;
  rsvps: Rsvp[];
  names: Map<string, string>;
  me: string;
  onChange: () => void;
  /** Change à chaque relecture de la fiche (temps réel : un autre organisateur a ajouté quelqu'un). */
  refreshKey?: number;
};

/** Pour chercher un prénom sans tenir compte des accents ni des majuscules. */
const fold = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/** Mots d'un nom, sans accents ni majuscules, sans les mots qui ne désignent personne (« Pote Théo du bar » → théo). */
const FILLER = new Set(['pote', 'ami', 'amie', 'copain', 'copine', 'cousin', 'cousine', 'frere', 'soeur', 'collegue', 'voisin',
  'voisine', 'du', 'de', 'des', 'la', 'le', 'les', 'et', 'bar', 'boulot', 'travail', 'club']);
const words = (text: string) => fold(text).split(/[^a-z0-9]+/).filter((w) => w.length >= 2 && !FILLER.has(w));

/** Même prénom (premier mot utile) ou un mot de 3 lettres et plus en commun : « Théo » ≈ « Théo Martin ». */
export function sameish(a: string, b: string): boolean {
  const A = words(a);
  const B = words(b);
  if (!A.length || !B.length) return false;
  return A[0] === B[0] || A.some((w) => w.length >= 3 && B.includes(w));
}

type Line =
  | { kind: 'member'; key: string; id: string; name: string; status: RsvpStatus; extra: string; sub: string }
  | { kind: 'manual'; key: string; id: string; name: string; status: RsvpStatus; extra: string; sub: string };

/**
 * Organisation de l'événement (créateur, co-organisateurs, admins) : noter qui vient, en un geste.
 * Un membre de Party (set_rsvp_for, il est prévenu) ou une personne SANS compte (« Pote Théo du bar » : juste un nom,
 * personne n'est prévenu). Les invités ne voient que les nombres.
 */
export function AttendanceEditor({ event, rsvps, names, me, onChange, refreshKey }: Props) {
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // ✕ : toujours une question d'abord (retour de l'admin du 27.11 : une ligne partait au premier toucher, sans le vouloir).
  const [removing, setRemoving] = useState<Line | null>(null);
  const options = rsvpOptions(event.allow_maybe);
  const nameOf = (id: string) => (id === me ? 'Toi' : names.get(id) ?? '?');
  // null : base d'avant (pas de présences sans compte) ; l'éditeur reste celui des membres.
  const { data: manual, reload: reloadManual } = useQuery(
    () => fetchManualGuests(event.id).catch((e) => { setError(e instanceof Error ? e.message : String(e)); return [] as ManualGuest[]; }),
    [event.id, refreshKey],
  );
  const withoutAccount = manual !== null && manual !== undefined;

  async function run(key: string, job: () => Promise<unknown>, after: () => void) {
    if (busy) return;
    setBusy(key);
    try {
      await job();
      setError(null);
      after();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(null);
    }
  }

  const applyMember = (member: string, answer: RsvpStatus | null) =>
    run(`m:${member}:${answer}`, () => setRsvpFor(event.id, member, answer), () => { setQuery(''); onChange(); });
  const addWithoutAccount = (name: string) => {
    if (!withoutAccount || !name.trim()) return;
    void run('add', () => addManualGuest(event.id, name, 'yes'), () => { setQuery(''); reloadManual(); onChange(); });
  };
  const applyManual = (id: string, answer: RsvpStatus | null) =>
    run(`g:${id}:${answer}`, () => (answer ? setManualGuest(id, answer) : removeManualGuest(id)), () => { reloadManual(); onChange(); });

  const lines: Line[] = [
    ...rsvps.map((r): Line => ({
      kind: 'member', key: `m:${r.user_id}`, id: r.user_id, name: nameOf(r.user_id), status: r.status,
      extra: `${r.plus_ones ? ` +${r.plus_ones}` : ''}${waitingPlusOnes(r) ? ` (+${waitingPlusOnes(r)} en attente)` : ''}`,
      sub: r.status === 'yes' && r.waitlisted ? 'A un compte · liste d’attente'
        : r.set_by && r.set_by !== r.user_id ? 'A un compte · prévenu' : 'A un compte',
    })),
    ...(manual ?? []).map((g): Line => ({ kind: 'manual', key: `g:${g.id}`, id: g.id, name: g.name, status: g.status, extra: '', sub: 'Sans compte' })),
  ].sort((a, b) => a.name.localeCompare(b.name, 'fr'));

  // Compteurs : têtes comme « Qui vient ? » (accompagnants compris), liste d'attente à part.
  const count = (k: RsvpStatus) =>
    rsvps.filter((r) => r.status === k && !(k === 'yes' && r.waitlisted)).reduce((n, r) => n + 1 + (k === 'yes' ? r.plus_ones : 0), 0)
    + (manual ?? []).filter((g) => g.status === k).length;

  // Une personne ajoutée ici (ou par un autre organisateur) apparaît en douceur ; la liste du départ reste posée.
  const grew = useChangedSinceMount(lines.length);

  const answered = new Set(rsvps.map((r) => r.user_id));
  const typed = query.trim();
  const q = fold(typed);
  const suggestions = q
    ? [...names].filter(([id, name]) => !answered.has(id) && fold(name).includes(q)).slice(0, MAX_SUGGESTIONS)
    : [];
  // Le champ cherche aussi dans la liste (les deux groupes) : retrouver vite quelqu'un, ou un doublon.
  const shown = q ? lines.filter((l) => fold(l.kind === 'member' ? names.get(l.id) ?? l.name : l.name).includes(q)) : lines;
  const members = rsvps.filter((r) => r.user_id !== me).map((r) => names.get(r.user_id)).filter((n): n is string => !!n);
  const twinOf = (name: string) => members.find((m) => sameish(name, m)) ?? null;
  const busyFor = (prefix: string) => options.find((k) => busy === `${prefix}:${k}`) ?? null;

  const renderLine = (l: Line) => {
    const prefix = l.kind === 'member' ? `m:${l.id}` : `g:${l.id}`;
    const set = (k: RsvpStatus | null) => (l.kind === 'member' ? applyMember(l.id, k) : applyManual(l.id, k));
    // Doublon probable : la personne notée sans compte a peut-être répondu elle-même depuis (même prénom, nom proche).
    const twin = l.kind === 'manual' ? twinOf(l.name) : null;
    return (
              <Reveal key={l.key} kind={grew ? 'rise' : null} style={st.person}>
                <View style={s.rowBetween}>
                <View style={[s.row, st.who]}>
                  {l.kind === 'member'
                    ? <Avatar id={l.id} name={names.get(l.id) ?? l.name} size={32} />
                    : <Avatar id={`sans-compte-${l.id}`} name={l.name} size={32} profile={false} />}
                  <View style={st.shrink}>
                    <T weight="semibold" numberOfLines={2}>{l.name}{l.extra}</T>
                    <T muted size={12} numberOfLines={2}>{l.sub}</T>
                  </View>
                </View>
                <View style={[s.row, st.actions]}>
                  <View style={st.choices} accessibilityRole="radiogroup">
                    {options.map((k) => {
                      const on = (busyFor(prefix) ?? l.status) === k;
                      const c = rsvpChoices[k];
                      return (
                        <Pressable key={k} accessibilityRole="button" accessibilityLabel={`${l.name} : ${c.label}`}
                          accessibilityState={{ selected: on, busy: busy === `${prefix}:${k}` }} disabled={!!busy}
                          onPress={() => { if (l.status !== k) set(k); }}
                          style={({ pressed }) => [st.choice, pressTransition,
                            on ? { backgroundColor: c.bg, borderColor: c.bg } : { backgroundColor: `${c.bg}14`, borderColor: `${c.bg}38` },
                            pressed && { transform: [{ scale: 0.94 }] }]}>
                          <T size={13} style={font.bold} color={on ? c.fg : colors.text}>{SHORT[k]}</T>
                        </Pressable>
                      );
                    })}
                  </View>
                  <Pressable accessibilityRole="button" accessibilityLabel={`Retirer ${l.name}`} disabled={!!busy} hitSlop={6}
                    onPress={() => setRemoving(l)} style={({ pressed }) => [st.remove, pressed && { opacity: 0.6 }]}>
                    <T size={15} muted>✕</T>
                  </Pressable>
                </View>
                </View>
                {twin ? (
                  <View style={st.twin} testID="presences-twin">
                    <T size={13} color={colors.coralSoft}>{`Peut-être la même personne que ${twin} ?`}</T>
                    <ConfirmButton small label="Retirer cette ligne" confirmLabel="Retirer" onConfirm={() => applyManual(l.id, null)} />
                  </View>
                ) : null}
              </Reveal>
    );
  };

  return (
    <Section title="Présences">
      <View style={st.counters}>
        {(['yes', 'maybe', 'no'] as const).filter((k) => k !== 'maybe' || event.allow_maybe || count('maybe') > 0).map((k) => (
          <View key={k} style={[st.counter, { backgroundColor: `${rsvpChoices[k].bg}14`, borderColor: `${rsvpChoices[k].bg}38` }]}
            accessible accessibilityLabel={`${k === 'yes' ? 'Présents' : k === 'maybe' ? 'Peut-être' : 'Absents'} : ${count(k)}`}>
            <T size={22} weight="bold" color={rsvpChoices[k].bg}>{count(k)}</T>
            <T size={12} muted>{k === 'yes' ? 'Présents' : k === 'maybe' ? 'Peut-être' : 'Absents'}</T>
          </View>
        ))}
      </View>

      <Input
        accessibilityLabel="Ajouter quelqu’un"
        placeholder={withoutAccount ? 'Ajouter ou chercher (nom, surnom…)' : 'Ajouter quelqu’un (prénom ou surnom)'}
        value={query}
        onChangeText={setQuery}
        maxLength={60}
        returnKeyType="done"
        onSubmitEditing={() => addWithoutAccount(typed)}
      />
      {q ? (
        <Rows>
          {suggestions.map(([id, name]) => (
            <Reveal key={id} kind="drop" style={[s.rowBetween, st.line]}>
              <View style={[s.row, st.who]}>
                <Avatar id={id} name={name} size={32} />
                <View style={st.shrink}>
                  <T weight="semibold" numberOfLines={1}>{name}</T>
                  <T muted size={12}>A un compte · sera prévenu</T>
                </View>
              </View>
              <Button small label="Noter présent" loading={busy === `m:${id}:yes`} disabled={!!busy && busy !== `m:${id}:yes`} onPress={() => applyMember(id, 'yes')} />
            </Reveal>
          ))}
          {withoutAccount ? (
            <Pressable accessibilityRole="button" accessibilityLabel={`Ajouter « ${typed} » sans compte, Présent`} disabled={!!busy}
              onPress={() => addWithoutAccount(typed)} style={({ pressed }) => [s.row, st.line, st.who, pressTransition, pressed && { opacity: 0.7 }]}>
              <View style={[st.plus]}><T size={18} weight="bold" color={colors.accentSoft}>+</T></View>
              <View style={st.shrink}>
                <T weight="semibold" numberOfLines={1}>Ajouter « {typed} »</T>
                <T muted size={12}>{busy === 'add' ? 'Ajout…' : 'Sans compte, Présent'}</T>
              </View>
            </Pressable>
          ) : suggestions.length ? null : <T muted size={13}>Personne d’autre ne porte ce nom.</T>}
        </Rows>
      ) : null}

      {lines.length ? (
        <>
          {([['member', 'Avec un compte'], ['manual', 'Sans compte']] as const).map(([kind, title]) => {
            const group = shown.filter((l) => l.kind === kind);
            const all = lines.filter((l) => l.kind === kind).length;
            if (!all) return null;
            return (
              <View key={kind} style={st.group} testID={`presences-${kind}`}>
                <T size={12} weight="bold" color={kind === 'member' ? colors.lavender : colors.coral}>
                  {`${title.toUpperCase()} · ${q ? `${group.length} sur ${all}` : all}`}
                </T>
                {group.length ? <Rows>{group.map(renderLine)}</Rows> : <T muted size={13}>Personne de ce nom ici.</T>}
              </View>
            );
          })}
        </>
      ) : <T muted size={13}>Personne n’a encore répondu : écris un nom pour l’ajouter.</T>}
      <ErrorText error={error} />
      <Modal visible={!!removing} transparent animationType="fade" onRequestClose={() => setRemoving(null)}>
        <View style={st.confirmOverlay}>
          <SheetBackdrop onPress={() => setRemoving(null)} />
          <View style={st.confirmCard} accessibilityViewIsModal accessibilityRole="alert">
            <T weight="bold" size={18}>{removing ? (removing.kind === 'member' && removing.id === me ? 'Te retirer des présences ?' : `Retirer ${removing.name} des présences ?`) : ''}</T>
            <T size={14} color={colors.textSoft}>
              {removing?.kind === 'member' ? (removing.id === me ? 'Ta réponse est effacée.' : 'Sa réponse est effacée et la personne est prévenue.') : 'Cette ligne est effacée.'}
            </T>
            <Button label="Retirer" variant="dangerSolid" loading={!!removing && busy === `${removing.kind === 'member' ? 'm' : 'g'}:${removing.id}:null`}
              disabled={!!busy} onPress={async () => {
                if (!removing) return;
                await (removing.kind === 'member' ? applyMember(removing.id, null) : applyManual(removing.id, null));
                setRemoving(null);
              }} />
            <Button label="Annuler" variant="secondary" onPress={() => setRemoving(null)} />
          </View>
        </View>
      </Modal>
      {withoutAccount ? (
        <T muted size={12}>Une personne sans compte n’est pas prévenue et ne voit rien. Les invités voient seulement les nombres.</T>
      ) : null}
    </Section>
  );
}

const st = StyleSheet.create({
  counters: { flexDirection: 'row', gap: 8 },
  counter: { flex: 1, minWidth: 0, alignItems: 'center', paddingVertical: 10, borderRadius: radius.md, borderWidth: 1, gap: 2 },
  line: { paddingVertical: 8 },
  who: { flexShrink: 1, gap: 8 },
  shrink: { flexShrink: 1 },
  person: { gap: 8, paddingVertical: 8 },
  group: { gap: 6 },
  twin: { gap: 8, padding: 10, borderRadius: radius.md, backgroundColor: colors.coralDim },
  actions: { gap: 6, flexShrink: 0 },
  choices: { flexDirection: 'row', gap: 4 },
  choice: { minWidth: 36, minHeight: 36, paddingHorizontal: 6, alignItems: 'center', justifyContent: 'center', borderRadius: radius.sm, borderWidth: 1 },
  remove: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  confirmOverlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.85)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  confirmCard: { width: '100%', maxWidth: 380, gap: 12, padding: 20, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  plus: { width: 32, height: 32, borderRadius: 16, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accentDim },
});
