import type { GroupMessage } from '@/lib/chats';

/**
 * File d'envoi des Discussions (demande de l'admin du 18.11 : « fluide, rapide, les gens ne doivent pas galérer ») :
 * la bulle s'affiche tout de suite (« Envoi… »), les messages partent dans l'ordre, un par conversation ; réseau coupé :
 * nouvel essai tout seul (0,8 s puis 2,5 s), puis « Pas envoyé · Toucher pour réessayer », et encore à chaque retour du
 * réseau. Le message reste ici même si l'écran se ferme : il n'est jamais perdu. Refus de la base (filtre, demande,
 * CGU…) : il quitte la file et son texte revient dans le champ (onRefused).
 */

export type SendResult = { ok: true } | { ok: false; network: boolean; message: string };

type Entry = {
  chat: string;
  message: GroupMessage;
  run: () => Promise<SendResult>;
  onSent?: () => void;
  onRefused?: (message: string) => void;
};

export const RETRY_MS = [800, 2500];

const entries = new Map<string, Entry>();
const queues = new Map<string, Promise<void>>();
const listeners = new Set<() => void>();
let version = 0;

function changed() {
  version += 1;
  listeners.forEach((l) => l());
}

export function subscribeOutbox(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

export const outboxVersion = () => version;

/** Messages de cette conversation pas encore revenus de la base (envoi en cours, envoyés, ou pas envoyés). */
export function outgoing(chat: string): GroupMessage[] {
  return [...entries.values()].filter((e) => e.chat === chat).map((e) => e.message);
}

/** Réseau absent (fetch qui échoue, hors ligne), par opposition à un refus de la base. */
export function isNetworkError(error: unknown): boolean {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) return true;
  if (!error) return false;
  const e = error as { name?: string; message?: string; code?: string };
  if (e.code) return false;  // la base a répondu (code Postgres / PostgREST)
  return e.name === 'TypeError' || /failed to fetch|networkerror|network request failed|load failed|fetch failed|timeout|aborted/i.test(e.message ?? '');
}

function update(id: string, change: Partial<GroupMessage>) {
  const e = entries.get(id);
  if (!e) return;
  entries.set(id, { ...e, message: { ...e.message, ...change } });
  changed();
}

const wait = (ms: number) => new Promise<void>((done) => { setTimeout(done, ms); });

async function attempt(id: string): Promise<void> {
  for (let i = 0; ; i += 1) {
    const e = entries.get(id);
    if (!e) return;
    if (e.message.failed || !e.message.pending) update(id, { pending: true, failed: false });
    let result: SendResult;
    try {
      result = await e.run();
    } catch (error) {
      result = { ok: false, network: isNetworkError(error), message: error instanceof Error ? error.message : String(error) };
    }
    if (result.ok) {
      update(id, { pending: false, failed: false });
      e.onSent?.();
      return;
    }
    if (!result.network) {
      entries.delete(id);
      changed();
      e.onRefused?.(result.message);
      return;
    }
    if (i < RETRY_MS.length) {
      await wait(RETRY_MS[i]);
      continue;
    }
    update(id, { pending: false, failed: true });
    return;
  }
}

function schedule(chat: string, id: string) {
  const next = (queues.get(chat) ?? Promise.resolve()).then(() => attempt(id));
  queues.set(chat, next.catch(() => {}));
}

/** Nouveau message : affiché aussitôt, envoyé après ceux d'avant de la même conversation. */
export function enqueue(entry: Entry): void {
  entries.set(entry.message.id, { ...entry, message: { ...entry.message, pending: true, failed: false } });
  changed();
  schedule(entry.chat, entry.message.id);
}

/** « Toucher pour réessayer » (ou réseau revenu). */
export function retry(id: string): void {
  const e = entries.get(id);
  if (!e || !e.message.failed) return;
  update(id, { pending: true, failed: false });
  schedule(e.chat, id);
}

export function retryAll(chat?: string): void {
  for (const e of [...entries.values()]) if (e.message.failed && (!chat || e.chat === chat)) retry(e.message.id);
}

/** Messages revenus de la base (lecture ou temps réel) : ils quittent la file. */
export function settle(chat: string, known: Set<string>): void {
  let any = false;
  for (const [id, e] of entries) {
    if (e.chat === chat && known.has(id) && !e.message.pending && !e.message.failed) {
      entries.delete(id);
      any = true;
    }
  }
  if (any) changed();
}

if (typeof window !== 'undefined') window.addEventListener('online', () => retryAll());
