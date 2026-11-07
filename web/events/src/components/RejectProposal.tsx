import { useState, type ReactNode } from 'react';
import { View } from 'react-native';

import { Button, Input, s } from '@/components/ui';
import { supabase } from '@/lib/supabase';

type Props = {
  eventId: string;
  /** Résultat de la décision (erreur de la base ou null), une fois envoyée. */
  onDone: (error: string | null) => void;
  /** Bouton « Approuver » à côté de « Refuser » (fiche) ; la page Administration a aussi « Modifier ». */
  extra?: ReactNode;
};

/** Refuser une proposition : toujours une confirmation, avec un motif facultatif pour l'organisateur (page Administration
 * et fiche de l'événement : campagne 2, un seul toucher refusait sans motif depuis la fiche). */
export function RejectProposal({ eventId, onDone, extra }: Props) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState('');
  const [sending, setSending] = useState(false);

  async function confirm() {
    if (sending) return;
    setSending(true);
    const { error } = await supabase.rpc('reject_event', { e: eventId, reason: reason.trim() || null });
    setSending(false);
    if (!error) {
      setOpen(false);
      setReason('');
    }
    onDone(error?.message ?? null);
  }

  if (!open) {
    return (
      <View style={s.row}>
        {extra}
        <Button small variant="danger" label="Refuser" style={{ flex: 1 }} onPress={() => setOpen(true)} />
      </View>
    );
  }
  return (
    <View style={{ gap: 8 }}>
      <Input placeholder="Message pour l’organisateur (optionnel)" accessibilityLabel="Motif du refus (optionnel)"
        value={reason} onChangeText={setReason} maxLength={500} />
      <View style={s.row}>
        <Button small variant="secondary" label="Annuler" onPress={() => setOpen(false)} style={{ flex: 1 }} />
        <Button small variant="danger" label="Confirmer le refus" loading={sending} style={{ flex: 1 }} onPress={confirm} />
      </View>
    </View>
  );
}
