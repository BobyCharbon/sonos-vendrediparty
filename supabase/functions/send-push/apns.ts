// Envoi direct à Apple (APNs, HTTP/2) pour l'app iOS native : jetons « apns:<hex> » (migration 20261028180000).
// Même principe que le serveur Party (app/apns.py) : jeton JWT ES256 signé par la clé .p8 de l'équipe, gardé 50 min.
// Secrets de la fonction : APNS_KEY_P8 (contenu du .p8), APNS_KEY_ID, APNS_TEAM_ID, APNS_TOPIC (identifiant de l'app :
// ch.bobycharbon.party en prod, ch.bobycharbon.party.beta sur la base de test) ; APNS_SANDBOX=1 pour un build Xcode.

export const APNS_TOKEN = /^apns:([0-9a-f]{64,200})$/;

/** App VendrediParty de l'App Store (topic sans « .beta ») : aucune notification du bar (refus Apple 1.4.3, 25.11 :
 *  le bar n'existe pas dans cette app). La BETA et le Web Push les gardent. */
export function storeAppSkips(topic: string, kind: string): boolean {
  return topic === 'ch.bobycharbon.party' && kind.startsWith('bar_');
}
const JWT_LIFETIME_MS = 50 * 60_000;
const PRODUCTION = 'api.push.apple.com', SANDBOX = 'api.sandbox.push.apple.com';

type Config = { key: string; keyId: string; teamId: string; topic: string; host: string };
export type ApnsResult = { ok: true } | { ok: false; code: string; permanent: boolean };

export function apnsConfig(env: (name: string) => string | undefined): Config | null {
  const key = env('APNS_KEY_P8'), keyId = env('APNS_KEY_ID'), teamId = env('APNS_TEAM_ID'), topic = env('APNS_TOPIC');
  if (!key || !keyId || !teamId || !topic) return null;
  const host = env('APNS_SANDBOX') === '1' ? SANDBOX : PRODUCTION;
  return { key, keyId, teamId, topic, host };
}

const base64url = (bytes: Uint8Array | string) =>
  btoa(typeof bytes === 'string' ? bytes : String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');

let cached: { jwt: string; at: number; keyId: string } | null = null;

async function jwt(config: Config): Promise<string> {
  if (cached && cached.keyId === config.keyId && Date.now() - cached.at < JWT_LIFETIME_MS) return cached.jwt;
  const pem = config.key.replace(/-----[^-]+-----/g, '').replace(/\s+/g, '');
  const der = Uint8Array.from(atob(pem), (c) => c.charCodeAt(0));
  const key = await crypto.subtle.importKey('pkcs8', der, { name: 'ECDSA', namedCurve: 'P-256' }, false, ['sign']);
  const header = base64url(JSON.stringify({ alg: 'ES256', kid: config.keyId }));
  const claims = base64url(JSON.stringify({ iss: config.teamId, iat: Math.floor(Date.now() / 1000) }));
  // WebCrypto rend la signature au format r||s (64 octets), celui qu'attend un JWT.
  const signature = new Uint8Array(await crypto.subtle.sign({ name: 'ECDSA', hash: 'SHA-256' }, key, new TextEncoder().encode(`${header}.${claims}`)));
  cached = { jwt: `${header}.${claims}.${base64url(signature)}`, at: Date.now(), keyId: config.keyId };
  return cached.jwt;
}

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

/** Toucher de la notification : la discussion du groupe (avis n°10) ou le message direct (4.11), sinon l'onglet Événements sur l'événement
 * concerné (comme send-web-push). */
export function tapPath(data: Record<string, unknown>): string {
  // Compagnon (onglet Jeux) : rappel, alertes, cadeau d'un ami, palier de série ; src=notif pour la mesure (pet_opens).
  if (typeof data.kind === 'string' && data.kind.startsWith('pet_')) return '/?tab=games&pet=1&src=notif';
  if ((data.kind === 'group_message' || data.kind === 'direct_message' || data.kind === 'group_added') && typeof data.group_id === 'string' && UUID.test(data.group_id)) return `/?tab=chats&chat=${data.group_id}`;
  // Demande de message (Discussions v2, 18.11) : l'écran des demandes.
  if (data.kind === 'message_request') return '/?tab=chats&requests=1';
  // Agenda (17.11) : demande de rendez-vous reçue ou annulée → la demande dans l'Agenda (app/static/events-shell.js).
  if ((data.kind === 'booking_request' || data.kind === 'booking_cancelled') && typeof data.booking_id === 'string' && UUID.test(data.booking_id)) return `/?tab=events&booking=${data.booking_id}`;
  // Pronos (17.11) : nouveau prono, résultat, résultat à donner → le prono (écran natif de l'app iPhone).
  if (typeof data.kind === 'string' && data.kind.startsWith('prono_') && typeof data.prono_id === 'string' && UUID.test(data.prono_id)) return `/?tab=events&prono=${data.prono_id}`;
  const event = typeof data.event_id === 'string' && /^[0-9a-f-]{36}$/.test(data.event_id) ? data.event_id : null;
  // Message de la discussion d'un événement : le toucher ouvre la discussion (écran natif de l'app iPhone).
  if (event && data.kind === 'message') return `/?tab=events&event=${event}&chat=1`;
  return event ? `/?tab=events&event=${event}` : '/?tab=events&activity=1';
}

/** Message de la discussion d'un événement (kind « message ») : son événement, sinon null. */
function eventChat(data: Record<string, unknown>): string | null {
  return data.kind === 'message' && typeof data.event_id === 'string' && UUID.test(data.event_id) ? data.event_id : null;
}

/** Regroupement sur l'iPhone (thread-id) : façon WhatsApp, une pile par discussion. `data.thread` (« event-chat:<id> »,
 * migration 20261117190000) sinon déduit du message ; les autres notifications : une pile par adresse ouverte. */
export function threadFor(data: Record<string, unknown>): string {
  if (typeof data.thread === 'string' && /^[a-z-]{1,20}:[0-9a-f-]{36}$/.test(data.thread)) return data.thread;
  const event = eventChat(data);
  return event ? `event-chat:${event}` : tapPath(data);
}

/** Catégorie iOS des actions de la notification (ChatNotificationActions.swift) : « Répondre » et « Marquer comme lu »
 * sur un message de discussion d'événement ; « Marquer comme lu » seul quand la personne ne peut pas écrire
 * (discussion « Organisation seulement » : data.can_reply = false ; absent = peut répondre). */
export function categoryFor(data: Record<string, unknown>): string | null {
  if (!eventChat(data)) return null;
  return data.can_reply === false ? 'EVENT_CHAT_READONLY' : 'EVENT_CHAT';
}

/** Pendant une pause (lune, Discussions), data.silent : la notification arrive sans son ni vibration, rangée
 * dans le centre de notifications sans allumer l'écran (interruption-level « passive »). */
export function apsFor(title: string, body: string, silent: boolean): Record<string, unknown> {
  const alert = { title: title.slice(0, 100), body: body.slice(0, 180) };
  return silent ? { alert, 'interruption-level': 'passive' } : { alert, sound: 'default' };
}

export async function sendApns(config: Config, token: string, notificationId: string, title: string, body: string,
                               data: Record<string, unknown>): Promise<ApnsResult> {
  const device = APNS_TOKEN.exec(token)?.[1];
  if (!device) return { ok: false, code: 'BadDeviceToken', permanent: true };
  const url = tapPath(data);
  // thread-id : les notifications d'une même discussion (ou d'un même événement) se regroupent sur l'iPhone ;
  // category : actions « Répondre » / « Marquer comme lu », qui ont besoin de l'événement (event_id).
  const category = categoryFor(data);
  const payload = {
    aps: { ...apsFor(title, body, data.silent === true), 'thread-id': threadFor(data), ...(category ? { category } : {}) },
    url, ...(category ? { event_id: data.event_id } : {}),
  };
  const post = async (host: string) => {
    const response = await fetch(`https://${host}/3/device/${device}`, {
      method: 'POST',
      headers: {
        authorization: `bearer ${await jwt(config)}`, 'apns-topic': config.topic, 'apns-push-type': 'alert',
        'apns-priority': data.silent === true ? '5' : '10', 'apns-collapse-id': `party-event-${notificationId}`.slice(0, 64),
      },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(10_000),
    });
    if (response.ok) return { response, reason: '' };
    return { response, reason: ((await response.json().catch(() => ({}))) as { reason?: string }).reason || `ApnsHTTP${response.status}` };
  };
  let response: Response, reason: string;
  try {
    ({ response, reason } = await post(config.host));
    // Jeton d'un build Xcode (serveur « sandbox » d'Apple) sur une base réglée pour TestFlight / l'App Store, ou
    // l'inverse : l'autre serveur d'Apple avant d'oublier l'appareil.
    if (reason === 'BadDeviceToken') {
      ({ response, reason } = await post(config.host === SANDBOX ? PRODUCTION : SANDBOX));
    }
  } catch {
    return { ok: false, code: 'ApnsUnavailable', permanent: false };
  }
  if (response.ok) return { ok: true };
  // Appareil désinscrit ou jeton d'une autre app : comme « DeviceNotRegistered » chez Expo, on oublie ce jeton.
  const gone = response.status === 410 || ['BadDeviceToken', 'DeviceTokenNotForTopic', 'Unregistered'].includes(reason);
  return { ok: false, code: gone ? 'DeviceNotRegistered' : reason, permanent: gone || response.status === 400 };
}
