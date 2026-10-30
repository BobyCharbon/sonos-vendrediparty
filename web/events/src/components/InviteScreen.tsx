import { router, Stack, type Href } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { Button, Card, ErrorText, Loading, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { hasCompleteIdentity } from '@/lib/profile';
import { supabase } from '@/lib/supabase';

const TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type EventPreview = { id: string; title: string; description: string | null; status: string; date_mode: string;
  starts_at: string | null; location_name: string | null; organizer: string | null; joined: boolean };
type GroupPreview = { id: string; name: string; creator: string | null; members: number; joined: boolean };

/** Lien d'invitation (événement réservé à un groupe, ou groupe privé), avis n°9 :
 * 1. sans compte : rien n'est montré, on s'inscrit d'abord avec son numéro (SMS) ;
 * 2. compte au profil incomplet : nom, prénom, surnom et photo sont demandés ici même ;
 * 3. profil complet : on rejoint tout de suite et on arrive sur l'événement (ou ses groupes).
 * L'organisateur (ou le créateur du groupe) est prévenu à l'arrivée. La base revérifie chaque étape. */
export function InviteScreen({ kind, token }: { kind: 'event' | 'group'; token: string | undefined }) {
  const { session, profile, refreshProfile } = useAuth();
  const valid = typeof token === 'string' && TOKEN.test(token);
  const complete = hasCompleteIdentity(profile);

  if (!valid) return <Unavailable />;
  if (!session) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
        <Stack.Screen options={{ title: 'Invitation' }} />
        <Title size={30}>Tu es invité !</Title>
        <T muted>
          Pour découvrir {kind === 'event' ? 'cet événement' : 'ce groupe'}, inscris-toi d’abord avec ton numéro de téléphone :
          un code te sera envoyé par SMS. Tu compléteras ensuite ton profil, puis tu y accéderas directement.
        </T>
        <Button label="M’inscrire ou me connecter" onPress={() => router.push('/sign-in')} />
      </Screen>
    );
  }
  if (!profile) return <Loading />;
  if (!complete) {
    return (
      <Screen contentStyle={{ gap: 20 }}>
        <Stack.Screen options={{ title: 'Invitation' }} />
        <View style={{ gap: 8 }}>
          <Title size={30}>Complète ton profil</Title>
          <T muted>
            Encore une étape : ton prénom, ton nom, ton surnom et ta photo, pour que le groupe te reconnaisse.
            Tu accèdes ensuite directement à {kind === 'event' ? 'l’événement' : 'ce groupe'}.
          </T>
        </View>
        <IdentityForm profile={profile} submitLabel="Continuer" onSaved={() => void refreshProfile()} />
      </Screen>
    );
  }
  return <JoinInvite kind={kind} token={token} />;
}

function Unavailable({ error }: { error?: string | null }) {
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Title>Lien indisponible</Title>
      <T muted>Ce lien n’est plus valable : un lien unique ne marche qu’une fois, pendant 7 jours, et l’organisateur peut l’annuler ou le remplacer. Demande ton propre lien à la personne qui t’a invité.</T>
      <ErrorText error={error ?? null} />
    </Screen>
  );
}

/** Profil complet : on rejoint aussitôt (une seule fois) puis on ouvre l'événement ou les groupes. */
function JoinInvite({ kind, token }: { kind: 'event' | 'group'; token: string }) {
  const { refreshProfile } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  const { data, loading, error: loadError, reload } = useQuery(async () => {
    const { data, error } = await supabase.rpc(kind === 'event' ? 'invite_event' : 'group_invite_info', { token });
    if (error) throw new Error('L’invitation n’a pas pu être lue. Réessaie dans un instant.');
    return (data as EventPreview | GroupPreview | null) ?? null;
  }, [token]);

  const event = kind === 'event' ? (data as EventPreview | null) : null;
  const cancelled = event?.status === 'cancelled';
  const target = (kind === 'event' && data ? `/event/${data.id}` : '/groups') as Href;

  useEffect(() => {
    if (!data || cancelled || started.current) return;
    started.current = true;
    void (async () => {
      if (!data.joined) {
        const { error } = await supabase.rpc(kind === 'event' ? 'join_event_by_link' : 'join_group_by_link', { token });
        if (error) {
          started.current = false;
          return setError(error.message.replace(/^\w+: /, ''));
        }
      }
      await refreshProfile();  // l'accès aux événements suit l'invitation
      router.replace(target);
    })();
  }, [data, cancelled, kind, token, target, refreshProfile]);

  if (loading) return <Loading />;
  if (!data) return <Unavailable error={loadError} />;
  if (cancelled && event) {
    return (
      <Screen contentStyle={{ gap: 16 }}>
        <Stack.Screen options={{ title: 'Invitation' }} />
        <Card>
          <Title size={24}>{event.title}</Title>
          <T muted>{event.starts_at ? formatShort(event.starts_at) : ''}</T>
          <T weight="bold">Événement annulé</T>
        </Card>
      </Screen>
    );
  }
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      {error ? (
        <>
          <ErrorText error={error} />
          <Button label="Réessayer" onPress={() => { setError(null); reload(); }} />
        </>
      ) : (
        <>
          <Loading />
          <T muted style={{ textAlign: 'center' }}>Ouverture de {kind === 'event' ? 'l’événement' : 'ton groupe'}…</T>
        </>
      )}
    </Screen>
  );
}
