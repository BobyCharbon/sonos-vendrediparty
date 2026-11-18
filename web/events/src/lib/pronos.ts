import { useCallback, useEffect, useState } from 'react';

import { useSignal } from './data';
import { formatShort } from './format';
import type { GroupColor } from './groups';
import { supabase } from './supabase';

/**
 * Pronos entre amis (avis f071c5f46e3d, 17.11.2026, migration 20261117180000 ; v2 du 18.11, migration 20261118090000).
 * Pour l'honneur (points au classement du groupe) et, dans un groupe ou un événement, des PATATES : monnaie fictive,
 * gratuite, sans aucune valeur (jamais d'argent, de lot ni d'achat), affichée « confettis 🎊 ». Vocabulaire imposé : « lancer »,
 * « la piste », « ramasser », « au balai », « ton sac », « rendus », « saison ». La base garde les réponses cachées (organisateur
 * compris) jusqu'au dévoilement et décide de tout ; ces fonctions ne font que l'appeler.
 * Toutes les clés v2 sont FACULTATIVES ici : un écran doit marcher avec la base d'avant (clé absente = éteint).
 * Patates : n'afficher QUE si `patates_on` (réglage de la base) ET `patates` (ce prono) sont vrais : `showPatates(p)`.
 * Dans l'app iPhone, les pronos sont des écrans NATIFS (window.PartyNative.pronos) : les pages web s'y effacent.
 */

export type Face = { id: string; name: string; avatar_url: string | null; me?: boolean };
export type PronoKind = 'choice' | 'number' | 'text' | 'person' | 'yesno' | 'overunder' | 'when' | 'majority' | 'award';
export type PronoState = 'open' | 'closed' | 'done' | 'cancelled';
export type Reveal = 'close' | 'result';

/** Le terrain d'un sac : le groupe ou l'événement du prono (sans terrain : pour l'honneur seulement). */
export type Terrain = { kind: 'group' | 'event'; id: string };
/** Le champ : total planté et nombre de planteurs (visibles avant le dévoilement) ; par réponse seulement après. */
export type Field = { total: number; planters: number; by_option?: { option_id: string; total: number }[] | null };
/** Mon sac sur le terrain du prono (null : pas de patates pour moi ici). */
export type Bag = { balance: number; refill_at: string; max_stake: number };
export type Contest = {
  until: string; open: boolean; contested: boolean; fair: number; unfair: number; my_vote: boolean | null;
  can_contest: boolean; can_vote: boolean; vote_until?: string | null; vote_open?: boolean;
  reasons?: { user: Face; reason: string; at: string }[];
};
export const REACTIONS = ['😂', '🔥', '🥔', '👀', '🤯', '👏'] as const;
export type ReactionEmoji = (typeof REACTIONS)[number];
export type Reaction = { emoji: ReactionEmoji; count: number; mine: boolean };
/** Couverture d'une carte : celle du groupe (null pour un événement). */
export type Cover = { color: GroupColor | string; emoji: string; photo: string | null };

export type Prono = {
  id: string; question: string; kind: PronoKind; points: number; closes_at: string; reveal: Reveal; state: PronoState;
  revealed: boolean; created_at: string; mine: boolean; locked: boolean; creator: Face;
  group: { id: string; name: string; emoji: string; color: GroupColor; photo: string | null } | null;
  event: { id: string; title: string; starts_at: string | null } | null;
  options: { id: string; label: string; count: number | null; correct: boolean | null }[];
  candidates: Face[] | null;
  my_answer: { option_id: string | null; number: number | null; text: string | null; person_id: string | null; winner: boolean;
    stake?: number; answer_at?: string | null; harvest?: number | null } | null;
  answered: Face[]; players: number;
  answers: { user: Face; option_id: string | null; number: number | null; text: string | null; hidden: boolean; person: Face | null; winner: boolean;
    stake?: number; harvest?: number | null; answer_at?: string | null }[] | null;
  result: { option_id: string | null; number: number | null; person: Face | null; at: string;
    time?: string | null; by_player?: boolean; people?: (Face & { votes?: number })[] | null } | null;
  winners: Face[] | null;
  can_answer: boolean; can_edit: boolean; can_move_end: boolean; can_result: boolean; can_cancel: boolean;
  link: { token: string | null; path: string | null } | null;
  // ── v2 (toutes facultatives) ──
  line?: number | null; not_over?: boolean; rules?: string | null; template?: string | null;
  patates?: boolean; patates_on?: boolean;
  award?: string | null; award_emoji?: string | null; award_label?: string | null;
  terrain?: Terrain | null; field?: Field | null; bag?: Bag | null;
  settled?: boolean; cancel_reason?: string | null; contest?: Contest | null;
  rarity?: { right: number; of: number } | null; unanimous?: boolean;
  reactions?: Reaction[]; optout?: boolean | null; can_happen?: boolean;
};

export type PronoCard = {
  id: string; question: string; kind: PronoKind; points: number; closes_at: string; state: PronoState; revealed: boolean;
  mine: boolean; creator: Face; group: Prono['group']; event: { id: string; title: string } | null;
  answered_count: number; players: number; faces: Face[]; answered: boolean; won: boolean;
  winners: Face[] | null; winners_count: number | null;
  // ── v2 (toutes facultatives) ──
  patates?: boolean; patates_on?: boolean; field_total?: number | null; my_stake?: number | null; my_harvest?: number | null;
  template?: string | null; award?: string | null; award_emoji?: string | null; award_label?: string | null;
  line?: number | null; settled?: boolean; cancel_reason?: string | null; closes_soon?: boolean; cover?: Cover | null;
};

export type Board = { since: string | null; manage: boolean; pronos: number; rows: { user: Face; points: number; right: number; played: number }[] };

/** prono_bag : mon sac sur un terrain + ma récolte nette de la saison (null : patates éteintes). */
export type BagSummary = Bag & { season: { month: string; harvest_net: number } };
export type BagReason = 'start' | 'refill' | 'plant' | 'unplant' | 'refund' | 'harvest';
/** Une ligne de MON historique (jamais celui d'un autre). */
export type BagMove = { at: string; delta: number; reason: BagReason; terrain?: Terrain; prono: { id: string; question: string | null } | null };
export type SeasonRow = { user: Face; harvest_net: number; right: number; played: number; rank: number; move: number | null };
/** prono_season : récolte nette du mois par personne (null : patates éteintes). */
export type Season = { month: string; rows: SeasonRow[]; me: SeasonRow | null };
export type PronoTemplate = {
  id: string; kind: PronoKind; emoji: string; title: string; question: string; hint: string;
  options?: string[]; line?: number; award?: string; awards?: { id: string; emoji: string; label: string }[];
};

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

/** Tous les types (v2), dans l'ordre de « Partir de zéro ». */
export const KINDS_V2: { key: PronoKind; label: string; hint: string }[] = [
  { key: 'choice', label: 'Choix', hint: 'De 2 à 8 réponses possibles' },
  { key: 'yesno', label: 'Oui / Non', hint: 'Deux réponses, d’un toucher' },
  { key: 'overunder', label: 'Plus / Moins', hint: 'Au-dessus ou en dessous d’une ligne (7,5)' },
  { key: 'number', label: 'Nombre', hint: 'Le plus proche l’emporte' },
  { key: 'when', label: 'Heure', hint: 'L’heure la plus proche l’emporte' },
  { key: 'person', label: 'Une personne', hint: 'On choisit quelqu’un de la bande' },
  { key: 'majority', label: 'Devine la bande', hint: 'La réponse la plus choisie l’emporte' },
  { key: 'award', label: 'Trophée', hint: 'Un trophée positif, voté par la bande' },
  { key: 'text', label: 'Libre', hint: 'Tu coches les bonnes réponses' },
];

/** « Choix », « Oui / Non », « Plus / Moins », « Trophée »… (type inconnu : « Prono »). */
export function kindLabel(kind: PronoKind | string | null | undefined): string {
  return KINDS_V2.find((k) => k.key === kind)?.label ?? 'Prono';
}

/** Types à réponses (options de la base) : choix, oui / non, plus / moins, devine la bande. */
export const hasOptions = (kind: PronoKind | string) => kind === 'choice' || kind === 'yesno' || kind === 'overunder' || kind === 'majority';

/** Trophées : liste FERMÉE et positive (même liste que private.prono_award_categories). */
export const AWARDS: { id: string; emoji: string; label: string }[] = [
  { id: 'ambiance', emoji: '🎉', label: 'Ambianceur·euse' },
  { id: 'piste', emoji: '💃', label: 'Roi / Reine de la piste' },
  { id: 'fou_rire', emoji: '😂', label: 'Fou rire' },
  { id: 'look', emoji: '👗', label: 'Meilleur look' },
  { id: 'chef', emoji: '🍳', label: 'Chef·fe de la soirée' },
  { id: 'voix', emoji: '🎤', label: 'Voix d’or' },
  { id: 'accueil', emoji: '🤝', label: 'Le / la plus accueillant·e' },
  { id: 'danse', emoji: '🕺', label: 'Danse de la soirée' },
];

/** « 🎉 Ambianceur·euse » : d'après les clés de la base (award_emoji / award_label), sinon la liste fermée. */
export function awardLabel(p: { award?: string | null; award_emoji?: string | null; award_label?: string | null } | string | null | undefined,
  withEmoji = true): string {
  const o = typeof p === 'string' ? { award: p } : p ?? {};
  const known = AWARDS.find((a) => a.id === o.award);
  const label = ('award_label' in o ? o.award_label : null) ?? known?.label ?? '';
  const emoji = ('award_emoji' in o ? o.award_emoji : null) ?? known?.emoji ?? '🏆';
  return label ? (withEmoji ? `${emoji} ${label}` : label) : '';
}

/** Ligne « Plus / Moins » en français : 7.5 → « 7,5 ». */
export function lineLabel(line: number | null | undefined): string {
  return line == null ? '' : String(line).replace('.', ',');
}

// ───────── Patates : vocabulaire (conformité : jamais pari, mise, pot, cagnotte, cote, gain, jackpot…) ─────────
export const PATATE = '🎊';
export const NO_VALUE = 'Les confettis n’ont aucune valeur : ils ne s’achètent pas, ne se vendent pas, ne s’échangent pas.';
export const MAX_PLANT = 20;

/** Les patates sont-elles à montrer pour ce prono ? (réglage de la base ET prono avec patates). */
export function showPatates(p: { patates?: boolean; patates_on?: boolean } | null | undefined): boolean {
  return !!(p?.patates && p.patates_on);
}
/** « 120 🎊 sur la piste · 5 joueurs » (jamais de multiplicateur ni de « tu peux ramasser »). */
export function fieldLine(f: { total: number; planters?: number | null } | null | undefined): string {
  if (!f) return '';
  const who = f.planters == null ? '' : ` · ${f.planters} joueur${f.planters > 1 ? 's' : ''}`;
  return `${f.total} ${PATATE} sur la piste${who}`;
}
/** Libellés de l'historique du sac (« Lancés · partis au balai » une fois le prono réglé sans rien ramasser). */
export function bagReasonLabel(reason: BagReason, opts?: { compost?: boolean; unanimous?: boolean }): string {
  switch (reason) {
    case 'start': return 'Ton sac de départ';
    case 'refill': return 'Remontée du lundi';
    case 'plant': return opts?.compost ? 'Lancés · partis au balai' : 'Lancés';
    case 'unplant': return 'Repris';
    case 'refund': return opts?.unanimous ? 'Rendus · Unanimes !' : 'Rendus';
    case 'harvest': return 'Tu ramasses';
    default: return '';
  }
}
/** Remontée du sac : « lundi 23 nov. à 0 h ». */
export function refillLabel(iso: string | null | undefined): string {
  if (!iso) return 'lundi à 0 h';
  const day = new Intl.DateTimeFormat('fr-CH', { timeZone: 'Europe/Zurich', weekday: 'long', day: 'numeric', month: 'short' }).format(new Date(iso));
  return `${day} à 0 h`;
}
/** Mois d'une saison (« 2026-11-01 ») : « novembre ». */
export function seasonMonth(month: string | null | undefined): string {
  if (!month) return '';
  return new Intl.DateTimeFormat('fr-CH', { timeZone: 'UTC', month: 'long' }).format(new Date(`${month.slice(0, 10)}T12:00:00Z`));
}

// ───────── Appels v2 (mêmes noms d'arguments que les fonctions SQL) ─────────
type Ground = { group?: string | null; event?: string | null };
const ground = (g?: Ground) => ({ group_id: g?.group ?? null, event_id: g?.event ?? null });

/** Mon sac sur le terrain (groupe OU événement) ; null si les patates sont éteintes. */
export const bag = (g: Ground) => rpc<BagSummary | null>('prono_bag', ground(g));
/** MON historique (60 derniers) ; sans terrain : tous mes sacs ; [] si les patates sont éteintes. */
export const bagHistory = (g?: Ground) => rpc<BagMove[]>('prono_bag_history', ground(g));
/** Saison d'un groupe (mois en cours sans `month`, sinon « 2026-10-01 ») ; null si les patates sont éteintes. */
export const season = (group: string, month?: string | null) => rpc<Season | null>('prono_season', { group_id: group, month: month ?? null });
/** Contester un résultat (raison obligatoire, 3 à 140 caractères, filtrée par la base). */
export const contest = (id: string, reason: string) => rpc<Prono>('prono_contest', { id, reason });
export const contestVote = (id: string, fair: boolean) => rpc<Prono>('prono_contest_vote', { id, fair });
/** Réaction (bascule). */
export const react = (id: string, emoji: ReactionEmoji) => rpc<Prono>('prono_react', { id, emoji });
/** Trophée : se retirer de la liste (out = true) ou y revenir. */
export const optout = (id: string, out: boolean) => rpc<Prono>('prono_optout', { id, out });
export const templates = () => rpc<PronoTemplate[]>('prono_templates');
/** « C'est arrivé ! » (prono « heure », organisateur) : le résultat est maintenant. */
export const happened = (id: string) => rpc<Prono>('prono_result', { id, body: { time: new Date().toISOString() } });

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

/** Heure d'un prono « heure » : « 21:40 » le jour même, sinon « Sam. 21 nov. · 21:40 ». */
export function timeLabel(iso: string): string {
  const ymd = (x: Date) => new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Zurich' }).format(x);
  const d = new Date(iso);
  if (ymd(d) !== ymd(new Date())) return formatShort(iso);
  return new Intl.DateTimeFormat('fr-CH', { timeZone: 'Europe/Zurich', hour: '2-digit', minute: '2-digit' }).format(d);
}

/** Réponse lisible (dévoilement, ma réponse). */
export function answerLabel(p: Prono, a: { option_id: string | null; number: number | null; text: string | null; person?: Face | null; person_id?: string | null;
  answer_at?: string | null }): string {
  if (hasOptions(p.kind)) return p.options.find((o) => o.id === a.option_id)?.label ?? '—';
  if (p.kind === 'number') return a.number == null ? '—' : String(a.number);
  if (p.kind === 'when') return a.answer_at ? timeLabel(a.answer_at) : '—';
  if (p.kind === 'person' || p.kind === 'award') {
    const who = a.person ?? p.candidates?.find((c) => c.id === a.person_id) ?? null;
    return who ? (who.me ? 'Toi' : who.name) : '—';
  }
  return a.text ?? 'Réponse masquée';
}

/** Le résultat, en mots (« Jo », « 25 », « Banane », « 21:40 »…). */
export function resultLabel(p: Prono): string {
  if (!p.result) return '';
  if (hasOptions(p.kind)) return p.options.find((o) => o.id === p.result?.option_id)?.label ?? '';
  if (p.kind === 'number') return String(p.result.number ?? '');
  if (p.kind === 'when') return p.result.time ? timeLabel(p.result.time) : '';
  if (p.kind === 'person' || p.kind === 'award') {
    const who = p.result.person ?? p.result.people?.[0] ?? null;
    return who ? (who.me ? 'Toi' : who.name) : '';
  }
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
