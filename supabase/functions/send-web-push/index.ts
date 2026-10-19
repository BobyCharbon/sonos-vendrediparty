import { createClient } from '@supabase/supabase-js';
import webpush from 'web-push';

type Keys = { publicKey: string; privateKey: string };
type Delivery = {
  id: string; attempts: number; subscription: { endpoint: string; keys: { auth: string; p256dh: string } };
  title: string; body: string; kind: string; origin: string; event_id: string | null; notification_id: string;
};
function checked<T>({ data, error }: { data: T; error: unknown }): T {
  if (error) throw new Error('Database operation failed');
  return data;
}

// Seul le cron possédant le secret de Vault peut utiliser cette fonction.
Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') return new Response('Method not allowed', { status: 405 });
  const secret = req.headers.get('x-job-secret');
  if (!secret || !/^[a-f0-9]{64}$/.test(secret)) return new Response('Unauthorized', { status: 401 });
  const db = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  try {
    if (!checked(await db.rpc('authorize_push_job', { candidate: secret }))) return new Response('Unauthorized', { status: 401 });
    let keys = checked(await db.rpc('web_push_config_keys')) as Keys | null;
    if (!keys) {
      const generated = webpush.generateVAPIDKeys();
      // L’insertion atomique conserve une seule paire même avec plusieurs passages concurrents.
      keys = checked(await db.rpc('web_push_config_keys', { initial_public: generated.publicKey, initial_private: generated.privateKey })) as Keys;
    }
    checked(await db.rpc('prepare_web_push_deliveries'));
    let accepted = 0;
    let postponed = 0;
    const deadline = Date.now() + 40000;
    while (Date.now() < deadline) {
      const batch = checked(await db.rpc('claim_web_push_deliveries', { batch_size: 20 })) as Delivery[];
      if (!batch.length) break;
      // Cinq envois au maximum en parallèle ; le cron suivant reprend le reste.
      for (let offset = 0; offset < batch.length; offset += 5) {
        await Promise.all(batch.slice(offset, offset + 5).map(async (row) => {
          let code = 0;
          try {
            if (!['https://party.bobycharbon.ch', 'https://partytest.bobycharbon.ch'].includes(row.origin)) throw new Error('Invalid origin');
            const endpoint = new URL(row.subscription.endpoint);
            const hosts = ['fcm.googleapis.com', 'push.services.mozilla.com', 'push.apple.com', 'notify.windows.com'];
            if (endpoint.protocol !== 'https:' || endpoint.username || endpoint.password || (endpoint.port && endpoint.port !== '443')
              || !hosts.some((host) => endpoint.hostname === host || (host !== 'fcm.googleapis.com' && endpoint.hostname.endsWith('.' + host)))) throw new Error('Invalid endpoint');
            const target = new URL('/', row.origin);
            target.searchParams.set('tab', 'events');
            if (row.event_id) target.searchParams.set('event', row.event_id);
            else target.searchParams.set('activity', '1');
            const payload = JSON.stringify({
              title: row.title.slice(0, 100), body: row.body.slice(0, 180),
              tag: 'party-event-' + row.notification_id, url: target.href,
            });
            const request = webpush.generateRequestDetails(row.subscription, payload, {
              vapidDetails: { ...keys!, subject: 'https://party.bobycharbon.ch' },
              TTL: 3600, contentEncoding: 'aes128gcm', urgency: 'normal',
            });
            const response = await fetch(row.subscription.endpoint, {
              method: 'POST', headers: request.headers, body: new Uint8Array(request.body),
              redirect: 'error', signal: AbortSignal.timeout(5000),
            });
            code = response.status;
            await response.body?.cancel();
          } catch {
            // Ni l’adresse d’un appareil ni ses clés ne sont écrites dans les logs.
          }
          checked(await db.rpc('finish_web_push_delivery', { delivery_id: row.id, result_code: code }));
          if (code >= 200 && code < 300) accepted++; else postponed++;
        }));
      }
    }
    // « accepted » signifie accepté par le service push, pas affiché sur le téléphone.
    return Response.json({ accepted, postponed });
  } catch {
    console.error('Web push job interrupted; pending leases will expire');
    return Response.json({ error: 'Web push job unavailable' }, { status: 500 });
  }
});
