import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { formatShort } from '@/lib/format';
import { enter } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';
import { chf, confirmPayment, fetchCheckins, setPaid, type TicketPerson } from '@/lib/tickets';

import { PersonName } from './PersonName';
import { Avatar, Button, ErrorText, Section, T } from './ui';

/**
 * Organisateur d'un événement payant : qui dit avoir payé (« en attente »), à confirmer « Reçu ✓ » ou « Pas reçu ».
 * Paiement en ligne (19.11) : rien à confirmer, « J'ai payé » compte ; la liste dit qui a payé et quand.
 * 20.11 : l'organisateur note lui-même « A payé » (payé sur le site ou à lui, sans l'avoir noté) et peut l'annuler.
 * `refreshKey` : relu quand les réponses changent (temps réel de la page).
 */
export function PendingPayments({ eventId, price, refreshKey, onConfirmed, online = false }: {
  eventId: string; price: number; refreshKey: string; online?: boolean;
  /** Après « Reçu » / « Pas reçu » : la place payée remet aussi le billet, la liste des billets se relit. */
  onConfirmed?: () => void;
}) {
  const [people, setPeople] = useState<TicketPerson[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(() => fetchCheckins(eventId).then(
    (rows) => { setPeople(rows); setError(null); },
    (e: unknown) => setError(e instanceof Error ? e.message : 'La liste ne se charge pas. Réessaie.'),
  ), [eventId]);
  useEffect(() => { void load(); }, [load, refreshKey]);

  async function confirm(p: TicketPerson, received: boolean, byOrganizer = false) {
    setBusy(`${p.user_id}:${received}`);
    try {
      const after = byOrganizer ? await setPaid(eventId, p.user_id, received, p) : await confirmPayment(eventId, p.user_id, received, p);
      setNotice(after.notice ?? null);  // « Pas reçu » : billet remis par ce paiement retiré
      await load();
      onConfirmed?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(null);
    }
  }

  if (!people) return error ? <ErrorText error={error} /> : null;
  const present = people.filter((p) => !p.waitlisted);
  const pending = online ? [] : present.filter((p) => p.pay_pending);
  const payers = present.filter((p) => p.paid || (online && p.pay_pending));
  const unpaid = present.filter((p) => !p.paid && !p.pay_pending);
  const paid = payers.length;

  return (
    <Section title="Paiements" right={<T size={13} weight="bold" color={colors.mint}>{paid} / {present.length} payé{paid > 1 ? 's' : ''}</T>}>
      {online ? (
        <T muted size={13}>{paid ? 'Paiement en ligne : rien à confirmer.' : 'Paiement en ligne : quand quelqu’un touche « J’ai payé », il apparaît ici. Rien à confirmer.'}</T>
      ) : pending.length ? (
        <T size={13} weight="semibold" color={colors.coral}>{pending.length} à confirmer · {chf(price)} chacun</T>
      ) : (
        <T muted size={13}>Aucun paiement à confirmer. Quand quelqu’un touche « J’ai payé », il apparaît ici.</T>
      )}
      {pending.map((p) => (
        <View key={p.user_id} style={[st.row, enter('pop')]}>
          <Avatar id={p.user_id} name={p.display_name} photo={p.avatar_url} size={36} />
          <View style={{ flex: 1, minWidth: 0 }}>
            <PersonName id={p.user_id} pseudo={p.display_name} weight="semibold" />
            <T size={12} muted>{p.pay_declared_at ? `Dit avoir payé · ${formatShort(p.pay_declared_at)}` : 'Dit avoir payé'}</T>
          </View>
          <Button small label="Reçu ✓" loading={busy === `${p.user_id}:true`} onPress={() => confirm(p, true)} />
          <Button small variant="ghost" label="Pas reçu" loading={busy === `${p.user_id}:false`} onPress={() => confirm(p, false)} />
        </View>
      ))}
      {payers.length ? (
        <View style={{ gap: 4 }}>
          <T size={12} weight="bold" color={colors.mint}>{'Ont payé'.toUpperCase()} · {payers.length}</T>
          {payers.map((p) => (
            <View key={p.user_id} style={[st.paidRow]}>
              <Avatar id={p.user_id} name={p.display_name} photo={p.avatar_url} size={24} />
              <PersonName id={p.user_id} pseudo={p.display_name} weight="semibold" />
              <T size={12} muted>{p.paid ? (p.pay_declared_at ? `payé · ${formatShort(p.pay_declared_at)}` : 'payé') : `en ligne · ${formatShort(p.pay_declared_at!)}`}</T>
              {p.paid ? <Button small variant="ghost" label="Annuler" loading={busy === `${p.user_id}:false`} onPress={() => confirm(p, false, true)} /> : null}
            </View>
          ))}
        </View>
      ) : null}
      {unpaid.length ? (
        <View style={{ gap: 4 }}>
          <T size={12} weight="bold" color={colors.muted}>{'Pas encore payé'.toUpperCase()} · {unpaid.length}</T>
          <T muted size={12}>{online ? 'Payé sur le site sans le noter ? Si on te le dit, note-le ici.' : 'Payé sans le noter ? Si tu as reçu le paiement, note-le ici.'}</T>
          {unpaid.map((p) => (
            <View key={p.user_id} style={st.paidRow}>
              <Avatar id={p.user_id} name={p.display_name} photo={p.avatar_url} size={24} />
              <View style={{ flex: 1, minWidth: 0 }}><PersonName id={p.user_id} pseudo={p.display_name} weight="semibold" /></View>
              <Button small variant="secondary" label="A payé ✓" loading={busy === `${p.user_id}:true`} onPress={() => confirm(p, true, true)} />
            </View>
          ))}
        </View>
      ) : null}
      <ErrorText error={error} />
      {notice ? <T size={13} weight="semibold" color={colors.coral}>{notice}</T> : null}
    </Section>
  );
}

const st = StyleSheet.create({
  paidRow: { flexDirection: 'row', alignItems: 'center', gap: 8, flexWrap: 'wrap' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8, padding: 8, borderRadius: radius.md, backgroundColor: 'rgba(255,179,71,0.08)', flexWrap: 'wrap' },
});
