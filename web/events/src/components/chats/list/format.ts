import type { ChatItem } from '@/lib/chatList';

const ZURICH = 'Europe/Zurich';
const dayKey = (d: Date) => new Intl.DateTimeFormat('fr-CH', { timeZone: ZURICH, dateStyle: 'short' }).format(d);
const cap = (s: string) => s.charAt(0).toUpperCase() + s.slice(1);

/** Heure de la liste : « 21:48 » aujourd'hui, « Hier », « Lun. » cette semaine, puis « 3 nov. » (heure de Suisse). */
export function listTime(iso: string, now = new Date()): string {
  const d = new Date(iso);
  if (dayKey(d) === dayKey(now)) return new Intl.DateTimeFormat('fr-CH', { timeZone: ZURICH, hour: '2-digit', minute: '2-digit' }).format(d);
  if (dayKey(d) === dayKey(new Date(now.getTime() - 86_400_000))) return 'Hier';
  const days = (now.getTime() - d.getTime()) / 86_400_000;
  if (days < 6.5) return cap(new Intl.DateTimeFormat('fr-CH', { timeZone: ZURICH, weekday: 'short' }).format(d)).replace(/\.?$/, '.');
  const sameYear = d.getFullYear() === now.getFullYear();
  return new Intl.DateTimeFormat('fr-CH', sameYear ? { timeZone: ZURICH, day: 'numeric', month: 'short' }
    : { timeZone: ZURICH, day: '2-digit', month: '2-digit', year: '2-digit' }).format(d);
}

/** Texte de l'aperçu (sans l'auteur) : photo, vocal, soirée, message supprimé. */
export function previewText(last: NonNullable<ChatItem['last']>): string {
  switch (last.type) {
    case 'photo': return last.text ? `📷 ${last.text}` : '📷 Photo';
    case 'audio': return last.text || 'Message vocal';
    case 'event': return `📅 ${last.text || 'Soirée partagée'}`;
    case 'deleted': return 'Message supprimé';
    default: return last.text ?? '';
  }
}

/** Morceaux de texte : les @citations à part (en rose dans l'aperçu). */
export function mentionChunks(text: string): { text: string; at: boolean }[] {
  const out: { text: string; at: boolean }[] = [];
  const re = /@[\p{L}\p{N}_.-]+/gu;
  let i = 0;
  for (const m of text.matchAll(re)) {
    if (m.index! > i) out.push({ text: text.slice(i, m.index), at: false });
    out.push({ text: m[0], at: true });
    i = m.index! + m[0].length;
  }
  if (i < text.length) out.push({ text: text.slice(i), at: false });
  return out;
}

export function plural(n: number, one: string, many = `${one}s`): string {
  return `${n} ${n > 1 ? many : one}`;
}
