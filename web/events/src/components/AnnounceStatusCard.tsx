import { useCallback, useEffect, useState } from 'react';
import { View } from 'react-native';

import { formatShort } from '@/lib/format';
import { fetchAnnounceStatus, statusLine, turnOnAnnounce, type AnnounceStatus } from '@/lib/groupAnnounce';
import { colors } from '@/lib/theme';
import { AnnounceToggle } from './AnnounceToggle';
import { Card, ErrorText, T } from './ui';

type Props = {
  eventId: string;
  /** Groupes choisis qui voient l'événement. */
  groupIds: string[];
  /** Réservé aux Membres Vendredi Party. */
  vip: boolean;
  announceOn: boolean;
  refreshKey?: string;
  onChanged: () => void;
};

/**
 * Fiche, pour l'organisateur d'un événement de groupe publié : où en est l'annonce (« Annonce en attente / envoyée /
 * refusée », groupe en attente de validation) ; « Prévenir le groupe » s'allume encore ici après la publication.
 */
export function AnnounceStatusCard({ eventId, groupIds, vip, announceOn, refreshKey, onChanged }: Props) {
  const [rows, setRows] = useState<AnnounceStatus[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => fetchAnnounceStatus(eventId).then(setRows, () => setRows([])), [eventId]);
  useEffect(() => { void load(); }, [load, refreshKey, announceOn]);

  async function turnOn(on: boolean) {
    if (!on) return;
    setBusy(true);
    setError(null);
    try {
      await turnOnAnnounce(eventId);
      onChanged();
      await load();
    } catch {
      setError('« Prévenir le groupe » n’a pas été enregistré. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  if ((!groupIds.length && !vip) || rows === null) return null;
  return (
    <Card>
      <T weight="bold">Annonce au groupe</T>
      {rows.map((r) => (
        <View key={`${r.group}:${r.status}`} accessibilityRole="text">
          <T size={14} color={r.status === 'refused' || r.status === 'group_refused' ? colors.coral : r.status.includes('pending') ? colors.textSoft : colors.mint}>
            {statusLine(r, formatShort)}
          </T>
        </View>
      ))}
      {!announceOn ? <AnnounceToggle groupIds={groupIds} vip={vip} value={false} onChange={(v) => void turnOn(v)} disabled={busy} /> : null}
      {announceOn && !rows.some((r) => !r.status.startsWith('group_')) ? (
        <T muted size={13}>L’annonce partira dès que le groupe verra l’événement.</T>
      ) : null}
      <ErrorText error={error} />
    </Card>
  );
}
