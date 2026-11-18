import { router } from 'expo-router';
import { useCallback, useMemo, useState } from 'react';
import { Text } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ChatsOff } from '@/components/ChatsOff';
import { ListPage, Nothing } from '@/components/chats/list/ListPage';
import { RequestCard } from '@/components/chats/list/RequestCard';
import { Snack } from '@/components/chats/list/useChatActions';
import { chatFont, useNeon } from '@/components/chats/neon';
import { ReportSheet } from '@/components/ReportSheet';
import { Loading } from '@/components/ui';
import { useMe } from '@/lib/auth';
import { acceptRequest, chatKey, declineRequest, fetchChatList, openChat, type ChatItem } from '@/lib/chatList';
import { useQuery, useRealtime, useSignal } from '@/lib/data';
import { discussionsOn } from '@/lib/features';
import { useMiniProfile } from '@/lib/miniProfile';
import { setBlocked, type ReportTarget } from '@/lib/moderation';

/** Demandes de message (contrat §2, §8) : écran à part, chaque demande = la personne + son message + Accepter / Supprimer /
 * Bloquer / Signaler. L'expéditeur n'est jamais prévenu d'un refus. */
export default function RequestsRoute() {
  return discussionsOn ? <Requests /> : <ChatsOff />;
}

function Requests() {
  const me = useMe();
  const c = useNeon();
  const mini = useMiniProfile();
  const insets = useSafeAreaInsets();
  const { data, error, loading, reload, setData } = useQuery(fetchChatList, []);
  useRealtime('chats-requests', [{ table: 'direct_messages' }, { table: 'direct_chats' }], reload);
  useSignal([`user:${me.id}`], reload);
  const list = useMemo(() => (data ?? []).filter((x) => x.request === 'incoming'), [data]);
  const [busy, setBusy] = useState<string | null>(null);
  const [failure, setFailure] = useState<string | null>(null);
  const [report, setReport] = useState<ReportTarget | null>(null);
  const [snack, setSnack] = useState<{ text: string } | null>(null);
  const push = useCallback((path: string) => router.push(path as never), []);

  const drop = (chat: ChatItem) => setData((data ?? []).filter((x) => chatKey(x) !== chatKey(chat)));
  const run = async (chat: ChatItem, send: () => Promise<void>, after: () => void) => {
    setBusy(chat.id); setFailure(null);
    try { await send(); after(); } catch (e) { setFailure(e instanceof Error ? e.message : 'Ça n’a pas marché. Réessaie.'); } finally { setBusy(null); }
  };

  if (loading && !data) return <Loading />;
  return (
    <ListPage title="Demandes"
      intro="Ces personnes veulent t’écrire sans vous connaître encore. Tant que tu n’acceptes pas, elles ne voient ni « Vu » ni « écrit… » et ne savent pas que tu as lu."
      overlay={(
        <>
          <Snack snack={snack} onDone={() => setSnack(null)} bottom={insets.bottom + 24} />
          <ReportSheet target={report} onClose={() => setReport(null)} />
        </>
      )}>
      {error || failure ? <Text role="alert" style={[chatFont.medium, { color: c.danger, fontSize: 14, paddingHorizontal: 16, paddingTop: 8 }]}>{failure ?? error}</Text> : null}
      {!list.length ? <Nothing icon="inbox" title="Aucune demande" text="Quand quelqu’un qui ne te connaît pas encore veut t’écrire, sa demande arrive ici." /> : null}
      {list.map((chat, i) => (
        <RequestCard key={chatKey(chat)} chat={chat} index={i} busy={busy === chat.id}
          onProfile={() => chat.user_id && mini.open(chat.user_id)}
          onAccept={() => void run(chat, () => acceptRequest(chat.id), () => { drop(chat); openChat(chat, push); })}
          onDecline={() => void run(chat, () => declineRequest(chat.id), () => { drop(chat); setSnack({ text: 'Demande supprimée' }); })}
          onBlock={() => void run(chat, () => setBlocked(chat.user_id ?? '', true), () => { drop(chat); setSnack({ text: 'Personne bloquée' }); })}
          onReport={() => setReport(chat.last?.id
            ? { kind: 'direct_message', id: chat.last.id, label: `la demande de ${chat.title}` }
            : { kind: 'profile', id: chat.user_id ?? chat.id, label: chat.title })} />
      ))}
    </ListPage>
  );
}
