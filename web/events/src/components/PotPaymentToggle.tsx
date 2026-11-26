import { useState } from 'react';
import { View } from 'react-native';
import { useQuery } from '@/lib/data';
import { potPaymentChoice, setPotPayment } from '@/lib/rsvp';
import { ErrorText, ToggleRow } from './ui';

/**
 * Pot commun d'un événement, pour qui y est (ajouté d'office en répondant Présent) : ses moyens de paiement restent cachés
 * tant qu'il ne les montre pas lui-même (`tc_members.show_payment`, `tc_set_show_payment`). Base d'avant : rien d'affiché.
 */
export function PotPaymentToggle({ eventId, me }: { eventId: string; me: string }) {
  const { data, reload } = useQuery(() => potPaymentChoice(eventId, me), [eventId, me]);
  const [on, setOn] = useState<boolean | null>(null);
  const [gone, setGone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!data || gone) return null;
  const value = on ?? data.on;

  async function change(next: boolean) {
    if (!data) return;
    setBusy(true);
    setError(null);
    setOn(next);
    try {
      if (!(await setPotPayment(data.group, next))) setGone(true);
      else void reload();
    } catch (e) {
      setOn(null);
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <View testID="pot-payment">
      <ToggleRow label="Montrer mes moyens de paiement dans ce pot" disabled={busy} value={value}
        hint={value ? 'Les membres de ce pot voient ton IBAN et tes liens de paiement. Éteins pour les cacher.'
          : 'Les membres verront ton IBAN et tes liens de paiement. Éteint : ils restent cachés.'}
        onChange={(v) => void change(v)} />
      <ErrorText error={error} />
    </View>
  );
}
