import { router, useLocalSearchParams } from 'expo-router';
import { useEffect } from 'react';

import { GroupChat } from '@/components/GroupChat';
import { Loading } from '@/components/ui';
import { nativeEventChat } from '@/lib/nativeChat';

/** Discussion d'un événement (16.11.2026) : même écran que les Discussions, façon WhatsApp (GroupChat, mode événement).
 * Dans l'app iPhone, l'écran natif la remplace : on l'ouvre et la page revient à la fiche. */
export default function ChatRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const native = nativeEventChat();
  useEffect(() => {
    if (!native || !id) return;
    native.openEvent(id);
    router.replace(`/event/${id}`);
  }, [native, id]);
  if (native) return <Loading />;
  return <GroupChat key={id} id={id} event />;
}
