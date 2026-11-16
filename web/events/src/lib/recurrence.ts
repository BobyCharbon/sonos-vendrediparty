/** Événements récurrents (demande de l'admin du 16.11.2026, migration 20261116170000) : une seule date à la fois, la
 * suivante apparaît quand celle-ci est terminée ; elle reprend la dernière (titre, lieu, options, invités, co-organisateurs). */
export type Frequency = 'none' | 'daily' | 'weekly' | 'monthly' | 'yearly';
export type Repeat = { frequency: Frequency; every: number; until: string };
export type Series = { frequency: Exclude<Frequency, 'none'>; every: number; until: string | null; stopped_at: string | null };

export const NO_REPEAT: Repeat = { frequency: 'none', every: 1, until: '' };

export const REPEAT_CHOICES: { label: string; frequency: Frequency; every: number }[] = [
  { label: 'Ne se répète pas', frequency: 'none', every: 1 },
  { label: 'Chaque jour', frequency: 'daily', every: 1 },
  { label: 'Chaque semaine', frequency: 'weekly', every: 1 },
  { label: 'Toutes les 2 semaines', frequency: 'weekly', every: 2 },
  { label: 'Chaque mois', frequency: 'monthly', every: 1 },
  { label: 'Chaque année', frequency: 'yearly', every: 1 },
];

const TZ = 'Europe/Zurich';
const weekday = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'long' });
const dayOfMonth = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, day: 'numeric' });
const dayMonth = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, day: 'numeric', month: 'long' });
const time = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, hour: '2-digit', minute: '2-digit' });
const untilFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: 'UTC', day: 'numeric', month: 'long', year: 'numeric' });

/** « Chaque semaine, le lundi à 19:00 », « Toutes les 2 semaines… », « Chaque mois, le 17 à 19:00 », « jusqu’au 20 décembre 2026 ». */
export function repeatLabel(r: { frequency: Frequency; every: number; until?: string | null }, startsIso: string | null): string {
  if (r.frequency === 'none') return 'Ne se répète pas';
  const base = REPEAT_CHOICES.find((c) => c.frequency === r.frequency && c.every === r.every)?.label
    ?? `Tous les ${r.every} ${{ daily: 'jours', weekly: 'semaines', monthly: 'mois', yearly: 'ans' }[r.frequency]}`;
  let when = '';
  if (startsIso) {
    const d = new Date(startsIso);
    const at = `à ${time.format(d)}`;
    when = r.frequency === 'weekly' ? `, le ${weekday.format(d)} ${at}` : r.frequency === 'monthly' ? `, le ${dayOfMonth.format(d)} ${at}`
      : r.frequency === 'yearly' ? `, le ${dayMonth.format(d)} ${at}` : ` ${at}`;
  }
  const day = r.until?.match(/^\d{4}-\d{2}-\d{2}/) ? new Date(`${r.until.slice(0, 10)}T12:00:00Z`) : null;
  const until = day && !Number.isNaN(day.getTime()) ? ` · jusqu’au ${untilFmt.format(day)}` : '';
  return `${base}${when}${until}`;
}

/** « JJ.MM.AAAA HH:MM » (champ du formulaire) → « AAAA-MM-JJ » ; vide → null. */
export function untilDate(field: string): string | null {
  const m = field.trim().match(/^(\d{2})\.(\d{2})\.(\d{4})/);
  return m ? `${m[3]}-${m[2]}-${m[1]}` : null;
}

/** « AAAA-MM-JJ » (base) → « JJ.MM.AAAA 23:55 » (champ du formulaire, l'heure n'y compte pas). */
export function untilField(date: string | null | undefined): string {
  const m = date?.match(/^(\d{4})-(\d{2})-(\d{2})/);
  return m ? `${m[3]}.${m[2]}.${m[1]} 23:55` : '';
}

export function repeatOf(series: Series | null | undefined): Repeat {
  if (!series || series.stopped_at) return NO_REPEAT;
  return { frequency: series.frequency, every: series.every, until: untilField(series.until) };
}
