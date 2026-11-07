/** Interrupteurs que la base n'honore jamais pour un compte sans « Voir les événements » (Membre de base, Guest) :
 * `private.may_receive_push` ne laisse passer pour eux ni ces types, ni leurs envois. On ne les affiche donc qu'aux
 * Membres VIP et au-delà (campagne 2, rapport 07 : 12 interrupteurs allumés qui ne servaient jamais).
 * Garder en phase avec la base : tests/test_web_notification_settings_c2.py compare à la dernière migration. */
export const MEMBERS_ONLY_PREFS: ReadonlySet<string> = new Set([
  'poll_new', 'poll_nudge', 'rsvp_set', 'ticket_pay_confirmed', 'ticket_issued',
  'rsvp_mine', 'proposal_result', 'ticket_pay_declared', 'proposals', 'chat', 'new_event',
]);

/** `isMember` = droit events.view (comme `private.is_member`). */
export function prefShown(key: string, isMember: boolean): boolean {
  return isMember || !MEMBERS_ONLY_PREFS.has(key);
}

const HHMM = /^([01]\d|2[0-3]):[0-5]\d$/;

/** Heure saisie « 7:5 », « 0730 », « 23h » → « 07:05 », « 07:30 », « 23:00 » ; null si ce n'est pas une heure. */
export function normalizeTime(raw: string): string | null {
  const t = raw.trim().toLowerCase().replace(/h$/, ':00').replace(/[h.]/, ':');
  const m = /^(\d{1,2}):?(\d{2})?$/.exec(t) ?? /^(\d{1,2}):(\d{1,2})$/.exec(t);
  if (!m) return null;
  const value = `${m[1].padStart(2, '0')}:${(m[2] ?? '00').padStart(2, '0')}`;
  return HHMM.test(value) ? value : null;
}
