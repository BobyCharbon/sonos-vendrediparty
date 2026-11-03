import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import type { Attendance } from '@/lib/attendance';
import { plural } from '@/lib/format';
import { enter, transition, useChangedSinceMount } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

import { Avatar, T } from './ui';

type Props = {
  attendance: Attendance;
  /** Grande version (page de l'événement) ; petite sur les cartes de la liste. */
  large?: boolean;
  /** Événement passé : « 12 y étaient », sans invitation à venir. */
  past?: boolean;
};

/**
 * Pastille en haut à droite d'un événement : visages des premiers présents et UN nombre, présents (accompagnants
 * compris) + peut-être (choix de l'admin). Le détail est dans l'étiquette d'accessibilité et, en petit, au toucher.
 * Le nombre « se pose » quand il change ; personne encore : « Sois le 1er ». Événement passé : les présents seulement.
 */
export function AttendeesBadge({ attendance, large = false, past = false }: Props) {
  const { going, maybe, faces } = attendance;
  const total = past ? going : going + maybe;
  const [detailed, setDetailed] = useState(false);
  const changed = useChangedSinceMount(total);
  const size = large ? 30 : 22;
  const detail = `${plural(going, 'présent')}${maybe ? ` · ${maybe} peut-être` : ''}`;
  const label = past
    ? plural(going, 'personne y était', 'personnes y étaient')
    : `${total} ${total > 1 ? 'présents ou peut-être' : 'présent ou peut-être'} : ${detail.replace(' · ', ', ')}`;

  if (total === 0 && !past) {
    return (
      <View accessible accessibilityLabel="Personne n’a encore répondu présent" style={st.wrap}>
        <View style={[st.pill, st.first, large && st.pillLarge]}>
          <T size={large ? 14 : 12} weight="bold" color={colors.accent}>Sois le 1er ✨</T>
        </View>
      </View>
    );
  }

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityHint={past ? undefined : 'Affiche le détail des présents et des peut-être'}
      disabled={past}
      hitSlop={6}
      onPress={() => setDetailed((d) => !d)}
      style={st.wrap}
    >
      <View style={[st.pill, past && st.pillPast, large && st.pillLarge, transition('transform', 240)]}>
        {faces.length ? (
          <View style={st.faces}>
            {faces.map((f, i) => (
              <View key={f.id} style={[st.face, { marginLeft: i ? -size * 0.38 : 0, zIndex: faces.length - i, borderRadius: size }]}>
                <Avatar id={f.id} name={f.name} size={size} photo={f.avatar_url} profile={false} />
              </View>
            ))}
          </View>
        ) : (
          <T size={large ? 16 : 13}>👥</T>
        )}
        {/* La clé change avec le nombre : il est recréé et « se pose » (jamais à l'ouverture de l'écran). */}
        <View key={total} style={changed ? enter('pop') : undefined}>
          <T style={[st.count, large && st.countLarge]} color={past ? colors.muted : colors.mint}>{total}</T>
        </View>
      </View>
      {past && large ? <T size={12} weight="semibold" muted>{going > 1 ? 'y étaient' : 'y était'}</T> : null}
      {!past && (detailed || large) ? (
        <View style={detailed && !large ? enter('drop') : undefined}>
          <T size={large ? 12 : 11} weight="semibold" color={colors.textSoft}>{detail}</T>
        </View>
      ) : null}
    </Pressable>
  );
}

const st = StyleSheet.create({
  wrap: { alignItems: 'flex-end', gap: 3 },
  pill: {
    flexDirection: 'row', alignItems: 'center', gap: 6, paddingLeft: 3, paddingRight: 9, paddingVertical: 3,
    borderRadius: radius.pill, backgroundColor: 'rgba(91,227,166,0.12)', borderWidth: 1, borderColor: 'rgba(91,227,166,0.4)',
    shadowColor: colors.mint, shadowOpacity: 0.35, shadowRadius: 10, shadowOffset: { width: 0, height: 2 },
  },
  pillLarge: { paddingLeft: 4, paddingRight: 12, paddingVertical: 4, gap: 8 },
  pillPast: { backgroundColor: colors.surface2, borderColor: colors.line, shadowOpacity: 0 },
  first: { paddingLeft: 10, paddingRight: 10, paddingVertical: 5, backgroundColor: colors.accentDim, borderColor: 'rgba(255,79,154,0.5)', shadowColor: colors.accent },
  faces: { flexDirection: 'row', alignItems: 'center' },
  face: { borderWidth: 2, borderColor: colors.surface },
  count: { ...font.display, fontSize: 17, lineHeight: 20, fontVariant: ['tabular-nums'] },
  countLarge: { fontSize: 24, lineHeight: 28 },
});
