const TZ = 'Europe/Zurich';

const dayFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' });
const longDayFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'long', day: 'numeric', month: 'long' });
const timeFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
const msgFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' });

const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** « Ven. 6 nov. · 19:30 » */
export function formatShort(iso: string | null | undefined): string {
  if (!iso) return 'Date à définir';
  const d = new Date(iso);
  return `${cap(dayFmt.format(d))} · ${timeFmt.format(d)}`;
}

/** « Vendredi 6 novembre » */
export function formatLongDay(iso: string): string {
  return cap(longDayFmt.format(new Date(iso)));
}

export function formatTime(iso: string): string {
  return timeFmt.format(new Date(iso));
}

export function formatMessageTime(iso: string): string {
  return msgFmt.format(new Date(iso));
}

/** Saisie « JJ.MM.AAAA HH:MM » (heure de Zurich) -> ISO. Renvoie null si invalide. */
export function parseLocalDateTime(input: string): string | null {
  const m = input.trim().match(/^(\d{1,2})[./](\d{1,2})[./](\d{4}|\d{2})(?:\s+(\d{1,2})[:h](\d{2}))?$/);
  if (!m) return null;
  const [, dd, mm, yy, hh = '0', mi = '0'] = m;
  const year = yy.length === 2 ? 2000 + Number(yy) : Number(yy);
  // Construit la date comme si elle était en UTC, puis corrige du décalage de Zurich à cette date.
  const asUtc = Date.UTC(year, Number(mm) - 1, Number(dd), Number(hh), Number(mi));
  const utc = new Date(asUtc);
  if (Number.isNaN(asUtc) || utc.getUTCFullYear() !== year || utc.getUTCMonth() !== Number(mm) - 1
    || utc.getUTCDate() !== Number(dd) || utc.getUTCHours() !== Number(hh) || utc.getUTCMinutes() !== Number(mi)) return null;
  const expected = `${dd.padStart(2, '0')}.${mm.padStart(2, '0')}.${year} ${hh.padStart(2, '0')}:${mi}`;
  // Les deux décalages couvrent les changements d'heure. Refuser une heure inexistante
  // au printemps ; en automne choisir la première occurrence de l'heure répétée.
  const offsets = new Set([zurichOffsetMinutes(utc), zurichOffsetMinutes(new Date(asUtc - 86_400_000))]);
  const candidates = [...offsets].map((offset) => new Date(asUtc - offset * 60_000).toISOString()).sort();
  return candidates.find((iso) => toLocalInput(iso) === expected) ?? null;
}

/** ISO -> « JJ.MM.AAAA HH:MM » en heure de Zurich (pour préremplir un champ). */
export function toLocalInput(iso: string | null | undefined): string {
  if (!iso) return '';
  const parts = new Intl.DateTimeFormat('fr-CH', {
    timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
  }).formatToParts(new Date(iso));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  return `${get('day')}.${get('month')}.${get('year')} ${get('hour')}:${get('minute')}`;
}

function zurichOffsetMinutes(d: Date): number {
  const parts = new Intl.DateTimeFormat('en-US', { timeZone: TZ, timeZoneName: 'longOffset' }).formatToParts(d);
  const name = parts.find((p) => p.type === 'timeZoneName')?.value ?? 'GMT+00:00';
  const m = name.match(/GMT([+-])(\d{2}):(\d{2})/);
  if (!m) return 0;
  return (m[1] === '-' ? -1 : 1) * (Number(m[2]) * 60 + Number(m[3]));
}

export function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((w) => w[0]!.toUpperCase()).join('') || '?';
}

const avatarPalette = ['#FF7A59', '#B9A7FF', '#7AD3C8', '#F2C14A', '#7AA7FF', '#D4F24A'];
export function avatarColor(id: string): string {
  let h = 0;
  for (const c of id) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return avatarPalette[h % avatarPalette.length]!;
}

const tileFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'short', day: 'numeric', month: 'short' });
const ymdFmt = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' });

/** Éléments d’une tuile calendrier : « VEN. », « 23 », « OCT. ». */
export function dateTile(iso: string): { weekday: string; day: string; month: string } {
  const parts = tileFmt.formatToParts(new Date(iso));
  const get = (t: string) => parts.find((p) => p.type === t)?.value ?? '';
  return { weekday: get('weekday').toUpperCase(), day: get('day'), month: get('month').toUpperCase() };
}

/** « Aujourd’hui », « Demain », « Dans 5 jours », « Il y a 2 jours » (jours calendaires de Zurich). */
export function relativeDay(iso: string, now = new Date()): string {
  const day = (d: Date) => Date.parse(`${ymdFmt.format(d)}T00:00:00Z`);
  const diff = Math.round((day(new Date(iso)) - day(now)) / 86_400_000);
  if (diff === 0) return 'Aujourd’hui';
  if (diff === 1) return 'Demain';
  if (diff === -1) return 'Hier';
  if (diff > 1) return diff < 14 ? `Dans ${diff} jours` : `Dans ${Math.round(diff / 7)} semaines`;
  return `Il y a ${-diff} jours`;
}

/** « 2 présents », « 1 présent », « 0 présent ». */
export function plural(n: number, singular: string, pluralForm = `${singular}s`): string {
  return `${n} ${n > 1 ? pluralForm : singular}`;
}
