// Envoi direct à Apple (APNs, HTTP/2) pour l'app iOS native : jetons « apns:<hex> » (migration 20261028180000).
// Même principe que le serveur Party (app/apns.py) : jeton JWT ES256 signé par la clé .p8 de l'équipe, gardé 50 min.
// Secrets de la fonction : APNS_KEY_P8 (contenu du .p8), APNS_KEY_ID, APNS_TEAM_ID, APNS_TOPIC (identifiant de l'app :
// ch.bobycharbon.party en prod, ch.bobycharbon.party.beta sur la base de test) ; APNS_SANDBOX=1 pour un build Xcode.

export const APNS_TOKEN = /^apns:([0-9a-f]{64,200})$/;
const JWT_LIFETIME_MS = 50 * 60_000;

type Config = { key: string; keyId: string; teamId: string; topic: string; host: string };
export type ApnsResult = { ok: true } | { ok: false; code: string; permanent: boolean };

export function apnsConfig(env: (name: string) => string | undefined): Config | null {
  const key = env('APNS_KEY_P8'), keyId = env('APNS_KEY_ID'), teamId = env('APNS_TEAM_ID'), topic = env('APNS_TOPIC');
  if (!key || !keyId || !teamId || !topic) return null;
  const host = env('APNS_SANDBOX') === '1' ? 'api.sandbox.push.apple.com' : 'api.push.apple.com';
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

/** Toucher de la notification : la discussion du groupe (avis n°10), sinon l'onglet Événements sur l'événement
 * concerné (comme send-web-push). */
export function tapPath(data: Record<string, unknown>): string {
  if (data.kind === 'group_message' && typeof data.group_id === 'string' && UUID.test(data.group_id)) return `/?tab=chats&chat=${data.group_id}`;
  const event = typeof data.event_id === 'string' && /^[0-9a-f-]{36}$/.test(data.event_id) ? data.event_id : null;
  return event ? `/?tab=events&event=${event}` : '/?tab=events&activity=1';
}

export async function sendApns(config: Config, token: string, notificationId: string, title: string, body: string,
                               data: Record<string, unknown>): Promise<ApnsResult> {
  const device = APNS_TOKEN.exec(token)?.[1];
  if (!device) return { ok: false, code: 'BadDeviceToken', permanent: true };
  const payload = { aps: { alert: { title: title.slice(0, 100), body: body.slice(0, 180) }, sound: 'default' }, url: tapPath(data) };
  let response: Response;
  try {
    response = await fetch(`https://${config.host}/3/device/${device}`, {
      method: 'POST',
      headers: {
        authorization: `bearer ${await jwt(config)}`, 'apns-topic': config.topic, 'apns-push-type': 'alert',
        'apns-priority': '10', 'apns-collapse-id': `party-event-${notificationId}`.slice(0, 64),
      },
      body: JSON.stringify(payload), signal: AbortSignal.timeout(10_000),
    });
  } catch {
    return { ok: false, code: 'ApnsUnavailable', permanent: false };
  }
  if (response.ok) return { ok: true };
  const reason = ((await response.json().catch(() => ({}))) as { reason?: string }).reason || `ApnsHTTP${response.status}`;
  // Appareil désinscrit ou jeton d'une autre app : comme « DeviceNotRegistered » chez Expo, on oublie ce jeton.
  const gone = response.status === 410 || ['BadDeviceToken', 'DeviceTokenNotForTopic', 'Unregistered'].includes(reason);
  return { ok: false, code: gone ? 'DeviceNotRegistered' : reason, permanent: gone || response.status === 400 };
}
