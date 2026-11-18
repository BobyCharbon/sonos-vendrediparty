import { useEffect, useState } from 'react';
import type { TextStyle, ViewStyle } from 'react-native';

import { formatShort } from '@/lib/format';
import { palette } from '@/lib/groups';
import { rpc, type Face, type PronoCard, type Prono } from '@/lib/pronos';

/**
 * Pronos v2, listes (maquettes 1-*, direction C « Néon club », 18.11) : jetons propres aux listes, clés v2 lues en
 * facultatif (la base les ajoute, migration 20261118090000), tri des onglets et sacs de patates par terrain.
 * Patates : rien n'apparaît si la base dit `patates_on: false` (les pronos restent pour l'honneur, aux points).
 */

type WebStyle = ViewStyle & Record<string, unknown>;
export const web = (style: WebStyle) => style as ViewStyle;

/** Jetons de 1-kit.css (sombre : le module web est en nuit violette). */
export const C = {
  bg: '#0E0A1F', s1: '#1A1433', s1b: '#211943', s2: 'rgba(37,29,71,0.80)', s3: 'rgba(255,255,255,0.06)',
  line: 'rgba(255,255,255,0.08)', line2: 'rgba(255,255,255,0.14)',
  t1: '#F4F1FF', t2: '#A79FC7', t3: '#857DA8',
  lav: '#B9A7FF', lavB: '#7B6CF6', pink: '#FF4F9A', pinkFill: '#D42A76', pinkInk: '#FF6FAE',
  mint: '#5BE3A6', gold: '#FFE27A', miss: '#8B84A8', amber: '#FFB347',
  chipDark: 'rgba(14,10,31,0.55)',
};
const ROUNDED = 'ui-rounded, "SF Pro Rounded", -apple-system, system-ui, sans-serif';
const TEXT = '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif';
/** Questions et titres : ui-rounded 800. */
export const round = (size: number, line = Math.round(size * 1.18)): TextStyle =>
  ({ fontFamily: ROUNDED, fontWeight: '800', fontSize: size, lineHeight: line, letterSpacing: -0.01 * size, color: C.t1 });
/** Chiffres : élargis, tabulaires. */
export const num = (size: number): TextStyle =>
  ({ fontFamily: TEXT, fontWeight: '800', fontSize: size, lineHeight: size, fontVariant: ['tabular-nums'],
    ...({ fontStretch: '112%' } as object) });
export const label: TextStyle = { fontFamily: TEXT, fontSize: 11, lineHeight: 14, fontWeight: '700', letterSpacing: 0.9,
  textTransform: 'uppercase', color: C.t2 };

/** Formes des réponses (jamais la couleur seule) : ▲ rose, ◆ ciel, ● orange, ■ lavande… */
export const SHAPES = [
  { glyph: '▲', color: '#FF6FAE', name: 'triangle' }, { glyph: '◆', color: '#8FD6FF', name: 'losange' },
  { glyph: '●', color: '#FFC977', name: 'rond' }, { glyph: '■', color: '#CBBDFF', name: 'carré' },
  { glyph: '★', color: '#7CEDBB', name: 'étoile' }, { glyph: '⬟', color: '#FFEA9C', name: 'pentagone' },
  { glyph: '⬢', color: '#FF8FC0', name: 'hexagone' }, { glyph: '✚', color: '#9DDBFF', name: 'croix' },
];
export const shape = (i: number) => SHAPES[i % SHAPES.length];

export const NO_VALUE = "Les patates n'ont aucune valeur : elles ne s'achètent pas, ne se vendent pas, ne s'échangent pas.";

// ───────── Données (clés v2 facultatives) ─────────
export type Cover = { color?: string | null; emoji?: string | null; photo?: string | null } | null;
export type Kind = PronoCard['kind'] | 'yesno' | 'overunder' | 'when' | 'majority' | 'award';

export type ListCard = Omit<PronoCard, 'kind'> & {
  kind: Kind; patates?: boolean; patates_on?: boolean; field_total?: number | null; planters?: number | null;
  my_stake?: number | null; my_harvest?: number | null; template?: string | null; award?: string | null;
  closes_soon?: boolean; cover?: Cover; settled?: boolean; unanimous?: boolean;
};

export type Detail = Omit<Prono, 'kind'> & {
  kind: Kind; line?: number | null; not_over?: boolean; award?: string | null; patates?: boolean; patates_on?: boolean;
  field?: { total: number; planters: number; by_option?: { option_id: string; total: number }[] } | null;
  my_answer: (Prono['my_answer'] & { answer_at?: string | null; stake?: number | null; harvest?: number | null }) | null;
  result: (NonNullable<Prono['result']> & { time?: string | null }) | null;
  settled?: boolean; unanimous?: boolean; can_happen?: boolean;
  contest?: { until: string; open: boolean; contested: boolean } | null;
  rarity?: { right: number; of: number } | null;
  reactions?: { emoji: string; count: number; mine: boolean }[];
};

export type Bag = { balance: number; refill_at: string | null; max_stake?: number; patates_on?: boolean;
  season?: { month: string; harvest_net: number } | null };

export type Terrain = { key: string; kind: 'group' | 'event'; id: string; name: string; emoji: string; color: string | null };

/** Le terrain (sac) d'un prono à patates : son groupe, sinon son événement. */
export function terrainOf(p: ListCard): Terrain | null {
  if (p.group) return { key: `g:${p.group.id}`, kind: 'group', id: p.group.id, name: p.group.name, emoji: p.group.emoji, color: p.group.color };
  if (p.event) return { key: `e:${p.event.id}`, kind: 'event', id: p.event.id, name: p.event.title, emoji: p.cover?.emoji ?? '🎉', color: p.cover?.color ?? 'lavender' };
  return null;
}

export const bagArgs = (t: { kind: 'group' | 'event'; id: string }) => (t.kind === 'group' ? { group_id: t.id } : { event_id: t.id });
export const fetchBag = (t: { kind: 'group' | 'event'; id: string }) => rpc<Bag | null>('prono_bag', bagArgs(t)).catch(() => null);
export const sacPath = (t: { kind: 'group' | 'event'; id: string }) => `/prono-sac?${t.kind}=${t.id}`;

/** Les patates sont-elles en jeu pour ce prono ? (réglage de la base ET prono à patates) */
export const withPatates = (p: { patates?: boolean; patates_on?: boolean }) => !!p.patates && p.patates_on !== false;

export type Tab = 'play' | 'wait' | 'done';
/** À jouer : ouverts pas joués ; En attente : joués encore ouverts + fermés sans résultat ; Terminés. */
export function tabOf(p: ListCard): Tab {
  if (p.state === 'open') return p.answered ? 'wait' : 'play';
  if (p.state === 'closed') return 'wait';
  return 'done';
}
const at = (iso: string) => new Date(iso).getTime();
export const byClose = (a: ListCard, b: ListCard) => at(a.closes_at) - at(b.closes_at);
export const soon = (p: ListCard, now = Date.now()) => p.closes_soon ?? (p.state === 'open' && at(p.closes_at) - now < 3600_000);

/** Couleurs (dégradé) de la couverture d'une carte : celles du groupe, sinon de l'événement (lavande par défaut). */
export function coverOf(p: ListCard) {
  const color = p.group?.color ?? p.cover?.color ?? 'lavender';
  const emoji = p.group?.emoji ?? p.cover?.emoji ?? (p.event ? '🎉' : '🔮');
  return { pal: palette(color), emoji };
}

/** « 🧀 Raclette chez Léa » / « 📅 Soirée » / « Proposé par Marc ». */
export function contextLine(p: ListCard): string {
  if (p.group) return `${p.group.emoji} ${p.group.name}`;
  if (p.event) return `${p.cover?.emoji ?? '📅'} ${p.event.title}`;
  return `Proposé par ${p.creator.me ? 'toi' : p.creator.name}`;
}

/** Réponse lisible d'après la fiche (my_answer, résultat). */
export function answerText(d: Detail, a: { option_id?: string | null; number?: number | null; text?: string | null; person_id?: string | null;
  person?: Face | null; answer_at?: string | null; time?: string | null } | null): string {
  if (!a) return '';
  const when = a.answer_at ?? a.time;
  if (d.kind === 'when' && when) return clock(when);
  if (a.option_id) return d.options.find((o) => o.id === a.option_id)?.label ?? '';
  if (a.number != null) return String(a.number).replace('.', ',');
  const who = a.person ?? d.candidates?.find((c) => c.id === a.person_id) ?? null;
  if (who) return who.me ? 'Toi' : who.name;
  return a.text ?? '';
}

/** « 20 h 40 » (heure de Suisse). */
export function clock(iso: string): string {
  const parts = new Intl.DateTimeFormat('fr-CH', { hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Zurich' }).formatToParts(new Date(iso));
  const h = parts.find((x) => x.type === 'hour')?.value ?? '';
  const m = parts.find((x) => x.type === 'minute')?.value ?? '';
  return `${Number(h)} h ${m}`;
}

/** « dans 3 h », « dans 12 min » (délai court, contestation). */
export function inTime(iso: string, now = Date.now()): string {
  const min = Math.max(1, Math.round((new Date(iso).getTime() - now) / 60_000));
  return min < 60 ? `dans ${min} min` : `dans ${Math.round(min / 60)} h`;
}

/** « Jusqu'à jeu. 19 h » pour une fin lointaine. */
export const untilLine = (iso: string) => `Jusqu’au ${formatShort(iso)}`;

export function monthName(iso?: string | null): string {
  const d = iso ? new Date(iso) : new Date();
  return new Intl.DateTimeFormat('fr-CH', { month: 'long', timeZone: 'Europe/Zurich' }).format(d);
}

/** L'heure, relue toutes les 30 s (cartes « ça ferme bientôt », compte à rebours long). */
export function useNow(everyMs = 30_000): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), everyMs);
    return () => clearInterval(t);
  }, [everyMs]);
  return now;
}
