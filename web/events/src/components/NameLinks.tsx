import { Fragment } from 'react';
import { StyleSheet, Text } from 'react-native';

import { openMiniProfile } from '@/lib/miniProfile';
import { colors } from '@/lib/theme';

import { T } from './ui';

/** Une personne citée : son identifiant (fiche profil) et ce qu'on écrit (« Léa ») ; `after` : « (Oui) »… */
export type NamedPerson = { id: string; label: string; after?: string };

/** Ouvre le mini-profil d'un membre (même feuille que les pastilles des participants). */
export function openProfile(id: string) {
  openMiniProfile(id);
}

/**
 * Liste de noms où chaque nom se touche pour ouvrir la fiche profil (avis 36c47b3d1f82) : « Absents : Léa, Tom »,
 * votants d'une date, d'un mini-sondage, qui amène quoi… Le texte autour (préfixe, « (Oui) ») reste du texte simple.
 */
export function NameLinks({ people, prefix, size = 12, separator = ', ', testID }: {
  people: NamedPerson[];
  prefix?: string;
  size?: number;
  separator?: string;
  testID?: string;
}) {
  if (!people.length) return null;
  return (
    <T muted size={size}>
      {prefix}
      {people.map((p, i) => (
        <Fragment key={`${p.id}:${i}`}>
          {i ? separator : ''}
          <Text accessibilityRole="link" accessibilityLabel={`Profil de ${p.label}`} testID={testID ? `${testID}-${p.id}` : undefined}
            onPress={() => openProfile(p.id)} style={[st.link, { fontSize: size }]}>
            {p.label}
          </Text>
          {p.after ?? ''}
        </Fragment>
      ))}
    </T>
  );
}

const st = StyleSheet.create({
  link: { color: colors.textSoft, fontWeight: '600', textDecorationLine: 'underline', textDecorationColor: colors.line },
});
