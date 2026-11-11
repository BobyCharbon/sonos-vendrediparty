import { useState } from 'react';
import { View } from 'react-native';

import { barSaveSettings, errorText, whenLabel, type BarOverview, type BarSettings } from '@/lib/bar';
import { parseLocalDateTime, toLocalInput } from '@/lib/format';
import { colors } from '@/lib/theme';

import { DateTimeField } from '../DateTimeField';
import { Button, Card, ErrorText, T, ToggleRow } from '../ui';

/** Commandes ouvertes, précommande (et sa date limite), heure de fermeture du bar. */
export function BarHours({ eventId, overview, onOverview }: { eventId: string; overview: BarOverview; onOverview: (o: BarOverview) => void }) {
  const [until, setUntil] = useState(() => toLocalInput(overview.preorder_until));
  const [closes, setCloses] = useState(() => toLocalInput(overview.closes_at));
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const closed = !!overview.closed_at;

  async function save(key: string, settings: BarSettings) {
    setBusy(key);
    setError(null);
    try {
      onOverview(await barSaveSettings(eventId, settings));
    } catch (e) {
      setError(errorText(e, 'Le réglage n’a pas pu être enregistré. Réessaie.'));
    } finally {
      setBusy(null);
    }
  }

  function saveDate(key: 'preorder_until' | 'closes_at', text: string) {
    if (!text && key === 'preorder_until') return void save(key, { preorder_until: null });
    const iso = parseLocalDateTime(text);
    if (!iso) return setError('Choisis un jour et une heure.');
    // Une heure passée fermerait le bar tout de suite, sans retour possible (tout ce qui attend serait annulé).
    if (new Date(iso).getTime() <= Date.now()) return setError('Choisis une heure à venir : une heure passée fermerait le bar tout de suite.');
    void save(key, { [key]: iso });
  }

  const untilDirty = until !== toLocalInput(overview.preorder_until);
  const closesDirty = closes !== toLocalInput(overview.closes_at);
  return (
    <Card>
      {closed ? (
        <T size={14} color={colors.coralSoft}>Bar fermé le {whenLabel(overview.closed_at!)} : plus de commande. Ce qui attendait a été annulé.</T>
      ) : null}
      <ToggleRow label="Commandes ouvertes" hint="Les invités peuvent commander." value={overview.orders_open} disabled={closed || !!busy}
        onChange={(v) => void save('orders', { orders_open: v })} />
      <ToggleRow label="Précommande" hint="Avant l’ouverture : sans maximum par personne, dans la limite du stock."
        value={overview.preorder_enabled} disabled={closed || !!busy} onChange={(v) => void save('preorder', { preorder_enabled: v })} />
      {overview.preorder_enabled && !closed ? (
        <View style={{ gap: 8 }}>
          <DateTimeField label="Précommande jusqu’au" value={until} onChangeText={setUntil} optional hint="Vide : jusqu’à l’ouverture des commandes." />
          {untilDirty ? <Button small variant="secondary" label="Enregistrer la date" loading={busy === 'preorder_until'}
            onPress={() => saveDate('preorder_until', until)} /> : null}
        </View>
      ) : null}
      <View style={{ gap: 8 }}>
        <DateTimeField label="Fermeture du bar" value={closes} onChangeText={setCloses}
          hint="À cette heure, ce qui n’a pas été servi est annulé (rien à payer)." />
        {closesDirty ? <Button small variant="secondary" label="Enregistrer l’heure de fermeture" loading={busy === 'closes_at'}
          onPress={() => saveDate('closes_at', closes)} /> : null}
      </View>
      <ErrorText error={error} />
    </Card>
  );
}
