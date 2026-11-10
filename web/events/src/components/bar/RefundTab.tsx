import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { useMe } from '@/lib/auth';
import { barSaveSettings, errorText, type BarOverview, type BarSettings, type EventPeople, type PayMethod } from '@/lib/bar';
import { colors, radius } from '@/lib/theme';

import { Button, Chip, ErrorText, s, Section, T } from '../ui';
import { DateField } from './DateField';

const METHODS: { key: PayMethod; label: string; hint: string }[] = [
  { key: 'revolut', label: 'Revolut', hint: 'Le lien Revolut de son profil de paiement' },
  { key: 'twint', label: 'Twint', hint: 'Le numéro Twint de son profil de paiement' },
  { key: 'iban', label: 'Virement', hint: 'L’IBAN de son profil de paiement' },
];

const today = () => new Date().toISOString().slice(0, 10);

/** Onglet « Rembourser » : moyen, bénéficiaire (organisateur ou co-organisateur), date limite ; ces choix forment le
 * texte d'engagement que chaque invité coche avant de commander (nouvelle version : chacun est prévenu). */
export function RefundTab({ eventId, overview, people, onOverview, onSaved }: {
  eventId: string; overview: BarOverview; people: EventPeople | null; onOverview: (o: BarOverview) => void;
  /** Enregistré : l'onglet est recréé avec les nouvelles conditions (la confirmation s'affiche au-dessus). */
  onSaved: () => void;
}) {
  const me = useMe();
  const [method, setMethod] = useState<PayMethod>(overview.pay_method);
  const [payee, setPayee] = useState<string | null>(overview.payee_id);
  const [repayBy, setRepayBy] = useState(overview.repay_by ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const dirty = method !== overview.pay_method || payee !== overview.payee_id || repayBy !== (overview.repay_by ?? '');

  async function save() {
    setBusy(true);
    setError(null);
    try {
      const settings: BarSettings = { pay_method: method, repay_by: repayBy || null, ...(payee ? { payee_id: payee } : {}) };
      onOverview(await barSaveSettings(eventId, settings));
      onSaved();
    } catch (e) {
      setError(errorText(e, 'Les conditions n’ont pas pu être enregistrées. Réessaie.'));
    } finally {
      setBusy(false);
    }
  }

  const organizers = people?.organizers ?? (overview.payee_id ? [overview.payee_id] : []);
  return (
    <>
      <Section title="Rembourser à">
        {METHODS.map((m) => {
          const on = method === m.key;
          return (
            <Pressable key={m.key} accessibilityRole="radio" accessibilityState={{ checked: on }} aria-checked={on} onPress={() => setMethod(m.key)}
              style={({ pressed }) => [st.radio, on && st.radioOn, pressed && { opacity: 0.85 }]}>
              <View style={[st.dot, on && st.dotOn]} />
              <View style={{ flex: 1 }}>
                <T weight="semibold" size={15}>{m.label}</T>
                <T muted size={12}>{m.hint}</T>
              </View>
            </Pressable>
          );
        })}
        <T muted size={13}>Bénéficiaire</T>
        <View style={s.wrap}>
          {organizers.map((id) => (
            <Chip key={id} selected={payee === id} onPress={() => setPayee(id)}
              label={`${people?.profiles.get(id)?.name ?? 'Organisateur'}${id === me.id ? ' (toi)' : ''}`} />
          ))}
        </View>
        <DateField label="À rembourser avant le" value={repayBy} onChange={setRepayBy} min={today()}
          hint="Vide : « après la soirée », sans date limite." />
      </Section>
      <Section title="Texte d’engagement">
        <T size={15} style={st.quote}>« {overview.pledge_text} »</T>
        <T muted size={12}>Coché à chaque commande. Party garde la date, l’heure et le texte accepté.</T>
        {dirty ? (
          <T size={13} color={colors.coral}>Après « Enregistrer », le texte suivra tes choix. Ceux qui ont déjà commandé sont prévenus et recochent à leur prochaine commande.</T>
        ) : null}
      </Section>
      <ErrorText error={error} />
      <Button label="Enregistrer" disabled={!dirty} loading={busy} onPress={() => void save()} />
    </>
  );
}

const st = StyleSheet.create({
  radio: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 52, padding: 12, borderRadius: radius.md, borderWidth: 1.5, borderColor: colors.line, backgroundColor: colors.fill },
  radioOn: { borderColor: colors.accent },
  dot: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: colors.muted },
  dotOn: { borderColor: colors.accent, borderWidth: 6 },
  quote: { lineHeight: 22, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface2, color: colors.textSoft },
});
