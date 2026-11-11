import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { barSetStaff, errorText, type BarOverview, type EventPeople } from '@/lib/bar';
import { plural } from '@/lib/format';
import { colors } from '@/lib/theme';

import { Avatar, Badge, Button, ErrorText, Section, T } from '../ui';

/** Onglet « Barmans » : les co-organisateurs gèrent tout ; les barmans, nommés parmi les présents, scannent et servent. */
export function StaffTab({ eventId, overview, people, onOverview }: {
  eventId: string; overview: BarOverview; people: EventPeople | null; onOverview: (o: BarOverview) => void;
}) {
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function set(member: string, barman: boolean) {
    setBusy(member);
    setError(null);
    try {
      onOverview(await barSetStaff(eventId, member, barman));
    } catch (e) {
      setError(errorText(e, 'Le changement n’a pas pu être enregistré. Réessaie.'));
    } finally {
      setBusy(null);
    }
  }

  const staff = new Set(overview.staff.map((b) => b.id));
  const organizers = people?.organizers ?? [];
  const candidates = (people?.present ?? []).filter((id) => !staff.has(id) && !organizers.includes(id));
  const nameOf = (id: string) => people?.profiles.get(id)?.name ?? 'Membre';

  return (
    <>
      {organizers.length ? (
        <Section title="Co-organisateurs">
          {organizers.map((id) => (
            <View key={id} style={st.row}>
              <Avatar id={id} name={nameOf(id)} photo={people?.profiles.get(id)?.avatar_url} size={36} />
              <T weight="semibold" size={15} style={{ flex: 1 }} numberOfLines={1}>{nameOf(id)}</T>
              <Badge label="Tout gérer" fg={colors.onAccent} bg={colors.accent} />
            </View>
          ))}
        </Section>
      ) : null}
      <Section title="Barmans">
        {overview.staff.length === 0 ? <T muted size={14}>Pas encore de barman : nomme-en parmi les présents ci-dessous.</T> : null}
        {overview.staff.map((b) => (
          <View key={b.id} style={st.row}>
            <Avatar id={b.id} name={b.name} photo={b.avatar_url} size={36} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <T weight="semibold" size={15} numberOfLines={1}>{b.name}</T>
              <T muted size={12}>{b.served ? `a servi ${plural(b.served, 'article')}` : 'pas encore servi'}</T>
            </View>
            <Button small variant="secondary" label="Retirer" accessibilityLabel={`Retirer ${b.name} des barmans`}
              loading={busy === b.id} onPress={() => void set(b.id, false)} />
          </View>
        ))}
        <T muted size={12}>Un barman scanne les QR et sert. Il ne change ni les prix, ni le stock, ni les conditions, et ne voit pas la liste de qui doit combien (seulement le solde de la personne qu’il sert).</T>
      </Section>
      <Section title="Nommer parmi les présents">
        {candidates.length === 0 ? <T muted size={14}>Personne d’autre n’est noté « Présent » pour l’instant.</T> : null}
        {candidates.map((id) => (
          <View key={id} style={st.row}>
            <Avatar id={id} name={nameOf(id)} photo={people?.profiles.get(id)?.avatar_url} size={36} />
            <T size={15} style={{ flex: 1 }} numberOfLines={1}>{nameOf(id)}</T>
            <Button small label="Nommer barman" accessibilityLabel={`Nommer ${nameOf(id)} barman`}
              loading={busy === id} onPress={() => void set(id, true)} />
          </View>
        ))}
      </Section>
      <ErrorText error={error} />
      <T muted size={12}>Un barman trouve « 🍹 Scanner au bar » sur la page de l’événement.</T>
    </>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10 },
});
