import { useEffect, useState } from 'react';
import { View } from 'react-native';

import { announceSentence, fetchAnnounceModes, type AnnounceMode } from '@/lib/groupAnnounce';
import { T, ToggleRow } from './ui';

type Props = {
  /** Groupes choisis qui voient l'événement. */
  groupIds: string[];
  /** Réservé aux Membres Vendredi Party (le groupe Vendredi Party est prévenu par « Nouvel événement »). */
  vip?: boolean;
  value: boolean;
  onChange: (on: boolean) => void;
  disabled?: boolean;
  /** Libellé (et nom lu par VoiceOver) quand deux interrupteurs se côtoient ; « Prévenir le groupe » sinon. */
  label?: string;
};

/**
 * « Prévenir le groupe » (décision de l'admin du 06.11) : éteint par défaut, jamais pour un événement public (l'écran ne
 * l'affiche pas, la base l'ignore). La phrase dit ce qui va se passer : notification directe (admin du groupe, groupe
 * « libre ») ou demande à l'admin du groupe, envoyée d'office après 48 h sans réponse.
 */
export function AnnounceToggle({ groupIds, vip = false, value, onChange, disabled = false, label = 'Prévenir le groupe' }: Props) {
  const [modes, setModes] = useState<AnnounceMode[]>([]);
  const key = groupIds.join(',');

  useEffect(() => {
    let live = true;
    fetchAnnounceModes(key ? key.split(',') : [], vip).then(
      (m) => { if (live) setModes(Object.values(m)); },
      () => { if (live) setModes(['request']); },  // dans le doute : la phrase prudente (demande à valider)
    );
    return () => { live = false; };
  }, [key, vip]);

  if (!groupIds.length && !vip) return null;
  return (
    <View style={{ gap: 4 }}>
      <ToggleRow label={label} value={value} onChange={onChange} disabled={disabled} />
      <View accessibilityLiveRegion="polite"><T muted size={13}>{announceSentence(value, modes)}</T></View>
    </View>
  );
}
