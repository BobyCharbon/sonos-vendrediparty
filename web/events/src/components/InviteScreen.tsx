import { router, Stack, type Href } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { View } from 'react-native';

import { GroupTile } from '@/components/GroupBits';
import { IdentityForm } from '@/components/IdentityForm';
import { Button, Card, ErrorText, Loading, Screen, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { hasCompleteIdentity } from '@/lib/profile';
import { supabase } from '@/lib/supabase';
import { leaveIfAlone, openInParty } from '@/lib/partyShell';

const TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type EventPreview = { id: string; title: string; description: string | null; status: string; date_mode: string;
  starts_at: string | null; location_name: string | null; organizer: string | null; joined: boolean };
type GroupPreview = { id: string; name: string; creator: string | null; members: number; joined: boolean;
  /** « Accepter chaque nouveau membre » (23.11) : le lien envoie une demande ; requested : elle attend l'accord. */
  approval?: boolean; requested?: boolean };

/** Lien d'invitation (événement réservé à un groupe, ou groupe privé), avis n°9 :
 * 1. sans compte : rien n'est montré, on s'inscrit d'abord avec son numéro (SMS) ;
 * 2. compte au profil incomplet : nom, prénom et surnom sont demandés ici même (photo facultative) ;
 * 3. profil complet : on rejoint tout de suite et on arrive sur l'événement (ou ses groupes).
 * L'organisateur (ou le créateur du groupe) est prévenu à l'arrivée. La base revérifie chaque étape. */
export function InviteScreen({ kind, token }: { kind: 'event' | 'group'; token: string | undefined }) {
  const { session, profile, refreshProfile } = useAuth();
  const valid = typeof token === 'string' && TOKEN.test(token);
  const complete = hasCompleteIdentity(profile);

  if (!valid) return <Unavailable kind={kind} />;
  if (!session) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
        <Stack.Screen options={{ title: 'Invitation' }} />
        {kind === 'group' ? <GroupTeaser token={token} /> : <Title size={30}>Tu es invité !</Title>}
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
          <Title size={30}>Faisons connaissance</Title>
          <T muted>
            Encore une étape : ton prénom, ton nom et ton surnom (une photo aussi, vivement conseillée), pour que les autres te reconnaissent.
            Tu accèdes ensuite directement à {kind === 'event' ? 'l’événement' : 'ce groupe'}.
          </T>
        </View>
        <IdentityForm profile={profile} submitLabel="Continuer" onSaved={() => void refreshProfile()} />
      </Screen>
    );
  }
  return <JoinInvite kind={kind} token={token} />;
}

type GroupTeaserData = { name: string; emoji: string | null; color: string | null; inviter: string | null };

/** Lien d'un groupe ouvert sans compte (recette du 27.11) : le groupe (nom, emoji, couleur) et qui invite, rien d'autre
 * (ni membres ni nombre : group_invite_preview, migration 20261127100000). Base d'avant ou lien mort : « Tu es invité ! ». */
function GroupTeaser({ token }: { token: string }) {
  const { data, loading } = useQuery(async () => {
    const { data, error } = await supabase.rpc('group_invite_preview', { token });
    return !error && data && typeof (data as GroupTeaserData).name === 'string' ? (data as GroupTeaserData) : null;
  }, [token]);
  if (loading) return <View style={{ height: 120 }} />;
  if (!data) return <Title size={30}>Tu es invité !</Title>;
  return (
    <View style={{ alignItems: 'center', gap: 12 }} testID="group-invite-teaser">
      <GroupTile group={{ emoji: data.emoji || '🎉', color: data.color }} size={88} />
      <T muted size={15} style={{ textAlign: 'center' }}>
        {data.inviter ? `${data.inviter} t’invite dans son groupe` : 'Tu es invité dans le groupe'}
      </T>
      <Title size={30} style={{ textAlign: 'center' }}>{data.name}</Title>
    </View>
  );
}

function Unavailable({ kind, error }: { kind: 'event' | 'group'; error?: string | null }) {
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Title>Lien indisponible</Title>
      <T muted>{kind === 'group'
        ? 'Ce lien n’est plus valable : un lien pour une personne ne marche qu’une fois, pendant 7 jours, et le lien du groupe change quand il est renouvelé. Demande un nouveau lien à la personne qui t’a invité.'
        : 'Ce lien n’est plus valable : un lien unique ne marche qu’une fois, pendant 7 jours, et l’organisateur peut l’annuler ou le remplacer. Demande ton propre lien à la personne qui t’a invité.'}</T>
      <ErrorText error={error ?? null} />
      <Button label="Découvrir Party" variant="secondary" onPress={() => openInParty('/')} />
    </Screen>
  );
}

/** Profil complet : on rejoint aussitôt (une seule fois) puis on ouvre l'événement ou les groupes. */
function JoinInvite({ kind, token }: { kind: 'event' | 'group'; token: string }) {
  const { refreshProfile } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);
  const started = useRef(false);
  const { data, loading, error: loadError, reload } = useQuery(async () => {
    const { data, error } = await supabase.rpc(kind === 'event' ? 'invite_event' : 'group_invite_info', { token });
    if (error) throw new Error('L’invitation n’a pas pu être lue. Réessaie dans un instant.');
    return (data as EventPreview | GroupPreview | null) ?? null;
  }, [token]);

  const event = kind === 'event' ? (data as EventPreview | null) : null;
  const cancelled = event?.status === 'cancelled';
  // Groupe : sa page, avec « Tu as rejoint le groupe » (promis par « Faisons connaissance », recette iPhone du 28.11).
  const target = (kind === 'event' && data ? `/event/${data.id}` : data ? `/group/${data.id}?joined=1` : '/groups') as Href;

  useEffect(() => {
    if (!data || cancelled || started.current) return;
    started.current = true;
    void (async () => {
      const group = kind === 'group' ? (data as GroupPreview) : null;
      if (group?.requested && !group.joined) return setPending(true);
      if (!data.joined) {
        const { error } = await supabase.rpc(kind === 'event' ? 'join_event_by_link' : 'join_group_by_link', { token });
        if (error) {
          started.current = false;
          return setError(error.message.replace(/^\w+: /, ''));
        }
        if (group?.approval) {  // l'admin du groupe accepte d'abord : la demande est partie
          const { data: after } = await supabase.rpc('group_invite_info', { token });
          if (!(after as GroupPreview | null)?.joined) return setPending(true);
        }
      }
      await refreshProfile();  // l'accès aux événements suit l'invitation
      // Module ouvert seul (lien) : Party s'ouvre directement sur la page, sans passer par une route protégée.
      if (!leaveIfAlone(String(target))) router.replace(target);
    })();
  }, [data, cancelled, kind, token, target, refreshProfile]);

  if (loading) return <Loading />;
  if (!data) return <Unavailable kind={kind} error={loadError} />;
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
  if (pending && data) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
        <Stack.Screen options={{ title: 'Invitation' }} />
        <Card>
          <Title size={24}>{(data as GroupPreview).name}</Title>
          <T weight="bold">Demande envoyée</T>
          <T muted>Ce groupe accepte chaque nouveau membre : son admin (ou un co-admin) va répondre. Tu seras prévenu dès que tu es dedans.</T>
        </Card>
        <Button label="Retour à mes groupes" variant="secondary" onPress={() => router.replace('/groups')} />
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
