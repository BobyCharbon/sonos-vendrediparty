import { Pressable, Text, View } from 'react-native';

import { C, cf, dateTileFill, Icon, web } from './kit';
import { GroupTile } from '../../GroupBits';
import { Avatar } from '../../ui';
import { dateTile } from '@/lib/format';
import { pressTransition } from '@/lib/motion';

export type HeaderLook =
  | { kind: 'direct'; userId: string; photo: string | null }
  | { kind: 'group'; emoji: string; color: string | null; photo_path: string | null; system_key: string | null }
  | { kind: 'event'; start: string | null };

type Props = {
  title: string;
  /** Sous le nom : « écrit… » (menthe), « 12 membres », « Demande de message »… */
  subtitle: string | null;
  typing: boolean;
  look: HeaderLook;
  /** Non lus des autres discussions (chat_badge), à côté de ‹ comme Messages. */
  unread: number;
  onBack: () => void;
  /** Toucher le nom ou la photo : mini-profil (direct), infos (groupe, soirée). */
  onWho: () => void;
  whoLabel: string;
  onInfo: () => void;
  infoLabel: string;
  infoOpen: boolean;
};

/** En-tête de la conversation (maquette 4) : ‹ + non lus, photo / tuile du groupe / tuile date, nom en Bricolage,
 * « écrit… » ou le nombre de membres, … pour les infos. Flou et dégradé sombre, liseré en bas. */
export function ChatHeader({ title, subtitle, typing, look, unread, onBack, onWho, whoLabel, onInfo, infoLabel, infoOpen }: Props) {
  return (
    <View style={[{ zIndex: 3, borderBottomWidth: 1, borderBottomColor: C.line },
      web({ backgroundImage: 'linear-gradient(180deg, rgba(14,10,31,0.96), rgba(14,10,31,0.82))', backdropFilter: 'blur(20px) saturate(1.5)' })]}>
      <View style={{ height: 58, flexDirection: 'row', alignItems: 'center', gap: 2, paddingLeft: 4, paddingRight: 6 }}>
        <Pressable accessibilityRole="button" accessibilityLabel={unread ? `Retour aux Discussions, ${unread} non lus` : 'Retour aux Discussions'}
          onPress={onBack} style={({ pressed }) => [{ minWidth: 44, height: 44, flexDirection: 'row', alignItems: 'center', gap: 2, paddingHorizontal: 4 },
            pressTransition, pressed && { opacity: 0.5 }]}>
          <Icon name="chevl" size={26} color={C.lav} />
          {unread ? (
            <View style={{ minWidth: 24, height: 24, borderRadius: 12, paddingHorizontal: 6, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(185,167,255,0.16)' }}>
              <Text style={[cf.bold, { color: C.lav, fontSize: 13 }]}>{unread > 99 ? '99+' : unread}</Text>
            </View>
          ) : null}
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={whoLabel} onPress={onWho}
          style={({ pressed }) => [{ flex: 1, minWidth: 0, height: 52, flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 6, borderRadius: 14 },
            pressTransition, pressed && { backgroundColor: C.glass }]}>
          <Face look={look} title={title} />
          <View style={{ flex: 1, minWidth: 0 }}>
            <Text numberOfLines={1} style={[cf.display, { color: C.t1, fontSize: 18, lineHeight: 22 }]}>{title}</Text>
            {typing ? (
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 5 }}>
                <View style={[{ width: 7, height: 7, borderRadius: 4, backgroundColor: C.mint }, web({ boxShadow: `0 0 8px ${C.mint}` })]} />
                <Text numberOfLines={1} style={[cf.semibold, { color: C.mint, fontSize: 13, lineHeight: 16 }]}>{subtitle}</Text>
              </View>
            ) : subtitle ? (
              <Text numberOfLines={1} style={[cf.text, { color: C.t2, fontSize: 13, lineHeight: 16 }]}>{subtitle}</Text>
            ) : null}
          </View>
        </Pressable>
        <Pressable accessibilityRole="button" accessibilityLabel={infoLabel} accessibilityState={{ expanded: infoOpen }} onPress={onInfo}
          style={({ pressed }) => [{ width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
            infoOpen && { backgroundColor: 'rgba(185,167,255,0.16)' }, pressTransition, pressed && { opacity: 0.5 }]}>
          <Icon name={infoOpen ? 'x' : 'more'} color={C.lav} stroke={infoOpen ? 2 : 2.6} />
        </Pressable>
      </View>
    </View>
  );
}

function Face({ look, title }: { look: HeaderLook; title: string }) {
  if (look.kind === 'direct') return <Avatar id={look.userId} name={title} photo={look.photo} size={40} profile={false} />;
  if (look.kind === 'group') {
    return <GroupTile group={{ emoji: look.emoji, color: look.color, photo_path: look.photo_path, system_key: look.system_key }} size={40} />;
  }
  const tile = look.start ? dateTile(look.start) : null;
  return (
    <View style={[{ width: 40, height: 40, borderRadius: 13, alignItems: 'center', justifyContent: 'center' }, dateTileFill]}>
      {tile ? (
        <>
          <Text style={[cf.label, { fontSize: 8, lineHeight: 9, color: '#2A1406', opacity: 0.82 }]}>{tile.weekday}</Text>
          <Text style={[cf.display, { fontSize: 17, lineHeight: 18, color: '#2A1406' }]}>{tile.day}</Text>
        </>
      ) : <Text style={{ fontSize: 20 }}>🎉</Text>}
    </View>
  );
}
