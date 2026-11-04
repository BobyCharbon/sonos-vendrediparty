import { useState } from 'react';
import { router } from 'expo-router';
import { Pressable, StyleSheet, View } from 'react-native';

import { formatShort, parseLocalDateTime } from '@/lib/format';
import { enter, pressTransition, useChangedSinceMount } from '@/lib/motion';
import { refreshPending } from '@/lib/pending';
import { rsvpChoices, rsvpClosed, rsvpOptions, saveRsvp } from '@/lib/rsvp';
import { supabase } from '@/lib/supabase';
import { colors, font, radius } from '@/lib/theme';
import type { BringItem, DateOption, DateVote, DateVoteRow, EventRow, Poll, PollOption, Rsvp, RsvpStatus } from '@/lib/types';
import { UNLIMITED_PLUS_ONES } from '@/lib/types';

import { SharedBringRow } from './BringShared';
import { DateTimeField } from './DateTimeField';
import { LinkedText } from './LinkedText';
import { RsvpButtons } from './RsvpButtons';
import { Avatar, Button, Chip, ErrorText, Input, Meter, Reveal, s, Section, T } from './ui';

type Names = Map<string, string>;

const voteLabel: Record<DateVote, string> = { yes: 'Oui', if_needed: 'Si besoin', no: 'Non' };
const voteColor: Record<DateVote, string> = { yes: colors.accent, if_needed: colors.lavender, no: colors.coral };

/**
 * Votes affichés tout de suite : le choix touché remplace la valeur de la base jusqu’à ce que la base rechargée
 * dise la même chose (ou qu’une erreur l’annule). Clé : l’option votée.
 */
function useInstantChoices<V>(server: (id: string) => V) {
  const [local, setLocal] = useState<Record<string, V>>({});
  const settled = Object.keys(local).filter((id) => Object.is(local[id], server(id)));
  if (settled.length) setLocal((prev) => Object.fromEntries(Object.entries(prev).filter(([id]) => !settled.includes(id))));
  return {
    value: (id: string) => (id in local ? local[id] : server(id)),
    set: (changes: Record<string, V>) => setLocal((prev) => ({ ...prev, ...changes })),
    forget: (ids: string[]) => setLocal((prev) => Object.fromEntries(Object.entries(prev).filter(([id]) => !ids.includes(id)))),
  };
}

async function act(p: PromiseLike<{ error: { message: string } | null }>, onDone: () => void, onError: (m: string) => void) {
  try {
    const { error } = await p;
    if (error) throw new Error(error.message);
    onError('');
    onDone();
    return true;
  } catch (e) {
    onError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    return false;
  }
}

// --------------------------------------------------------------------------
// Présent / Peut-être / Absent
// --------------------------------------------------------------------------
const confirmations: Record<RsvpStatus, string> = {
  yes: 'C’est noté, tu viens !',
  maybe: 'Noté en peut-être. Pense à confirmer.',
  no: 'Dommage ! Tu es noté absent.',
};

export function RsvpCard({
  event,
  me,
  rsvps,
  onChange,
}: {
  event: EventRow;
  me: string;
  rsvps: Rsvp[];
  onChange: () => void;
}) {
  const mine = rsvps.find((r) => r.user_id === me);
  const [note, setNote] = useState(mine?.note ?? '');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  // Choix enregistré, affiché jusqu’à ce que la fiche rechargée le confirme (pas de retour en arrière d’un instant).
  const [picked, setPicked] = useState<RsvpStatus | null>(null);
  if (picked && mine?.status === picked) setPicked(null);
  const closed = rsvpClosed(event);
  const heads = rsvps.filter((r) => r.status === 'yes' && !r.waitlisted).reduce((n, r) => n + 1 + r.plus_ones, 0);
  const full = !!event.max_participants && heads >= event.max_participants && !(mine?.status === 'yes' && !mine.waitlisted);
  // Retour immédiat : le choix touché s’affiche (couleur, phrase) pendant l’enregistrement.
  const saving = (['yes', 'maybe', 'no'] as const).find((k) => k === busy) ?? null;
  const choosing = saving ?? picked;
  const shown = choosing ?? mine?.status ?? null;
  const plusChanged = useChangedSinceMount(mine?.plus_ones ?? 0);

  async function upsert(key: string, patch: Partial<Rsvp>) {
    setBusy(key);
    try {
      await saveRsvp(event.id, me, mine, patch);
      if (patch.status) setPicked(patch.status);
      setError(null);
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(null);
    }
  }

  const subtitle = closed
    ? mine ? 'Les réponses sont closes.' : 'Les réponses sont closes : tu n’as pas répondu.'
    : choosing
      ? confirmations[choosing]
    : mine
      ? mine.waitlisted ? 'Complet : tu es sur liste d’attente, on te prévient si une place se libère.' : confirmations[mine.status]
      : event.rsvp_deadline
        ? `Réponds avant le ${formatShort(event.rsvp_deadline)} pour que l’organisateur puisse s’organiser.`
        : 'Un clic suffit pour prévenir le groupe.';

  return (
    <Section
      title={mine ? 'Ta réponse' : 'Tu viens ?'}
      style={!mine && !closed ? { borderColor: 'rgba(255,79,154,0.55)', borderWidth: 1.5 } : undefined}
      right={!mine && !closed ? <View style={st.pill}><T size={12} weight="bold" color={colors.accent}>À répondre</T></View> : null}
    >
      <T key={subtitle} size={14} style={enter('fade')} color={shown && !(mine?.waitlisted && !choosing) ? rsvpChoices[shown].bg : colors.textSoft}>{subtitle}</T>
      {mine?.set_by && mine.set_by !== me ? (
        <T muted size={13}>C’est l’organisateur qui a noté ta réponse : tu peux la changer ici.</T>
      ) : null}
      {full && !closed && event.waitlist_enabled && mine?.status !== 'yes' ? (
        <T size={13} color={colors.lavender}>L’événement est complet : en répondant Présent, tu passes en liste d’attente.</T>
      ) : null}
      <RsvpButtons
        options={rsvpOptions(event.allow_maybe)}
        selected={picked ?? mine?.status ?? null}
        busy={saving}
        disabled={closed}
        onSelect={(k) => upsert(k, { status: k })}
      />
      {event.allow_plus_ones && mine?.status === 'yes' && event.max_plus_ones > 0 ? (
        <Reveal kind="drop" style={[s.rowBetween, st.subRow]}>
          <View style={{ flex: 1 }}>
            <T>Accompagnants</T>
            <T muted size={12}>{event.max_plus_ones >= UNLIMITED_PLUS_ONES ? '∞ Illimité' : `Jusqu’à ${event.max_plus_ones} personne${event.max_plus_ones > 1 ? 's' : ''}`}</T>
          </View>
          <View style={s.row}>
            <Button small variant="secondary" label="−" disabled={!mine.plus_ones || closed} onPress={() => upsert('minus', { plus_ones: Math.max(0, mine.plus_ones - 1) })} />
            <T key={mine.plus_ones} weight="bold" style={[{ minWidth: 28, textAlign: 'center' }, plusChanged ? enter('pop') : null]}>+{mine.plus_ones}</T>
            <Button small variant="secondary" label="+" disabled={mine.plus_ones >= event.max_plus_ones || closed} onPress={() => upsert('plus', { plus_ones: Math.min(event.max_plus_ones, mine.plus_ones + 1) })} />
          </View>
        </Reveal>
      ) : null}
      {mine?.status === 'yes' && !(event.allow_plus_ones && event.max_plus_ones > 0) ? (
        <Reveal kind="drop" style={[st.note, { borderLeftColor: colors.lavender }]}>
          <T size={13} color={colors.textSoft}>Pas d’accompagnant pour cet événement : l’organisateur a réservé les places aux membres du groupe.</T>
        </Reveal>
      ) : null}
      {mine && !closed ? (
        <Reveal kind="drop" style={s.row}>
          <Input
            accessibilityLabel="Un petit mot perso pour l’organisateur"
            placeholder="Un petit mot perso pour l’organisateur (facultatif)"
            value={note}
            onChangeText={setNote}
            onSubmitEditing={() => note !== (mine.note ?? '') && upsert('note', { note: note.trim() || null })}
            style={{ flex: 1 }}
            maxLength={140}
          />
          {note !== (mine.note ?? '') ? <Reveal kind="pop"><Button small label="Envoyer" loading={busy === 'note'} onPress={() => upsert('note', { note: note.trim() || null })} /></Reveal> : null}
        </Reveal>
      ) : null}
      <ErrorText error={error} />
    </Section>
  );
}

/** Participant : photo et prénom ; toucher l'un ou l'autre ouvre sa fiche profil. En orange : arrivé par le lien
 * d'invitation (visible des organisateurs). */
function PersonChip({ id, name, extra, viaLink = false, fresh = false }: { id: string; name: string; extra?: string; viaLink?: boolean; fresh?: boolean }) {
  // Fixé à l’apparition : les pastilles déjà là ne rebondissent pas quand une autre arrive.
  const [arrive] = useState(() => (fresh ? enter('pop') : undefined));
  return (
    <Pressable style={({ pressed }) => [st.person, arrive, pressTransition, viaLink && st.viaLink, pressed && { opacity: 0.7 }]} accessibilityRole="button"
      accessibilityLabel={`Profil de ${name}${viaLink ? ', invité par lien' : ''}`} onPress={() => router.push(`/member/${id}`)}>
      <Avatar id={id} name={name} size={24} profile={false} />
      <T size={13} weight="semibold" color={viaLink ? colors.coral : undefined}>
        {name}{extra ? <T size={13} muted> {extra}</T> : null}{viaLink ? <T size={11} color={colors.coral}> · lien</T> : null}
      </T>
    </Pressable>
  );
}

export function ParticipantsSection({
  event,
  me,
  rsvps,
  names,
  viaLink = new Set<string>(),
}: {
  event: EventRow;
  me: string;
  rsvps: Rsvp[];
  names: Names;
  viaLink?: Set<string>;
}) {
  const nameOf = (id: string) => (id === me ? 'Toi' : names.get(id) ?? '?');
  const group = (st: RsvpStatus, waitlisted = false) => rsvps.filter((r) => r.status === st && r.waitlisted === waitlisted);
  const yes = group('yes');
  const maybe = group('maybe');
  const no = group('no');
  const waiting = group('yes', true);
  const heads = yes.reduce((n, r) => n + 1 + r.plus_ones, 0);
  const left = event.max_participants ? event.max_participants - heads : null;
  const notes = rsvps.filter((r) => r.note);
  // Une pastille qui arrive ou change de groupe « se pose » ; à l’ouverture, la liste s’affiche telle quelle.
  const moved = useChangedSinceMount(rsvps.map((r) => `${r.user_id}:${r.status}:${r.waitlisted}`).sort().join(','));
  if (!event.show_participants && rsvps.length <= 1) return null;

  const block = (label: string, list: Rsvp[], color: string, count = list.length) =>
    list.length ? (
      <View style={{ gap: 8 }} accessibilityLabel={`${label} : ${list.map((r) => nameOf(r.user_id)).join(', ')}`}>
        <T size={12} weight="bold" color={color}>{label.toUpperCase()} · {count}</T>
        <View style={s.wrap}>
          {list.map((r) => <PersonChip key={r.user_id} id={r.user_id} name={nameOf(r.user_id)} extra={r.plus_ones ? `+${r.plus_ones}` : undefined} viaLink={viaLink.has(r.user_id)} fresh={moved} />)}
        </View>
      </View>
    ) : null;

  return (
    <Section
      title="Qui vient ?"
      right={event.max_participants ? (
        <T muted size={13}>{left! > 0 ? `${left} place${left! > 1 ? 's' : ''} libre${left! > 1 ? 's' : ''}` : 'Complet'}</T>
      ) : <T muted size={13}>{heads} personne{heads > 1 ? 's' : ''} · ∞</T>}
    >
      {event.max_participants ? (
        <View accessibilityLabel={`${heads} sur ${event.max_participants} places prises`}>
          <Meter parts={[{ fraction: heads / event.max_participants, color: colors.accent }]} />
        </View>
      ) : null}
      {rsvps.length === 0 ? <T muted size={14}>Personne n’a encore répondu. Sois le premier !</T> : null}
      {block('Présents', yes, colors.mint, heads)}
      {block('Peut-être', maybe, colors.coral)}
      {block('Liste d’attente', waiting, colors.lavender)}
      {no.length ? <T muted size={13}>Absents : {no.map((r) => nameOf(r.user_id)).join(', ')}</T> : null}
      {notes.length ? (
        <View style={{ gap: 6 }}>
          {notes.map((r) => (
            <View key={r.user_id} style={st.note}>
              <LinkedText size={13} color={colors.textSoft} prefix={<T size={13} weight="bold">{nameOf(r.user_id)} · </T>} text={r.note} />
            </View>
          ))}
        </View>
      ) : null}
    </Section>
  );
}

// --------------------------------------------------------------------------
// Sondage de dates
// --------------------------------------------------------------------------
export function DatePollSection({
  event,
  me,
  canManage,
  options,
  votes,
  names,
  onChange,
}: {
  event: EventRow;
  me: string;
  canManage: boolean;
  options: DateOption[];
  votes: DateVoteRow[];
  names: Names;
  onChange: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [proposal, setProposal] = useState('');
  const closed = event.status !== 'published' || (!!event.poll_deadline && new Date(event.poll_deadline) < new Date());
  const voters = new Set(votes.map((v) => v.user_id));

  const scored = options
    .map((o) => {
      const vs = votes.filter((v) => v.option_id === o.id);
      const count = (k: DateVote) => vs.filter((v) => v.vote === k).length;
      return { o, vs, yes: count('yes'), ifNeeded: count('if_needed'), no: count('no') };
    })
    .sort((a, b) => a.o.starts_at.localeCompare(b.o.starts_at));
  const best = [...scored].sort((a, b) => b.yes - a.yes || b.ifNeeded - a.ifNeeded)[0];

  const myVote = useInstantChoices<DateVote | null>((id) => votes.find((x) => x.option_id === id && x.user_id === me)?.vote ?? null);

  function vote(optionId: string, v: DateVote) {
    const next = myVote.value(optionId) === v ? null : v;
    myVote.set({ [optionId]: next });
    act(
      next === null
        ? supabase.from('date_votes').delete().eq('option_id', optionId).eq('user_id', me)
        : supabase.from('date_votes').upsert({ option_id: optionId, user_id: me, vote: next }),
      () => { refreshPending(); onChange(); },
      (message) => { setError(message); if (message) myVote.forget([optionId]); },
    );
  }

  async function propose() {
    const iso = parseLocalDateTime(proposal);
    if (!iso) return setError('Format attendu JJ.MM.AAAA HH:MM');
    if (await act(supabase.from('date_options').insert({ event_id: event.id, starts_at: iso, proposed_by: me }), onChange, setError)) setProposal('');
  }

  return (
    <Section
      title="Quelle date ?"
      style={!closed && !voters.has(me) && options.length ? { borderColor: colors.accent, borderWidth: 2, backgroundColor: '#22152A' } : undefined}
      right={!closed && !voters.has(me) && options.length ? <View style={st.pill}><T size={12} weight="bold" color={colors.accent}>À répondre</T></View> : <T muted size={12}>{voters.size} votant{voters.size > 1 ? 's' : ''}</T>}
    >
      {!closed && !voters.has(me) && options.length ? <T size={14} color={colors.textSoft}>Indique pour chaque date si tu es dispo : l’organisateur fixera celle qui arrange le plus de monde.</T> : null}
      <T muted size={13}>
        {event.status !== 'published' ? 'Les votes seront disponibles lorsque l’événement sera publié.' : closed ? 'Le vote est terminé.' : event.poll_deadline ? `Vote jusqu’au ${formatShort(event.poll_deadline)}` : 'Pour chaque date : Oui, Si besoin ou Non.'}
      </T>
      {scored.map(({ o, vs, yes, ifNeeded, no }) => {
        const mine = myVote.value(o.id);
        const total = Math.max(1, yes + ifNeeded + no);
        const lead = best && best.o.id === o.id && yes > 0;
        return (
          <View
            key={o.id}
            style={{ gap: 8, padding: 12, borderRadius: radius.md, backgroundColor: colors.bg, borderWidth: 1, borderColor: lead ? colors.accent : colors.line }}
          >
            <View style={s.rowBetween}>
              <View style={{ flex: 1 }}>
                <T weight="bold">{formatShort(o.starts_at)}</T>
                <T muted size={12}>{yes} oui · {ifNeeded} si besoin · {no} non</T>
              </View>
              {lead ? <View style={[st.pill, enter('pop')]}><T size={11} weight="bold" color={colors.onAccent}>EN TÊTE</T></View> : null}
            </View>
            <Meter parts={[{ fraction: yes / total, color: colors.accent }, { fraction: ifNeeded / total, color: colors.lavender }]} />
            {!closed ? (
              <View style={s.row}>
                {(['yes', 'if_needed', 'no'] as DateVote[]).map((k) => (
                  <Pressable
                    key={k}
                    accessibilityRole="button"
                    accessibilityState={{ selected: mine === k }}
                    onPress={() => vote(o.id, k)}
                    style={({ pressed }) => [{
                      flex: 1, height: 44, borderRadius: radius.sm, alignItems: 'center', justifyContent: 'center', borderWidth: 1,
                      borderColor: mine === k ? voteColor[k] : colors.lineStrong, backgroundColor: mine === k ? voteColor[k] : 'transparent',
                    }, pressTransition, pressed && st.pressed]}
                  >
                    <T size={13} style={{ ...font.bold }} color={mine === k ? colors.onAccent : colors.textSoft}>{voteLabel[k]}</T>
                  </Pressable>
                ))}
              </View>
            ) : null}
            {canManage && vs.length ? (
              <T muted size={12}>{vs.map((v) => `${names.get(v.user_id) ?? '?'} (${voteLabel[v.vote]})`).join(', ')}</T>
            ) : null}
            {canManage ? (
              <Button small variant={lead ? 'primary' : 'secondary'} label="Fixer cette date" onPress={() => act(supabase.rpc('fix_event_date', { e: event.id, opt: o.id }), onChange, setError)} />
            ) : null}
          </View>
        );
      })}
      {!closed && event.members_can_propose_dates ? (
        <View style={{ gap: 8 }}>
          <DateTimeField label="Proposer une date" value={proposal} onChangeText={setProposal} />
          <Button small label="Ajouter" onPress={propose} disabled={!proposal.trim()} />
        </View>
      ) : null}
      {canManage ? (
        <T muted size={12}>
          Fixer une date : les Oui deviennent Présent, les Si besoin deviennent Peut-être, et tout le monde est prévenu.
        </T>
      ) : null}
      <ErrorText error={error} />
    </Section>
  );
}

// --------------------------------------------------------------------------
// Mini-sondage
// --------------------------------------------------------------------------
export function PollSection({
  poll,
  options,
  results,
  myVotes,
  voters,
  me,
  canManage,
  canParticipate,
  onChange,
}: {
  poll: Poll;
  options: PollOption[];
  results: Map<string, number> | null;
  myVotes: Set<string>;
  voters: Map<string, string[]>;
  me: string;
  canManage: boolean;
  canParticipate: boolean;
  onChange: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [newOption, setNewOption] = useState('');
  const closed = !!poll.closes_at && new Date(poll.closes_at) < new Date();
  const total = results ? Math.max(1, [...results.values()].reduce((a, b) => a + b, 0)) : 1;

  const picked = useInstantChoices<boolean>((id) => myVotes.has(id));

  function toggle(optionId: string) {
    const on = !picked.value(optionId);
    // Choix unique : la base retire l’autre vote (guard_poll_vote) ; l’écran le fait tout de suite aussi.
    const others = on && !poll.multiple_choice ? options.filter((o) => o.id !== optionId && picked.value(o.id)).map((o) => o.id) : [];
    picked.set({ [optionId]: on, ...Object.fromEntries(others.map((id) => [id, false])) });
    act(
      on
        ? supabase.from('poll_votes').insert({ poll_id: poll.id, option_id: optionId, user_id: me })
        : supabase.from('poll_votes').delete().eq('option_id', optionId).eq('user_id', me),
      onChange,
      (message) => { setError(message); if (message) picked.forget([optionId, ...others]); },
    );
  }

  const flags = [poll.multiple_choice ? 'Choix multiple' : '1 choix', poll.anonymous ? 'anonyme' : null].filter(Boolean).join(' · ');

  return (
    <Section title={poll.question} right={<T muted size={12}>{flags}</T>}>
      {options.sort((a, b) => a.sort - b.sort).map((o) => {
        const n = results?.get(o.id) ?? 0;
        const on = picked.value(o.id);
        return (
          <Pressable
            key={o.id}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
            disabled={closed || !canParticipate}
            onPress={() => toggle(o.id)}
            style={({ pressed }) => [{ height: 48, borderRadius: 12, borderWidth: 1, borderColor: on ? colors.accent : colors.lineStrong, backgroundColor: colors.bg, overflow: 'hidden', justifyContent: 'center' }, pressTransition, pressed && st.pressed]}
          >
            {results ? (
              <Meter parts={[{ fraction: n / total, color: on ? colors.accentDim : colors.surface2 }]} track="transparent" height={null} style={st.pollFill} />
            ) : null}
            <View style={[s.rowBetween, { paddingHorizontal: 14 }]}>
              <View style={[s.row, { flex: 1 }]}>
                <View style={[st.radio, { borderColor: on ? colors.accent : colors.muted }, !poll.multiple_choice ? null : { borderRadius: 4 }]}>
                  {on ? <View style={[st.radioDot, enter('pop'), poll.multiple_choice && { borderRadius: 1 }]} /> : null}
                </View>
                <T weight="semibold" size={14} style={{ flex: 1 }} numberOfLines={1}>{o.label}</T>
              </View>
              {results ? <T muted size={13}>{n}</T> : null}
            </View>
          </Pressable>
        );
      })}
      {!results ? <T muted size={12}>Les résultats s’affichent après ton vote.</T> : null}
      {!poll.anonymous && results
        ? options.filter((o) => voters.get(o.id)?.length).map((o) => (
            <T key={o.id} muted size={12}>{o.label} : {voters.get(o.id)!.join(', ')}</T>
          ))
        : null}
      {!canParticipate ? <T muted size={12}>Les votes seront disponibles lorsque l’événement sera publié.</T> : closed ? <T muted size={12}>Ce sondage est clos.</T> : null}
      {!closed && canParticipate && (poll.members_can_add_options || canManage) ? (
        <View style={s.row}>
          <Input placeholder="Proposer une option" value={newOption} onChangeText={setNewOption} style={{ flex: 1 }} />
          <Button
            small
            label="Ajouter"
            disabled={!newOption.trim()}
            onPress={async () => {
              if (await act(supabase.from('poll_options').insert({ poll_id: poll.id, label: newOption.trim(), created_by: me, sort: options.length }), onChange, setError)) setNewOption('');
            }}
          />
        </View>
      ) : null}
      {canManage ? (
        <View style={s.wrap}>
          <Chip
            label={closed ? 'Rouvrir' : 'Clore le sondage'}
            onPress={() => act(supabase.from('polls').update({ closes_at: closed ? null : new Date().toISOString() }).eq('id', poll.id), onChange, setError)}
          />
        </View>
      ) : null}
      <ErrorText error={error} />
    </Section>
  );
}

// --------------------------------------------------------------------------
// Qui amène quoi
// --------------------------------------------------------------------------
export function BringSection({
  items,
  me,
  eventId,
  names,
  canParticipate,
  onChange,
}: {
  items: BringItem[];
  me: string;
  eventId: string;
  names: Names;
  canParticipate: boolean;
  onChange: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  const [label, setLabel] = useState('');
  const grew = useChangedSinceMount(items.length);
  const claimsChanged = useChangedSinceMount(items.map((it) => it.claimed_by ?? '').join());
  if (!items.length && !canParticipate) return null;
  const add = async () => {
    const text = label.trim();
    if (!text) return;
    const sort = items.reduce((max, it) => Math.max(max, it.sort), 0) + 1;
    if (await act(supabase.from('bring_items').insert({ event_id: eventId, label: text, sort, added_by: me, claimed_by: me }), onChange, setError)) setLabel('');
  };
  return (
    <Section title="Qui amène quoi">
      {[...items].sort((a, b) => a.sort - b.sort).map((it) => (
        <Reveal key={it.id} kind={grew ? 'rise' : null}>
          {it.quantity ? (
            <SharedBringRow item={it} me={me} names={names} canParticipate={canParticipate} onChange={onChange} onError={setError} />
          ) : (
          <View style={s.rowBetween}>
            <LinkedText style={{ flex: 1 }} text={it.label} />
            {/* Qui le prend change (moi, un autre, personne) : la nouvelle action se pose à sa place. */}
            <Reveal key={`${it.claimed_by ?? 'libre'}`} kind={grew || claimsChanged ? 'pop' : null}>
            {it.added_by === me ? (
              <Button small variant="secondary" label="Retirer" onPress={() => act(supabase.from('bring_items').delete().eq('id', it.id), onChange, setError)} />
            ) : it.claimed_by === me ? (
              <Button small variant="secondary" label="Je ne prends plus" onPress={() => act(supabase.from('bring_items').update({ claimed_by: null }).eq('id', it.id), onChange, setError)} />
            ) : it.claimed_by ? (
              <T muted>{names.get(it.claimed_by) ?? '?'}</T>
            ) : canParticipate ? (
              <Button small label="Je prends" onPress={() => act(supabase.from('bring_items').update({ claimed_by: me }).eq('id', it.id), onChange, setError)} />
            ) : (
              <T muted>Libre</T>
            )}
            </Reveal>
          </View>
          )}
          {it.added_by ? null : <T style={{ color: colors.coral, fontSize: 12 }}>Demandé par l’organisateur</T>}
        </Reveal>
      ))}
      {canParticipate ? (
        <View style={s.rowBetween}>
          <Input placeholder="Ce que j’amène" value={label} onChangeText={setLabel} maxLength={100} style={{ flex: 1 }} />
          <Button small label="Ajouter" onPress={add} />
        </View>
      ) : null}
      <ErrorText error={error} />
    </Section>
  );
}

const st = StyleSheet.create({
  pill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: 999, backgroundColor: 'rgba(255,79,154,0.16)' },
  subRow: { paddingTop: 4 },
  person: { flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 3, paddingRight: 10, paddingVertical: 3, borderRadius: 999, backgroundColor: colors.surface2 },
  viaLink: { borderWidth: 1, borderColor: colors.coral },
  pollFill: { position: 'absolute', left: 0, top: 0, bottom: 0, right: 0, borderRadius: 0 },
  pressed: { transform: [{ scale: 0.98 }] },
  note: { padding: 10, borderRadius: radius.sm, backgroundColor: colors.bg, borderLeftWidth: 3, borderLeftColor: colors.lineStrong },
  radio: { width: 18, height: 18, borderRadius: 9, borderWidth: 2, alignItems: 'center', justifyContent: 'center' },
  radioDot: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.accent },
});
