import { useCallback, useEffect, useState } from 'react';

import { useSignal } from './data';
import { formatShort } from './format';
import type { GroupColor } from './groups';
import { supabase } from './supabase';

/**
 * Pronos entre amis (avis f071c5f46e3d, 17.11.2026, migration 20261117180000). Pour l'honneur : jamais d'argent, de mise,
 * de pot, de lot ni d'enjeu (revue de conformité) ; des points au classement du groupe. La base garde les réponses
 * cachées (organisateur compris) jusqu'au dévoilement et décide de tout ; ces fonctions ne font que l'appeler.
 * Dans l'app iPhone, les pronos sont des écrans NATIFS (window.PartyNative.pronos) : les pages web s'y effacent.
 */

export type Face = { id: string; name: string; avatar_url: string | null; me?: boolean };
export type PronoKind = 'choice' | 'number' | 'text' | 'person';
export type PronoState = 'open' | 'closed' | 'done' | 'cancelled';
export type Reveal = 'close' | 'result';

export type Prono = {
  id: string; question: string; kind: PronoKind; points: number; closes_at: string; reveal: Reveal; state: PronoState;
  revealed: boolean; created_at: string; mine: boolean; locked: boolean; creator: Face;
  group: { id: string; name: string; emoji: string; color: GroupColor; photo: string | null } | null;
  event: { id: string; title: string; starts_at: string | null } | null;
  options: { id: string; label: string; count: number | null; correct: boolean | null }[];
  candidates: Face[] | null;
  my_answer: { option_id: string | null; number: number | null; text: string | null; person_id: string | null; winner: boolean } | null;
  answered: Face[]; players: number;
  answers: { user: Face; option_id: string | null; number: number | null; text: string | null; hidden: boolean; person: Face | null; winner: boolean }[] | null;
  result: { option_id: string | null; number: number | null; person: Face | null; at: string } | null;
  winners: Face[] | null;
  can_answer: boolean; can_edit: boolean; can_move_end: boolean; can_result: boolean; can_cancel: boolean;
  link: { token: string | null; path: string | null } | null;
};

export type PronoCard = {
  id: string; question: string; kind: PronoKind; points: number; closes_at: string; state: PronoState; revealed: boolean;
  mine: boolean; creator: Face; group: Prono['group']; event: { id: string; title: string } | null;
  answered_count: number; players: number; faces: Face[]; answered: boolean; won: boolean;
  winners: Face[] | null; winners_count: number | null;
};

export type Board = { since: string | null; manage: boolean; pronos: number; rows: { user: Face; points: number; right: number; played: number }[] };

export class PronoError extends Error {
  code: string;
  constructor(raw: string) {
    const m = /^([a-z_]+): (.*)$/s.exec(raw ?? '');
    super(m ? m[2].charAt(0).toUpperCase() + m[2].slice(1) : 'Ça n’a pas marché. Réessaie dans un instant.');
    this.code = m ? m[1] : 'error';
  }
}

export async function rpc<T>(fn: string, args?: Record<string, unknown>): Promise<T> {
  const { data, error } = await supabase.rpc(fn, args ?? {});
  if (error) throw new PronoError(error.message);
  return data as T;
}

export const isTerms = (e: unknown) => e instanceof PronoError && e.code === 'terms_required';
export const errorText = (e: unknown) => (e instanceof Error ? e.message : 'Ça n’a pas marché. Réessaie dans un instant.');

export const KINDS: { key: PronoKind; label: string; hint: string }[] = [
  { key: 'choice', label: 'Choix', hint: 'De 2 à 8 réponses possibles' },
  { key: 'person', label: 'Une personne', hint: 'On choisit quelqu’un du prono' },
  { key: 'number', label: 'Nombre', hint: 'Le plus proche gagne' },
  { key: 'text', label: 'Libre', hint: 'Tu coches les bonnes réponses' },
];

/** « Fin sam. 21.11 à 18:00 », « Fermé », « Terminé ». */
export function stateLine(p: { state: PronoState; closes_at: string; revealed: boolean }): string {
  if (p.state === 'open') return `Fin ${formatShort(p.closes_at)}`;
  if (p.state === 'closed') return p.revealed ? 'Fermé · réponses dévoilées' : 'Fermé · résultat attendu';
  if (p.state === 'done') return 'Terminé';
  return 'Annulé';
}

export function pointsLabel(n: number): string {
  return `${n} point${n > 1 ? 's' : ''}`;
}

/** Où le prono se joue : le groupe, l'événement, ou « Invités de … ». */
export function placeLine(p: { group: Prono['group'] | PronoCard['group']; event: { title: string } | null; creator: Face }): string {
  if (p.group) return `${p.group.emoji} ${p.group.name}`;
  if (p.event) return `📅 ${p.event.title}`;
  return `Proposé par ${p.creator.me ? 'toi' : p.creator.name}`;
}

/** Réponse lisible (dévoilement, ma réponse). */
export function answerLabel(p: Prono, a: { option_id: string | null; number: number | null; text: string | null; person?: Face | null; person_id?: string | null }): string {
  if (p.kind === 'choice') return p.options.find((o) => o.id === a.option_id)?.label ?? '—';
  if (p.kind === 'number') return a.number == null ? '—' : String(a.number);
  if (p.kind === 'person') {
    const who = a.person ?? p.candidates?.find((c) => c.id === a.person_id) ?? null;
    return who ? (who.me ? 'Toi' : who.name) : '—';
  }
  return a.text ?? 'Réponse masquée';
}

/** Le résultat, en mots (« Jo », « 25 », « Banane »…). */
export function resultLabel(p: Prono): string {
  if (!p.result) return '';
  if (p.kind === 'choice') return p.options.find((o) => o.id === p.result?.option_id)?.label ?? '';
  if (p.kind === 'number') return String(p.result.number ?? '');
  if (p.kind === 'person') return p.result.person ? (p.result.person.me ? 'Toi' : p.result.person.name) : '';
  return '';
}

// ───────── App iPhone : écrans natifs ─────────
type NativePronos = { open: (id: string) => void; create?: (ctx: { group?: string; event?: string }) => void;
  list?: (group?: string) => void; board?: (group: string) => void };

export function nativePronos(): NativePronos | null {
  const native = (globalThis as { PartyNative?: { pronos?: Partial<NativePronos> } }).PartyNative?.pronos;
  return typeof native?.open === 'function' ? (native as NativePronos) : null;
}

/** Ouvrir un prono : écran natif dans l'app iPhone, sinon la page web. */
export function openProno(id: string, push: (path: string) => void): void {
  const native = nativePronos();
  if (native) native.open(id);
  else push(`/prono/${id}`);
}

export function newProno(ctx: { group?: string; event?: string }, push: (path: string) => void): void {
  const native = nativePronos();
  if (native?.create) native.create(ctx);
  else push(`/prono/new${ctx.group ? `?group=${ctx.group}` : ctx.event ? `?event=${ctx.event}` : ''}`);
}

export function openPronoList(group: string | undefined, push: (path: string) => void): void {
  const native = nativePronos();
  if (native?.list) native.list(group);
  else push(group ? `/group/${group}/pronos` : '/pronos');
}

/** Pastille de « Pronos » (Réglages › Autres apps) : à jouer + résultats à donner ; suit les signaux du compte. */
export function usePronoBadge(me: string | null): number {
  const [n, setN] = useState(0);
  const load = useCallback(() => {
    if (!me) return;
    void rpc<{ to_play: number; to_result: number }>('prono_badge').then((b) => setN((b?.to_play ?? 0) + (b?.to_result ?? 0))).catch(() => undefined);
  }, [me]);
  useEffect(() => { load(); }, [load]);
  useSignal(me ? [`user:${me}`] : [], load);
  return n;
}
