import { useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';

import { chatKey, type ChatItem } from '@/lib/chatList';
import { supabase } from '@/lib/supabase';

/** Un « écrit… » s'efface s'il n'est pas répété (la conversation le renvoie tant qu'on tape). */
const TYPING_MS = 6000;
/** Au plus tant de conversations écoutées (les plus récentes, visibles en haut de la liste). */
const MAX = 20;

/**
 * « écrit… » dans la liste (contrat §6) : signal en direct, jamais écrit en base, canal Supabase `typing:<kind>:<id>`,
 * charge `{user, name}`. Seulement pendant que la liste est à l'écran (la conversation ouverte écoute le même canal),
 * jamais pour une demande ni une personne bloquée. Renvoie, par discussion, le prénom de qui écrit.
 */
export function useTyping(chats: ChatItem[], me: string): Record<string, string> {
  const [typing, setTyping] = useState<Record<string, { name: string; at: number }>>({});
  const keys = chats.filter((c) => !c.request && !c.blocked && !c.archived && !(c.kind === 'event' && c.event_past))
    .slice(0, MAX).map(chatKey).join(',');

  useFocusEffect(useCallback(() => {
    if (!keys) return undefined;
    const channels = keys.split(',').map((key) => supabase.channel(`typing:${key}`)
      .on('broadcast', { event: '*' }, (msg: { payload?: { user?: string; name?: string; typing?: boolean } }) => {
        const p = msg.payload ?? {};
        if (!p.user || p.user === me) return;
        setTyping((t) => {
          const next = { ...t };
          if (p.typing === false) delete next[key];
          else next[key] = { name: p.name ?? '', at: Date.now() };
          return next;
        });
      })
      .subscribe());
    const sweep = setInterval(() => setTyping((t) => {
      const now = Date.now();
      const stale = Object.keys(t).filter((k) => now - t[k]!.at > TYPING_MS);
      if (!stale.length) return t;
      const next = { ...t };
      stale.forEach((k) => delete next[k]);
      return next;
    }), 1000);
    return () => {
      clearInterval(sweep);
      channels.forEach((ch) => void supabase.removeChannel(ch));
      setTyping({});
    };
  }, [keys, me]));

  const out: Record<string, string> = {};
  for (const [k, v] of Object.entries(typing)) out[k] = v.name;
  return out;
}
