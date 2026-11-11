import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { amount, barCancelUnits, barChf, barCorrectUnit, barPerson, errorText, itemLabel, useBarRefresh, type BarPersonDetail, type BarUnit } from '@/lib/bar';
import { useQuery } from '@/lib/data';
import { formatMessageTime, formatTime, plural } from '@/lib/format';
import { colors, font, radius } from '@/lib/theme';

import { Button, ConfirmButton, ErrorText, Loading, Screen, Section, T } from '../ui';
import { BarHeader } from './BarHeader';

type Reserved = { item: string; label: string; name: string; qty: number; last: string };

/** Verres en attente regroupés par article (le plus récent d'abord : c'est lui que « Annuler 1 » retire). */
function reservedOf(units: BarUnit[]): Reserved[] {
  const byItem = new Map<string, Reserved>();
  for (const u of units.filter((x) => x.status === 'pending')) {
    const prev = byItem.get(u.item);
    byItem.set(u.item, prev
      ? { ...prev, qty: prev.qty + 1, last: u.ordered_at > prev.last ? u.ordered_at : prev.last }
      : { item: u.item, label: itemLabel(u), name: u.name, qty: 1, last: u.ordered_at });
  }
  return [...byItem.values()];
}

/**
 * Réservations d'une personne (organisateurs, depuis « Direct ») : annuler un verre réservé pour libérer du stock, ou
 * corriger un verre servi par erreur. Chaque geste est noté (qui, quand) et la personne est prévenue.
 */
export function BarPersonScreen({ eventId, member }: { eventId: string; member: string }) {
  const { data: person, error, loading, reload, setData } = useQuery(() => barPerson(eventId, member), [eventId, member]);
  useBarRefresh(reload, !!person);
  const [busy, setBusy] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  async function act(key: string, run: () => Promise<BarPersonDetail>) {
    setBusy(key);
    setActionError(null);
    try {
      setData(await run());
    } catch (e) {
      setActionError(errorText(e, 'Le changement n’a pas pu être enregistré. Réessaie.'));
      void reload();
    } finally {
      setBusy(null);
    }
  }

  if (loading) return <Loading />;
  if (!person) {  // une relecture ratée garde la fiche déjà affichée
    return (
      <Screen edges={[]}>
        <BarHeader title="Réservations" eventId={eventId} />
        <ErrorText error={error ?? 'Cette fiche n’existe pas.'} />
      </Screen>
    );
  }

  const name = person.name ?? 'Membre';
  const reserved = reservedOf(person.units);
  const served = person.units.filter((u) => u.status === 'served');
  const gone = person.units.filter((u) => u.status === 'cancelled' || u.status === 'corrected');
  return (
    <Screen edges={[]}>
      <BarHeader title={name} eventId={eventId} />
      <View style={st.hero}>
        <View style={{ flex: 1, gap: 2 }}>
          <T size={12} weight="bold" color={colors.coralSoft}>{person.balance < 0 ? 'À LUI RENDRE' : 'À REMBOURSER'}</T>
          <T size={13} color={colors.textSoft}>
            {person.pledges.length ? `✓ ${plural(person.pledges.length, 'engagement accepté', 'engagements acceptés')}` : 'Pas encore d’engagement'}
          </T>
        </View>
        <Text style={st.amount}>{amount(Math.abs(person.balance))}</Text>
        <T size={14} weight="bold" color={colors.textSoft}>CHF</T>
      </View>

      <Section title="Réservé, pas encore servi">
        {reserved.length === 0 ? <T muted size={14}>Rien en attente.</T> : null}
        {reserved.map((r) => (
          <View key={r.item} style={st.row}>
            <View style={{ flex: 1, minWidth: 0 }}>
              <T weight="semibold" size={15} numberOfLines={2}>{r.label}</T>
              <T muted size={12}>× {r.qty} · commandé à {formatTime(r.last)}</T>
            </View>
            <Button small variant="danger" label="Annuler 1" accessibilityLabel={`Annuler 1 ${r.name} de ${name}`}
              loading={busy === r.item} disabled={!!busy && busy !== r.item}
              onPress={() => void act(r.item, () => barCancelUnits(eventId, member, r.item, 1))} />
          </View>
        ))}
        {reserved.length ? <T muted size={12}>Annuler libère la place pour les autres ; {name} est prévenu·e, rien à payer.</T> : null}
      </Section>

      <Section title="Servi">
        {served.length === 0 ? <T muted size={14}>Rien de servi pour l’instant.</T> : null}
        {served.map((u) => (
          <View key={u.id} style={st.served}>
            <View style={st.line}>
              <T muted size={13} style={st.hour}>{u.served_at ? formatTime(u.served_at) : ''}</T>
              <T size={14} style={{ flex: 1 }} numberOfLines={2}>{itemLabel(u)}{u.served_by ? ` · ${u.served_by}` : ''}</T>
              <T size={14} weight="semibold">{barChf(u.price_chf)}</T>
            </View>
            <ConfirmButton small label="Servi par erreur" confirmLabel="Oui, corriger" onConfirm={() => act(u.id, () => barCorrectUnit(eventId, u.id))} />
          </View>
        ))}
        {served.length ? <T muted size={12}>Un verre servi par erreur ? « Servi par erreur » le retire du solde de {name}.</T> : null}
      </Section>

      {gone.length ? (
        <Section title="Annulés et corrigés">
          {gone.map((u) => (
            <View key={u.id} style={st.line}>
              <T size={14} color={colors.muted} style={{ flex: 1 }} numberOfLines={2}>{itemLabel(u)}</T>
              <T muted size={12}>{u.status === 'corrected' ? 'corrigé' : 'annulé'} · commandé {formatMessageTime(u.ordered_at)}</T>
            </View>
          ))}
        </Section>
      ) : null}
      <ErrorText error={actionError} />
      <T muted size={12}>Chaque annulation ou correction est notée (qui, quand) et {name} est prévenu·e.</T>
    </Screen>
  );
}

const st = StyleSheet.create({
  hero: { flexDirection: 'row', alignItems: 'baseline', gap: 8, padding: 16, borderRadius: radius.lg, backgroundColor: colors.accentDim, borderWidth: 1, borderColor: '#5A2346' },
  amount: { ...font.display, color: colors.text, fontSize: 40, lineHeight: 44, fontVariant: ['tabular-nums'] },
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 10, borderRadius: radius.md, backgroundColor: colors.fill },
  served: { gap: 6, paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: colors.line },
  line: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 28 },
  hour: { width: 46, fontVariant: ['tabular-nums'] },
});
