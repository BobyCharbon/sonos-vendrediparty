import { useCallback, useEffect, useRef, useState } from 'react';

import { supabase } from '@/lib/supabase';

/** Discussions v2 (contrat §2, §6) : demandes de message, Vu, « écrit… », cartes de soirée, réponse en privé. */

export type ChatEventCard = { id: string; title: string; start: string | null; place: string | null; cover: string | null;
  going: number; mine: 'yes' | 'maybe' | 'no' | 'invited' | null };

/** Citation d'un message de groupe / de soirée dans une conversation directe (« Répondre en privé »). */
export type PrivateQuote = { from: 'group' | 'event'; title: string; author: string; excerpt: string };

/** État d'une conversation directe : 'request' tant que le destinataire n'a pas accepté. */
export type DirectState = { status: 'active' | 'request'; requestedBy: string | null; declined: boolean };

/** Cartes des soirées citées dans les messages (seulement celles que je peux voir : can_see_event). */
export async function fetchEventCards(ids: string[]): Promise<Map<string, ChatEventCard>> {
  const unique = [...new Set(ids)];
  if (!unique.length) return new Map();
  const { data, error } = await supabase.rpc('chat_event_cards', { ids: unique });
  if (error || !Array.isArray(data)) return new Map();
  return new Map((data as ChatEventCard[]).map((c) => [c.id, c]));
}

/** Ce qui attend la conversation directe qu'on ouvre (« Répondre en privé », « Envoyer à un ami ») : gardé le temps
 * de la navigation, repris une seule fois par l'écran de la conversation. */
const drafts = new Map<string, { quote?: PrivateQuote; event?: string }>();
export function putDraft(chat: string, draft: { quote?: PrivateQuote; event?: string }) {
  drafts.set(chat, { ...drafts.get(chat), ...draft });
}
export function takeDraft(chat: string): { quote?: PrivateQuote; event?: string } {
  const d = drafts.get(chat) ?? {};
  drafts.delete(chat);
  return d;
}

export type OpenDirect = { chat: string | null; status: 'active' | 'request' | 'none'; reason: string | null };

/** Ouvre (ou crée) LA conversation avec cette personne ; la base dit directe, demande ou impossible. */
export async function openDirectChat(target: string): Promise<OpenDirect> {
  const { data, error } = await supabase.rpc('open_direct_chat', { target });
  if (error || !data) return { chat: null, status: 'none', reason: null };
  return data as OpenDirect;
}

/** Pourquoi on ne peut pas écrire (même phrase neutre pour un blocage, on ne dit jamais qui a bloqué). */
export function cannotWrite(name: string, reason: string | null): string {
  switch (reason) {
    case 'profile_required': return 'Complète ton profil (prénom, nom, surnom) pour écrire un message.';
    case 'terms_required': return 'Accepte les conditions d’utilisation pour écrire un message.';
    case 'limit': return 'Tu as envoyé beaucoup de demandes de message : réessaie demain.';
    default: return `Tu ne peux pas écrire à ${name} pour le moment.`;
  }
}

const EXCERPT = 140;
export function excerpt(text: string): string {
  const t = text.replace(/\s+/g, ' ').trim();
  return t.length > EXCERPT ? `${t.slice(0, EXCERPT - 1)}…` : t;
}

/** « écrit… » (contrat §6) : signal en direct sur le canal Supabase `typing:<kind>:<id>`, jamais écrit en base.
 * topic null : ni envoi ni écoute (demande de message, personne bloquée). Les signaux des personnes `ignore`
 * (bloquées) sont jetés. */
const TYPING_TTL = 4000;
const TYPING_EVERY = 2500;
export function useTyping(topic: string | null, me: { id: string; name: string }, ignore: Set<string>, mayListen = true) {
  const [typers, setTypers] = useState<Map<string, { name: string; at: number }>>(new Map());
  const channel = useRef<ReturnType<typeof supabase.channel> | null>(null);
  const lastSent = useRef(0);
  const ignored = useRef(ignore);
  useEffect(() => { ignored.current = ignore; }, [ignore]);

  useEffect(() => {
    if (!topic) return undefined;
    const ch = supabase.channel(topic, { config: { broadcast: { self: false } } });
    if (mayListen) {
      ch.on('broadcast', { event: 'typing' }, ({ payload }) => {
        const p = payload as { user?: string; name?: string; stop?: boolean };
        if (!p?.user || p.user === me.id || ignored.current.has(p.user)) return;
        setTypers((prev) => {
          const next = new Map(prev);
          if (p.stop) next.delete(p.user!);
          else next.set(p.user!, { name: String(p.name ?? '').slice(0, 60), at: Date.now() });
          return next;
        });
      });
    }
    ch.subscribe();
    channel.current = ch;
    return () => {
      channel.current = null;
      setTypers(new Map());
      void supabase.removeChannel(ch);
    };
  }, [topic, me.id, mayListen]);

  // Un signal vaut 4 s : sans nouvelle frappe, « écrit… » s'efface.
  useEffect(() => {
    if (!typers.size) return undefined;
    const timer = setInterval(() => {
      const now = Date.now();
      setTypers((prev) => {
        const next = new Map([...prev].filter(([, t]) => now - t.at < TYPING_TTL));
        return next.size === prev.size ? prev : next;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [typers.size]);

  /** À chaque frappe : un signal toutes les 2,5 s au plus. */
  const ping = useCallback(() => {
    const ch = channel.current;
    if (!ch || Date.now() - lastSent.current < TYPING_EVERY) return;
    lastSent.current = Date.now();
    void ch.send({ type: 'broadcast', event: 'typing', payload: { user: me.id, name: me.name } });
  }, [me.id, me.name]);

  /** Message envoyé : « écrit… » s'efface aussitôt chez les autres. */
  const stop = useCallback(() => {
    const ch = channel.current;
    if (!ch || !lastSent.current) return;
    lastSent.current = 0;
    void ch.send({ type: 'broadcast', event: 'typing', payload: { user: me.id, name: me.name, stop: true } });
  }, [me.id, me.name]);

  return { typers: [...typers.values()].map((t) => t.name), ping, stop };
}
