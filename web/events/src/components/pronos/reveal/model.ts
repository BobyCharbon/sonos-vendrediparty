import type { Face, Prono } from '@/lib/pronos';

import { shapeAt } from './theme';

/**
 * Lecture du prono v2 (contrat Pronos v2, clés de `prono_json`) pour le dévoilement et le résultat. Toutes les clés v2
 * sont facultatives : un prono d'avant (pour l'honneur) s'affiche aussi. Aucun calcul ici ne décide de rien : la base
 * règle les récoltes ; on ne refait le partage du champ que pour l'afficher pendant les 12 h d'attente.
 */

export type V2Answer = {
  user: Face; option_id: string | null; number: number | null; text: string | null; hidden?: boolean; person: Face | null;
  winner: boolean; stake?: number | null; harvest?: number | null; answer_at?: string | null;
};

export type V2 = {
  id: string; question: string; kind: string; points: number; state: string; revealed: boolean; mine: boolean;
  created_at: string; creator: Face; closes_at: string;
  group: { id: string; name: string; emoji: string; color: string | null; photo?: string | null } | null;
  event: { id: string; title: string; starts_at?: string | null } | null;
  options: { id: string; label: string; count: number | null; correct: boolean | null }[];
  candidates: Face[] | null;
  answered: Face[];
  answers: V2Answer[] | null;
  my_answer: { option_id: string | null; number: number | null; text: string | null; person_id: string | null; winner: boolean;
    stake?: number | null; answer_at?: string | null; harvest?: number | null } | null;
  result: { option_id: string | null; number: number | null; person: Face | null; at: string; time?: string | null;
    by_player?: boolean; people?: (Face & { votes: number })[] | null } | null;
  winners: Face[] | null;
  line?: number | null; not_over?: boolean; rules?: string | null; patates?: boolean; patates_on?: boolean;
  award?: string | null; award_emoji?: string | null; award_label?: string | null;
  field?: { total: number; planters: number; by_option?: { option_id: string; total: number }[] | null } | null;
  settled?: boolean; cancel_reason?: string | null;
  bag?: { balance: number; refill_at?: string | null; max_stake?: number } | null;
  contest?: { until: string | null; open: boolean; contested: boolean; vote_until?: string | null; vote_open?: boolean;
    fair: number; unfair: number; my_vote: boolean | null; can_contest: boolean; can_vote: boolean } | null;
  rarity?: { right: number; of: number } | null;
  unanimous?: boolean;
  reactions?: { emoji: string; count: number; mine: boolean }[];
};

export const v2 = (p: Prono): V2 => p as unknown as V2;

export const OPTION_KINDS = ['choice', 'yesno', 'overunder', 'majority'];
export const isAxis = (k: string) => k === 'number' || k === 'when';
export const nameOf = (f: Face | null | undefined) => (f ? (f.me ? 'Toi' : f.name) : '—');

/** Patates à l'écran : le prono en a ET la base les a allumées (sinon : pour l'honneur, des points seulement). */
export const potatoesOn = (p: V2) => !!p.patates && p.patates_on !== false;

export type Fate = { stake: number; harvest: number; kind: 'harvest' | 'compost' | 'refund' | 'none' };

/**
 * Ce que chaque joueur récolte (contrat, règle 🔴 3) : partage du champ entre ceux qui ont vu juste, au prorata de ce
 * qu'ils ont planté, arrondi vers le bas, reste au plus fort reste. Tout est rendu si personne n'a vu juste, si tous
 * ont vu juste, si moins de 2 joueurs ont planté ou si le prono est annulé. La récolte versée par la base l'emporte.
 */
export function fates(p: V2): Map<string, Fate> {
  const out = new Map<string, Fate>();
  const answers = p.answers ?? [];
  const stake = (a: V2Answer) => Math.max(0, a.stake ?? 0);
  const field = p.field?.total ?? answers.reduce((s, a) => s + stake(a), 0);
  const planters = p.field?.planters ?? answers.filter((a) => stake(a) > 0).length;
  const winners = answers.filter((a) => a.winner);
  const wPlanted = winners.reduce((s, a) => s + stake(a), 0);
  const refundAll = p.state === 'cancelled' || planters < 2 || wPlanted === 0 || !!p.unanimous
    || (answers.length > 0 && winners.length === answers.length);
  const exact = new Map<string, number>();
  if (!refundAll) {
    let given = 0;
    const rest: [number, string][] = [];
    for (const a of winners) {
      const x = (stake(a) * field) / wPlanted;
      exact.set(a.user.id, Math.floor(x));
      given += Math.floor(x);
      rest.push([x % 1, a.user.id]);
    }
    rest.sort((a, b) => b[0] - a[0]);
    for (let i = 0; i < field - given && i < rest.length; i++) exact.set(rest[i][1], (exact.get(rest[i][1]) ?? 0) + 1);
  }
  for (const a of answers) {
    const s = stake(a);
    if (!s) { out.set(a.user.id, { stake: 0, harvest: 0, kind: 'none' }); continue; }
    if (refundAll) { out.set(a.user.id, { stake: s, harvest: s, kind: 'refund' }); continue; }
    if (a.winner) out.set(a.user.id, { stake: s, harvest: a.harvest ?? exact.get(a.user.id) ?? 0, kind: 'harvest' });
    else out.set(a.user.id, { stake: s, harvest: 0, kind: 'compost' });
  }
  return out;
}

/** Mon sort : ma ligne parmi les réponses, ou ma réponse seule (bloqués exclus de la liste). */
export function myFate(p: V2): Fate | null {
  if (!p.my_answer) return null;
  const me = (p.answers ?? []).find((a) => a.user.me);
  const f = me ? fates(p).get(me.user.id) : undefined;
  if (f) return p.my_answer.harvest != null && f.kind === 'harvest' ? { ...f, harvest: p.my_answer.harvest } : f;
  const s = p.my_answer.stake ?? 0;
  return s ? { stake: s, harvest: p.my_answer.harvest ?? 0, kind: p.my_answer.winner ? 'harvest' : 'compost' } : { stake: 0, harvest: 0, kind: 'none' };
}

export function rarity(p: V2): { right: number; of: number } {
  if (p.rarity) return p.rarity;
  const a = p.answers ?? [];
  return { right: a.filter((x) => x.winner).length, of: a.length };
}

/** « 🔮 Seuls 2 sur 8 l'avaient vu ». */
export function rarityText(r: { right: number; of: number }): string {
  if (!r.right) return 'Personne ne l’avait vu';
  if (r.right === 1) return `1 seule personne sur ${r.of} l’avait vu`;
  if (r.right * 2 <= r.of) return `Seuls ${r.right} sur ${r.of} l’avaient vu`;
  return `${r.right} sur ${r.of} l’avaient vu`;
}

export const isUnanimous = (p: V2) => !!p.unanimous || (!!p.answers?.length && p.answers.every((a) => a.winner));

/** Une ligne de réponse (choix, Oui / Non, Plus / Moins, majorité, personne) : forme, libellé, visages. */
export type Row = { key: string; label: string; shape: ReturnType<typeof shapeAt>; faces: Face[]; count: number; right: boolean; planted: number };

export function rows(p: V2): Row[] {
  const answers = p.answers ?? [];
  const planted = (list: V2Answer[]) => list.reduce((s, a) => s + Math.max(0, a.stake ?? 0), 0);
  if (OPTION_KINDS.includes(p.kind)) {
    return p.options.map((o, i) => {
      const who = answers.filter((a) => a.option_id === o.id);
      const byField = p.field?.by_option?.find((b) => b.option_id === o.id)?.total;
      return { key: o.id, label: o.label, shape: shapeAt(i), faces: who.map((a) => a.user), count: o.count ?? who.length,
        right: !!o.correct || p.result?.option_id === o.id, planted: byField ?? planted(who) };
    });
  }
  if (p.kind === 'person') {
    const m = new Map<string, { face: Face; list: V2Answer[] }>();
    for (const a of answers) {
      if (!a.person) continue;
      const cur = m.get(a.person.id) ?? { face: a.person, list: [] };
      cur.list.push(a);
      m.set(a.person.id, cur);
    }
    const good = p.result?.person;
    if (good && !m.has(good.id)) m.set(good.id, { face: good, list: [] });
    return [...m.values()].sort((a, b) => b.list.length - a.list.length).map((x, i) => ({
      key: x.face.id, label: nameOf(x.face), shape: shapeAt(i), faces: x.list.map((a) => a.user), count: x.list.length,
      right: good?.id === x.face.id, planted: planted(x.list),
    }));
  }
  return [];
}

// ───────── Nombre et heure : l'axe ─────────

const hmFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: 'Europe/Zurich', hour: 'numeric', minute: '2-digit', hourCycle: 'h23' });

/** « 22 h 47 », « 23 h ». */
export function hm(iso: string | number): string {
  const parts = hmFmt.formatToParts(new Date(iso));
  const h = parts.find((x) => x.type === 'hour')?.value ?? '';
  const m = parts.find((x) => x.type === 'minute')?.value ?? '00';
  return m === '00' ? `${Number(h)} h` : `${Number(h)} h ${m}`;
}

export const fmtNum = (n: number) => String(Math.round(n * 100) / 100).replace('.', ',');

/** Écart en mots : « 7 min », « 1 h 05 », « 3 », « 0,5 ». */
export function gapText(kind: string, d: number): string {
  if (kind !== 'when') return fmtNum(d);
  const m = Math.round(d);
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${String(m % 60).padStart(2, '0')}`;
}

export type AxisPoint = { face: Face; value: number; gap: number; winner: boolean; stake: number; rank: number };

/** Les réponses sur l'axe : valeur (nombre, ou minutes pour une heure), écart à la vraie valeur, rang avec égalités. */
export function axis(p: V2): { real: number | null; points: AxisPoint[] } {
  const isWhen = p.kind === 'when';
  const val = (a: { number: number | null; answer_at?: string | null }) =>
    isWhen ? (a.answer_at ? Date.parse(a.answer_at) / 60_000 : null) : a.number;
  const realRaw = isWhen ? (p.result?.time ? Date.parse(p.result.time) / 60_000 : null) : p.result?.number ?? null;
  const pts: AxisPoint[] = [];
  for (const a of p.answers ?? []) {
    const v = val(a);
    if (v == null || Number.isNaN(v)) continue;
    pts.push({ face: a.user, value: v, gap: realRaw == null ? 0 : Math.abs(v - realRaw), winner: a.winner, stake: Math.max(0, a.stake ?? 0), rank: 0 });
  }
  pts.sort((a, b) => a.gap - b.gap || b.stake - a.stake);
  pts.forEach((x, i) => { x.rank = i && pts[i - 1].gap === x.gap ? pts[i - 1].rank : i + 1; });
  return { real: realRaw, points: pts };
}

/** Valeur lisible sur l'axe. */
export const axisLabel = (kind: string, v: number) => (kind === 'when' ? hm(v * 60_000) : fmtNum(v));

/** Bornes et graduations « rondes » autour des réponses et de la vraie valeur. */
export function axisScale(kind: string, values: number[]): { min: number; max: number; ticks: number[] } {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const span = Math.max(hi - lo, kind === 'when' ? 30 : 2);
  const steps = kind === 'when' ? [5, 10, 15, 30, 60, 120, 240, 720, 1440] : [0.5, 1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 5000, 10000];
  const step = steps.find((s) => span / s <= (kind === 'when' ? 4 : 7)) ?? span / 6;
  const min = Math.floor((lo - span * 0.08) / step) * step;
  const max = Math.ceil((hi + span * 0.08) / step) * step;
  const ticks: number[] = [];
  for (let t = min; t <= max + 1e-9 && ticks.length < 12; t += step) ticks.push(t);
  return { min, max, ticks };
}

/** Trophée : le ou la lauréat·e (égalité : plusieurs) et ses voix ; jamais les voix des autres. */
export function laureates(p: V2): { people: (Face & { votes: number })[]; voters: number } {
  const people = p.result?.people ?? (p.result?.person ? [{ ...p.result.person, votes: 0 }] : []);
  return { people, voters: p.answers?.length ?? p.answered.length };
}

/** Le terrain : groupe (couleur, emoji) ou événement. */
export function terrainChip(p: V2): string {
  if (p.group) return `${p.group.emoji} ${p.group.name}`;
  if (p.event) return `🎉 ${p.event.title}`;
  return '🔮 Pronos';
}

/** Date courte du jour (« mer. 18 nov. 2026 »), pour la carte à partager. */
export function dayLong(iso: string): string {
  return new Intl.DateTimeFormat('fr-CH', { timeZone: 'Europe/Zurich', weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })
    .format(new Date(iso));
}

/** Ma réponse en mots (choix, personne, nombre, heure, texte). */
export function myAnswerText(p: V2): string {
  const a = p.my_answer;
  if (!a) return '';
  if (OPTION_KINDS.includes(p.kind)) return p.options.find((o) => o.id === a.option_id)?.label ?? '—';
  if (p.kind === 'person') return nameOf(p.candidates?.find((c) => c.id === a.person_id) ?? p.answers?.find((x) => x.user.me)?.person);
  if (p.kind === 'number') return a.number == null ? '—' : fmtNum(a.number);
  if (p.kind === 'when') return a.answer_at ? hm(a.answer_at) : '—';
  return a.text ?? '—';
}

/** La bonne réponse en mots. */
export function rightText(p: V2): string {
  const r = p.result;
  if (!r) return '';
  if (OPTION_KINDS.includes(p.kind)) return p.options.find((o) => o.id === r.option_id || o.correct)?.label ?? '';
  if (p.kind === 'person' || p.kind === 'award') return nameOf(r.person);
  if (p.kind === 'number') return r.number == null ? '' : fmtNum(r.number);
  if (p.kind === 'when') return r.time ? hm(r.time) : '';
  return '';
}

/** Heures restantes avant `iso` (arrondi au-dessus, 0 au plus bas). */
export function hoursLeft(iso: string | null | undefined): number {
  if (!iso) return 0;
  return Math.max(0, Math.ceil((Date.parse(iso) - Date.now()) / 3_600_000));
}

/** Nom du mois (« novembre ») d'une date ISO ou « AAAA-MM-01 ». */
export function monthName(iso: string): string {
  return new Intl.DateTimeFormat('fr-CH', { timeZone: 'UTC', month: 'long' }).format(new Date(`${iso.slice(0, 7)}-01T12:00:00Z`));
}

/** « AAAA-MM-01 » du mois en cours, heure de Suisse. */
export function thisMonth(): string {
  const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Zurich', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  return `${ymd.slice(0, 7)}-01`;
}

/** Décale « AAAA-MM-01 » de `n` mois. */
export function shiftMonth(m: string, n: number): string {
  const d = new Date(`${m.slice(0, 7)}-01T12:00:00Z`);
  d.setUTCMonth(d.getUTCMonth() + n);
  return `${d.toISOString().slice(0, 7)}-01`;
}

/** Jours restants dans le mois en cours (heure de Suisse). */
export function daysLeftInMonth(): number {
  const ymd = new Intl.DateTimeFormat('en-CA', { timeZone: 'Europe/Zurich', year: 'numeric', month: '2-digit', day: '2-digit' }).format(new Date());
  const [y, mo, d] = ymd.split('-').map(Number);
  return new Date(Date.UTC(y, mo, 0)).getUTCDate() - d;
}
