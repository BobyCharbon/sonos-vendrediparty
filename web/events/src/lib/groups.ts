import type { ViewStyle } from 'react-native';

import { must, supabase } from './supabase';

/**
 * Groupes : nouveau graphisme (17.11, maquette A « Néon & couvertures »). Chaque groupe porte un emoji (liste fermée)
 * et une des 6 couleurs de Party ; sa couverture = dégradé de sa couleur + son emoji (aucune photo : contenu à modérer).
 * Mêmes listes que la base (migration 20261117100000, contraintes member_groups_emoji_check / _color_check).
 */
export const GROUP_EMOJIS = ['👯', '🎉', '🪩', '⚽', '🏡', '🎲', '🥾', '🎸', '🍕', '🍻', '🍷', '🎂', '🌴', '🎮', '🎤', '🏀'] as const;

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
  /** creator : je l'ai créé ; manage : je gère (créateur ou Admin du site) ; member : j'en fais partie. */
  creator: boolean; manage: boolean; member: boolean;
  created_by_name: string | null; members: number; faces: GroupFace[];
  last: string | null; last_by: string | null; last_at: string | null; unread: number;
  next_event: { id: string; title: string; starts_at: string | null; date_mode: 'fixed' | 'poll' } | null;
};

/** Mes groupes (créés ou dont je fais partie), Vendredi Party d'abord puis le plus récent (base : my_groups_overview). */
export async function fetchMyGroups(): Promise<GroupOverview[]> {
  return (must(await supabase.rpc('my_groups_overview')) ?? []) as GroupOverview[];
}

export type GroupSuggestion = { id: string; display_name: string; avatar_url: string | null; together: number; last_title: string | null; invited: boolean };

/** « Déjà sur Party » : les personnes croisées à un événement, jamais tout le site (base : group_invite_suggestions). */
export async function fetchSuggestions(group: string): Promise<GroupSuggestion[]> {
  return (must(await supabase.rpc('group_invite_suggestions', { grp: group })) ?? []) as GroupSuggestion[];
}

/** Événements du groupe que je peux voir, à venir d'abord (base : group_events). */
export async function fetchGroupEventIds(group: string): Promise<{ id: string; upcoming: boolean }[]> {
  return (must(await supabase.rpc('group_events', { grp: group })) ?? []) as { id: string; upcoming: boolean }[];
}

/** Étiquette du groupe sur une carte d'événement : seulement les groupes dont je fais partie (jamais le nom d'un autre). */
export type GroupLook = Pick<GroupOverview, 'id' | 'name' | 'emoji' | 'color' | 'system'>;
