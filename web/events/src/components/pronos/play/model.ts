import type { TextStyle, ViewStyle } from 'react-native';

import { addDays, dayKey, minutesOf, zdate } from '@/lib/agenda';
import type { Face, Prono } from '@/lib/pronos';
import type { ShapeKey } from '@/components/pronos/Kit';

/**
 * Fiche d'un prono, Pronos v2 (maquettes 3-*, 18.11.2026) : clés de la fiche (prono_json) ajoutées par la migration
 * 20261118090000, toutes facultatives ici (la base les ajoute, l'écran ne casse pas sans elles), réponse à envoyer,
 * formes des réponses, heure de Suisse. Les patates ne s'affichent que si `patates_on` ET `patates` sont vrais.
 */

export type PlayKind = 'choice' | 'number' | 'text' | 'person' | 'yesno' | 'overunder' | 'when' | 'majority' | 'award';

export type Bag = { balance: number; refill_at?: string | null; max_stake?: number };
export type Contest = {
  until: string; open: boolean; contested: boolean; fair: number; unfair: number; my_vote: boolean | null;
  can_contest: boolean; can_vote: boolean; reason?: string | null; by?: Face | null;
};
export type Reaction = { emoji: string; count: number; mine: boolean };

type Answer = { option_id: string | null; number: number | null; text: string | null; person_id?: string | null; winner: boolean;
  stake?: number | null; answer_at?: string | null; harvest?: number | null };

export type PronoV2 = Omit<Prono, 'kind' | 'my_answer' | 'result'> & {
  kind: PlayKind;
  my_answer: Answer | null;
  result: (NonNullable<Prono['result']> & { time?: string | null }) | null;
  patates_on?: boolean; patates?: boolean;
  line?: number | null; not_over?: boolean; rules?: string | null; template?: string | null; award?: string | null;
  terrain?: { kind: 'group' | 'event'; id: string } | null;
  field?: { total: number; planters: number; by_option?: { option_id: string; total: number }[] } | null;
  bag?: Bag | null;
  settled?: boolean;
  contest?: Contest | null;
  rarity?: { right: number; of: number } | null;
  reactions?: Reaction[];
  optout?: boolean;
  can_happen?: boolean;
  unanimous?: boolean;
};

/** Les patates se montrent-elles sur ce prono ? (réglage de la base ET prono avec patates ; jamais trophée ni libre). */
export const withPatates = (p: PronoV2) => !!p.patates_on && !!p.patates && p.kind !== 'award' && p.kind !== 'text';

/** Choix tranchés par l'organisateur parmi des options (pastilles, Oui / Non, Plus / Moins). */
export const OPTION_KINDS: PlayKind[] = ['choice', 'yesno', 'overunder', 'majority'];

// ───────── Couleurs et typo de la direction C « Néon club » (maquettes 3-*) ─────────
export const C = {
  t1: '#F4F1FF', t2: '#A79FC7', t3: '#8C84AE', s1: '#1A1433', bg: '#0E0A1F', line: 'rgba(255,255,255,0.08)',
  glass: 'rgba(255,255,255,0.06)', glassLine: 'rgba(255,255,255,0.10)',
  lav: '#B9A7FF', lavDeep: '#7B6CF6', mint: '#5BE3A6', lemon: '#FFE27A', amber: '#FFB347', soft: '#FF7A8A', missed: '#8B84A8',
  patate: '#F5C27A', patateInk: '#2A1A06', action: '#D42A76', accent: '#FF4F9A', sky: '#6CC7FF', pink: '#FF6FAE',
};

const ROUNDED = 'ui-rounded, "SF Pro Rounded", -apple-system, system-ui, sans-serif';
type WebText = TextStyle & Record<string, unknown>;
export const rounded = (size: number, weight: '700' | '800' | '900' = '800'): TextStyle =>
  ({ fontFamily: ROUNDED, fontSize: size, fontWeight: weight, color: C.t1 }) as TextStyle;
export const wide = (size: number, color: string = C.t1): TextStyle =>
  ({ fontFamily: '-apple-system, system-ui, sans-serif', fontSize: size, fontWeight: '800', color, fontStretch: 'expanded',
    fontVariant: ['tabular-nums'], letterSpacing: 0.5 } as WebText) as TextStyle;
export const webView = (style: Record<string, unknown>) => style as ViewStyle;

// ───────── Formes : forme + couleur + texte, jamais la couleur seule ─────────
export const SHAPES: { key: ShapeKey; glyph: string; color: string; name: string }[] = [
  { key: 'triangle', glyph: '▲', color: '#FF6FAE', name: 'triangle' },
  { key: 'diamond', glyph: '◆', color: '#6CC7FF', name: 'losange' },
  { key: 'circle', glyph: '●', color: '#FFB347', name: 'rond' },
  { key: 'square', glyph: '■', color: '#B9A7FF', name: 'carré' },
  { key: 'hexagon', glyph: '⬢', color: '#5BE3A6', name: 'hexagone' },
  { key: 'star', glyph: '★', color: '#FFE27A', name: 'étoile' },
  { key: 'down', glyph: '▼', color: '#FF9F5A', name: 'triangle vers le bas' },
  { key: 'plus', glyph: '✚', color: '#9DDBFF', name: 'croix' },
];
export const shapeAt = (i: number) => SHAPES[i % SHAPES.length];

// ───────── Ce qu'on envoie à prono_answer / prono_result ─────────
export type Draft = { option_id?: string | null; person_id?: string | null; number?: number | null; text?: string; at?: string | null };

export function draftFrom(p: PronoV2, pick?: string | null): Draft {
  const a = p.my_answer;
  const picked = pick && p.options.some((o) => o.id === pick) ? pick : null;
  return { option_id: picked ?? a?.option_id ?? null, person_id: a?.person_id ?? null, number: a?.number ?? null,
    text: a?.text ?? '', at: a?.answer_at ?? (p.kind === 'when' ? whenAt(p, Math.round((whenMinutes(p.closes_at) ?? 1320) / 30) * 30 % 1440) : null) };
}

export function draftReady(p: PronoV2, d: Draft): boolean {
  if (OPTION_KINDS.includes(p.kind)) return !!d.option_id;
  if (p.kind === 'person' || p.kind === 'award') return !!d.person_id;
  if (p.kind === 'number') return d.number != null && Number.isFinite(d.number);
  if (p.kind === 'when') return !!d.at;
  return !!d.text?.trim();
}

/** Corps de prono_answer : la réponse, et les patates plantées (0 à 20) quand le prono en a. */
export function answerBody(p: PronoV2, d: Draft, planted: number): Record<string, unknown> {
  const body: Record<string, unknown> = OPTION_KINDS.includes(p.kind) ? { option_id: d.option_id }
    : p.kind === 'person' || p.kind === 'award' ? { person_id: d.person_id }
      : p.kind === 'number' ? { number: d.number }
        : p.kind === 'when' ? { answer_at: d.at }
          : { text: d.text?.trim() };
  if (withPatates(p)) body.stake = planted;
  return body;
}

/** La réponse en mots (résumé au-dessus du bouton, réponse scellée). */
export function draftLabel(p: PronoV2, d: Draft): string {
  if (OPTION_KINDS.includes(p.kind)) return p.options.find((o) => o.id === d.option_id)?.label ?? '';
  if (p.kind === 'person' || p.kind === 'award') {
    const who = p.candidates?.find((c) => c.id === d.person_id);
    return who ? (who.me ? 'Toi' : who.name) : '';
  }
  if (p.kind === 'number') return d.number == null ? '' : String(d.number).replace('.', ',');
  if (p.kind === 'when') return d.at ? hhmm(d.at) : '';
  return d.text?.trim() ?? '';
}

// ───────── Heure de Suisse (prono « heure ») ─────────
const pad = (n: number) => String(n).padStart(2, '0');
export const hhmm = (iso: string) => { const m = minutesOf(new Date(iso)); return `${pad(Math.floor(m / 60))}:${pad(m % 60)}`; };

/** Jour du prono « heure » : celui de l'événement, sinon celui de la fin des réponses. Avant 6 h : la nuit d'après. */
export function whenBase(p: PronoV2): string {
  return dayKey(new Date(p.event?.starts_at ?? p.closes_at));
}
export function whenAt(p: PronoV2, minutes: number): string {
  const base = whenBase(p);
  return zdate(minutes < 6 * 60 ? addDays(base, 1) : base, minutes).toISOString();
}
export function whenMinutes(iso: string | null | undefined): number | null {
  return iso ? minutesOf(new Date(iso)) : null;
}

/** « 2 j 04 h », « 42 min », « 11 h » : temps restant, en mots courts. */
export function leftText(iso: string, now = Date.now()): string {
  const s = Math.max(0, Math.round((new Date(iso).getTime() - now) / 1000));
  if (s >= 86400) return `${Math.floor(s / 86400)} j ${pad(Math.floor((s % 86400) / 3600))} h`;
  if (s >= 3600) return `${Math.floor(s / 3600)} h`;
  if (s >= 60) return `${Math.floor(s / 60)} min`;
  return `${s} s`;
}

export const meName = (f: Face) => (f.me ? 'Toi' : f.name);

/** « 7,5 » */
export const decimal = (n: number) => String(n).replace('.', ',');
