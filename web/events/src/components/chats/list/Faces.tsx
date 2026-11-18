import { useEffect, useState } from 'react';
import { Image, Text, View, type StyleProp, type ViewStyle } from 'react-native';

import { chatFont, web } from '../neon';
import { Avatar } from '@/components/ui';
import { initials } from '@/lib/format';
import { GROUP_COLORS, palette, PARTY_LOGO, useGroupImage } from '@/lib/groups';
import type { ChatItem } from '@/lib/chatList';
import { PROFILE_PHOTOS } from '@/lib/photos';
import { supabase } from '@/lib/supabase';

/** Rond = une personne, carré emoji = un groupe, petit calendrier = une soirée (maquette 1-liste). */
export function ChatFace({ chat, size = 54 }: { chat: ChatItem; size?: number }) {
  if (chat.kind === 'event') return <DateTile iso={chat.event_start} past={chat.event_past} size={size} />;
  if (chat.kind === 'group') return <GroupSquare chat={chat} size={size} />;
  return <PersonFace id={chat.user_id ?? chat.id} name={chat.title} photo={chat.photo} path={chat.avatar_path} size={size} />;
}

const isUrl = (v: string) => /^(https?:|data:|blob:|\/)/.test(v);
const signed = new Map<string, { at: number; url: Promise<string | null> }>();

/** Photo de profil : chat_list donne un chemin (compartiment profile-photos) ; lien signé 1 h, gardé 40 min. */
function useProfilePhoto(photo: string | null): string | null {
  const path = photo && !isUrl(photo) ? photo : null;
  const [got, setGot] = useState<{ path: string; url: string | null } | null>(null);
  useEffect(() => {
    if (!path) return undefined;
    let live = true;
    let hit = signed.get(path);
    if (!hit || Date.now() - hit.at > 40 * 60_000) {
      hit = { at: Date.now(), url: supabase.storage.from(PROFILE_PHOTOS).createSignedUrl(path, 3600).then(({ data }) => data?.signedUrl ?? null, () => null) };
      signed.set(path, hit);
    }
    void hit.url.then((url) => { if (live) setGot({ path, url }); });
    return () => { live = false; };
  }, [path]);
  if (!photo) return null;
  return path ? (got?.path === path ? got.url : null) : photo;
}

/** Couleur stable d'une personne sans photo : une des 6 couleurs de Party. */
function faceColor(id: string) {
  const keys = Object.keys(GROUP_COLORS) as (keyof typeof GROUP_COLORS)[];
  let h = 0;
  for (const ch of id) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return GROUP_COLORS[keys[h % keys.length]!];
}

/** Photo de la personne (chemin à signer, ou lien), sinon ses initiales sur un dégradé de Party. */
export function PersonFace({ id, name, photo: given, path, size = 54 }: { id: string; name: string; photo: string | null; path?: string | null; size?: number }) {
  const photo = useProfilePhoto(given);
  if (!given && path) return <Avatar id={id} name={name} photo={path} size={size} profile={false} />;
  const p = faceColor(id);
  return (
    <View style={[{ width: size, height: size, borderRadius: size / 2, overflow: 'hidden', alignItems: 'center', justifyContent: 'center' },
      web({ backgroundImage: `linear-gradient(135deg, ${p.from}, ${p.to})`, backgroundColor: p.main })]}>
      {photo
        ? <Image source={{ uri: photo }} accessibilityIgnoresInvertColors style={{ width: size, height: size }} resizeMode="cover" />
        : <Text style={[chatFont.display, { color: '#0E0A1F', fontSize: size * 0.35, letterSpacing: -0.3 }]}>{initials(name)}</Text>}
      <View pointerEvents="none" style={[{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: size / 2 },
        web({ boxShadow: 'inset 0 0 0 1px rgba(255,255,255,.12)' })]} />
    </View>
  );
}

/** Tuile du groupe : sa photo, le logo officiel (Membres Vendredi Party) ou son emoji sur le dégradé de sa couleur. */
function GroupSquare({ chat, size }: { chat: ChatItem; size: number }) {
  const given = chat.photo ?? chat.photo_path ?? null;
  const fromPath = useGroupImage({ system: chat.is_vp, photo: given && !isUrl(given) ? given : null });
  const image = chat.is_vp ? PARTY_LOGO : given && isUrl(given) ? given : fromPath;
  const p = palette(chat.color);
  const radius = Math.round(size * 0.315);
  return (
    <View style={[{ width: size, height: size, borderRadius: radius, alignItems: 'center', justifyContent: 'center', overflow: 'hidden' },
      chat.is_vp
        ? web({ backgroundColor: '#0E0A1F', boxShadow: 'inset 0 0 0 1.5px rgba(255,255,255,.28)' })
        : web({ backgroundColor: p.main, backgroundImage: `linear-gradient(135deg, ${p.from}, ${p.to})`,
          boxShadow: `inset 0 0 0 1.5px rgba(255,255,255,.28), 0 8px 18px -10px ${p.to}` })]}>
      {image
        ? <Image source={{ uri: image }} accessibilityIgnoresInvertColors style={{ width: size, height: size }} resizeMode="cover" testID={chat.is_vp ? 'vp-logo' : undefined} />
        : <Text style={{ fontSize: size * 0.5, lineHeight: size * 0.62 }}>{chat.emoji ?? '👯'}</Text>}
      {image ? <View pointerEvents="none" style={[{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, borderRadius: radius },
        web({ boxShadow: 'inset 0 0 0 1.5px rgba(255,255,255,.28)' })]} /> : null}
    </View>
  );
}

const ZURICH = 'Europe/Zurich';

/** Petit calendrier d'une soirée : « VEN. » et le jour, en orange (encre brune) ; sans date : 🗳️ (sondage). */
export function DateTile({ iso, past = false, size = 54, style }: { iso: string | null; past?: boolean; size?: number; style?: StyleProp<ViewStyle> }) {
  const radius = Math.round(size * 0.315);
  const d = iso ? new Date(iso) : null;
  const wd = d ? new Intl.DateTimeFormat('fr-CH', { timeZone: ZURICH, weekday: 'short' }).format(d).replace(/\.?$/, '.') : '';
  const day = d ? new Intl.DateTimeFormat('fr-CH', { timeZone: ZURICH, day: 'numeric' }).format(d) : '';
  const big = size >= 60;
  const small = size <= 44;
  return (
    <View style={[{ width: size, height: size, borderRadius: radius, alignItems: 'center', justifyContent: 'center', opacity: past ? 0.72 : 1 },
      web({ backgroundColor: '#FF9A62', backgroundImage: 'linear-gradient(150deg, #FFC977, #FF7A59)',
        boxShadow: 'inset 0 0 0 1.5px rgba(255,255,255,.3), 0 8px 18px -10px #FF7A59' }), style]}>
      {d ? (
        <>
          <Text style={[chatFont.heavy, { color: '#2A1406', opacity: 0.82, fontSize: small ? 8 : 10, lineHeight: small ? 9 : 12,
            letterSpacing: 0.8, textTransform: 'uppercase' }]}>{wd}</Text>
          <Text style={[chatFont.display, { color: '#2A1406', fontSize: big ? 26 : small ? 17 : 22, lineHeight: big ? 28 : small ? 18 : 24, letterSpacing: -0.6 }]}>{day}</Text>
        </>
      ) : <Text style={{ fontSize: size * 0.42 }}>🗳️</Text>}
    </View>
  );
}
