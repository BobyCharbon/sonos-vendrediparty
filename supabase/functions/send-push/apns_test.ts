// deno test supabase/functions/send-push/apns_test.ts : envoi APNs de l'app native, sans réseau (fetch simulé).
import { assert, assertEquals } from 'jsr:@std/assert@1';
import { apnsConfig, sendApns, tapPath } from './apns.ts';

const TOKEN = 'apns:' + 'ab'.repeat(32);

async function config() {
  const pair = await crypto.subtle.generateKey({ name: 'ECDSA', namedCurve: 'P-256' }, true, ['sign', 'verify']);
  const der = new Uint8Array(await crypto.subtle.exportKey('pkcs8', pair.privateKey));
  const pem = `-----BEGIN PRIVATE KEY-----\n${btoa(String.fromCharCode(...der))}\n-----END PRIVATE KEY-----`;
  const env: Record<string, string> = { APNS_KEY_P8: pem, APNS_KEY_ID: 'KEY1234567', APNS_TEAM_ID: 'GS2B6GA9JA', APNS_TOPIC: 'ch.bobycharbon.party.beta' };
  return { cfg: apnsConfig((n) => env[n])!, publicKey: pair.publicKey };
}

const unb64 = (s: string) => Uint8Array.from(atob(s.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - s.length % 4) % 4)), (c) => c.charCodeAt(0));

Deno.test('sans tous les secrets, pas de configuration', () => {
  assertEquals(apnsConfig(() => undefined), null);
});

Deno.test("le toucher ouvre l'événement, sinon l'activité", () => {
  assertEquals(tapPath({ event_id: '11111111-2222-3333-4444-555555555555' }), '/?tab=events&event=11111111-2222-3333-4444-555555555555');
  assertEquals(tapPath({ event_id: 'x"><script>' }), '/?tab=events&activity=1');
});

Deno.test('envoi signé ES256 vers le bon appareil, avec titre, texte et adresse', async () => {
  const { cfg, publicKey } = await config();
  let seen: { url: string; init: RequestInit } | null = null;
  globalThis.fetch = ((url: string, init: RequestInit) => { seen = { url, init }; return Promise.resolve(new Response(null, { status: 200 })); }) as typeof fetch;
  assertEquals(await sendApns(cfg, TOKEN, 'n1', 'Soirée raclette', 'Date choisie', { event_id: '11111111-2222-3333-4444-555555555555' }), { ok: true });
  assertEquals(seen!.url, `https://api.push.apple.com/3/device/${'ab'.repeat(32)}`);
  const headers = seen!.init.headers as Record<string, string>;
  assertEquals(headers['apns-topic'], 'ch.bobycharbon.party.beta');
  const [h, c, sig] = headers.authorization.replace('bearer ', '').split('.');
  assertEquals(JSON.parse(new TextDecoder().decode(unb64(h))), { alg: 'ES256', kid: 'KEY1234567' });
  assertEquals(JSON.parse(new TextDecoder().decode(unb64(c))).iss, 'GS2B6GA9JA');
  assert(await crypto.subtle.verify({ name: 'ECDSA', hash: 'SHA-256' }, publicKey, unb64(sig), new TextEncoder().encode(`${h}.${c}`)));
  const body = JSON.parse(seen!.init.body as string);
  assertEquals(body.aps.alert, { title: 'Soirée raclette', body: 'Date choisie' });
  assertEquals(body.url, '/?tab=events&event=11111111-2222-3333-4444-555555555555');
});

Deno.test("jeton refusé par Apple : à oublier, pas de nouvel essai", async () => {
  const { cfg } = await config();
  globalThis.fetch = (() => Promise.resolve(new Response(JSON.stringify({ reason: 'Unregistered' }), { status: 410 }))) as typeof fetch;
  assertEquals(await sendApns(cfg, TOKEN, 'n2', 't', 'b', {}), { ok: false, code: 'DeviceNotRegistered', permanent: true });
  globalThis.fetch = (() => Promise.resolve(new Response(JSON.stringify({ reason: 'TooManyRequests' }), { status: 429 }))) as typeof fetch;
  assertEquals(await sendApns(cfg, TOKEN, 'n3', 't', 'b', {}), { ok: false, code: 'TooManyRequests', permanent: false });
});
