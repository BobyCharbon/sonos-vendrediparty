import { useMemo, type ReactNode } from 'react';
import { Linking, Platform, Text, type StyleProp, type TextStyle } from 'react-native';

import { T } from '@/components/ui';
import { linkify, type Segment } from '@/lib/links';
import { colors, type FontWeight } from '@/lib/theme';

/**
 * Texte d’un événement (description, paiement, message, note…) dont les adresses web, e-mails et numéros
 * deviennent des liens (avis 2c221fd8effc). Aucun HTML : chaque morceau est un texte React (échappé).
 *
 * Sur le web, un vrai <a href> : appui long, copie du lien, lecteur d’écran. Adresse web : nouvel onglet
 * (rel noopener noreferrer) ; dans l’app iPhone, la vue web l’ouvre alors dans Safari (PartyWebView). E-mail et
 * téléphone : fenêtre principale (_top), sinon l’iframe du module tenterait de charger tel:/mailto: sur place.
 */
interface LinkedTextProps {
  text: string | null | undefined;
  size?: number;
  muted?: boolean;
  weight?: FontWeight;
  color?: string;
  linkColor?: string;
  style?: StyleProp<TextStyle>;
  numberOfLines?: number;
  /** Placé avant le texte, dans la même ligne (ex. le prénom en gras devant une note). */
  prefix?: ReactNode;
}

/** Web : une longue adresse se coupe n'importe où plutôt que d'élargir sa bulle au-delà de l'écran (le lien aussi :
 * chaque texte imbriqué de react-native-web reprend sinon « break-word », qui ne réduit pas la largeur minimale). */
const breakAnywhere = (Platform.OS === 'web' ? { overflowWrap: 'anywhere' } : {}) as TextStyle;

const linkStyle: TextStyle = { textDecorationLine: 'underline', ...breakAnywhere };

function Link({ segment, color }: { segment: Segment; color: string }) {
  const href = segment.href!;
  if (Platform.OS === 'web') {
    // react-native-web : href + hrefAttrs rendent un <a> (props absentes des types natifs).
    const webProps = {
      href,
      hrefAttrs: segment.kind === 'url' ? { target: '_blank', rel: 'noopener noreferrer' } : { target: '_top', rel: 'noopener noreferrer' },
    } as object;
    return (
      <Text accessibilityRole="link" style={[linkStyle, { color }]} {...webProps}>
        {segment.text}
      </Text>
    );
  }
  return (
    <Text accessibilityRole="link" style={[linkStyle, { color }]} onPress={() => void Linking.openURL(href)}>
      {segment.text}
    </Text>
  );
}

export function LinkedText({ text, linkColor = colors.accent, prefix, style, ...rest }: LinkedTextProps) {
  const segments = useMemo(() => linkify(text), [text]);
  return (
    <T {...rest} style={[breakAnywhere, style]}>
      {prefix}
      {segments.map((seg, i) => (seg.href ? <Link key={i} segment={seg} color={linkColor} /> : seg.text))}
    </T>
  );
}
