// Chaque appel est authentifié par un secret conservé dans Vault.
// Une livraison par appareil, avec reprise sur erreur et suivi des reçus Expo.
import { createClient } from 'npm:@supabase/supabase-js@2.117.3';
import { APNS_TOKEN, apnsConfig, sendApns } from './apns.ts';

const EXPO_URL = 'https://exp.host/--/api/v2/push';
type Delivery = {
  delivery_id: string; notification_id: string; user_id: string; token: string;
  attempts: number; title: string; body: string; data: Record<string, unknown>;
};
type Ticket = { status?: string; id?: string; details?: { error?: string } };
type ReceiptRow = { id: string; token: string; ticket_id: string; requested_at: string };

function checked<T>({ data, error }: { data: T; error: { message: string } | null }): T {
  if (error) throw new Error('Database operation failed');
  return data;
}

async function expoRequest(path: string, body: unknown) {
  const accessToken = Deno.env.get('EXPO_ACCESS_TOKEN');
  return await fetch(`${EXPO_URL}/${path}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json', Accept: 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
    },
    body: JSON.stringify(body), signal: AbortSignal.timeout(10_000),
  });
}

Deno.serve(async (req: Request) => {
  if (req.method !== 'POST') return new Response('Method not allowed', { status: 405 });
  const secret = req.headers.get('x-job-secret');
  if (!secret || !/^[a-f0-9]{64}$/.test(secret)) return new Response('Unauthorized', { status: 401 });
  const db = createClient(Deno.env.get('SUPABASE_URL')!, Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!, {
    auth: { persistSession: false, autoRefreshToken: false },
  });
  const totals = { accepted: 0, delivered: 0, retried: 0, failed: 0 };
  try {
    if (!checked(await db.rpc('authorize_push_job', { candidate: secret }))) {
      return new Response('Unauthorized', { status: 401 });
    }
    checked(await db.rpc('prepare_push_deliveries'));

    async function failOrRetry(row: Delivery, code: string, permanent = false) {
      const failed = permanent || row.attempts >= 8;
      const next = new Date(Date.now() + Math.min(3_600_000, 30_000 * 2 ** (row.attempts - 1))).toISOString();
      checked(await db.from('notification_deliveries').update({
        status: failed ? 'failed' : 'queued', error: code.slice(0, 100),
        next_attempt_at: next, lease_until: null,
      }).eq('id', row.delivery_id).eq('status', 'queued'));
      if (code === 'DeviceNotRegistered') checked(await db.from('push_tokens').delete().eq('token', row.token).eq('user_id', row.user_id));
      totals[failed ? 'failed' : 'retried']++;
    }

    // Limite la durée d'un passage ; les suivants reprendront les autres lignes.
    for (let page = 0; page < 5; page++) {
      const claimed = checked(await db.rpc('claim_push_deliveries', { batch_size: 100 })) as Delivery[];
      if (!claimed.length) break;
      // App iOS native : directement chez Apple (pas de reçu à attendre). Sans clé APNs configurée, on réessaie plus tard.
      const apns = apnsConfig((name) => Deno.env.get(name));
      for (const row of claimed.filter((r) => APNS_TOKEN.test(r.token))) {
        if (!apns) { await failOrRetry(row, 'ApnsNotConfigured'); continue; }
        const sent = await sendApns(apns, row.token, row.notification_id, row.title, row.body, row.data ?? {});
        if (sent.ok) {
          checked(await db.from('notification_deliveries').update({
            status: 'delivered', requested_at: new Date().toISOString(), lease_until: null, error: null,
          }).eq('id', row.delivery_id).eq('status', 'queued'));
          totals.delivered++;
        } else {
          await failOrRetry(row, sent.code, sent.permanent);
        }
      }
      const batch = claimed.filter((r) => !APNS_TOKEN.test(r.token));
      if (!batch.length) continue;
      let tickets: Ticket[];
      try {
        const response = await expoRequest('send', batch.map((row) => ({
          to: row.token, title: row.title, body: row.body, data: row.data, sound: 'default',
        })));
        if (!response.ok) {
          for (const row of batch) await failOrRetry(row, `ExpoHTTP${response.status}`);
          break;
        }
        const result = await response.json();
        tickets = Array.isArray(result.data) ? result.data : [];
      } catch {
        for (const row of batch) await failOrRetry(row, 'ExpoUnavailable');
        break;
      }
      for (const [index, row] of batch.entries()) {
        const ticket = tickets[index];
        if (ticket?.status === 'ok' && ticket.id) {
          checked(await db.from('notification_deliveries').update({
            status: 'ticketed', ticket_id: ticket.id, requested_at: new Date().toISOString(), lease_until: null, error: null,
          }).eq('id', row.delivery_id).eq('status', 'queued'));
          totals.accepted++;
        } else {
          const code = ticket?.details?.error || 'InvalidExpoTicket';
          await failOrRetry(row, code, ['DeviceNotRegistered', 'MessageTooBig'].includes(code));
        }
      }
    }

    const now = Date.now();
    const receipts = checked(await db.from('notification_deliveries')
      .select('id, token, ticket_id, requested_at').eq('status', 'ticketed')
      .lt('requested_at', new Date(now - 15 * 60_000).toISOString())
      .or(`receipt_checked_at.is.null,receipt_checked_at.lt.${new Date(now - 5 * 60_000).toISOString()}`)
      .order('requested_at').limit(300)) as ReceiptRow[];
    if (receipts.length) {
      // Un reçu absent n'entraîne jamais le renvoi d'un ticket déjà accepté.
      try {
        const response = await expoRequest('getReceipts', { ids: receipts.map((row) => row.ticket_id) });
        if (response.ok) {
          const result = await response.json() as { data?: Record<string, Ticket> };
          for (const row of receipts) {
            const receipt = result.data?.[row.ticket_id];
            const expired = now - Date.parse(row.requested_at) >= 24 * 60 * 60_000;
            const status = receipt?.status === 'ok' ? 'delivered' : receipt?.status === 'error' || expired ? 'failed' : 'ticketed';
            const code = receipt?.details?.error || (expired && !receipt ? 'ReceiptUnavailable' : null);
            checked(await db.from('notification_deliveries').update({
              status, error: code, receipt_checked_at: new Date(now).toISOString(),
            }).eq('id', row.id).eq('status', 'ticketed'));
            if (code === 'DeviceNotRegistered') {
              // Conserve un jeton réenregistré depuis l'envoi.
              checked(await db.from('push_tokens').delete().eq('token', row.token).lt('updated_at', row.requested_at));
            }
            if (status === 'delivered') totals.delivered++;
            if (status === 'failed') totals.failed++;
          }
        }
      } catch {
        // Reprise au passage suivant, sans exposer les jetons dans les logs.
        console.warn('Expo receipts temporarily unavailable');
      }
    }
    checked(await db.rpc('finalize_push_notifications'));
    return Response.json(totals);
  } catch {
    console.error('Push delivery job interrupted; queued leases will expire');
    return Response.json({ error: 'Push job unavailable' }, { status: 500 });
  }
});
