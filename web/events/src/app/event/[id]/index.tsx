import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, useWindowDimensions, View } from 'react-native';

import { AIEventSteps } from '@/components/AIEventSteps';
import { AttendanceEditor } from '@/components/AttendanceEditor';
import { AttendeesBadge } from '@/components/AttendeesBadge';
import { PendingPayments } from '@/components/PendingPayments';
import { RejectProposal } from '@/components/RejectProposal';
import { ReportSheet } from '@/components/ReportSheet';
import { TicketCard } from '@/components/TicketCard';
import { TicketsManager } from '@/components/TicketsManager';
import { CalendarButton } from '@/components/CalendarButton';
import { EventGiftsLink } from '@/components/EventGifts';
import { compagnonOn, invitesV2On } from '@/lib/features';
import { GuestListCard } from '@/components/GuestListCard';
import { AnnounceStatusCard } from '@/components/AnnounceStatusCard';
import { InviteLinkCard } from '@/components/InviteLinkCard';
import { parseIds } from '@/components/InviteStep';
import { LinkedText } from '@/components/LinkedText';
import { BringSection, DatePollSection, ParticipantsSection, PollSection, RsvpCard } from '@/components/EventSections';
import { Badge, Button, Card, Cascade, ConfirmButton, ErrorText, HeaderAction, HeaderBack, Screen, s, Section, Skeleton, T, Title, Toast } from '@/components/ui';
import { fetchAttendance, localAttendance } from '@/lib/attendance';
import { settleNativeDates } from '@/lib/calendar';
import { useAuth, useMe } from '@/lib/auth';
import { personLabel, useContactNames, withContactNames } from '@/lib/contactNames';
import { useQuery, useRealtime } from '@/lib/data';
import { GONE_TEXT, isGoneError, isNetworkError } from '@/lib/errors';
import { eventPeopleIds, undecidedNames } from '@/lib/eventPeople';
import { useOnline, usePaymentsTick, useSlowLoad } from '@/lib/connectivity';
import { safeHref } from '@/lib/links';
import { formatLongDay, formatMessageTime, formatShort, formatTime, plural, relativeDay } from '@/lib/format';
import type { ReportTarget } from '@/lib/moderation';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import { ticketRelevant, chf } from '@/lib/tickets';
import type { BringItem, Category, DateOption, DateVoteRow, EventRow, Message, Poll, PollOption, Rsvp, Tag } from '@/lib/types';
import { plusOnesLabel } from '@/lib/types';
import { notifyWallet } from '@/lib/wallet';

type Full = EventRow & {
  category: Category | null;
  author: { id?: string; display_name: string } | null;
  event_tags: { tags: Tag }[];
  event_organizers: { user_id: string }[];
  rsvps: Rsvp[];
  date_options: (DateOption & { date_votes: DateVoteRow[] })[];
  polls: (Poll & { poll_options: PollOption[] })[];
  bring_items: BringItem[];
  event_groups: { group_id: string }[];
};

/** Le temps réel accepte au plus 100 valeurs dans un filtre « in ». */
const REALTIME_IN_MAX = 100;
/** En dessous (ou texte agrandi), les actions d'en-tête passent en icônes : le retour « ‹ Événements » garde sa place. */
const NARROW_HEADER_WIDTH = 380;
/** Avec « ✨ IA » (app iPhone, organisateur) : il faut environ 460 pt pour tout écrire (recette du 10.11 : chevauchement). */
const NARROW_HEADER_WIDTH_WITH_AI = 470;

/** Lien à partager : ouvre Party sur cet événement (page publique pour qui n'est pas membre). */
async function sharePublicLink(ev: Pick<EventRow, 'id' | 'title'>): Promise<string> {
  const url = `${location.origin}/?tab=events&event=${ev.id}`;
  try {
    if (navigator.share) { await navigator.share({ title: ev.title, url }); return ''; }
  } catch (e) {
    if (e instanceof Error && e.name === 'AbortError') return '';  // partage annulé
  }
  try {
    await navigator.clipboard.writeText(url);
    return 'Lien copié';
  } catch {
    return url;  // copie refusée : on l'affiche pour une copie manuelle
  }
}

export default function EventScreen() {
  // ?step=online : étape 3 de l'assistant IA ; &invite=link : la feuille « Inviter » s'ouvre (lien prêt, ?suggested= cochés) ;
  // &invite=more : la carte « Invités » passe en tête (publié pour un groupe).
  const { id, step, invite, suggested } = useLocalSearchParams<{ id: string; step?: string; invite?: string; suggested?: string }>();
  const me = useMe();
  const { can } = useAuth();
  const { width, fontScale } = useWindowDimensions();
  const isAdmin = can('events.manage_all');
  const [error, setError] = useState<string | null>(null);
  const [shareNote, setShareNote] = useState('');
  const [report, setReport] = useState<ReportTarget | null>(null);
  /** Paiement confirmé (« Reçu ») : il remet aussi le billet, la liste « Billets QR » se relit. */
  const [paymentsSeen, setPaymentsSeen] = useState(0);

  // Campagne 2 (07.11) : seul l'événement est obligatoire (must) ; le reste (sondages, profils, messages…) se lit avec un
  // repli, et seulement pour CET événement (avant : tous les profils, résultats et votes de Party à chaque ouverture).
  const { data: loaded, reload, error: loadError } = useQuery(async () => {
    const [ev, messages, mute, links, attendance, groupNames] = await Promise.all([
      supabase
        .from('events')
        .select(
          '*, category:categories(*), author:profiles!events_created_by_fkey(id, display_name), event_tags(tags(*)), event_organizers(user_id), rsvps(*), date_options(*, date_votes(*)), polls(*, poll_options(*)), bring_items(*, bring_claims(user_id, quantity)), event_groups(group_id)',
        )
        .eq('id', id)
        .single(),
      supabase.from('messages').select('*').eq('event_id', id).is('deleted_at', null).order('created_at', { ascending: false }).limit(2),
      supabase.from('event_mutes').select('event_id').eq('event_id', id).eq('user_id', me.id),
      // Invités arrivés par le lien (lisible par les organisateurs et les admins : orange dans « Qui vient ? »).
      supabase.from('event_invites').select('user_id').eq('event_id', id).eq('via_link', true),
      // Pastille des présents : totaux exacts même si la liste des participants est cachée.
      fetchAttendance([id]).catch(() => new Map()),
      // Noms des groupes invités : lisibles par qui voit l'événement, même sans faire partie du groupe.
      supabase.rpc('event_group_names', { e: id }),
    ]);
    const event = must(ev) as unknown as Full;
    const pollIds = event.polls.map((p) => p.id);
    const [results, allVotes] = pollIds.length
      ? await Promise.all([
          supabase.from('poll_results').select('*').in('poll_id', pollIds),
          supabase.from('poll_votes').select('option_id, user_id').in('poll_id', pollIds),
        ])
      : [{ data: [] }, { data: [] }];
    const votes = (allVotes.data ?? []) as { option_id: string; user_id: string }[];
    const msgs = (messages.data ?? []) as Message[];
    const peopleIds = eventPeopleIds(event, votes, msgs);
    const members = peopleIds.length ? await supabase.from('profiles').select('id, display_name').in('id', peopleIds) : { data: [] };
    return {
      event,
      names: new Map(((members.data ?? []) as { id: string; display_name: string }[]).map((m) => [m.id, m.display_name])),
      results: (results.data ?? []) as { poll_id: string; option_id: string; votes: number }[],
      myVotes: new Set(votes.filter((v) => v.user_id === me.id).map((v) => v.option_id)),
      allVotes: votes,
      messages: msgs,
      muted: (mute.data ?? []).length > 0,
      viaLink: new Set(((links.data ?? []) as { user_id: string }[]).map((l) => l.user_id)),
      attendance: attendance.get(id) ?? null,
      groupNames: ((groupNames.data ?? []) as string[]).join(', '),
      loadedAt: Date.now(),
    };
  }, [id, me.id]);

  // App iPhone : les membres de mon répertoire sous le nom de mes contacts (« Nom · pseudo »), partout sur la page.
  const contacts = useContactNames();
  const data = useMemo(() => (loaded ? { ...loaded, names: withContactNames(loaded.names, contacts) } : loaded), [loaded, contacts]);

  // Temps réel filtré sur CET événement : un vote ailleurs dans Party ne recharge plus la fiche (campagne 2, rapport 10).
  const optionIds = (loaded?.event.date_options ?? []).map((o) => o.id).slice(0, REALTIME_IN_MAX);
  const pollIds = (loaded?.event.polls ?? []).map((p) => p.id).slice(0, REALTIME_IN_MAX);
  useRealtime(`event-${id}`, [
    { table: 'rsvps', filter: `event_id=eq.${id}` },
    ...(optionIds.length ? [{ table: 'date_votes', filter: `option_id=in.(${optionIds.join(',')})` }] : []),
    ...(pollIds.length ? [{ table: 'poll_votes', filter: `poll_id=in.(${pollIds.join(',')})` }] : []),
    { table: 'messages', filter: `event_id=eq.${id}` },
    // Ce que font les autres dans l'événement, sans recharger (retour du 08.11).
    { table: 'events', filter: `id=eq.${id}` },
    { table: 'bring_items', filter: `event_id=eq.${id}` },
    { table: 'date_options', filter: `event_id=eq.${id}` },
    { table: 'event_organizers', filter: `event_id=eq.${id}` },
  ], reload);

  const online = useOnline(reload);
  const slow = useSlowLoad(!loaded && !loadError);

  const ev = data?.event;
  // Dates « À confirmer » mises dans le calendrier de l'iPhone (avis 9ddbdea7fe8f) : date fixée ou événement annulé,
  // l'app garde la bonne entrée et retire les autres, sans rien demander.
  useEffect(() => {
    if (ev) void settleNativeDates(ev);
  }, [ev?.id, ev?.status, ev?.date_mode, ev?.starts_at, ev?.ends_at, ev?.title]);  // eslint-disable-line react-hooks/exhaustive-deps
  // Payant : « J'ai payé » (invité) et « Reçu » (organisateur) apparaissent sans recharger la page. Les billets ne sont pas
  // lisibles en direct (table fermée, fonctions seulement) : relecture légère des deux cartes, page visible seulement.
  const mineYes = !!ev && ev.rsvps.some((r) => r.user_id === me.id && r.status === 'yes');
  const paymentsTick = usePaymentsTick(!!ev && ev.status === 'published' && (ev.price_chf ?? 0) > 0 && (mineYes || isAdmin || ev.created_by === me.id || ev.event_organizers.some((o) => o.user_id === me.id)));
  const isOrganizer = !!ev && (ev.created_by === me.id || ev.event_organizers.some((o) => o.user_id === me.id));
  const canManage = isAdmin || isOrganizer;

  const pollData = useMemo(() => {
    if (!data) return new Map<string, { results: Map<string, number> | null; voters: Map<string, string[]> }>();
    const out = new Map<string, { results: Map<string, number> | null; voters: Map<string, string[]> }>();
    for (const p of data.event.polls) {
      const rows = data.results.filter((r) => r.poll_id === p.id);
      const voters = new Map<string, string[]>();
      for (const o of p.poll_options) {
        voters.set(o.id, data.allVotes.filter((v) => v.option_id === o.id).map((v) => data.names.get(v.user_id) ?? '?'));
      }
      out.set(p.id, { results: rows.length ? new Map(rows.map((r) => [r.option_id, r.votes])) : null, voters });
    }
    return out;
  }, [data]);

  if (!data || !ev) {
    if (!loadError && online && !slow) return <EventSkeleton />;
    return <LoadProblem error={loadError} online={online} onRetry={reload} />;
  }

  const published = ev.status === 'published';
  const canEdit = isAdmin || (isOrganizer && (ev.status !== 'published' || can('events.edit_own_published')));
  // App iPhone et droit IA : « ✨ IA » ouvre l'écran natif où l'on dit ce qui change (« décale à 21h »…).
  const native = (globalThis as { PartyNative?: { ai?: { editEvent?: (id: string) => void } } }).PartyNative;
  const aiEdit = can('ai.use') && native?.ai?.editEvent ? (id: string) => native.ai!.editEvent!(id) : null;
  const narrow = width < (aiEdit && canEdit ? NARROW_HEADER_WIDTH_WITH_AI : NARROW_HEADER_WIDTH) || fontScale > 1.15;

  async function run(p: PromiseLike<{ error: { message: string } | null }>) {
    const { error } = await p;
    setError(error?.message ?? null);
    reload();
  }

  const toggleMute = () =>
    run(
      data.muted
        ? supabase.from('event_mutes').delete().eq('event_id', ev.id).eq('user_id', me.id)
        : supabase.from('event_mutes').insert({ event_id: ev.id, user_id: me.id }),
    );

  const people = data.attendance ?? localAttendance(ev.rsvps, data.names);
  const heads = people.going;
  const past = !!ev.starts_at && new Date(ev.ends_at ?? ev.starts_at).getTime() < data.loadedAt - 6 * 3600_000;
  // Lien du lieu saisi librement : seulement http(s) (jamais javascript:/data:), sinon la recherche Plans.
  const mapsUrl = safeHref(ev.location_url) ?? (ev.location_address || ev.location_name ? `https://maps.apple.com/?q=${encodeURIComponent(ev.location_address ?? ev.location_name!)}` : null);
  const mine = ev.rsvps.find((r) => r.user_id === me.id);
  const showCalendar = published && ev.date_mode === 'fixed' && !!ev.starts_at && mine?.status !== 'no';

  const infoRows = [
    ev.price_chf != null ? { k: 'Prix', v: ev.price_chf === 0 ? 'Gratuit' : `${chf(ev.price_chf)} / personne`, sub: ev.payment_info } : null,
    ev.max_participants
      ? { k: 'Places', v: `${heads} / ${ev.max_participants}`, sub: heads >= ev.max_participants ? (ev.waitlist_enabled ? 'Complet · liste d’attente ouverte' : 'Complet') : plural(ev.max_participants - heads, 'place libre', 'places libres') }
      : ev.date_mode === 'fixed' ? { k: 'Places', v: '∞ Illimité', sub: plural(heads, 'personne inscrite', 'personnes inscrites') } : null,
    ev.date_mode === 'fixed' && ev.allow_plus_ones && ev.max_plus_ones > 0 ? { k: 'Accompagnants', v: plusOnesLabel(ev.max_plus_ones) } : null,
    ev.rsvp_deadline ? { k: 'Réponse avant', v: formatShort(ev.rsvp_deadline) } : null,
  ].filter(Boolean) as { k: string; v: string; sub?: string | null }[];

  return (
    <>
      <Stack.Screen
        options={{
          // Le titre de l'événement est le titre de niveau 1 de la page (plus de h1 vide dans l'en-tête).
          title: ev.title,
          headerTitle: () => null,
          // Ouvert par un lien (rien derrière) : ‹ Événements ramène à la liste ; sinon le ‹ commun de la pile.
          ...(router.canGoBack() ? {} : { headerLeft: () => <HeaderBack label="Événements" onPress={() => router.replace('/')} /> }),
          headerRight: () => (
            <View style={s.row}>
              {/* Écran étroit (360 px, texte agrandi) : l'icône seule, sinon « ‹ Événements » passait sous « 🔔 Sourdine ». */}
              {published ? (
                <HeaderAction label={narrow ? (data.muted ? '🔕' : '🔔') : data.muted ? '🔕 Réactiver' : '🔔 Sourdine'}
                  accessibilityLabel={data.muted ? 'Réactiver les notifications de cet événement' : 'Mettre cet événement en sourdine'} onPress={toggleMute} />
              ) : null}
              {canEdit && aiEdit ? <HeaderAction label={narrow ? '✨' : '✨ IA'} accessibilityLabel="Modifier avec l’IA" onPress={() => aiEdit(ev.id)} /> : null}
              {canEdit ? <HeaderAction prominent label="Modifier" onPress={() => router.push(`/event/${ev.id}/edit`)} /> : null}
            </View>
          ),
        }}
      />
    <Screen edges={[]}>
      {/* Ouverture : l’en-tête puis chaque bloc montent en cascade (une seule fois, pas aux rechargements). */}
      <Cascade>
      {/* Affiche de l’événement (lue sur la page de l’événement par l’assistant IA) */}
      {ev.cover_url?.startsWith('https://') ? (
        <Image source={{ uri: ev.cover_url }} style={st.cover} resizeMode="cover" accessibilityLabel="Affiche de l’événement" />
      ) : null}
      {/* En-tête : l’essentiel en un coup d’œil */}
      <View style={{ gap: 10 }}>
        {/* En haut : les étiquettes, et à droite qui vient et combien (donne envie d’en être). Le titre, dessous,
            garde toute la largeur : un long titre ne pousse plus la pastille hors de l’écran. */}
        <View style={st.titleRow}>
          <View style={[s.wrap, st.badges]}>
            {ev.status === 'pending' ? <Badge label="En attente de validation" fg={colors.lavender} bg={colors.lavenderDim} /> : null}
            {ev.status === 'draft' ? <Badge label="Brouillon" fg={colors.textSoft} bg={colors.surface2} /> : null}
            {ev.status === 'rejected' ? <Badge label="Refusé" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
            {ev.status === 'cancelled' ? <Badge label="Annulé" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
            {ev.date_mode === 'poll' ? <Badge label="Date à définir" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
            {ev.category ? <Badge label={ev.category.name} fg={colors.onAccent} bg={ev.category.color} /> : null}
          </View>
          {published && ev.date_mode === 'fixed' ? <AttendeesBadge attendance={people} large past={past} /> : null}
        </View>
        <Title level={1} size={32} style={{ lineHeight: 36 }}>{ev.title}</Title>
        {ev.visibility === 'invited' ? (
          <T muted size={13}>
            🔒 Sur invitation{data?.groupNames ? ` · ${data.groupNames}` : ''}
          </T>
        ) : !ev.public_link ? (
          <T muted size={13}>👥 Groupe Vendredi Party{data?.groupNames ? ` + ${data.groupNames}` : ''}</T>
        ) : null}
        {ev.public_link && published ? (
          <View style={s.row}>
            <T muted size={13} style={{ flex: 1 }}>🌍 Publique : tous les comptes Party et toute personne qui a le lien{shareNote && shareNote !== 'Lien copié' ? ` · ${shareNote}` : ''}</T>
            <Button small variant="secondary" label="Partager le lien" onPress={async () => setShareNote(await sharePublicLink(ev))} />
          </View>
        ) : null}

        {ev.date_mode === 'fixed' && ev.starts_at ? (
          <View style={st.keyRow}>
            <View style={st.keyIcon}><T size={16}>📅</T></View>
            <View style={{ flex: 1 }}>
              <T weight="bold" size={16}>{formatLongDay(ev.starts_at)} · {formatTime(ev.starts_at)}</T>
              <T muted size={13}>
                {relativeDay(ev.starts_at)}{ev.ends_at ? ` · jusqu’à ${formatShort(ev.ends_at)}` : ''}
              </T>
            </View>
          </View>
        ) : null}
        {ev.location_name || ev.location_address ? (
          <Pressable
            accessibilityRole={mapsUrl ? 'link' : undefined}
            disabled={!mapsUrl}
            onPress={() => mapsUrl && Linking.openURL(mapsUrl)}
            style={({ pressed }) => [st.keyRow, pressed && { opacity: 0.75 }]}
          >
            <View style={st.keyIcon}><T size={16}>📍</T></View>
            <View style={{ flex: 1 }}>
              <T weight="bold" size={16}>{ev.location_name ?? ev.location_address}</T>
              {ev.location_name && ev.location_address ? <T muted size={13}>{ev.location_address}</T> : null}
            </View>
            {mapsUrl ? <T size={13} weight="bold" color={colors.accent}>Itinéraire ›</T> : null}
          </Pressable>
        ) : null}

        {/* « À propos » juste après le lieu : on lit de quoi il s'agit avant de répondre (demande de l'admin, 08.11). */}
        {ev.description ? (
          <Section title="À propos">
            <LinkedText text={ev.description} color={colors.textSoft} style={{ lineHeight: 22 }} />
          </Section>
        ) : null}

        {showCalendar ? <CalendarButton event={ev} prominent={mine?.status === 'yes' || mine?.status === 'maybe'} /> : null}

        {ev.status === 'cancelled' ? (
          <View style={[st.notice, { backgroundColor: colors.coralDim }]}>
            <T color={colors.coralSoft} weight="semibold">Cet événement a été annulé.</T>
          </View>
        ) : null}
        {ev.status === 'rejected' && ev.rejection_reason ? <T color={colors.coralSoft}>Motif du refus : {ev.rejection_reason}</T> : null}
      </View>

      {/* « Créer avec l'IA », étape 3 : c'est en ligne, et tout se modifie ici. */}
      {step === 'online' && canManage && (published || ev.status === 'pending') ? (
        <Card style={{ backgroundColor: colors.accentDim, borderColor: '#5A2346' }}>
          <AIEventSteps current={3} />
          <T weight="bold" size={17}>{!published ? 'Envoyé pour validation' : invite === 'link' ? 'C’est en ligne : envoie le lien à tes invités' : 'C’est en ligne !'}</T>
          <T size={13} color={colors.textSoft}>
            {published ? 'Tu peux tout changer toi-même : « Modifier » en haut' : 'Il sera visible une fois validé par un admin. Tu peux encore tout changer : « Modifier » en haut'}
            {invitesV2On && published ? ', et inviter d’autres personnes ou envoyer un lien avec la carte « Invités ».' : '.'}
            {!published && ev.visibility === 'invited' ? ' Le lien à partager à tes invités sera disponible dès la validation.' : ''}
          </T>
        </Card>
      ) : null}
      {/* Brouillon (assistant IA ou formulaire) : choisir les invités puis publier, comme l'étape 2 de l'assistant. */}
      {ev.status === 'draft' && canManage ? (
        <Card>
          <T weight="semibold">Ce brouillon n’est visible que par toi.</T>
          <Button label="Inviter et publier" onPress={() => router.push(`/event/${ev.id}/invite`)} />
        </Card>
      ) : null}

      {/* Invitations v2 (bêta) : qui vient, qui n'a pas répondu, les liens envoyés ; « + » pour inviter. */}
      {/* Invitations v2 éteintes : juste publié sur invitation, le lien à partager en tête de fiche. */}
      {!invitesV2On && canManage && published && ev.visibility === 'invited' && step === 'online' ? <InviteLinkCard kind="event" id={ev.id} /> : null}
      {invitesV2On && canManage && published ? (
        <GuestListCard event={ev} me={{ id: me.id, display_name: me.display_name ?? '' }} onChanged={reload}
          openSheet={step === 'online' && invite === 'link'} headline={step === 'online' && invite === 'link' ? 'C’est en ligne : envoie le lien à tes invités' : undefined}
          initialPeople={step === 'online' && invite === 'link' ? parseIds(suggested) : []} />
      ) : null}

      {/* Événement de groupe : où en est l'annonce (« Prévenir le groupe », validation de l'admin du groupe, 06.11). */}
      {canManage && published && !ev.public_link && ((ev.event_groups ?? []).length || ev.visibility === 'all') ? (
        <AnnounceStatusCard eventId={ev.id} groupIds={(ev.event_groups ?? []).map((g) => g.group_id)} vip={ev.visibility === 'all'}
          announceOn={!!ev.announce_group} refreshKey={ev.updated_at} onChanged={reload} />
      ) : null}

      {ev.status === 'pending' && can('events.approve') ? (
        <Card style={{ backgroundColor: colors.lavenderDim, borderColor: '#4A3F78' }}>
          <T weight="semibold">Cette proposition attend ta validation.</T>
          <RejectProposal eventId={ev.id} onDone={(failed) => { setError(failed); reload(); }}
            extra={<Button small label="Approuver" style={{ flex: 1 }} onPress={() => run(supabase.rpc('approve_event', { e: ev.id }))} />} />
        </Card>
      ) : null}

      {/* L’action principale passe avant les détails */}
      {ev.date_mode === 'poll' ? (
        <DatePollSection
          event={ev}
          me={me.id}
          canManage={canManage && published}
          options={ev.date_options}
          votes={ev.date_options.flatMap((o) => o.date_votes)}
          names={data.names}
          undecided={canManage ? undecidedNames(ev, data.names) : []}
          onChange={reload}
        />
      ) : published && can('events.rsvp') ? (
        <RsvpCard event={ev} me={me.id} rsvps={ev.rsvps} onChange={reload} />
      ) : null}
      {mine?.status === 'yes' && ticketRelevant(ev, data.loadedAt) ? (
        <TicketCard event={ev} me={me} answerKey={`${mine.status}:${mine.waitlisted}:${mine.plus_ones}:${paymentsTick}`} />
      ) : null}

      {infoRows.length ? (
        <Card>
          {infoRows.map((r, i) => (
            <View key={r.k} style={[s.rowBetween, { alignItems: 'flex-start' }, i > 0 && st.divided]}>
              <T muted size={14}>{r.k}</T>
              <View style={{ flexShrink: 1, alignItems: 'flex-end' }}>
                <T weight="semibold" style={{ textAlign: 'right' }}>{r.v}</T>
                {r.sub ? <LinkedText text={r.sub} muted size={13} style={{ textAlign: 'right' }} /> : null}
              </View>
            </View>
          ))}
        </Card>
      ) : null}

      {ev.date_mode === 'fixed' && published ? <ParticipantsSection event={ev} me={me.id} rsvps={ev.rsvps} names={data.names} viaLink={data.viaLink} /> : null}
      {ev.date_mode === 'fixed' && published && canManage ? (
        <AttendanceEditor event={ev} rsvps={ev.rsvps} names={data.names} me={me.id} onChange={reload} />
      ) : null}
      {ev.date_mode === 'fixed' && published && canManage ? (
        <TicketsManager eventId={ev.id} enabled={!!ev.tickets_enabled} canToggle onToggled={reload}
          refreshKey={`${paymentsSeen}|${ev.rsvps.map((r) => `${r.user_id}:${r.status}:${r.waitlisted}`).join(',')}`} />
      ) : null}
      {ev.date_mode === 'fixed' && published && canManage && (ev.price_chf ?? 0) > 0 ? (
        <PendingPayments eventId={ev.id} price={ev.price_chf!} refreshKey={`${paymentsTick}|${ev.rsvps.map((r) => `${r.user_id}:${r.status}`).join(',')}`}
          onConfirmed={() => setPaymentsSeen((n) => n + 1)} />
      ) : null}

      {ev.polls
        .sort((a, b) => a.sort - b.sort)
        .map((p) => (
          <PollSection
            key={p.id}
            poll={p}
            options={p.poll_options}
            results={pollData.get(p.id)?.results ?? null}
            voters={pollData.get(p.id)?.voters ?? new Map()}
            myVotes={new Set(p.poll_options.filter((o) => data.myVotes.has(o.id)).map((o) => o.id))}
            me={me.id}
            canManage={canManage}
            canParticipate={published}
            onChange={reload}
          />
        ))}

      <BringSection items={ev.bring_items} me={me.id} eventId={ev.id} names={data.names} canParticipate={published} onChange={reload} />

      {ev.forum_enabled && published ? (
        <Pressable onPress={() => router.push(`/event/${ev.id}/chat`)} accessibilityRole="link" style={({ pressed }) => pressed && { opacity: 0.85 }}>
          <Section title="Discussion" right={<T size={13} weight="semibold" color={colors.accent}>Ouvrir ›</T>}>
            {data.messages.length === 0 ? <T muted size={14}>Aucun message. Lance la discussion !</T> : null}
            {[...data.messages].reverse().map((m) => (
              <T key={m.id} size={14} color={colors.textSoft} numberOfLines={2}>
                <T size={14} weight="bold">{data.names.get(m.user_id)} </T>
                {m.body}
                <T muted size={11}>  {formatMessageTime(m.created_at)}</T>
              </T>
            ))}
          </Section>
        </Pressable>
      ) : null}

      <T muted size={13}>Proposé par {ev.author ? personLabel(contacts, ev.author.id ?? ev.created_by, ev.author.display_name).primary || '?' : '?'}{data.muted ? ' · notifications coupées pour cet événement' : ''}</T>
      {ev.event_tags.length ? (
        <View style={s.wrap}>
          {ev.event_tags.map(({ tags: t }) => <T key={t.id} size={13} weight="semibold" color={t.color}>#{t.name}</T>)}
        </View>
      ) : null}
      {/* Apple 1.2 : titre, description et photo sont du contenu de membre ; tout le monde peut les signaler sauf l'auteur. */}
      {ev.created_by !== me.id ? (
        <Button small variant="ghost" label="Signaler cet événement" style={{ alignSelf: 'flex-start' }}
          onPress={() => setReport({ kind: 'event', id: ev.id, label: 'cet événement' })} />
      ) : null}

      <ErrorText error={error} />
      {compagnonOn && published && ev.date_mode === 'fixed' ? <EventGiftsLink eventId={ev.id} canManage={canManage} /> : null}
      {!invitesV2On && canManage && published && ev.visibility === 'invited' && step !== 'online' ? <InviteLinkCard kind="event" id={ev.id} /> : null}
      {canManage && published ? (
        <View style={st.orgZone}>
          <T muted size={12} weight="bold">ZONE ORGANISATEUR</T>
          {ev.date_mode === 'fixed' ? (
            <Button label="📷 Scanner les billets" onPress={() => router.push(`/event/${ev.id}/scan`)} />
          ) : null}
          {/* La base exige le droit de modifier pour annuler, sauf pour le créateur (campagne 2, lot A) : un co-organisateur
              « Membre » sans « Modifier » ne voit plus « Annuler l’événement ». */}
          {canEdit || ev.created_by === me.id ? <ConfirmButton
            small
            label="Annuler l’événement"
            confirmLabel="Oui, annuler"
            onConfirm={() => run(supabase.from('events').update({ status: 'cancelled' }).eq('id', ev.id)).then(() => notifyWallet(ev.id))}
          /> : null}
        </View>
      ) : null}
      {/* Droits « Scanner les billets » (tickets.scan) ou « Confirmer les paiements » (tickets.pay) sans organiser l'événement : l'entrée seulement. */}
      {!canManage && published && ev.date_mode === 'fixed' && (can('tickets.scan') || can('tickets.pay')) ? (
        <View style={st.orgZone}>
          <T muted size={12} weight="bold">ENTRÉE</T>
          <Button label="📷 Scanner les billets" onPress={() => router.push(`/event/${ev.id}/scan`)} />
        </View>
      ) : null}
      {/* Annulé : l'admin (events.manage_all) le rouvre ; son créateur ou un admin le supprime (base : 20261106200000). */}
      {ev.status === 'cancelled' && (isAdmin || ev.created_by === me.id) ? (
        <View style={st.orgZone}>
          <T muted size={12} weight="bold">ÉVÉNEMENT ANNULÉ</T>
          {isAdmin ? (
            <ConfirmButton small label="Rouvrir l’événement" confirmLabel="Oui, rouvrir"
              onConfirm={() => run(supabase.from('events').update({ status: 'published' }).eq('id', ev.id)).then(() => notifyWallet(ev.id))} />
          ) : null}
          <ConfirmButton small label="Supprimer l’événement" confirmLabel="Oui, supprimer"
            onConfirm={async () => {
              const { error: failed } = await supabase.from('events').delete().eq('id', ev.id);
              if (failed) return setError(failed.message);
              if (router.canGoBack()) router.back();
              else router.replace('/');
            }} />
        </View>
      ) : null}
      {ev.created_by === me.id && ['draft', 'pending', 'rejected'].includes(ev.status) ? (
        <ConfirmButton
          label="Supprimer la proposition"
          confirmLabel="Oui, supprimer"
          onConfirm={async () => {
            await run(supabase.from('events').delete().eq('id', ev.id));
            if (router.canGoBack()) router.back();
            else router.replace('/');
          }}
        />
      ) : null}
      </Cascade>
    </Screen>
    {shareNote === 'Lien copié' ? <Toast message="Lien copié" onHide={() => setShareNote('')} /> : null}
    <ReportSheet target={report} onClose={() => setReport(null)} />
    </>
  );
}

/** Chargement impossible : jamais une impasse ni l'anglais de la base. Supprimé / pas ouvert : pas de « Réessayer » inutile ;
 * hors ligne : « Pas de connexion », la fiche se recharge seule au retour du réseau. */
function LoadProblem({ error, online, onRetry }: { error: string | null; online: boolean; onRetry: () => void }) {
  const gone = !!error && isGoneError(error);
  const offline = !online || (!!error && isNetworkError(error));
  const text = gone ? GONE_TEXT
    : offline ? 'Pas de connexion. Vérifie ton réseau : la fiche se chargera dès qu’il revient.'
    : error ?? 'Le chargement prend plus de temps que prévu.';
  return (
    <Screen edges={[]}>
      <Stack.Screen options={{ title: 'Événement', ...(router.canGoBack() ? {} : { headerLeft: () => <HeaderBack label="Événements" onPress={() => router.replace('/')} /> }) }} />
      <ErrorText error={text} />
      {gone ? (
        <Button label="Retour aux événements" variant="secondary" onPress={() => (router.canGoBack() ? router.back() : router.replace('/'))} />
      ) : (
        <Button label="Réessayer" variant="secondary" onPress={onRetry} />
      )}
    </Screen>
  );
}

/** Fiche fantôme pendant le chargement : titre, date, lieu et carte de réponse prennent déjà leur place. */
function EventSkeleton() {
  return (
    <Screen edges={[]}>
      <View accessibilityRole="progressbar" accessibilityLabel="Chargement de l’événement…" style={{ gap: 14 }}>
        <Skeleton width={84} height={22} radius={radius.pill} />
        <Skeleton width="85%" height={32} />
        <Skeleton width="50%" height={32} />
        {[0, 1].map((i) => (
          <View key={i} style={st.keyRow}>
            <Skeleton width={40} height={40} radius={radius.sm} />
            <View style={{ flex: 1, gap: 6 }}>
              <Skeleton width="65%" height={16} />
              <Skeleton width="40%" height={12} />
            </View>
          </View>
        ))}
        <Card>
          <Skeleton width="40%" height={18} />
          <View style={s.row}>
            {[0, 1, 2].map((i) => <Skeleton key={i} height={60} radius={radius.md} style={{ flex: 1 }} />)}
          </View>
        </Card>
      </View>
    </Screen>
  );
}

const st = StyleSheet.create({
  cover: { width: '100%', aspectRatio: 16 / 9, borderRadius: radius.md, backgroundColor: colors.surface2, marginBottom: 14 },
  keyRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  // Étiquettes à gauche (au moins une catégorie), pastille à droite ; trop étroit : la pastille passe dessous.
  badges: { flexGrow: 1, flexShrink: 1, flexBasis: 0, minWidth: 110 },
  titleRow: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'flex-start', justifyContent: 'flex-end', gap: 12 },
  keyIcon: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, alignItems: 'center', justifyContent: 'center' },
  notice: { padding: 12, borderRadius: radius.md },
  divided: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 12 },
  orgZone: { padding: 12, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, borderStyle: 'dashed', gap: 8 },
});
