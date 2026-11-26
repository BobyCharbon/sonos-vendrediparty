// deno test supabase/functions/send-push/apns_test.ts : envoi APNs de l'app native, sans réseau (fetch simulé).
import { assert, assertEquals } from 'jsr:@std/assert@1';
import { apnsConfig, apsFor, categoryFor, sendApns, storeAppSkips, tapPath, threadFor } from './apns.ts';

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
  assertEquals(tapPath({ kind: 'pet_daily' }), '/?tab=games&pet=1&src=notif');
  assertEquals(tapPath({ kind: 'pet_alert', event_id: '11111111-2222-3333-4444-555555555555' }), '/?tab=games&pet=1&src=notif');
  assertEquals(tapPath({ kind: 'pet_gift' }), '/?tab=games&pet=1&src=notif');
  assertEquals(tapPath({ kind: 'pet_streak' }), '/?tab=games&pet=1&src=notif');
  assertEquals(tapPath({ kind: 'pet_bar' }), '/?tab=games&pet=1&src=notif');
  assertEquals(tapPath({ kind: 'group_message', group_id: '11111111-2222-3333-4444-555555555555' }), '/?tab=chats&chat=11111111-2222-3333-4444-555555555555');
  assertEquals(tapPath({ kind: 'group_message', group_id: '../admin' }), '/?tab=events&activity=1');
  assertEquals(tapPath({ kind: 'direct_message', group_id: '11111111-2222-3333-4444-555555555555' }), '/?tab=chats&chat=11111111-2222-3333-4444-555555555555');
  assertEquals(tapPath({ kind: 'booking_request', booking_id: '11111111-2222-3333-4444-555555555555', link_id: 'x' }), '/?tab=events&booking=11111111-2222-3333-4444-555555555555');
  assertEquals(tapPath({ kind: 'booking_cancelled', booking_id: '11111111-2222-3333-4444-555555555555' }), '/?tab=events&booking=11111111-2222-3333-4444-555555555555');
  assertEquals(tapPath({ kind: 'booking_request', booking_id: '../admin' }), '/?tab=events&activity=1');
  assertEquals(tapPath({ kind: 'prono_result', prono_id: '11111111-2222-3333-4444-555555555555' }), '/?tab=events&prono=11111111-2222-3333-4444-555555555555');
  assertEquals(tapPath({ kind: 'prono_new', prono_id: '../x' }), '/?tab=events&activity=1');
  assertEquals(tapPath({ kind: 'souvenirs_revealed', event_id: '11111111-2222-3333-4444-555555555555' }), '/?tab=events&event=11111111-2222-3333-4444-555555555555&souvenirs=1');
  assertEquals(tapPath({ kind: 'souvenir_reported', event_id: '11111111-2222-3333-4444-555555555555' }), '/?tab=events&event=11111111-2222-3333-4444-555555555555&souvenirs=review');
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

Deno.test('pendant une pause : sans son, interruption « passive »', () => {
  assertEquals(apsFor('T', 'B', false), { alert: { title: 'T', body: 'B' }, sound: 'default' });
  assertEquals(apsFor('T', 'B', true), { alert: { title: 'T', body: 'B' }, 'interruption-level': 'passive' });
});

Deno.test("les notifications d'un même événement se regroupent (thread-id)", async () => {
  const { cfg } = await config();
  let sent: { aps: Record<string, unknown>; url: string } | null = null;
  globalThis.fetch = ((_: string, init: RequestInit) => { sent = JSON.parse(init.body as string); return Promise.resolve(new Response(null, { status: 200 })); }) as typeof fetch;
  await sendApns(cfg, TOKEN, 'n4', 't', 'b', { event_id: '11111111-2222-3333-4444-555555555555' });
  assertEquals(sent!.aps['thread-id'], '/?tab=events&event=11111111-2222-3333-4444-555555555555');
});

Deno.test("jeton d'un build Xcode (sandbox) : l'autre serveur d'Apple avant d'oublier l'appareil", async () => {
  const { cfg } = await config();
  const hosts: string[] = [];
  globalThis.fetch = ((url: string) => {
    hosts.push(new URL(url).host);
    const sandbox = url.includes('sandbox');
    return Promise.resolve(sandbox ? new Response(null, { status: 200 }) : new Response(JSON.stringify({ reason: 'BadDeviceToken' }), { status: 400 }));
  }) as typeof fetch;
  assertEquals(await sendApns(cfg, TOKEN, 'n5', 't', 'b', {}), { ok: true });
  assertEquals(hosts, ['api.push.apple.com', 'api.sandbox.push.apple.com']);
  globalThis.fetch = (() => Promise.resolve(new Response(JSON.stringify({ reason: 'BadDeviceToken' }), { status: 400 }))) as typeof fetch;
  assertEquals(await sendApns(cfg, TOKEN, 'n6', 't', 'b', {}), { ok: false, code: 'DeviceNotRegistered', permanent: true });
});

const EVENT = '11111111-2222-3333-4444-555555555555';

Deno.test("discussion d'événement façon WhatsApp : une pile par discussion, actions Répondre / Marquer comme lu", async () => {
  const { cfg } = await config();
  let sent: { aps: Record<string, unknown>; url: string; event_id?: string } | null = null;
  globalThis.fetch = ((_: string, init: RequestInit) => { sent = JSON.parse(init.body as string); return Promise.resolve(new Response(null, { status: 200 })); }) as typeof fetch;
  const data = { kind: 'message', event_id: EVENT, message_id: '99999999-2222-3333-4444-555555555555', thread: `event-chat:${EVENT}` };
  await sendApns(cfg, TOKEN, 'n7', 'Soirée raclette', 'Léa : On amène quoi ?', data);
  assertEquals(sent!.aps['thread-id'], `event-chat:${EVENT}`);
  assertEquals(sent!.aps.category, 'EVENT_CHAT');
  assertEquals(sent!.aps.alert, { title: 'Soirée raclette', body: 'Léa : On amène quoi ?' });
  assertEquals(sent!.event_id, EVENT);
  assertEquals(sent!.url, `/?tab=events&event=${EVENT}&chat=1`);
  // « Organisation seulement » et pas de l'organisation : « Marquer comme lu » seul, jamais « Répondre ».
  await sendApns(cfg, TOKEN, 'n9', 'Soirée raclette', 'Léa : Rendez-vous à 20 h', { ...data, can_reply: false });
  assertEquals(sent!.aps.category, 'EVENT_CHAT_READONLY');
  // Autre notification de l'événement : ni catégorie ni event_id, regroupée par adresse comme avant.
  await sendApns(cfg, TOKEN, 'n8', 'Soirée raclette', 'Date choisie', { kind: 'event_changed', event_id: EVENT });
  assertEquals(sent!.aps.category, undefined);
  assertEquals(sent!.event_id, undefined);
  assertEquals(sent!.aps['thread-id'], `/?tab=events&event=${EVENT}`);
});

Deno.test('thread-id et catégorie : data.thread, sinon déduits du message ; rien de forgé', () => {
  assertEquals(threadFor({ kind: 'message', event_id: EVENT }), `event-chat:${EVENT}`);   // base d'avant 20261117190000
  assertEquals(threadFor({ kind: 'message', event_id: EVENT, thread: `event-chat:${EVENT}` }), `event-chat:${EVENT}`);
  assertEquals(threadFor({ kind: 'message', event_id: EVENT, thread: 'x"><b>' }), `event-chat:${EVENT}`);
  assertEquals(threadFor({ kind: 'group_message', group_id: EVENT }), `/?tab=chats&chat=${EVENT}`);
  assertEquals(categoryFor({ kind: 'message', event_id: EVENT }), 'EVENT_CHAT');
  assertEquals(categoryFor({ kind: 'message', event_id: EVENT, can_reply: true }), 'EVENT_CHAT');
  assertEquals(categoryFor({ kind: 'message', event_id: EVENT, can_reply: false }), 'EVENT_CHAT_READONLY');
  assertEquals(categoryFor({ kind: 'message', event_id: '../admin' }), null);
  assertEquals(categoryFor({ kind: 'event_changed', event_id: EVENT }), null);
  assertEquals(categoryFor({ kind: 'group_message', group_id: EVENT }), null);
});

Deno.test('app App Store : aucune notification du bar ; la BETA les garde', () => {
  assertEquals(storeAppSkips('ch.bobycharbon.party', 'bar_served'), true);
  assertEquals(storeAppSkips('ch.bobycharbon.party', 'bar_refund_declared'), true);
  assertEquals(storeAppSkips('ch.bobycharbon.party', 'event_changed'), false);
  assertEquals(storeAppSkips('ch.bobycharbon.party.beta', 'bar_served'), false);
});
