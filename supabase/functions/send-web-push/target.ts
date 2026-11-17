/** Page ouverte au toucher d'une notification Web Push. `url` vient de notifications.data.url : seul un chemin du
 * même site (« /?tab=account ») est suivi, jamais une autre adresse (pas de redirection vers un autre site). */
export function notificationTarget(row: {
  origin: string; kind: string; event_id: string | null; group_id?: string | null; url?: unknown;
}): string {
  const target = new URL('/', row.origin);
  if ((row.kind === 'group_message' || row.kind === 'direct_message') && row.group_id && /^[0-9a-f-]{36}$/.test(row.group_id)) {
    // Discussion de groupe (avis n°10) ou message direct (4.11) : le toucher ouvre la conversation.
    target.searchParams.set('tab', 'chats');
    target.searchParams.set('chat', row.group_id);
  } else if (typeof row.kind === 'string' && row.kind.startsWith('pet_')) {
    // Compagnon (4.11) : le toucher ouvre le personnage dans l'onglet Jeux (rappel, alertes, cadeau d'un
    // ami, palier de série) ; src=notif pour la mesure des ouvertures (pet_opens).
    target.searchParams.set('tab', 'games');
    target.searchParams.set('pet', '1');
    target.searchParams.set('src', 'notif');
  } else if (row.event_id) {
    target.searchParams.set('tab', 'events');
    target.searchParams.set('event', row.event_id);
    // Message de la discussion d'un événement : le toucher ouvre la discussion (native dans l'app iPhone).
    if (row.kind === 'message') target.searchParams.set('chat', '1');
  } else {
    const own = typeof row.url === 'string' && /^\/(?![/\\])/.test(row.url) ? new URL(row.url, row.origin) : null;
    if (own && own.origin === target.origin) return own.href;  // ex. « Nouveau compte » → /?tab=account
    target.searchParams.set('tab', 'events');
    target.searchParams.set('activity', '1');
  }
  return target.href;
}

/** Étiquette de la notification (`tag`) : façon WhatsApp, un message de la discussion d'un événement remplace le
 * précédent de la même discussion au lieu de s'empiler (sw.js la refait sonner : renotify hors « party-event- ») ;
 * toute autre notification garde sa propre étiquette. */
export function notificationTag(row: { kind: string; event_id: string | null; notification_id: string }): string {
  if (row.kind === 'message' && row.event_id && /^[0-9a-f-]{36}$/.test(row.event_id)) return 'event-chat-' + row.event_id;
  return 'party-event-' + row.notification_id;
}
