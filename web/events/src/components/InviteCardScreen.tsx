import { router, Stack, type Href } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, View } from 'react-native';

import { CalendarButton } from './CalendarButton';
import { IdentityForm } from './IdentityForm';
import { InviteDateVotes } from './InviteDateVotes';
import { useTermsGate } from './TermsSheet';
import { Button, ErrorText, Loading, Screen, T, Title } from './ui';
import { appDownload } from '@/lib/appInvite';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { avatarColor, formatLongDay, formatTime, initials } from '@/lib/format';
import { acceptInvite, fetchInviteCard, type Accepted, type InviteCard } from '@/lib/invites';
import { clearInviteAnswer, peekInviteAnswer, rememberInviteAnswer } from '@/lib/inviteIntent';
import { canInstallWebApp, insideInstalledApp, installWebApp, isAndroid } from '@/lib/installPrompt';
import { enter, pressTransition } from '@/lib/motion';
import { safeHref } from '@/lib/links';
import { dbMessage, isTermsError } from '@/lib/moderation';
import { hasCompleteIdentity } from '@/lib/profile';
import { colors, radius, rsvpColors } from '@/lib/theme';
import type { RsvpStatus } from '@/lib/types';

const TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const ANSWERS: { key: RsvpStatus; label: string }[] = [
  { key: 'yes', label: 'Je viens !' }, { key: 'maybe', label: 'Peut-être' }, { key: 'no', label: 'Je ne peux pas' },
];
type Answer = RsvpStatus | 'poll';
const DONE_WORDS: Record<RsvpStatus, string> = { yes: 'Tu viens à', maybe: 'Tu viens peut-être à', no: 'Tu ne viens pas à' };
const CLOSED: Record<string, string> = {
  full: 'Ce lien a déjà servi : toutes ses places sont prises. Demande ton propre lien à la personne qui t’a invité.',
  expired: 'Ce lien n’est plus valable (date limite passée). Demande un nouveau lien à la personne qui t’a invité.',
  revoked: 'La personne qui t’a invité a arrêté ce lien. Demande-lui un nouveau lien.',
  removed: 'L’organisateur t’a retiré de la liste des invités : ce lien ne te permet plus de répondre.',
};
/** Refus définitifs de accept_invite (retiré de la liste, lien arrêté / plein / expiré, événement annulé ou fermé,
 * organisateur sur son propre lien) : inutile de réessayer, on ne propose plus de répondre. */
const FINAL_REFUSAL = /retiré de la liste|arrêté|déjà servi|places de ce lien|plus valable|annulé|n'est plus ouvert|n’est plus ouvert|n'existe|n’existe|ton propre lien|organisat|ne peux pas répondre/i;

export function isFinalRefusal(message: string): boolean {
  return FINAL_REFUSAL.test(message);
}

const OWN_LINK = 'Envoie-le à la personne invitée : il ne sert pas pour toi. Ta propre réponse se donne sur la fiche de l’événement.';
const isOrganizer = (value: object) => (value as { organizer?: boolean }).organizer === true;

function refusalText(message: string): string {
  return /retiré de la liste/i.test(message)
    ? 'L’organisateur t’a retiré de la liste des invités : tu ne peux plus répondre à cette invitation.'
    : message;
}

/**
 * Invitation à un événement, lisible SANS compte (invites_v2) : qui invite, quand, où, qui vient ou a voté → réponse →
 * inscription COMPLÈTE par le parcours normal de l'app (10.11, avis 39f148377a8f) : page de connexion (pays, numéro, code
 * SMS), puis « Faisons connaissance » (prénom, nom, surnom ; photo facultative) → la réponse choisie est reprise d'elle-
 * même → c'est noté (sondage : on vote les dates, puis la fiche s'ouvre). Rouvrir le même lien permet de changer sa réponse.
 */
export function InviteCardScreen({ token }: { token: string | undefined }) {
  const valid = typeof token === 'string' && TOKEN.test(token);
  const { session } = useAuth();
  const opened = useRef(false);
  const { data: card, loading, error, reload } = useQuery(async () => {
    if (!valid) return null;
    const first = !opened.current;
    opened.current = true;
    return fetchInviteCard(token!, first);  // première lecture : « A ouvert » chez l'organisateur
  }, [token, session?.user.id]);
  // Retour de la page de connexion : la réponse choisie avant est reprise d'elle-même (un seul toucher en tout).
  const [answer, setAnswer] = useState<Answer | null>(() => (valid && session ? peekInviteAnswer(token!) : null));
  const [done, setDone] = useState<Accepted | null>(null);
  const [refused, setRefused] = useState<string | null>(null);

  /** Sans compte : la page de connexion normale de l'app (jamais un formulaire à part), puis retour ici. */
  function choose(a: Answer) {
    if (session) return setAnswer(a);
    rememberInviteAnswer(token!, a);
    router.push('/sign-in' as Href);
  }

  if (!valid) return <Closed text="Ce lien d’invitation n’est pas complet. Copie-le en entier depuis le message reçu." />;
  if (loading && !card) return <Loading />;
  // Panne passagère (réseau, base lente) : jamais « n'existe plus », un bouton pour réessayer.
  if (!card && error) return <Closed title="Connexion difficile" text="L’invitation n’a pas pu être chargée. Vérifie ta connexion puis réessaie." onRetry={() => void reload()} />;
  if (!card) return <Closed text="Ce lien d’invitation n’existe plus." />;
  if (refused) return <Closed title="Réponse impossible" text={refused} />;
  // L'organisateur (ou un co-organisateur) sur son propre lien : la base ne le consomme pas et le dit (organizer).
  if (done && isOrganizer(done)) {
    return <Closed title="C’est ton lien d’invitation" text={OWN_LINK} />;
  }
  if (done) return <Done card={card} done={done} onChange={() => { setDone(null); setAnswer(null); reload(); }} />;
  if (answer) {
    return <Respond token={token!} card={card} answer={answer} onBack={() => { clearInviteAnswer(); setAnswer(null); }}
      onDone={(a) => { clearInviteAnswer(); setDone(a); }} onRefused={(text) => { clearInviteAnswer(); setAnswer(null); setRefused(text); }} />;
  }
  return <Card card={card} onAnswer={choose} />;
}

function Closed({ text, title = 'Lien indisponible', onRetry }: { text: string; title?: string; onRetry?: () => void }) {
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Title>{title}</Title>
      <T muted>{text}</T>
      {onRetry ? <Button label="Réessayer" onPress={onRetry} /> : null}
    </Screen>
  );
}

function when(card: Pick<InviteCard, 'starts_at' | 'all_day' | 'date_mode'>): string | null {
  if (card.date_mode === 'poll' || !card.starts_at) return 'Date à définir';
  const day = formatLongDay(card.starts_at);
  return card.all_day ? day : `${day} · ${formatTime(card.starts_at)}`;
}

function Host({ card }: { card: InviteCard }) {
  const name = card.inviter || 'Un ami';
  return (
    <View style={st.host}>
      <View style={[st.hostAvatar, { backgroundColor: avatarColor(name) }]}>
        <T weight="bold" color={colors.onAccent}>{initials(name)}</T>
      </View>
      <View style={{ flex: 1 }}>
        <T weight="bold" size={15}>{name} t’invite{card.label ? `, ${card.label}` : ''}</T>
        <T muted size={12}>{card.places_left != null ? `Lien pour plusieurs · reste ${card.places_left} ${card.places_left > 1 ? 'places' : 'place'}` : card.multi ? 'Lien pour plusieurs' : 'Seulement toi, avec ce lien'}</T>
      </View>
    </View>
  );
}

function Card({ card, onAnswer }: { card: InviteCard; onAnswer: (a: Answer) => void }) {
  const closed = card.state === 'full' || card.state === 'expired' || card.state === 'revoked' || card.state === 'removed';
  const cancelled = card.status === 'cancelled';
  // Sondage : on compte les votants, comme le sondage de la fiche (10.11 : « 2 viennent » mais 3 votes).
  const poll = card.date_mode === 'poll';
  const names = poll ? card.voter_names ?? [] : card.going_names;
  const total = poll ? card.voters ?? 0 : card.going;
  const others = Math.max(total - names.length, 0);
  const verb = poll ? (total > 1 ? 'ont voté' : 'a voté') : (total > 1 ? 'viennent' : 'vient');
  const coming = names.length
    ? `${names.join(', ')}${others ? ` et ${others} ${others > 1 ? 'autres' : 'autre'}` : ''} ${verb}`
    : total ? `${total} ${total > 1 ? 'personnes' : 'personne'} ${verb}` : poll ? 'Sois le premier à voter' : 'Sois le premier à répondre';
  const answers = ANSWERS.filter((a) => a.key !== 'maybe' || card.allow_maybe);
  return (
    <Screen contentStyle={{ gap: 18 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Host card={card} />
      <View style={[st.invite, enter('rise')]}>
        {card.cover_url ? (
          <Image source={{ uri: card.cover_url }} style={st.cover} resizeMode="cover" accessibilityLabel="Affiche de l’événement" />
        ) : (
          <View style={[st.cover, st.coverEmpty]}><T size={44}>🎉</T></View>
        )}
        <View style={{ padding: 18, gap: 14 }}>
          <Title size={30} style={{ lineHeight: 34 }}>{card.title}</Title>
          <Line icon="📅" title={when(card) ?? ''} />
          {card.location_name ? <Line icon="📍" title={card.location_name} hint={card.mine ? undefined : 'L’adresse exacte après ta réponse'} /> : null}
          {card.description ? <T size={14} color={colors.textSoft} numberOfLines={5}>{card.description}</T> : null}
          <View style={st.coming}>
            <View style={{ flexDirection: 'row' }}>
              {names.map((n, i) => (
                <View key={`${n}${i}`} style={[st.face, { backgroundColor: avatarColor(n + i), marginLeft: i ? -8 : 0 }]}>
                  <T size={11} weight="bold" color={colors.onAccent}>{initials(n)}</T>
                </View>
              ))}
            </View>
            <T size={13} weight="semibold" color={colors.textSoft} style={{ flex: 1 }}>{coming}</T>
          </View>
        </View>
      </View>
      {cancelled ? (
        <View style={st.notice}><T weight="bold" color={colors.coralSoft}>Cet événement est annulé.</T></View>
      ) : isOrganizer(card) ? (
        // L'organisateur voit la carte telle que l'invité la verra, sans y répondre (le lien n'est pas pour lui).
        <View style={st.notice}><T color={colors.coralSoft}>C’est ton lien d’invitation. {OWN_LINK}</T></View>
      ) : closed && card.already && card.event_id ? (
        // Déjà invité autrement (liste, groupe, autre lien) : ce lien ne sert plus, mais l'événement l'attend.
        <View style={{ gap: 10 }}>
          <View style={st.notice}><T color={colors.textSoft}>Tu es déjà invité à cet événement{card.mine ? ` (ta réponse : ${(ANSWERS.find((a) => a.key === card.mine)?.label ?? '').replace(/\s*[.!]\s*$/, '')})` : ''}.</T></View>
          <OpenEvent id={card.event_id} label="Voir l’événement" />
        </View>
      ) : closed ? (
        <View style={st.notice}><T color={colors.coralSoft}>{CLOSED[card.state]}</T></View>
      ) : card.closed ? (
        <View style={st.notice}><T color={colors.coralSoft}>{card.date_mode === 'poll' ? 'Les votes sont fermés pour ce sondage : l’organisateur va fixer la date.' : 'Les réponses sont fermées pour cet événement.'}</T></View>
      ) : card.date_mode === 'poll' ? (
        // Sondage de dates : on répond en votant les dates, comme dans l'app (jamais « Je viens » avant la date fixée).
        <View style={{ gap: 10 }}>
          <T style={{ textAlign: 'center' }} color={colors.textSoft}>La date n’est pas encore fixée : indique les dates où tu es dispo, {card.inviter || 'l’organisateur'} choisira celle qui arrange le plus de monde.</T>
          <Pressable accessibilityRole="button" onPress={() => onAnswer('poll')}
            style={({ pressed }) => [st.answer, st.answerYes, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
            <T weight="bold" size={17} color={colors.onAction}>📅 Choisir mes dates</T>
          </Pressable>
          {insideInstalledApp() ? null : <T muted size={13} style={{ textAlign: 'center' }}>Pas besoin d’installer l’app.</T>}
        </View>
      ) : (
        <View style={{ gap: 10 }}>
          {card.mine ? <T weight="semibold" style={{ textAlign: 'center' }}>Ta réponse : {(ANSWERS.find((a) => a.key === card.mine)?.label ?? '').replace(/\s*[.!]\s*$/, '')}. Tu peux la changer.</T> : null}
          {answers.map((a) => (
            <Pressable key={a.key} accessibilityRole="button" accessibilityState={{ selected: card.mine === a.key }} onPress={() => onAnswer(a.key)}
              style={({ pressed }) => [st.answer, a.key === 'yes' ? st.answerYes : null, card.mine === a.key && { borderColor: rsvpColors[a.key] },
                pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
              <T weight="bold" size={17} color={a.key === 'yes' ? colors.onAction : colors.text}>{a.label}</T>
            </Pressable>
          ))}
          {insideInstalledApp() ? null : <T muted size={13} style={{ textAlign: 'center' }}>Pas besoin d’installer l’app.</T>}
        </View>
      )}
    </Screen>
  );
}

function Line({ icon, title, hint }: { icon: string; title: string; hint?: string }) {
  return (
    <View style={st.line}>
      <View style={st.lineIcon}><T size={16}>{icon}</T></View>
      <View style={{ flex: 1 }}>
        <T weight="bold" size={16}>{title}</T>
        {hint ? <T muted size={12}>{hint}</T> : null}
      </View>
    </View>
  );
}

/**
 * Réponse d'un compte connecté. Profil incomplet (compte neuf, ancien compte « au prénom seul ») : « Faisons
 * connaissance », le même formulaire que partout dans l'app (prénom, nom, surnom ; photo facultative), puis la réponse
 * part d'elle-même. Profil complet : la réponse part tout de suite (un seul essai automatique, puis « Réessayer »).
 */
function Respond({ token, card, answer, onBack, onDone, onRefused }: {
  token: string; card: InviteCard; answer: Answer; onBack: () => void; onDone: (a: Accepted) => void;
  onRefused: (text: string) => void;
}) {
  const { profile } = useAuth();
  const complete = hasCompleteIdentity(profile);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  const busyRef = useRef(false);
  // CGU : acceptées dans « Faisons connaissance » (premier surnom). Un ancien compte qui ne les a pas encore acceptées
  // voit la feuille des CGU si la base les exige (jamais d'acceptation silencieuse, Apple 1.2), puis un seul nouvel essai.
  const terms = useTermsGate();

  async function accept() {
    if (busyRef.current) return;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    try {
      try {
        onDone(await acceptInvite(token, answer));
      } catch (e) {
        if (!(e instanceof Error && isTermsError(e.message) && (await terms.ensure()))) throw e;
        onDone(await acceptInvite(token, answer));
      }
    } catch (e) {
      const raw = e instanceof Error ? e.message : String(e);
      const message = dbMessage(raw, raw || 'Ta réponse n’a pas pu être enregistrée. Réessaie.');
      // Refus définitif : on s'arrête au premier (jamais de nouvel essai automatique, ≈150 appels refusés avant).
      if (isFinalRefusal(message)) return onRefused(refusalText(message));
      setError(message);
    } finally {
      busyRef.current = false;
      setBusy(false);
    }
  }

  // Profil complet (tout de suite, ou juste après « Faisons connaissance ») : la réponse part une seule fois.
  useEffect(() => {
    if (complete && !started.current) {
      started.current = true;
      void accept();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- un seul départ, dès que le profil est complet
  }, [complete]);

  if (!profile) return <Loading />;
  if (complete) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
        <Stack.Screen options={{ title: 'Invitation' }} />
        {terms.sheet}
        {error ? (
          <>
            <ErrorText error={error} />
            <Button label="Réessayer" loading={busy} onPress={() => void accept()} />
            <Button label="Retour à l’invitation" variant="secondary" onPress={onBack} />
          </>
        ) : <Loading />}
      </Screen>
    );
  }

  const host = card.inviter || 'L’organisateur';
  return (
    <Screen contentStyle={{ gap: 18 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <View style={[{ gap: 6 }, enter('slideIn')]}>
        <Title size={30}>Faisons connaissance</Title>
        <T muted>{`Pour répondre à ${host}, complète ton profil Party : c’est le même partout dans l’app. Ta réponse part juste après.`}</T>
      </View>
      <IdentityForm profile={profile} submitLabel={answer === 'poll' ? 'Continuer vers mes dates' : 'Continuer'} />
      <ErrorText error={error} />
      <Button small variant="ghost" label="‹ Retour à l’invitation" onPress={onBack} />
    </Screen>
  );
}

function Done({ card, done, onChange }: { card: InviteCard; done: Accepted; onChange: () => void }) {
  if (done.status === null) return <PollDone card={card} done={done} />;
  return <Answered card={card} done={done as Accepted & { status: RsvpStatus }} onChange={onChange} />;
}

/** La fiche complète de l'événement, comme pour tout membre (profil complet : elle s'ouvre). Identifiant vérifié. */
function OpenEvent({ id, label }: { id: string; label: string }) {
  if (!TOKEN.test(id)) return null;
  return <Button label={label} variant="secondary" onPress={() => router.replace(`/event/${id}` as Href)} />;
}

/** Sondage de dates : on vote les dates tout de suite ; l'organisateur fixe ensuite celle qui arrange le plus de monde. */
function PollDone({ card, done }: { card: InviteCard; done: Accepted }) {
  const { profile } = useAuth();
  const [votes, setVotes] = useState(0);
  const first = profile?.first_name?.trim() || (profile?.display_name ?? '').split(' ')[0];  // le prénom (profil complet)
  const host = card.inviter || 'L’organisateur';
  return (
    <Screen contentStyle={{ gap: 18 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <View style={[{ gap: 6 }, enter('rise')]}>
        <Title size={28}>{votes ? `C’est noté${first ? `, ${first}` : ''} !` : `Tes dates${first ? `, ${first}` : ''}`}</Title>
        <T color={colors.textSoft}>
          Pour <T weight="bold">{done.title}</T> : réponds pour chaque date. {host} fixera celle qui arrange le plus de monde,
          et tu seras inscrit selon ton vote pour cette date.
        </T>
      </View>
      <InviteDateVotes eventId={done.event_id} onVoted={setVotes}
        calendar={{ title: done.title, description: done.description ?? '', location_name: done.location_name, location_address: done.location_address }} />
      <T muted size={13} style={{ textAlign: 'center' }}>Tes votes sont enregistrés à chaque toucher. Rouvre ce même lien pour les changer.</T>
      <OpenEvent id={done.event_id} label="Voir l’événement et les votes" />
    </Screen>
  );
}

function Answered({ card, done, onChange }: { card: InviteCard; done: Accepted & { status: RsvpStatus }; onChange: () => void }) {
  const { profile } = useAuth();
  const [later, setLater] = useState(false);
  const first = profile?.first_name?.trim() || (profile?.display_name ?? '').split(' ')[0];  // le prénom (profil complet)
  const host = card.inviter || 'L’organisateur';
  const place = done.location_address ?? done.location_name;
  const maps = safeHref(done.location_url) ?? (place ? `https://maps.apple.com/?q=${encodeURIComponent(place)}` : null);
  const download = appDownload();
  // Android : jamais l'App Store d'Apple ; la page s'installe si Chrome le propose, sinon pas de bouton.
  const android = isAndroid();
  const [installable, setInstallable] = useState(() => !android || canInstallWebApp());
  const install = () => (android ? void installWebApp().catch(() => false).then(() => setInstallable(false)) : void Linking.openURL(download.url));
  const coming = done.status !== 'no';
  return (
    <Screen contentStyle={{ gap: 18 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <View style={[{ alignItems: 'center', gap: 10 }, enter('rise')]}>
        <View style={[st.check, { backgroundColor: coming ? colors.mint : colors.surface2 }]}>
          <T size={30} weight="bold" color={coming ? colors.onMint : colors.text}>{coming ? '✓' : '👋'}</T>
        </View>
        <Title size={30} style={{ textAlign: 'center' }}>C’est noté{first ? `, ${first}` : ''} !</Title>
        <T style={{ textAlign: 'center' }} color={colors.textSoft}>
          {DONE_WORDS[done.status]} <T weight="bold">{done.title}</T>{done.starts_at ? `, ${when({ ...done, date_mode: done.date_mode as InviteCard['date_mode'] })?.toLowerCase()}` : ''}.
        </T>
        <T muted>{host} est prévenu.</T>
        {done.waitlisted ? <T size={13} color={colors.coralSoft} style={{ textAlign: 'center' }}>C’est complet pour l’instant : tu es sur la liste d’attente.</T> : null}
      </View>
      {coming ? (
        <View style={{ gap: 10 }}>
          {place ? <Line icon="📍" title={done.location_name ?? place} hint={done.location_address && done.location_name ? done.location_address : undefined} /> : null}
          <View style={{ flexDirection: 'row', gap: 10 }}>
            {done.starts_at ? (
              <View style={{ flex: 1 }}>
                <CalendarButton event={{ id: done.event_id, title: done.title, description: done.description ?? '', starts_at: done.starts_at,
                  ends_at: done.ends_at, location_name: done.location_name, location_address: done.location_address }} />
              </View>
            ) : null}
            {maps ? <Button label="📍 Itinéraire" variant="secondary" style={{ flex: 1 }} onPress={() => void Linking.openURL(maps)} /> : null}
          </View>
        </View>
      ) : null}
      {!later && !insideInstalledApp() ? (
        <View style={st.appCard}>
          <View style={st.appIcon}><T weight="bold" color={colors.onAction}>P!</T></View>
          <T weight="bold" size={17}>Reçois les nouvelles de la soirée</T>
          <T size={14} color={colors.textSoft}>
            Si l’heure change, ce que chacun amène, la musique en direct. Installer Party est facultatif : avec ton numéro, tu y retrouves ton invitation.
          </T>
          {installable ? (
            <View style={{ flexDirection: 'row', gap: 10 }}>
              <Button label="Installer Party" style={{ flex: 1 }} onPress={install} />
              <Button label="Plus tard" variant="secondary" style={{ flex: 1 }} onPress={() => setLater(true)} />
            </View>
          ) : (
            <T size={13} color={colors.textSoft}>Garde ce lien : en le rouvrant, tu retrouves ton invitation.</T>
          )}
        </View>
      ) : null}
      <OpenEvent id={done.event_id} label="Voir l’événement" />
      <T muted size={13} style={{ textAlign: 'center' }}>Un empêchement ? Rouvre ce même lien pour changer ta réponse.</T>
      <Button small variant="ghost" label="Changer ma réponse" onPress={onChange} />
    </Screen>
  );
}

const st = StyleSheet.create({
  host: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  hostAvatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  invite: { borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, overflow: 'hidden' },
  cover: { width: '100%', aspectRatio: 16 / 9, backgroundColor: colors.surface2 },
  coverEmpty: { aspectRatio: 3, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accentDim },
  line: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  lineIcon: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.line, alignItems: 'center', justifyContent: 'center' },
  coming: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.line },
  face: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: colors.surface },
  answer: { minHeight: 54, borderRadius: radius.md, backgroundColor: colors.fillStrong, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: 'transparent' },
  answerYes: { backgroundColor: colors.action },
  notice: { padding: 14, borderRadius: radius.md, backgroundColor: colors.coralDim },
  check: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center' },
  appCard: { gap: 10, padding: 16, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  appIcon: { width: 44, height: 44, borderRadius: 12, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center' },
});
