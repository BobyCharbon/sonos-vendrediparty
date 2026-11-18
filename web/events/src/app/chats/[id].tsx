import { Stack, useLocalSearchParams } from 'expo-router';

import { ChatsOff } from '@/components/ChatsOff';
import { GroupChat } from '@/components/GroupChat';
import { Empty, Loading, Screen } from '@/components/ui';
import { knownKinds } from '@/lib/chatList';
import { useQuery } from '@/lib/data';
import { discussionsOn } from '@/lib/features';
import { supabase } from '@/lib/supabase';

const GROUP_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export default function GroupChatRoute() {
  const { id, event } = useLocalSearchParams<{ id: string; event?: string }>();
  if (!discussionsOn) return <ChatsOff />;  // production : Discussions absentes
  if (typeof id !== 'string' || !GROUP_ID.test(id)) {
    return (
      <Screen>
        <Stack.Screen options={{ title: 'Discussion' }} />
        <Empty>Cette discussion n’existe pas.</Empty>
      </Screen>
    );
  }
  // ?event=<id> : soirée à joindre au prochain message (« Envoyer à un ami », Nouveau message).
  return <ChatScreen key={id} id={id} attachEvent={typeof event === 'string' && GROUP_ID.test(event) ? event : null} />;
}

/** Groupe ou message direct (conversation privée à deux) : même adresse /chats/<id> (notifications comprises) ;
 * direct_chats ne répond qu'aux deux personnes de la conversation. */
function ChatScreen({ id, attachEvent }: { id: string; attachEvent: string | null }) {
  // Ouverte depuis la liste : on sait déjà si c'est un message direct (aucun aller-retour avant la conversation).
  const known = knownKinds.get(id);
  const { data, loading } = useQuery(async () => {
    if (known) return { direct: known === 'direct' };
    const { data } = await supabase.from('direct_chats').select('id').eq('id', id).maybeSingle();
    return { direct: Boolean(data) };
  }, [id], known ? { direct: known === 'direct' } : null);
  if (loading && !data) return <Loading />;
  return <GroupChat id={id} direct={Boolean(data?.direct)} attachEvent={attachEvent} />;
}
