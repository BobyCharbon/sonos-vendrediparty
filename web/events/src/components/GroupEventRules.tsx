import { useState } from 'react';
import { View } from 'react-native';

import { setGroupRules } from '@/lib/groupAnnounce';
import { colors } from '@/lib/theme';
import { ErrorText, Segmented, T, ToggleRow } from './ui';

type Mode = 'request' | 'free';

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
        // « Événements à valider » (avis f0e9bf158133, 22.11, éteint par défaut) : base events_need_approval.
        <ToggleRow label="Événements à valider" value={needApproval} disabled={busy}
          hint={needApproval
            ? 'Un événement créé pour le groupe par un membre attend ton accord (ou celui d’un admin du groupe) avant que le groupe le voie. Tu es prévenu et tu acceptes ou refuses dans Activité › À valider.'
            : 'Un membre qui crée un événement pour le groupe le rend visible tout de suite à tout le groupe.'}
          onChange={(on) => void save(on, mode)} />
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
