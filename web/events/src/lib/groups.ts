import { useEffect, useState } from 'react';
import type { ViewStyle } from 'react-native';

import { storeApp } from './features';
import { must, supabase } from './supabase';

/**
 * Groupes : nouveau graphisme (17.11, maquette A « Néon & couvertures »). Chaque groupe porte un emoji (liste fermée)
 * et une des 6 couleurs de Party ; sa couverture = dégradé de sa couleur + son emoji. Photo facultative (17.11, migration
 * 20261117130000) : elle remplace l'emoji et devient la couverture ; Membres Vendredi Party = le logo officiel, fixe.
 * Mêmes listes que la base (migration 20261117100000, contraintes member_groups_emoji_check / _color_check).
 */
export const GROUP_EMOJIS = ['👯', '🎉', '🪩', '⚽', '🏡', '🎲', '🥾', '🎸', '🍕', '🍻', '🍷', '🎂', '🌴', '🎮', '🎤', '🏀'] as const;

/** Emojis proposés au choix : sans 🍻 ni 🍷 dans l'app App Store (refus 1.4.3). */
export const PICKABLE_EMOJIS: readonly string[] = storeApp ? GROUP_EMOJIS.filter((e) => e !== '🍻' && e !== '🍷') : GROUP_EMOJIS;
/** Emoji montré pour un groupe : 🍻 / 🍷 deviennent 🎉 dans l'app App Store (la base garde le choix du groupe). */
export function groupEmoji(emoji?: string | null): string {
  return storeApp && (emoji === '🍻' || emoji === '🍷') ? '🎉' : emoji ?? '';
}

export const GROUP_COLORS = {
  pink: { name: 'Rose', main: '#FF4F9A', from: '#FF8FC0', to: '#FF4F9A', dim: '#3A1730', text: '#FF8FC0' },
  coral: { name: 'Orange', main: '#FFB347', from: '#FFC977', to: '#FF7A59', dim: '#3B2918', text: '#FFD099' },
  mint: { name: 'Vert', main: '#5BE3A6', from: '#7CEDBB', to: '#22B07D', dim: '#123527', text: '#7CEDBB' },
  sky: { name: 'Bleu', main: '#6CC7FF', from: '#8FD6FF', to: '#3D8BFF', dim: '#14304A', text: '#9DDBFF' },
  lavender: { name: 'Lavande', main: '#B9A7FF', from: '#CBBDFF', to: '#7B6CF6', dim: '#2A2440', text: '#CBBDFF' },
  lemon: { name: 'Citron', main: '#FFE27A', from: '#FFEA9C', to: '#FFB347', dim: '#3A3214', text: '#FFE89A' },
} as const;
export type GroupColor = keyof typeof GROUP_COLORS;
export const GROUP_COLOR_KEYS = Object.keys(GROUP_COLORS) as GroupColor[];

/** Couleurs d'un groupe (couleur inconnue : rose, la couleur de Party). */
export function palette(color?: string | null) {
  return GROUP_COLORS[(color && color in GROUP_COLORS ? color : 'pink') as GroupColor];
}

// Propriétés CSS du web (dégradés) : absentes des types de React Native, rendues telles quelles par react-native-web.
const web = (style: ViewStyle & Record<string, unknown>) => style as ViewStyle;

/** Dégradé de la tuile ou de la couverture d'un groupe. */
export function gradient(color?: string | null, angle = 135): ViewStyle {
  const p = palette(color);
  return web({ backgroundColor: p.main, backgroundImage: `linear-gradient(${angle}deg, ${p.from}, ${p.to})` });
}

/** Couverture de la page du groupe : la couleur en haut, qui se fond dans la nuit de Party. */
export function coverGradient(color?: string | null): ViewStyle {
  const p = palette(color);
  return web({ backgroundColor: p.dim,
    backgroundImage: `radial-gradient(120% 90% at 20% 0%, ${p.from}cc, transparent 60%), linear-gradient(180deg, ${p.to} 0%, ${p.dim} 70%, #15102A 100%)` });
}

/** Le groupe de tout le monde s'affiche « Membres Vendredi Party » (son nom en base : Vendredi Party). */
export function groupName(g: { name: string; system?: boolean | null; system_key?: string | null }): string {
  return g.system || g.system_key ? 'Membres Vendredi Party' : g.name;
}

export type GroupFace = { id: string; name: string; avatar_url: string | null };
export type GroupOverview = {
  id: string; name: string; emoji: string; color: GroupColor; system: boolean;
  /** Chemin de la photo du groupe (compartiment group-photos), ou null. */
  photo: string | null;
  /** creator : je l'ai créé ; manage : je gère (créateur ou Admin du site) ; member : j'en fais partie. */
  creator: boolean; manage: boolean; member: boolean;
  /** invite : je peux inviter (qui gère, ou tout membre si « Tous les membres peuvent inviter »). */
  invite?: boolean;
  /** events : je peux créer un événement pour le groupe (23.11, « Qui peut… »). */
  events?: boolean;
  created_by_name: string | null; members: number; faces: GroupFace[];
  last: string | null; last_by: string | null; last_at: string | null; unread: number;
  next_event: { id: string; title: string; starts_at: string | null; date_mode: 'fixed' | 'poll' } | null;
};

/** Mes groupes (créés ou dont je fais partie), Vendredi Party d'abord puis le plus récent (base : my_groups_overview). */
export async function fetchMyGroups(): Promise<GroupOverview[]> {
  return (must(await supabase.rpc('my_groups_overview')) ?? []) as GroupOverview[];
}

/** Personne trouvée par « Numéro exact ou nom » : surnom, photo, initiale du nom ; jamais son numéro. */
export type GroupFound = { id: string; display_name: string; avatar_url: string | null; initial: string | null; invited: boolean };

/** Numéro complet (« +41 79… », « 079… », comme la connexion SMS) → la personne si elle a un compte ; nom, prénom ou
 * surnom (3 lettres au moins) → 5 personnes au plus. 30 recherches par heure (base : group_people_search). */
export async function searchPeople(group: string, q: string): Promise<GroupFound[]> {
  return (must(await supabase.rpc('group_people_search', { grp: group, q })) ?? []) as GroupFound[];
}

/** Événements du groupe que je peux voir, à venir d'abord (base : group_events). */
export async function fetchGroupEventIds(group: string): Promise<{ id: string; upcoming: boolean }[]> {
  return (must(await supabase.rpc('group_events', { grp: group })) ?? []) as { id: string; upcoming: boolean }[];
}

/** Étiquette du groupe sur une carte d'événement : seulement les groupes dont je fais partie (jamais le nom d'un autre). */
export type GroupLook = Pick<GroupOverview, 'id' | 'name' | 'emoji' | 'color' | 'system'>;

/** Photo de groupe : compartiment privé, dossier = le groupe (lisible par ses membres seulement). */
export const GROUP_PHOTOS = 'group-photos';
/** Membres Vendredi Party : le logo officiel de Party, que personne ne change. */
export const PARTY_LOGO = '/static/icon-192.png';

const signed = new Map<string, { at: number; url: Promise<string | null> }>();

/** Lien signé (1 h) d'une photo de groupe, gardé 40 min : la même image d'un écran à l'autre, sans rechargement. */
export function signGroupPhoto(path: string): Promise<string | null> {
  const hit = signed.get(path);
  if (hit && Date.now() - hit.at < 40 * 60_000) return hit.url;
  const url = supabase.storage.from(GROUP_PHOTOS).createSignedUrl(path, 3600)
    .then(({ data }) => data?.signedUrl ?? null, () => null);
  signed.set(path, { at: Date.now(), url });
  return url;
}

/** Image d'un groupe : logo de Party pour Membres Vendredi Party, sa photo (lien signé) sinon, null : son emoji. */
export function useGroupImage(group: { system?: boolean | null; system_key?: string | null; photo?: string | null; photo_path?: string | null }): string | null {
  const system = !!(group.system || group.system_key);
  const path = system ? null : group.photo ?? group.photo_path ?? null;
  const [signedFor, setSigned] = useState<{ path: string; url: string | null } | null>(null);
  useEffect(() => {
    let live = true;
    if (path) void signGroupPhoto(path).then((url) => { if (live) setSigned({ path, url }); });
    return () => { live = false; };
  }, [path]);
  return system ? PARTY_LOGO : signedFor && signedFor.path === path ? signedFor.url : null;
}

/** Pose (ou retire, uri null) la photo du groupe : envoi de la photo recadrée, puis l'ancien fichier part. */
export async function saveGroupPhoto(groupId: string, uri: string | null, old: string | null): Promise<void> {
  let path: string | null = null;
  if (uri) {
    const blob = await fetch(uri).then((r) => r.blob()).catch(() => null);
    if (!blob) throw new Error('La photo n’a pas pu être lue. Choisis-la à nouveau.');
    if (blob.size > 5 * 1024 * 1024) throw new Error('La photo est trop volumineuse. Choisis-en une autre.');
    path = `${groupId}/${Date.now()}-${Math.random().toString(36).slice(2)}.jpg`;
    const { error } = await supabase.storage.from(GROUP_PHOTOS).upload(path, blob, { contentType: 'image/jpeg', upsert: false });
    if (error) throw new Error('La photo n’a pas pu être envoyée. Vérifie ta connexion puis réessaie.');
  }
  // « Modifier le nom, l'emoji et la photo » (23.11) : la base vérifie le droit (set_group_photo) ; base d'avant : la table.
  let { error } = await supabase.rpc('set_group_photo', { grp: groupId, path });
  if (error?.code === 'PGRST202') ({ error } = await supabase.from('member_groups').update({ photo_path: path }).eq('id', groupId));
  if (error) {
    if (path) void supabase.storage.from(GROUP_PHOTOS).remove([path]);
    throw error;
  }
  if (old && old !== path) void supabase.storage.from(GROUP_PHOTOS).remove([old]);
}
