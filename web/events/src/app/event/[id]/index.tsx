import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Linking, Pressable, StyleSheet, View } from 'react-native';

import { CalendarButton } from '@/components/CalendarButton';
import { BringSection, DatePollSection, ParticipantsSection, PollSection, RsvpCard } from '@/components/EventSections';
import { Badge, Button, Card, ConfirmButton, ErrorText, Loading, Screen, s, Section, T, Title } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery, useRealtime } from '@/lib/data';
import { formatLongDay, formatMessageTime, formatShort, formatTime, plural, relativeDay } from '@/lib/format';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { BringItem, Category, DateOption, DateVoteRow, EventRow, Message, Poll, PollOption, Rsvp, Tag } from '@/lib/types';
import { plusOnesLabel } from '@/lib/types';

type Full = EventRow & {
  category: Category | null;
  author: { display_name: string } | null;
  event_tags: { tags: Tag }[];
  event_organizers: { user_id: string }[];
  rsvps: Rsvp[];
  date_options: (DateOption & { date_votes: DateVoteRow[] })[];
  polls: (Poll & { poll_options: PollOption[] })[];
  bring_items: BringItem[];
  event_groups: { member_groups: { name: string } | null }[];
};

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
  const { id } = useLocalSearchParams<{ id: string }>();
  const me = useMe();
  const { can } = useAuth();
  const isAdmin = can('events.manage_all');
  const [error, setError] = useState<string | null>(null);
  const [shareNote, setShareNote] = useState('');

  const { data, reload, error: loadError } = useQuery(async () => {
    const [ev, members, results, myVotes, allVotes, messages, mute] = await Promise.all([
      supabase
        .from('events')
        .select(
          '*, category:categories(*), author:profiles!events_created_by_fkey(display_name), event_tags(tags(*)), event_organizers(user_id), rsvps(*), date_options(*, date_votes(*)), polls(*, poll_options(*)), bring_items(*), event_groups(member_groups(name))',
        )
        .eq('id', id)
        .single(),
      supabase.from('profiles').select('id, display_name'),
      supabase.from('poll_results').select('*'),
      supabase.from('poll_votes').select('poll_id, option_id').eq('user_id', me.id),
      supabase.from('poll_votes').select('option_id, user_id'),
      supabase.from('messages').select('*').eq('event_id', id).is('deleted_at', null).order('created_at', { ascending: false }).limit(2),
      supabase.from('event_mutes').select('event_id').eq('event_id', id).eq('user_id', me.id),
    ]);
    return {
      event: must(ev) as unknown as Full,
      names: new Map(must(members).map((m) => [m.id as string, m.display_name as string])),
      results: must(results) as { poll_id: string; option_id: string; votes: number }[],
      myVotes: new Set(must(myVotes).map((v) => v.option_id as string)),
      allVotes: must(allVotes) as { option_id: string; user_id: string }[],
      messages: must(messages) as Message[],
      muted: must(mute).length > 0,
    };
  }, [id, me.id]);

  useRealtime(`event-${id}`, [
    { table: 'rsvps', filter: `event_id=eq.${id}` },
    { table: 'date_votes' },
    { table: 'poll_votes' },
    { table: 'messages', filter: `event_id=eq.${id}` },
  ], reload);

  const ev = data?.event;
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

  if (!data || !ev) return loadError ? <Screen edges={[]}><ErrorText error={loadError} /></Screen> : <Loading />;

  const published = ev.status === 'published';
  const canEdit = isAdmin || (isOrganizer && (ev.status !== 'published' || can('events.edit_own_published')));

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

  const heads = ev.rsvps.filter((r) => r.status === 'yes' && !r.waitlisted).reduce((n, r) => n + 1 + r.plus_ones, 0);
  const mapsUrl = ev.location_url ?? (ev.location_address || ev.location_name ? `https://maps.apple.com/?q=${encodeURIComponent(ev.location_address ?? ev.location_name!)}` : null);
  const mine = ev.rsvps.find((r) => r.user_id === me.id);
  const showCalendar = published && ev.date_mode === 'fixed' && !!ev.starts_at && mine?.status !== 'no';

  const infoRows = [
    ev.price_chf != null ? { k: 'Prix', v: ev.price_chf === 0 ? 'Gratuit' : `${ev.price_chf} CHF / personne`, sub: ev.payment_info } : null,
    ev.max_participants
      ? { k: 'Places', v: `${heads} / ${ev.max_participants}`, sub: heads >= ev.max_participants ? (ev.waitlist_enabled ? 'Complet · liste d’attente ouverte' : 'Complet') : plural(ev.max_participants - heads, 'place libre', 'places libres') }
      : ev.date_mode === 'fixed' ? { k: 'Places', v: '∞ Illimité', sub: plural(heads, 'personne inscrite', 'personnes inscrites') } : null,
    ev.date_mode === 'fixed' && ev.allow_plus_ones && ev.max_plus_ones > 0 ? { k: 'Accompagnants', v: plusOnesLabel(ev.max_plus_ones) } : null,
    ev.rsvp_deadline ? { k: 'Réponse avant', v: formatShort(ev.rsvp_deadline) } : null,
  ].filter(Boolean) as { k: string; v: string; sub?: string | null }[];

  return (
    <Screen edges={[]}>
      <Stack.Screen
        options={{
          title: '',
          headerLeft: router.canGoBack()
            ? undefined
            : () => <Button small variant="ghost" label="‹ Événements" onPress={() => router.replace('/')} />,
          headerRight: () => (
            <View style={s.row}>
              {published ? <Button small variant="ghost" label={data.muted ? '🔕 Réactiver' : '🔔 Sourdine'} onPress={toggleMute} /> : null}
              {canEdit ? <Button small variant="secondary" label="Modifier" onPress={() => router.push(`/event/${ev.id}/edit`)} /> : null}
            </View>
          ),
        }}
      />

      {/* En-tête : l’essentiel en un coup d’œil */}
      <View style={{ gap: 10 }}>
        <View style={s.wrap}>
          {ev.status === 'pending' ? <Badge label="En attente de validation" fg={colors.lavender} bg={colors.lavenderDim} /> : null}
          {ev.status === 'draft' ? <Badge label="Brouillon" fg={colors.textSoft} bg={colors.surface2} /> : null}
          {ev.status === 'rejected' ? <Badge label="Refusé" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
          {ev.status === 'cancelled' ? <Badge label="Annulé" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
          {ev.date_mode === 'poll' ? <Badge label="Date à définir" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
          {ev.category ? <Badge label={ev.category.name} fg={colors.onAccent} bg={ev.category.color} /> : null}
        </View>
        <Title size={32} style={{ lineHeight: 36 }}>{ev.title}</Title>
        {ev.visibility === 'invited' ? (
          <T muted size={13}>
            🔒 Événement privé, sur invitation{ev.event_groups.length ? ` · ${ev.event_groups.map((g) => g.member_groups?.name).filter(Boolean).join(', ')}` : ''}
          </T>
        ) : null}
        {ev.public_link && published ? (
          <View style={s.row}>
            <T muted size={13} style={{ flex: 1 }}>🔗 Ouvert à toute personne qui a le lien{shareNote ? ` · ${shareNote}` : ''}</T>
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

        {showCalendar ? <CalendarButton event={ev} prominent={mine?.status === 'yes' || mine?.status === 'maybe'} /> : null}

        {ev.status === 'cancelled' ? (
          <View style={[st.notice, { backgroundColor: colors.coralDim }]}>
            <T color={colors.coralSoft} weight="semibold">Cet événement a été annulé.</T>
          </View>
        ) : null}
        {ev.status === 'rejected' && ev.rejection_reason ? <T color={colors.coralSoft}>Motif du refus : {ev.rejection_reason}</T> : null}
      </View>

      {ev.status === 'pending' && can('events.approve') ? (
        <Card style={{ backgroundColor: colors.lavenderDim, borderColor: '#4A3F78' }}>
          <T weight="semibold">Cette proposition attend ta validation.</T>
          <View style={s.row}>
            <Button small label="Approuver" style={{ flex: 1 }} onPress={() => run(supabase.rpc('approve_event', { e: ev.id }))} />
            <Button small variant="danger" label="Refuser" style={{ flex: 1 }} onPress={() => run(supabase.rpc('reject_event', { e: ev.id, reason: null }))} />
          </View>
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
          onChange={reload}
        />
      ) : published ? (
        <RsvpCard event={ev} me={me.id} rsvps={ev.rsvps} onChange={reload} />
      ) : null}

      {ev.description ? (
        <Section title="À propos">
          <T color={colors.textSoft} style={{ lineHeight: 22 }}>{ev.description}</T>
        </Section>
      ) : null}

      {infoRows.length ? (
        <Card>
          {infoRows.map((r, i) => (
            <View key={r.k} style={[s.rowBetween, { alignItems: 'flex-start' }, i > 0 && st.divided]}>
              <T muted size={14}>{r.k}</T>
              <View style={{ flexShrink: 1, alignItems: 'flex-end' }}>
                <T weight="semibold" style={{ textAlign: 'right' }}>{r.v}</T>
                {r.sub ? <T muted size={13} style={{ textAlign: 'right' }}>{r.sub}</T> : null}
              </View>
            </View>
          ))}
        </Card>
      ) : null}

      {ev.date_mode === 'fixed' && published ? <ParticipantsSection event={ev} me={me.id} rsvps={ev.rsvps} names={data.names} /> : null}

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

      <BringSection items={ev.bring_items} me={me.id} names={data.names} canParticipate={published} onChange={reload} />

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

      <T muted size={13}>Proposé par {ev.author?.display_name ?? '?'}{data.muted ? ' · notifications coupées pour cette sortie' : ''}</T>
      {ev.event_tags.length ? (
        <View style={s.wrap}>
          {ev.event_tags.map(({ tags: t }) => <T key={t.id} size={13} weight="semibold" color={t.color}>#{t.name}</T>)}
        </View>
      ) : null}

      <ErrorText error={error} />
      {canManage && published ? (
        <View style={st.orgZone}>
          <T muted size={12} weight="bold">ZONE ORGANISATEUR</T>
          <ConfirmButton
            small
            label="Annuler l’événement"
            confirmLabel="Oui, annuler"
            onConfirm={() => run(supabase.from('events').update({ status: 'cancelled' }).eq('id', ev.id))}
          />
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
    </Screen>
  );
}

const st = StyleSheet.create({
  keyRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  keyIcon: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, alignItems: 'center', justifyContent: 'center' },
  notice: { padding: 12, borderRadius: radius.md },
  divided: { borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 12 },
  orgZone: { padding: 12, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, borderStyle: 'dashed', gap: 8 },
});
