import { useState } from 'react';
import { View } from 'react-native';

import { setGroupRules } from '@/lib/groupAnnounce';
import { colors } from '@/lib/theme';
import { ErrorText, Segmented, T } from './ui';

type Mode = 'request' | 'free';
type Approval = 'free' | 'approval';

type Props = {
  groupId: string;
  needApproval: boolean;
  mode: Mode;
  /** Vendredi Party : tous les Membres VIP y sont d'office, seule l'annonce se règle. */
  system: boolean;
  onSaved: () => void;
};

/**
 * Réglages du groupe, décidés par son créateur (décision de l'admin du 06.11) :
 * - « Les membres peuvent créer des événements pour le groupe » : sans validation, ou avec celle d'un admin du groupe ;
 * - « Notifications des événements » : les membres préviennent librement le groupe, ou font une demande à valider.
 */
export function GroupEventRules({ groupId, needApproval, mode, system, onSaved }: Props) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function save(nextApproval: boolean, nextMode: Mode) {
    setBusy(true);
    setError(null);
    try {
      await setGroupRules(groupId, nextApproval, nextMode);
      onSaved();
    } catch {
      setError('Le réglage n’a pas été enregistré. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  return (
    <View style={{ gap: 10 }} accessibilityLabel="Réglages des événements du groupe">
      {system ? null : (
        <View style={{ gap: 6 }}>
          <T weight="semibold">Les membres créent des événements pour le groupe</T>
          <Segmented<Approval>
            options={[{ key: 'free', label: 'Sans validation' }, { key: 'approval', label: 'Avec validation' }]}
            value={needApproval ? 'approval' : 'free'} disabled={busy}
            onChange={(k) => void save(k === 'approval', mode)} />
          <T muted size={13}>
            {needApproval
              ? 'Un événement proposé au groupe par un membre reste invisible pour le groupe tant qu’un admin du groupe ne l’a pas accepté (Activité › À valider).'
              : 'Un membre qui réserve un événement au groupe le rend visible tout de suite à tout le groupe.'}
          </T>
        </View>
      )}
      <View style={{ gap: 6 }}>
        <T weight="semibold">Notifications des événements</T>
        <Segmented<Mode>
          options={[{ key: 'request', label: 'Sur demande' }, { key: 'free', label: 'Libres' }]}
          value={mode} disabled={busy}
          onChange={(k) => void save(needApproval, k)} />
        <T muted size={13}>
          {mode === 'request'
            ? '« Prévenir le groupe » d’un membre devient une demande : toi, les admins et les organisateurs du groupe l’acceptez ou la refusez. Sans réponse sous 48 h, l’annonce part automatiquement.'
            : 'Chaque membre décide lui-même de prévenir le groupe quand il publie un événement.'}
        </T>
        <T size={12} color={colors.muted}>Les admins et organisateurs du groupe préviennent toujours le groupe sans demande.</T>
      </View>
      <ErrorText error={error} />
    </View>
  );
}
