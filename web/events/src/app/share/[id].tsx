import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useRef, useState } from 'react';
import { Linking, Pressable, View } from 'react-native';

import { LinkedText } from '@/components/LinkedText';
import { ReportSheet } from '@/components/ReportSheet';
import { RsvpButtons } from '@/components/RsvpButtons';
import { useTermsGate } from '@/components/TermsSheet';
import { Badge, Button, Card, ErrorText, Field, Loading, Screen, s, T, Title } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { SUPPORT_EMAIL } from '@/lib/contact';
import { useQuery } from '@/lib/data';
import { safeHref } from '@/lib/links';
import { dbMessage, isTermsError, type ReportTarget } from '@/lib/moderation';
import { formatLongDay, formatShort, formatTime, plural, relativeDay } from '@/lib/format';
import { rsvpChoices, rsvpClosed, rsvpOptions, saveRsvp } from '@/lib/rsvp';
import { supabase } from '@/lib/supabase';
import { chf } from '@/lib/tickets';
import { colors } from '@/lib/theme';
import type { EventRow, Rsvp } from '@/lib/types';

const EVENT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

type PublicEvent = Pick<EventRow, 'id' | 'title' | 'description' | 'status' | 'date_mode' | 'starts_at' | 'ends_at' | 'location_name'
  | 'location_address' | 'location_url' | 'price_chf' | 'allow_maybe' | 'rsvp_deadline' | 'max_participants'> & {
  going: number;
  mine: Pick<Rsvp, 'status' | 'waitlisted' | 'plus_ones' | 'note'> | null;
};

/** Lien public d'un événement : l'essentiel sans compte, la réponse après connexion par SMS (même sans être membre). */
export default function PublicEventScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const { session, profile, refreshProfile } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [report, setReport] = useState<ReportTarget | null>(null);
  const validId = typeof id === 'string' && EVENT_ID.test(id);

  const { data, reload, error: loadError, loading } = useQuery(async () => {
    if (!validId) return null;  // lien tronqué : pas de requête refusée par la base
    const { data, error } = await supabase.rpc('public_event', { e: id });
    if (error) throw new Error(error.message);
    return (data as PublicEvent | null) ?? null;
  }, [id, session?.user.id]);

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
  const closed = ev.status !== 'published' || rsvpClosed(ev);

  async function answer(status: Rsvp['status']) {
    setBusy(true);
    setError(null);
    try {
      await saveRsvp(ev.id, session!.user.id, ev.mine ?? undefined, { status });
      await reload();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }



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
          👥 {plural(ev.going, 'participant', 'participants')}{ev.max_participants ? ` sur ${ev.max_participants} places` : ''}
          {ev.rsvp_deadline ? ` · réponse avant le ${formatShort(ev.rsvp_deadline)}` : ''}
        </T>
        {ev.description ? <LinkedText text={ev.description} /> : null}
      </View>

      <Card>
        {closed && !session ? (
          // Annulé ou réponses closes : rien à faire en se connectant.
          <T muted>{ev.status === 'cancelled' ? 'Cet événement a été annulé.' : 'Les réponses sont closes.'}</T>
        ) : !session ? (
          <>
            <T weight="semibold">Tu viens ?</T>
            <T muted size={13}>Connecte-toi avec ton numéro de téléphone pour répondre. Tu reçois un code par SMS.</T>
            <Button label="Se connecter pour répondre" onPress={() => router.push('/sign-in')} />
          </>
        ) : closed ? (
          <T muted>{ev.status === 'cancelled' ? 'Cet événement a été annulé.' : 'Les réponses sont closes.'}</T>
        ) : !profile?.display_name.trim() ? (
          <>
            <FirstNameForm userId={session.user.id} onSaved={refreshProfile} />
          </>
        ) : (
          <>
            <T weight="semibold">
              {ev.mine ? `Ta réponse : ${rsvpChoices[ev.mine.status].mine}${ev.mine.waitlisted && ev.mine.status === 'yes' ? ' (liste d’attente)' : ''}` : 'Tu viens ?'}
            </T>
            {/* Mêmes boutons que la fiche et la liste (couleur et pictogramme par réponse). */}
            <RsvpButtons
              options={rsvpOptions(ev.allow_maybe)}
              selected={ev.mine?.status ?? null}
              disabled={busy}
              onSelect={(choice) => void answer(choice)}
              accessibilityLabel={(k) => `${rsvpChoices[k].label} à ${ev.title}`}
            />
          </>
        )}
        <ErrorText error={error} />
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

/** Prénom d'un compte neuf : il est vu des autres, donc CGU acceptées avant (exigées en prod : sinon 403 terms_required
 * sans issue). Composant à part : la feuille ne lit les CGU qu'une fois connecté (jamais pour un visiteur). */
function FirstNameForm({ userId, onSaved }: { userId: string; onSaved: () => Promise<unknown> | void }) {
  const [name, setName] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saving = useRef(false);
  const terms = useTermsGate();

  async function saveName() {
    const value = name.trim();
    if (!value || saving.current) return;
    saving.current = true;  // avant l'attente des CGU : un double toucher n'enregistre qu'une fois
    setError(null);
    try {
      if (!(await terms.ensure())) return;
      setBusy(true);
      const write = () => supabase.from('profiles').update({ display_name: value }).eq('id', userId);
      let { error } = await write();
      // La base exige encore les CGU (statut lu avant leur exigence) : la feuille, puis un seul nouvel essai.
      if (error && isTermsError(error.message) && (await terms.ensure())) ({ error } = await write());
      if (error) return setError(dbMessage(error.message, 'Ton prénom n’a pas été enregistré. Réessaie.'));
      await onSaved();
    } finally {
      saving.current = false;
      setBusy(false);
    }
  }

  return (
    <>
      <Field label="Ton prénom, pour que l’organisateur sache qui vient" value={name} onChangeText={setName} maxLength={40} />
      <Button label="Continuer" disabled={!name.trim()} loading={busy} onPress={saveName} />
      <ErrorText error={error} />
      {terms.sheet}
    </>
  );
}
