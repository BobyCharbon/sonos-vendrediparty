import { router, Stack, type Href } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Button, Card, ErrorText, Loading, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { supabase } from '@/lib/supabase';

const TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type EventPreview = { id: string; title: string; description: string | null; status: string; date_mode: string;
  starts_at: string | null; location_name: string | null; organizer: string | null; joined: boolean };
type GroupPreview = { id: string; name: string; creator: string | null; members: number; joined: boolean };

/** Lien d'invitation (événement sur invitation ou groupe) : l'essentiel sans compte ; on se connecte (ou on crée
 * son compte par SMS), puis on rejoint. L'événement : visible pour cette personne seulement, rien d'autre. */
export function InviteScreen({ kind, token }: { kind: 'event' | 'group'; token: string | undefined }) {
  const { session } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const valid = typeof token === 'string' && TOKEN.test(token);
  const { data, loading, error: loadError } = useQuery(async () => {
    if (!valid) return null;
    const { data, error } = await supabase.rpc(kind === 'event' ? 'invite_event' : 'group_invite_info', { token });
    if (error) throw new Error(error.message);
    return (data as EventPreview | GroupPreview | null) ?? null;
  }, [token, session?.user.id]);

  if (loading) return <Loading />;
  if (!data) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
        <Stack.Screen options={{ title: '' }} />
        <Title>Lien indisponible</Title>
        <T muted>Ce lien d’invitation n’existe plus ou a été remplacé. Demande un nouveau lien à la personne qui t’a invité.</T>
        <ErrorText error={loadError} />
      </Screen>
    );
  }

  const target = (kind === 'event' ? `/event/${data.id}` : '/groups') as Href;

  async function join() {
    setBusy(true);
    setError(null);
    const { error } = await supabase.rpc(kind === 'event' ? 'join_event_by_link' : 'join_group_by_link', { token });
    setBusy(false);
    if (error) return setError(error.message.replace(/^\w+: /, ''));
    router.replace(target);
  }

  const event = kind === 'event' ? (data as EventPreview) : null;
  const group = kind === 'group' ? (data as GroupPreview) : null;
  const inviter = event ? `${event.organizer ?? 'Quelqu’un'} t’invite à un événement` : `${group?.creator ?? 'Quelqu’un'} t’invite dans un groupe`;
  return (
    <Screen contentStyle={{ gap: 16 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <T muted size={14}>{inviter}</T>
      <Card>
        <Title size={24}>{event ? event.title : group?.name}</Title>
        {event ? (
          <View style={{ gap: 4 }}>
            <T muted>{event.date_mode === 'poll' ? 'Date à définir (sondage)' : event.starts_at ? formatShort(event.starts_at) : ''}</T>
            {event.location_name ? <T muted>📍 {event.location_name}</T> : null}
            {event.description ? <T numberOfLines={6}>{event.description}</T> : null}
            {event.status === 'cancelled' ? <T weight="bold">Événement annulé</T> : null}
          </View>
        ) : (
          <T muted>{group?.members ?? 0} membre{(group?.members ?? 0) > 1 ? 's' : ''}</T>
        )}
      </Card>
      <ErrorText error={error} />
      {data.joined ? (
        <Button label={event ? 'Ouvrir l’événement' : 'Voir mes groupes'} onPress={() => router.replace(target)} />
      ) : !session ? (
        <>
          <Button label="Me connecter ou créer mon compte" onPress={() => router.push('/sign-in')} />
          <T muted size={13}>Connexion par SMS avec ton numéro ; ton profil (surnom, photo, prénom et nom) est demandé pour rejoindre.</T>
        </>
      ) : (
        <Button label={event ? 'Rejoindre l’événement' : 'Rejoindre le groupe'} loading={busy}
          disabled={event?.status === 'cancelled'} onPress={join} />
      )}
    </Screen>
  );
}
