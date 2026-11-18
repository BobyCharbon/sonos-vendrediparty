import { parseLocalDateTime, toLocalInput } from '@/lib/format';
import type { GroupColor } from '@/lib/groups';

/**
 * Création d'un prono, en 4 étapes (maquettes 2-1 à 2-4 de Pronos v2, 18.11) : modèle, question, réglages, « C'est lancé ! ».
 * Ici : les données de l'écran (types, familles de modèles, formes, fins rapides) et le corps envoyé à `prono_create`.
 * La base décide de tout (filtre, patates seulement avec un groupe ou un événement, trophée écrit par Party).
 */

export type Kind = 'choice' | 'yesno' | 'overunder' | 'number' | 'when' | 'person' | 'text' | 'majority' | 'award';
export type Award = { id: string; emoji: string; label: string };
export type Template = {
  id: string; kind: Kind; emoji: string; title: string; question: string; hint: string;
  options?: string[]; line?: number; award?: string; awards?: Award[];
  /** Facultatif (pas encore renvoyé par la base) : famille et règle proposée. Sinon déduites ici. */
  family?: Family; rules?: string;
};

/** Ordre et phrases de « Partir de zéro » (maquette 2-1) ; le nom du type vient de kindLabel (Kit). */
export const KINDS: { kind: Kind; phrase: string; tint: [string, string] }[] = [
  { kind: 'choice', phrase: 'De 2 à 8 réponses, une seule juste', tint: ['#CBBDFF', '#7B6CF6'] },
  { kind: 'yesno', phrase: 'Ça arrive, ou pas ?', tint: ['#7CEDBB', '#22B07D'] },
  { kind: 'overunder', phrase: 'Au-dessus ou sous la ligne', tint: ['#8FD6FF', '#3D8BFF'] },
  { kind: 'number', phrase: 'Le plus proche l’emporte', tint: ['#FFC977', '#FF7A59'] },
  { kind: 'when', phrase: 'À quelle heure ça arrive ?', tint: ['#FFEA9C', '#FFB347'] },
  { kind: 'person', phrase: 'Quelqu’un de la bande', tint: ['#FF8FC0', '#FF4F9A'] },
  { kind: 'text', phrase: 'Chacun écrit, tu tranches à la fin', tint: ['#A79FC7', '#5D5585'] },
  { kind: 'majority', phrase: 'Trouve ce que la majorité choisira', tint: ['#8FD6FF', '#7B6CF6'] },
  { kind: 'award', phrase: 'Un prix positif, voté par tous', tint: ['#FFEA9C', '#FFB347'] },
];

export type Family = 'soiree' | 'sport' | 'bande' | 'votes';
export const FAMILIES: { key: Family; label: string; emoji: string; hint: string; color: GroupColor }[] = [
  { key: 'soiree', label: 'Soirée', emoji: '🌙', hint: 'pour ce soir', color: 'coral' },
  { key: 'sport', label: 'Sport', emoji: '⚽', hint: 'match, tournoi, baby-foot', color: 'mint' },
  { key: 'bande', label: 'La bande', emoji: '👯', hint: 'entre vous', color: 'sky' },
  { key: 'votes', label: 'Votes', emoji: '🏆', hint: 'la bande décide', color: 'pink' },
];

const SPORT = /match|but|score|baby|ping|foot|sport|tournoi|equipe|équipe/i;

/** Famille d'un modèle : celle de la base si elle la donne, sinon d'après son type et ses mots. */
export function familyOf(t: Template): Family {
  if (t.family && FAMILIES.some((f) => f.key === t.family)) return t.family;
  if (t.kind === 'award') return 'votes';
  if (t.kind === 'majority') return /bande/i.test(`${t.id} ${t.title}`) ? 'bande' : 'votes';
  if (SPORT.test(`${t.id} ${t.title}`)) return 'sport';
  if (t.kind === 'yesno' || t.kind === 'text') return 'bande';
  return 'soiree';
}

/** Les 8 trophées (liste fermée de la base, private.prono_award_categories) : repli si le modèle ne les donne pas. */
export const AWARDS: Award[] = [
  { id: 'ambiance', emoji: '🎉', label: 'Ambianceur·euse' },
  { id: 'piste', emoji: '💃', label: 'Roi / Reine de la piste' },
  { id: 'fou_rire', emoji: '😂', label: 'Fou rire' },
  { id: 'look', emoji: '👗', label: 'Meilleur look' },
  { id: 'chef', emoji: '🍳', label: 'Chef·fe de la soirée' },
  { id: 'voix', emoji: '🎤', label: 'Voix d’or' },
  { id: 'accueil', emoji: '🤝', label: 'Le / la plus accueillant·e' },
  { id: 'danse', emoji: '🕺', label: 'Danse de la soirée' },
];

/** Une forme ET une couleur par réponse (jamais la couleur seule), dans l'ordre. */
export const SHAPES = [
  { glyph: '▲', color: '#FF5FA2', name: 'triangle' },
  { glyph: '◆', color: '#4D9BFF', name: 'losange' },
  { glyph: '●', color: '#FFC24D', name: 'rond' },
  { glyph: '■', color: '#3FD08F', name: 'carré' },
  { glyph: '★', color: '#A08CFF', name: 'étoile' },
  { glyph: '⬢', color: '#FF8A5C', name: 'hexagone' },
  { glyph: '✚', color: '#7CEDBB', name: 'croix' },
  { glyph: '♥', color: '#FF8FC0', name: 'cœur' },
];
export const UP = { glyph: '▲', color: '#FF5FA2' };
export const DOWN = { glyph: '▼', color: '#4D9BFF' };

export const UNITS = ['buts', 'points', 'minutes', 'personnes', 'parties'];

export const MAX_QUESTION = 120;

export type Draft = {
  template: string | null; kind: Kind; emoji: string; question: string; options: string[];
  line: number; unit: string; notOver: boolean; rules: string; award: string; ruleHint: string | null;
};

const RULE_HINTS: Partial<Record<Kind, string>> = {
  choice: 'Si ça n’a pas lieu, le prono est annulé',
  yesno: 'Si ça n’a pas lieu, le prono est annulé',
  number: 'On compte jusqu’à minuit',
  when: 'L’heure de mon téléphone fait foi',
  person: 'Si personne ne le fait, le prono est annulé',
  text: 'Je coche les réponses qui veulent dire la même chose',
};

const KIND_EMOJI: Record<Kind, string> = {
  choice: '🔮', yesno: '🤞', overunder: '📈', number: '🎯', when: '⏰', person: '🙋', text: '✍️', majority: '👥', award: '🏆',
};

/** Brouillon de départ : un modèle, ou un type « Partir de zéro ». */
export function draftFrom(t: Template | null, kind: Kind = t?.kind ?? 'choice'): Draft {
  const line = typeof t?.line === 'number' ? t.line : 2.5;
  const sport = t ? familyOf(t) === 'sport' : false;
  return {
    template: t?.id ?? null, kind, emoji: t?.emoji ?? KIND_EMOJI[kind],
    question: kind === 'award' ? '' : t?.question ?? '',
    options: t?.options?.length ? [...t.options] : kind === 'choice' || kind === 'majority' ? ['', ''] : [],
    line, unit: /point/i.test(t?.question ?? '') ? 'points' : 'buts', notOver: false, rules: '',
    award: t?.award ?? 'ambiance',
    ruleHint: t?.rules ?? (sport && (kind === 'overunder' || kind === 'number' || kind === 'choice')
      ? 'Score à 90 minutes, sans prolongations' : RULE_HINTS[kind] ?? null),
  };
}

/** Changer de type garde la question ; les réponses suivent le type. */
export function switchKind(d: Draft, kind: Kind): Draft {
  const needsOptions = kind === 'choice' || kind === 'majority';
  const options = needsOptions ? (d.options.length >= 2 ? d.options : ['', '']) : d.options;
  return { ...d, kind, options, emoji: d.template ? d.emoji : KIND_EMOJI[kind], ruleHint: d.ruleHint ?? RULE_HINTS[kind] ?? null };
}

/** « 7,5 » */
export function lineLabel(n: number): string {
  return String(n).replace('.', ',');
}

export function awardOf(d: Draft, awards: Award[]): Award {
  return awards.find((a) => a.id === d.award) ?? awards[0] ?? AWARDS[0];
}

/** La question telle que les joueurs la liront (trophée : écrite par Party, comme la base). */
export function shownQuestion(d: Draft, awards: Award[]): string {
  if (d.kind === 'award') return `Qui mérite le trophée « ${awardOf(d, awards).label} » ?`;
  return d.question.trim();
}

export const filledOptions = (d: Draft) => d.options.map((o) => o.trim()).filter(Boolean);

/** Ce qui manque encore à l'étape 2 (null : on peut continuer). */
export function questionProblem(d: Draft): string | null {
  if (d.kind === 'award') return null;
  if (d.question.trim().length < 5) return 'Écris la question (5 caractères au moins).';
  if (d.kind === 'choice' || d.kind === 'majority') {
    const opts = filledOptions(d);
    if (opts.length < 2) return 'Ajoute au moins 2 réponses.';
    if (new Set(opts.map((o) => o.toLowerCase())).size < opts.length) return 'Deux réponses sont identiques.';
  }
  return null;
}

/** Les patates se plantent sur des choix tranchés : jamais pour un trophée ni une réponse libre. */
export const patatesPossible = (k: Kind) => k !== 'award' && k !== 'text';
/** Dévoilement imposé par la base : réponse libre et majorité à la fin, trophée avec le résultat. */
export const fixedReveal = (k: Kind): 'close' | 'result' | null => (k === 'text' || k === 'majority' ? 'close' : k === 'award' ? 'result' : null);

// ───────── Fin des réponses : puces rapides, en heure de Zurich ─────────

export type EndChoice = { key: string; label: string; time: string; local: string };

function zurichDate(offsetDays: number, now: Date): { local: string; weekday: number } {
  const [d, m, y] = toLocalInput(now.toISOString()).slice(0, 10).split('.').map(Number);
  const day = new Date(Date.UTC(y, m - 1, d + offsetDays));
  const pad = (n: number) => String(n).padStart(2, '0');
  return { local: `${pad(day.getUTCDate())}.${pad(day.getUTCMonth() + 1)}.${day.getUTCFullYear()}`, weekday: day.getUTCDay() };
}

const WEEKDAYS = ['Dimanche', 'Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi'];

/** « Ce soir 23:00 » (ou « Dans 1 h » s'il est trop tard), « Demain 20:00 », « Samedi 20:00 » (le prochain après demain). */
export function endChoices(now = new Date()): EndChoice[] {
  const out: EndChoice[] = [];
  const tonight = `${zurichDate(0, now).local} 23:00`;
  const tonightIso = parseLocalDateTime(tonight);
  if (tonightIso && Date.parse(tonightIso) - now.getTime() > 60 * 60_000) {
    out.push({ key: 'tonight', label: 'Ce soir', time: '23:00', local: tonight });
  } else {
    const soon = toLocalInput(new Date(Math.ceil((now.getTime() + 60 * 60_000) / 300_000) * 300_000).toISOString());
    out.push({ key: 'hour', label: 'Dans 1 h', time: soon.slice(11), local: soon });
  }
  out.push({ key: 'tomorrow', label: 'Demain', time: '20:00', local: `${zurichDate(1, now).local} 20:00` });
  for (let i = 2; i <= 8; i++) {
    const z = zurichDate(i, now);
    if (z.weekday === 6) { out.push({ key: 'weekend', label: WEEKDAYS[6], time: '20:00', local: `${z.local} 20:00` }); break; }
  }
  return out;
}

/** « dans 5 jours », « demain », « ce soir » : jours calendaires de Zurich. */
export function inDays(local: string, now = new Date()): string {
  const today = zurichDate(0, now).local;
  const [d1, m1, y1] = today.split('.').map(Number);
  const [d2, m2, y2] = local.slice(0, 10).split('.').map(Number);
  const n = Math.round((Date.UTC(y2, m2 - 1, d2) - Date.UTC(y1, m1 - 1, d1)) / 86_400_000);
  if (n <= 0) return Number(local.slice(11, 13)) >= 18 ? 'ce soir' : 'aujourd’hui';
  if (n === 1) return 'demain';
  return `dans ${n} jours`;
}

// ───────── Corps envoyé à prono_create ─────────

export type Who = { group: string | null; event: string | null; people: string[]; link: boolean };
export type Settings = { who: Who; end: string; patates: boolean; points: number; reveal: 'close' | 'result' };

export function createBody(d: Draft, s: Settings, closesAt: string): Record<string, unknown> {
  const terrain = !!(s.who.group || s.who.event);
  return {
    question: d.kind === 'award' ? '' : d.question.trim(),
    kind: d.kind,
    options: d.kind === 'choice' || d.kind === 'majority' ? filledOptions(d) : [],
    points: s.points,
    closes_at: closesAt,
    reveal: fixedReveal(d.kind) ?? s.reveal,
    group_id: s.who.group,
    event_id: s.who.event,
    people: s.who.people,
    link: s.who.link,
    template: d.template,
    rules: d.kind === 'award' || d.kind === 'majority' ? null : d.rules.trim() || null,
    ...(d.kind === 'overunder' ? { line: d.line } : {}),
    ...(d.kind === 'number' || d.kind === 'when' ? { not_over: d.notOver } : {}),
    ...(d.kind === 'award' ? { award: d.award } : {}),
    patates: terrain && s.patates && patatesPossible(d.kind),
  };
}
