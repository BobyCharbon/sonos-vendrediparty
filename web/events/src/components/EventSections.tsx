import { useState } from 'react';
import { Pressable, View } from 'react-native';

import { formatShort, parseLocalDateTime } from '@/lib/format';
import { supabase } from '@/lib/supabase';
import { colors, fonts, radius, rsvpColors } from '@/lib/theme';
import type { BringItem, DateOption, DateVote, DateVoteRow, EventRow, Poll, PollOption, Rsvp, RsvpStatus } from '@/lib/types';

import { DateTimeField } from './DateTimeField';
import { Button, Chip, ErrorText, Input, s, Section, T } from './ui';

type Names = Map<string, string>;

const voteLabel: Record<DateVote, string> = { yes: 'Oui', if_needed: 'Si besoin', no: 'Non' };
const voteColor: Record<DateVote, string> = { yes: colors.accent, if_needed: colors.lavender, no: colors.coral };

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
export function RsvpSection({
  event,
  me,
  rsvps,
  names,
  onChange,
}: {
  event: EventRow;
  me: string;
  rsvps: Rsvp[];
  names: Names;
  onChange: () => void;
}) {
  const mine = rsvps.find((r) => r.user_id === me);
  const [note, setNote] = useState(mine?.note ?? '');
  const [error, setError] = useState<string | null>(null);
  const closed = !!event.rsvp_deadline && new Date(event.rsvp_deadline) < new Date();

  const upsert = (patch: Partial<Rsvp>) =>
    act(
      supabase.from('rsvps').upsert({
        event_id: event.id,
        user_id: me,
        status: mine?.status ?? 'yes',
        plus_ones: mine?.plus_ones ?? 0,
        note: mine?.note ?? null,
        ...patch,
      }),
      onChange,
      setError,
    );

  const options: { key: RsvpStatus; label: string }[] = [
    { key: 'yes', label: 'Présent' },
    ...(event.allow_maybe ? [{ key: 'maybe' as const, label: 'Peut-être' }] : []),
    { key: 'no', label: 'Absent' },
  ];

  const by = (st: RsvpStatus, waitlisted = false) =>
    rsvps.filter((r) => r.status === st && r.waitlisted === waitlisted).map((r) => (names.get(r.user_id) ?? '?') + (r.plus_ones ? ` +${r.plus_ones}` : ''));
  const yes = by('yes');
  const heads = rsvps.filter((r) => r.status === 'yes' && !r.waitlisted).reduce((n, r) => n + 1 + r.plus_ones, 0);

  return (
    <>
      <Section title="Tu viens ?" right={closed ? <T muted size={12}>Réponses closes</T> : null}>
        <View style={s.row}>
          {options.map((o) => {
            const on = mine?.status === o.key;
            return (
              <Pressable
                key={o.key}
                accessibilityRole="button"
                accessibilityState={{ selected: on }}
                disabled={closed}
                onPress={() => upsert({ status: o.key })}
                style={{
                  flex: 1, height: 52, borderRadius: radius.md, borderWidth: 2, alignItems: 'center', justifyContent: 'center',
                  borderColor: on ? rsvpColors[o.key] : colors.lineStrong, backgroundColor: on ? rsvpColors[o.key] : 'transparent',
                }}
              >
                <T style={{ fontFamily: fonts.bold }} color={on ? colors.onAccent : colors.text}>{o.label}</T>
              </Pressable>
            );
          })}
        </View>
        {mine?.waitlisted ? <T color={colors.lavender} size={13}>Complet : tu es sur liste d’attente, on te prévient si une place se libère.</T> : null}
        {event.allow_plus_ones && mine?.status === 'yes' ? (
          <View style={s.rowBetween}>
            <T>Accompagnants</T>
            <View style={s.row}>
              <Button small variant="secondary" label="−" onPress={() => upsert({ plus_ones: Math.max(0, (mine.plus_ones ?? 0) - 1) })} />
              <T weight="bold">+{mine.plus_ones}</T>
              <Button small variant="secondary" label="+" onPress={() => upsert({ plus_ones: Math.min(event.max_plus_ones, (mine.plus_ones ?? 0) + 1) })} />
            </View>
          </View>
        ) : null}
        {mine ? (
          <View style={s.row}>
            <Input placeholder="Petit mot (optionnel)" value={note} onChangeText={setNote} style={{ flex: 1 }} maxLength={140} />
            {note !== (mine.note ?? '') ? <Button small label="OK" onPress={() => upsert({ note: note.trim() || null })} /> : null}
          </View>
        ) : null}
        <ErrorText error={error} />
      </Section>

      {event.show_participants || rsvps.length > 1 ? (
        <Section
          title="Participants"
          right={event.max_participants ? <T muted size={13}>{heads}/{event.max_participants} places</T> : null}
        >
          <View style={{ flexDirection: 'row', gap: 8 }}>
            {[
              { n: yes.length, label: 'Présents', fg: colors.accent, bg: colors.accentDim },
              { n: by('maybe').length, label: 'Peut-être', fg: colors.lavender, bg: colors.lavenderDim },
              { n: by('no').length, label: 'Absents', fg: colors.coralSoft, bg: colors.coralDim },
            ].map((c) => (
              <View key={c.label} style={{ flex: 1, padding: 10, borderRadius: radius.md, backgroundColor: c.bg }}>
                <T size={22} weight="bold" color={c.fg}>{c.n}</T>
                <T size={12} color={c.fg}>{c.label}</T>
              </View>
            ))}
          </View>
          {yes.length ? <T muted size={13}>Présents : {yes.join(', ')}</T> : null}
          {by('maybe').length ? <T muted size={13}>Peut-être : {by('maybe').join(', ')}</T> : null}
          {by('yes', true).length ? <T muted size={13}>Liste d’attente : {by('yes', true).join(', ')}</T> : null}
          {rsvps.filter((r) => r.note).map((r) => (
            <T key={r.user_id} size={13} color={colors.textSoft}>
              <T size={13} weight="semibold">{names.get(r.user_id)} : </T>{r.note}
            </T>
          ))}
        </Section>
      ) : null}
    </>
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

  function vote(optionId: string, v: DateVote) {
    const current = votes.find((x) => x.option_id === optionId && x.user_id === me);
    act(
      current?.vote === v
        ? supabase.from('date_votes').delete().eq('option_id', optionId).eq('user_id', me)
        : supabase.from('date_votes').upsert({ option_id: optionId, user_id: me, vote: v }),
      onChange,
      setError,
    );
  }

  async function propose() {
    const iso = parseLocalDateTime(proposal);
    if (!iso) return setError('Format attendu JJ.MM.AAAA HH:MM');
    if (await act(supabase.from('date_options').insert({ event_id: event.id, starts_at: iso, proposed_by: me }), onChange, setError)) setProposal('');
  }

  return (
    <Section title="Quelle date ?" right={<T muted size={12}>{voters.size} votant(s)</T>}>
      <T muted size={13}>
        {event.status !== 'published' ? 'Les votes seront disponibles lorsque l’événement sera publié.' : closed ? 'Le vote est terminé.' : event.poll_deadline ? `Vote jusqu’au ${formatShort(event.poll_deadline)}` : 'Pour chaque date : Oui, Si besoin ou Non.'}
      </T>
      {scored.map(({ o, vs, yes, ifNeeded, no }) => {
        const mine = vs.find((v) => v.user_id === me)?.vote;
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
              {lead ? <T size={11} weight="bold" color={colors.accent}>EN TÊTE</T> : null}
            </View>
            <View style={{ height: 6, borderRadius: 99, backgroundColor: colors.line, flexDirection: 'row', overflow: 'hidden' }}>
              <View style={{ width: `${(yes / total) * 100}%`, backgroundColor: colors.accent }} />
              <View style={{ width: `${(ifNeeded / total) * 100}%`, backgroundColor: colors.lavender }} />
            </View>
            {!closed ? (
              <View style={s.row}>
                {(['yes', 'if_needed', 'no'] as DateVote[]).map((k) => (
                  <Pressable
                    key={k}
                    accessibilityRole="button"
                    accessibilityState={{ selected: mine === k }}
                    onPress={() => vote(o.id, k)}
                    style={{
                      flex: 1, height: 44, borderRadius: radius.sm, alignItems: 'center', justifyContent: 'center', borderWidth: 1,
                      borderColor: mine === k ? voteColor[k] : colors.lineStrong, backgroundColor: mine === k ? voteColor[k] : 'transparent',
                    }}
                  >
                    <T size={13} style={{ fontFamily: fonts.bold }} color={mine === k ? colors.onAccent : colors.textSoft}>{voteLabel[k]}</T>
                  </Pressable>
                ))}
              </View>
            ) : null}
            {canManage && vs.length ? (
              <T muted size={12}>{vs.map((v) => `${names.get(v.user_id) ?? '?'} (${voteLabel[v.vote]})`).join(', ')}</T>
            ) : null}
            {canManage ? (
              <Button small variant="secondary" label="Fixer cette date" onPress={() => act(supabase.rpc('fix_event_date', { e: event.id, opt: o.id }), onChange, setError)} />
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

  function toggle(optionId: string) {
    act(
      myVotes.has(optionId)
        ? supabase.from('poll_votes').delete().eq('option_id', optionId).eq('user_id', me)
        : supabase.from('poll_votes').insert({ poll_id: poll.id, option_id: optionId, user_id: me }),
      onChange,
      setError,
    );
  }

  const flags = [poll.multiple_choice ? 'Choix multiple' : '1 choix', poll.anonymous ? 'anonyme' : null].filter(Boolean).join(' · ');

  return (
    <Section title={poll.question} right={<T muted size={12}>{flags}</T>}>
      {options.sort((a, b) => a.sort - b.sort).map((o) => {
        const n = results?.get(o.id) ?? 0;
        const on = myVotes.has(o.id);
        return (
          <Pressable
            key={o.id}
            accessibilityRole="button"
            accessibilityState={{ selected: on }}
            disabled={closed || !canParticipate}
            onPress={() => toggle(o.id)}
            style={{ height: 48, borderRadius: 12, borderWidth: 1, borderColor: on ? colors.accent : colors.lineStrong, backgroundColor: colors.bg, overflow: 'hidden', justifyContent: 'center' }}
          >
            {results ? (
              <View style={{ position: 'absolute', left: 0, top: 0, bottom: 0, width: `${(n / total) * 100}%`, backgroundColor: on ? colors.accentDim : colors.surface2 }} />
            ) : null}
            <View style={[s.rowBetween, { paddingHorizontal: 14 }]}>
              <T weight="semibold" size={14}>{on ? '● ' : '○ '}{o.label}</T>
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
  names,
  canParticipate,
  onChange,
}: {
  items: BringItem[];
  me: string;
  names: Names;
  canParticipate: boolean;
  onChange: () => void;
}) {
  const [error, setError] = useState<string | null>(null);
  if (!items.length) return null;
  return (
    <Section title="Qui amène quoi">
      {items.sort((a, b) => a.sort - b.sort).map((it) => (
        <View key={it.id} style={s.rowBetween}>
          <T style={{ flex: 1 }}>{it.label}</T>
          {it.claimed_by === me ? (
            <Button small variant="secondary" label="Je ne prends plus" onPress={() => act(supabase.from('bring_items').update({ claimed_by: null }).eq('id', it.id), onChange, setError)} />
          ) : it.claimed_by ? (
            <T muted>{names.get(it.claimed_by) ?? '?'}</T>
          ) : canParticipate ? (
            <Button small label="Je prends" onPress={() => act(supabase.from('bring_items').update({ claimed_by: me }).eq('id', it.id), onChange, setError)} />
          ) : (
            <T muted>Libre</T>
          )}
        </View>
      ))}
      <ErrorText error={error} />
    </Section>
  );
}
