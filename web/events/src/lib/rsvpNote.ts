/** Petit mot pour l'organisateur (campagne 2) : rangé par la base dans `rsvp_notes`, lu par la personne, l'organisation
 * et les admins seulement. On l'écrit toujours par `rsvps.note` : `null` = mot inchangé, `''` = mot effacé.
 * Module sans dépendance : testé tel quel par Node (tests/test_web_rsvp_note.py). */

export type RsvpNote = { id: string; user_id: string; note: string };

/** Valeur à envoyer dans `rsvps.note` : `undefined` = ne rien envoyer (mot inchangé), `''` = effacer, sinon le mot. */
export function noteToSend(saved: string | null | undefined, typed: string | null | undefined): string | undefined {
  const before = (saved ?? '').trim();
  const after = (typed ?? '').trim();
  return after === before ? undefined : after;
}

/** Mots que l'écran « Qui vient ? » montre : ceux des AUTRES (le mien est dans le champ de ma réponse), dans l'ordre
 * des réponses. La base ne rend que ce qu'on a le droit de lire : un invité ne voit jamais le mot d'un autre. */
export function othersNotes(notes: readonly RsvpNote[], me: string, order: readonly string[]): RsvpNote[] {
  const rank = new Map(order.map((id, i) => [id, i]));
  return notes
    .filter((n) => n.user_id !== me && n.note.trim() !== '')
    .slice()
    .sort((a, b) => (rank.get(a.user_id) ?? order.length) - (rank.get(b.user_id) ?? order.length));
}
