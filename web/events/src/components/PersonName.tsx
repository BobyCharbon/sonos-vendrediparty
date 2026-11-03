import { type StyleProp, type TextStyle } from 'react-native';

import { T } from '@/components/ui';
import { labelText, personLabel, useContactNames } from '@/lib/contactNames';
import { type FontWeight } from '@/lib/theme';

interface PersonNameProps {
  id: string | null | undefined;
  pseudo: string;
  size?: number;
  weight?: FontWeight;
  color?: string;
  muted?: boolean;
  numberOfLines?: number;
  style?: StyleProp<TextStyle>;
}

/**
 * « Nom du contact · pseudo » (app iPhone, avis f780431defe7) : le nom de mon répertoire en principal, le pseudo en
 * plus petit et gris. Hors de l'app, ou sans contact : le pseudo seul, exactement comme avant.
 */
export function PersonName({ id, pseudo, size = 15, weight, color, muted, numberOfLines = 1, style }: PersonNameProps) {
  const label = personLabel(useContactNames(), id, pseudo);
  return (
    <T size={size} weight={weight} color={color} muted={muted} numberOfLines={numberOfLines} style={style}>
      {label.primary}
      {label.secondary ? (
        <T muted size={Math.max(11, size - 3)} weight="body">{` · ${label.secondary}`}</T>
      ) : null}
    </T>
  );
}

/** Même chose en texte simple (accessibilité, phrases). */
export function usePersonText(): (id: string | null | undefined, pseudo: string) => string {
  const table = useContactNames();
  return (id, pseudo) => labelText(personLabel(table, id, pseudo));
}
