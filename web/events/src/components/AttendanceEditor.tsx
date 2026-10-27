import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { rsvpChoices, rsvpOptions, setRsvpFor } from '@/lib/rsvp';
import type { EventRow, Rsvp, RsvpStatus } from '@/lib/types';

import { RsvpButtons } from './RsvpButtons';
import { Avatar, Button, ErrorText, Input, Rows, s, Section, T } from './ui';

const MAX_SUGGESTIONS = 6;

type Props = {
  event: Pick<EventRow, 'id' | 'allow_maybe'>;
  rsvps: Rsvp[];
  names: Map<string, string>;
  me: string;
  onChange: () => void;
};

/** Pour chercher un prénom sans tenir compte des accents ni des majuscules. */
const fold = (text: string) => text.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();

/**
 * Organisateur (ou admin) : noter quelqu’un Présent / Peut-être / Absent, retirer sa réponse,
 * ou ajouter une personne qui n’a pas répondu. La personne est prévenue par la base.
 */
export function AttendanceEditor({ event, rsvps, names, me, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const options = rsvpOptions(event.allow_maybe);
  const nameOf = (id: string) => (id === me ? 'Toi' : names.get(id) ?? '?');

  async function apply(member: string, answer: RsvpStatus | null) {
    setBusy(`${member}:${answer}`);
    try {
      await setRsvpFor(event.id, member, answer);
      setError(null);
      setQuery('');
      onChange();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(null);
    }
  }

  if (!open) {
    return (
      <Section title="Présences" right={<Button small variant="secondary" label="Gérer" onPress={() => setOpen(true)} />}>
        <T muted size={13}>Note toi-même quelqu’un présent ou absent, par exemple s’il ne vient finalement pas.</T>
      </Section>
    );
  }

  const answered = new Set(rsvps.map((r) => r.user_id));
  const q = fold(query.trim());
  const suggestions = q
    ? [...names].filter(([id, name]) => !answered.has(id) && fold(name).includes(q)).slice(0, MAX_SUGGESTIONS)
    : [];
  const people = [...rsvps].sort((a, b) => nameOf(a.user_id).localeCompare(nameOf(b.user_id), 'fr'));
  const busyFor = (member: string) => options.find((k) => busy === `${member}:${k}`) ?? null;

  return (
    <Section title="Présences" right={<Button small variant="ghost" label="Terminé" onPress={() => setOpen(false)} />}>
      <Input
        accessibilityLabel="Ajouter quelqu’un"
        placeholder="Ajouter quelqu’un (prénom ou surnom)"
        value={query}
        onChangeText={setQuery}
        maxLength={40}
      />
      {suggestions.length ? (
        <Rows>
          {suggestions.map(([id, name]) => (
            <View key={id} style={[s.rowBetween, st.line]}>
              <View style={[s.row, st.who]}>
                <Avatar id={id} name={name} size={28} />
                <T weight="semibold" numberOfLines={1} style={st.shrink}>{name}</T>
              </View>
              <Button small label="Noter présent" loading={busy === `${id}:yes`} onPress={() => apply(id, 'yes')} />
            </View>
          ))}
        </Rows>
      ) : q ? <T muted size={13}>Personne d’autre ne porte ce nom.</T> : null}

      {people.length ? (
        <Rows>
          {people.map((r) => (
            <View key={r.user_id} style={st.person}>
              <View style={s.rowBetween}>
                <View style={[s.row, st.who]}>
                  <Avatar id={r.user_id} name={nameOf(r.user_id)} size={28} />
                  <View style={st.shrink}>
                    <T weight="semibold" numberOfLines={1}>{nameOf(r.user_id)}{r.plus_ones ? ` +${r.plus_ones}` : ''}</T>
                    {r.set_by ? <T muted size={12}>Noté par {nameOf(r.set_by)}</T> : null}
                  </View>
                </View>
                <Button small variant="ghost" label="Retirer" loading={busy === `${r.user_id}:null`} onPress={() => apply(r.user_id, null)} />
              </View>
              <RsvpButtons
                options={options}
                selected={r.status}
                busy={busyFor(r.user_id)}
                disabled={!!busy}
                onSelect={(k) => apply(r.user_id, k)}
                accessibilityLabel={(k) => `${nameOf(r.user_id)} : ${rsvpChoices[k].label}`}
              />
            </View>
          ))}
        </Rows>
      ) : <T muted size={13}>Personne n’a encore répondu : cherche un prénom pour l’ajouter.</T>}
      <ErrorText error={error} />
    </Section>
  );
}

const st = StyleSheet.create({
  line: { paddingVertical: 6 },
  who: { flexShrink: 1, gap: 10 },
  shrink: { flexShrink: 1 },
  person: { gap: 8, paddingVertical: 10 },
});
