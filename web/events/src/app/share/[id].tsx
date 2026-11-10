import { router, Stack, useLocalSearchParams, type Href } from 'expo-router';
import { useEffect, useState } from 'react';
import { Linking, Pressable, View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { LinkedText } from '@/components/LinkedText';
import { ReportSheet } from '@/components/ReportSheet';
import { Badge, Button, Card, Loading, Screen, s, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { SUPPORT_EMAIL } from '@/lib/contact';
import { useQuery } from '@/lib/data';
import { safeHref } from '@/lib/links';
import { type ReportTarget } from '@/lib/moderation';
import { formatLongDay, formatShort, formatTime, plural, relativeDay } from '@/lib/format';
import { hasCompleteIdentity } from '@/lib/profile';
import { rsvpClosed } from '@/lib/rsvp';
import { supabase } from '@/lib/supabase';
import { chf } from '@/lib/tickets';
import { colors } from '@/lib/theme';
import type { EventRow, Profile, Rsvp } from '@/lib/types';

const EVENT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type PublicEvent = Pick<EventRow, 'id' | 'title' | 'description' | 'status' | 'date_mode' | 'starts_at' | 'ends_at' | 'location_name'
  | 'location_address' | 'location_url' | 'price_chf' | 'allow_maybe' | 'rsvp_deadline' | 'max_participants'> & {
  going: number;
  /** Sondage : personnes qui ont voté au moins une date (10.11 ; base plus ancienne : absent). */
  voters?: number;
  mine: Pick<Rsvp, 'status' | 'waitlisted' | 'plus_ones' | 'note'> | null;
};

/**
 * Lien public d'un événement (« Partager le lien ») : l'essentiel sans compte. Pour répondre, le parcours normal de l'app
 * (10.11, avis 39f148377a8f) : connexion SMS, profil complet (« Faisons connaissance »), puis la FICHE de l'événement,
 * comme pour tout membre (sondage : on y vote les dates ; jamais de « Présent » sans date sur un sondage).
 */
export default function PublicEventScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { session, profile } = useAuth();
  const [report, setReport] = useState<ReportTarget | null>(null);
  const validId = typeof id === 'string' && EVENT_ID.test(id);
  const ready = !!session && hasCompleteIdentity(profile) && profile?.status === 'active';

  const { data, reload, error: loadError, loading } = useQuery(async () => {
    if (!validId) return null;  // lien tronqué : pas de requête refusée par la base
    const { data, error } = await supabase.rpc('public_event', { e: id });
    if (error) throw new Error(error.message);
    return (data as PublicEvent | null) ?? null;
  }, [id, session?.user.id]);

  // Compte prêt (profil complet) : la fiche de l'événement, où l'on répond ou vote comme dans toute l'app.
  useEffect(() => {
    if (validId && ready) router.replace(`/event/${id}` as Href);
  }, [validId, ready, id]);

  if (loading && !data) return <Loading />;
  if (!data && loadError) {
    // Panne passagère (réseau, base lente) : jamais « n'existe plus ».
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
        <Stack.Screen options={{ title: '' }} />
        <Title>Connexion difficile</Title>
        <T muted>L’événement n’a pas pu être chargé. Vérifie ta connexion puis réessaie.</T>
        <Button label="Réessayer" onPress={() => void reload()} />
      </Screen>
    );
  }
  if (validId && ready) return <OpeningEvent id={id} />;
  if (session && profile && hasCompleteIdentity(profile) && profile.status !== 'active') {
    // Profil complet mais compte en attente ou banni : jamais un formulaire sans bouton (comme « welcome »).
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
        <Stack.Screen options={{ title: '' }} />
        <Title>{profile.status === 'banned' ? 'Accès retiré' : 'Compte en attente'}</Title>
        <T muted>{profile.status === 'banned' ? 'Ton accès a été retiré par un admin du groupe.' : 'Ton compte n’est pas encore actif : réessaie un peu plus tard.'}</T>
      </Screen>
    );
  }
  if (!data && session && validId && profile && !hasCompleteIdentity(profile)) {
    // Événement sur invitation ouvert par un compte au profil incomplet (ancien « prénom seul ») : on complète, puis la fiche.
    return <CompleteProfile profile={profile} intro="Complète ton profil Party pour ouvrir l’événement." />;
  }
  if (!data) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
        <Stack.Screen options={{ title: '' }} />
        {!session && validId ? (
          // Événement sur invitation (ou session expirée) : on propose de se connecter au lieu d'un lien « mort ».
          <>
            <Title>Connecte-toi pour voir cet événement</Title>
            <T muted>Cet événement n’est pas public. Si tu y es invité, connecte-toi avec ton numéro de téléphone pour l’ouvrir.</T>
            <Button label="Se connecter" onPress={() => router.push('/sign-in')} />
          </>
        ) : (
          <>
            <Title>Lien indisponible</Title>
            <T muted>{validId ? 'Cet événement n’existe plus ou n’est plus partagé publiquement.' : 'Ce lien n’est pas complet. Copie-le en entier depuis le message reçu.'}</T>
          </>
        )}
      </Screen>
    );
  }

  const ev = data;
  const mapsUrl = safeHref(ev.location_url) ?? (ev.location_address || ev.location_name ? `https://maps.apple.com/?q=${encodeURIComponent(ev.location_address ?? ev.location_name!)}` : null);
  const poll = ev.date_mode === 'poll';
  const closed = ev.status !== 'published' || rsvpClosed(ev);
  const voters = ev.voters ?? 0;

  return (
    <Screen>
      <Stack.Screen options={{ title: '' }} />
      <View style={{ gap: 10 }}>
        <View style={s.wrap}>
          <Badge label="🔗 Lien public" fg={colors.textSoft} bg={colors.surface2} />
          {ev.status === 'cancelled' ? <Badge label="Annulé" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
          {ev.date_mode === 'poll' ? <Badge label="Date à définir" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
        </View>
        <Title size={32} style={{ lineHeight: 36 }}>{ev.title}</Title>
        {ev.date_mode === 'fixed' && ev.starts_at ? (
          <View>
            <T weight="bold" size={16}>📅 {formatLongDay(ev.starts_at)} · {formatTime(ev.starts_at)}</T>
            <T muted size={13}>{relativeDay(ev.starts_at)}{ev.ends_at ? ` · jusqu’à ${formatShort(ev.ends_at)}` : ''}</T>
          </View>
        ) : null}
        {ev.location_name || ev.location_address ? (
          <Pressable accessibilityRole={mapsUrl ? 'link' : undefined} disabled={!mapsUrl} onPress={() => mapsUrl && Linking.openURL(mapsUrl)}>
            <T weight="bold" size={16}>📍 {ev.location_name ?? ev.location_address}</T>
            {ev.location_name && ev.location_address ? <T muted size={13}>{ev.location_address}</T> : null}
          </Pressable>
        ) : null}
        {ev.price_chf != null ? <T>💶 {ev.price_chf === 0 ? 'Gratuit' : `${chf(ev.price_chf)} / personne`}</T> : null}
        <T muted>
          {poll
            ? `🗳️ ${voters ? `${plural(voters, 'personne a', 'personnes ont')} déjà voté` : 'Personne n’a encore voté'} pour la date`
            : `👥 ${plural(ev.going, 'participant', 'participants')}${ev.max_participants ? ` sur ${ev.max_participants} places` : ''}`}
          {!poll && ev.rsvp_deadline ? ` · réponse avant le ${formatShort(ev.rsvp_deadline)}` : ''}
        </T>
        {ev.description ? <LinkedText text={ev.description} /> : null}
      </View>

      <Card>
        {closed && !session ? (
          // Annulé ou réponses closes : rien à faire en se connectant.
          <T muted>{ev.status === 'cancelled' ? 'Cet événement a été annulé.' : 'Les réponses sont closes.'}</T>
        ) : !session ? (
          <>
            <T weight="semibold">{poll ? 'Tes dates ?' : 'Tu viens ?'}</T>
            <T muted size={13}>
              {poll ? 'Connecte-toi avec ton numéro de téléphone pour choisir les dates où tu es dispo.' : 'Connecte-toi avec ton numéro de téléphone pour répondre.'} Tu reçois un code par SMS.
            </T>
            <Button label={poll ? 'Se connecter pour choisir mes dates' : 'Se connecter pour répondre'} onPress={() => router.push('/sign-in' as Href)} />
          </>
        ) : closed ? (
          <T muted>{ev.status === 'cancelled' ? 'Cet événement a été annulé.' : 'Les réponses sont closes.'}</T>
        ) : profile ? (
          <CompleteProfile profile={profile} inCard
            intro={poll ? 'Pour choisir tes dates, complète ton profil Party : c’est le même partout dans l’app.' : 'Pour répondre, complète ton profil Party : c’est le même partout dans l’app.'} />
        ) : <Loading />}
      </Card>
      {/* Apple 1.2 : contenu de membre visible sans compte ; signaler demande d'être connecté (anti-abus), sinon l'adresse de contact. */}
      {session ? (
        <Button small variant="ghost" label="Signaler cet événement" style={{ alignSelf: 'flex-start' }}
          onPress={() => setReport({ kind: 'event', id: ev.id, label: 'cet événement' })} />
      ) : (
        <Pressable accessibilityRole="link" accessibilityLabel="Signaler cet événement par e-mail"
          onPress={() => Linking.openURL(`mailto:${SUPPORT_EMAIL}?subject=${encodeURIComponent(`Signalement : événement ${ev.id}`)}`)}>
          <T muted size={13}>Un contenu choquant ? Signale-le à {SUPPORT_EMAIL}</T>
        </Pressable>
      )}
      <ReportSheet target={report} onClose={() => setReport(null)} />
    </Screen>
  );
}

/** Profil complet, par le formulaire de toute l'app (prénom, nom, surnom ; photo facultative ; CGU au premier surnom). */
function CompleteProfile({ profile, intro, inCard = false }: { profile: Profile; intro: string; inCard?: boolean }) {
  const form = (
    <View style={{ gap: 14 }}>
      <View style={{ gap: 6 }}>
        <Title size={inCard ? 24 : 32}>Faisons connaissance</Title>
        <T muted>{intro}</T>
      </View>
      <IdentityForm profile={profile} submitLabel="Continuer" />
    </View>
  );
  return inCard ? form : <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}><Stack.Screen options={{ title: '' }} />{form}</Screen>;
}

/** Redirection vers la fiche en cours ; le bouton reste là si elle tarde (jamais d'écran vide). */
function OpeningEvent({ id }: { id: string }) {
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: '' }} />
      <Loading />
      <Button label="Ouvrir l’événement" variant="secondary" onPress={() => router.replace(`/event/${id}` as Href)} />
    </Screen>
  );
}
