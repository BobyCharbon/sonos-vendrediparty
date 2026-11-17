import { router } from 'expo-router';
import { View } from 'react-native';

import { PronoCardView } from '@/components/pronos/Bits';
import { Button, Section, T } from '@/components/ui';
import { useQuery, useSignal } from '@/lib/data';
import { newProno, openProno, rpc, type PronoCard } from '@/lib/pronos';

/** « 🔮 Pronos de la soirée » sur la fiche d'un événement publié : les pronos des participants, et « Nouveau prono ». */
export function EventPronos({ eventId }: { eventId: string }) {
  const { data, reload } = useQuery(() => rpc<PronoCard[]>('prono_list', { event_id: eventId }).catch((): PronoCard[] => []), [eventId]);
  useSignal([`pronos:${eventId}`], reload);
  const push = (path: string) => router.push(path as never);
  const list = data ?? [];
  return (
    <Section title="🔮 Pronos de la soirée">
      {list.length ? (
        <View style={{ gap: 10 }}>
          {list.slice(0, 4).map((p, i) => <PronoCardView key={p.id} p={p} index={i} showPlace={false} onPress={() => openProno(p.id, push)} />)}
        </View>
      ) : <T muted size={14}>Qui arrive en dernier ? Qui gagne le blind test ? Les réponses restent cachées jusqu’au dévoilement.</T>}
      <Button small variant="secondary" label="＋ Nouveau prono" onPress={() => newProno({ event: eventId }, push)} />
    </Section>
  );
}
