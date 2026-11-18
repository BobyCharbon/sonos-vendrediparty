import { useEffect, useRef, useState } from 'react';

import { rpc } from '@/lib/pronos';

import type { Detail, ListCard } from './model';

const MAX = 12;

/**
 * Fiches des cartes affichées (prono_get) : choix, visages, ma réponse scellée, résultat. La liste (prono_list) ne les
 * porte pas ; on ne lit que les MAX premières cartes de l'onglet, une seule fois par état de carte (relue quand la carte
 * change : réponse, fermeture, résultat). Une fiche qui ne vient pas laisse la carte en version simple.
 */
export function useDetails(cards: ListCard[]): Record<string, Detail> {
  const [details, setDetails] = useState<Record<string, Detail>>({});
  const asked = useRef(new Map<string, string>());
  const wanted = cards.slice(0, MAX).map((p) => [p.id, `${p.state}|${p.answered}|${p.answered_count}|${p.revealed}`] as const);
  const key = wanted.map(([id, v]) => `${id}:${v}`).join(',');
  useEffect(() => {
    for (const [id, version] of wanted) {
      if (asked.current.get(id) === version) continue;
      asked.current.set(id, version);
      void rpc<Detail>('prono_get', { id }).then((d) => {
        if (d) setDetails((m) => ({ ...m, [id]: d }));
      }).catch(() => undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return details;
}
