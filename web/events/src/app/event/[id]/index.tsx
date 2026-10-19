import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useMemo, useState } from 'react';
import { Linking, Pressable, View } from 'react-native';

import { BringSection, DatePollSection, PollSection, RsvpSection } from '@/components/EventSections';
import { Badge, Button, Card, ErrorText, Loading, Screen, s, Section, T, Title } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery, useRealtime } from '@/lib/data';
import { formatLongDay, formatMessageTime, formatShort, formatTime } from '@/lib/format';
import { must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { BringItem, Category, DateOption, DateVoteRow, EventRow, Message, Poll, PollOption, Rsvp, Tag } from '@/lib/types';

type Full = EventRow & {
  category: Category | null;
  author: { display_name: string } | null;
  event_tags: { tags: Tag }[];
  event_organizers: { user_id: string }[];
  rsvps: Rsvp[];
  date_options: (DateOption & { date_votes: DateVoteRow[] })[];
  polls: (Poll & { poll_options: PollOption[] })[];
  bring_items: BringItem[];
};

export default function EventScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const me = useMe();
  const { isAdmin } = useAuth();
  const [error, setError] = useState<string | null>(null);

  const { data, reload, error: loadError } = useQuery(async () => {
    const [ev, members, results, myVotes, allVotes, messages, mute, settings] = await Promise.all([
      supabase
        .from('events')
        .select(
          '*, category:categories(*), author:profiles!events_created_by_fkey(display_name), event_tags(tags(*)), event_organizers(user_id), rsvps(*), date_options(*, date_votes(*)), polls(*, poll_options(*)), bring_items(*)',
        )
        .eq('id', id)
        .single(),
      supabase.from('profiles').select('id, display_name'),
      supabase.from('poll_results').select('*'),
      supabase.from('poll_votes').select('poll_id, option_id').eq('user_id', me.id),
      supabase.from('poll_votes').select('option_id, user_id'),
      supabase.from('messages').select('*').eq('event_id', id).is('deleted_at', null).order('created_at', { ascending: false }).limit(2),
      supabase.from('event_mutes').select('event_id').eq('event_id', id).eq('user_id', me.id),
      supabase.from('group_settings').select('organizers_can_edit_published').single(),
    ]);
    return {
      event: must(ev) as unknown as Full,
      names: new Map(must(members).map((m) => [m.id as string, m.display_name as string])),
      results: must(results) as { poll_id: string; option_id: string; votes: number }[],
      myVotes: new Set(must(myVotes).map((v) => v.option_id as string)),
      allVotes: must(allVotes) as { option_id: string; user_id: string }[],
      messages: must(messages) as Message[],
      muted: must(mute).length > 0,
      canEditPublished: (must(settings) as { organizers_can_edit_published: boolean }).organizers_can_edit_published,
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

  if (!data || !ev) return loadError ? <Screen><ErrorText error={loadError} /></Screen> : <Loading />;

  const published = ev.status === 'published';
  const canEdit = isAdmin || (isOrganizer && (ev.status !== 'published' || data.canEditPublished));

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

  const infoRows = [
    ev.date_mode === 'fixed' && ev.starts_at
      ? { k: 'Quand', v: `${formatLongDay(ev.starts_at)}`, sub: `${formatTime(ev.starts_at)}${ev.ends_at ? ` – ${formatShort(ev.ends_at)}` : ''}` }
      : null,
    ev.location_name || ev.location_address
      ? { k: 'Où', v: ev.location_name ?? ev.location_address!, sub: ev.location_name ? ev.location_address : null, url: ev.location_url ?? (ev.location_address ? `https://maps.apple.com/?q=${encodeURIComponent(ev.location_address)}` : null) }
      : null,
    ev.price_chf != null ? { k: 'Prix', v: `${ev.price_chf} CHF / personne`, sub: ev.payment_info } : null,
    ev.max_participants ? { k: 'Places', v: `${ev.max_participants} max`, sub: ev.waitlist_enabled ? 'Liste d’attente activée' : null } : null,
    ev.rsvp_deadline ? { k: 'Réponse avant', v: formatShort(ev.rsvp_deadline) } : null,
  ].filter(Boolean) as { k: string; v: string; sub?: string | null; url?: string | null }[];

  return (
    <Screen edges={[]}>
      <Stack.Screen
        options={{
          title: '',
          headerRight: () => (
            <View style={s.row}>
              {published ? <Button small variant="ghost" label={data.muted ? 'Réactiver' : 'Sourdine'} onPress={toggleMute} /> : null}
              {canEdit ? <Button small variant="ghost" label="Modifier" onPress={() => router.push(`/event/${ev.id}/edit`)} /> : null}
            </View>
          ),
        }}
      />

      <View style={{ gap: 8 }}>
        <View style={s.wrap}>
          {ev.status === 'pending' ? <Badge label="En attente de validation" fg={colors.lavender} bg={colors.lavenderDim} /> : null}
          {ev.status === 'draft' ? <Badge label="Brouillon" fg={colors.textSoft} bg={colors.surface2} /> : null}
          {ev.status === 'rejected' ? <Badge label="Refusé" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
          {ev.status === 'cancelled' ? <Badge label="Annulé" fg={colors.coralSoft} bg={colors.coralDim} /> : null}
          {ev.date_mode === 'poll' ? <Badge label="Date à définir" fg={colors.coralSoft} bg={colors.coralDim} /> : <Badge label="Date fixée" fg={colors.accent} bg={colors.accentDim} />}
          {ev.category ? <Badge label={ev.category.name} fg={colors.onAccent} bg={ev.category.color} /> : null}
        </View>
        <Title size={32}>{ev.title}</Title>
        <T muted size={13}>Proposé par {ev.author?.display_name ?? '?'}{data.muted ? ' · notifications coupées' : ''}</T>
        {ev.event_tags.length ? (
          <View style={s.wrap}>
            {ev.event_tags.map(({ tags: t }) => <T key={t.id} size={13} weight="semibold" color={t.color}>#{t.name}</T>)}
          </View>
        ) : null}
        {ev.status === 'rejected' && ev.rejection_reason ? <T color={colors.coralSoft}>Motif : {ev.rejection_reason}</T> : null}
        {ev.description ? <T color={colors.textSoft} style={{ lineHeight: 22 }}>{ev.description}</T> : null}
      </View>

      {infoRows.length ? (
        <Card>
          {infoRows.map((r) => (
            <Pressable key={r.k} disabled={!r.url} onPress={() => r.url && Linking.openURL(r.url)} style={{ gap: 2 }}>
              <T muted size={12}>{r.k}</T>
              <T weight="semibold" color={r.url ? colors.accent : colors.text}>{r.v}</T>
              {r.sub ? <T muted size={13}>{r.sub}</T> : null}
            </Pressable>
          ))}
        </Card>
      ) : null}

      {canManage && ev.status === 'pending' && isAdmin ? (
        <Card style={{ backgroundColor: colors.lavenderDim }}>
          <T>Cette proposition attend ta validation.</T>
          <View style={s.row}>
            <Button small label="Approuver" style={{ flex: 1 }} onPress={() => run(supabase.rpc('approve_event', { e: ev.id }))} />
            <Button small variant="danger" label="Refuser" style={{ flex: 1 }} onPress={() => run(supabase.rpc('reject_event', { e: ev.id, reason: null }))} />
          </View>
        </Card>
      ) : null}

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
        <RsvpSection event={ev} me={me.id} rsvps={ev.rsvps} names={data.names} onChange={reload} />
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

      <BringSection items={ev.bring_items} me={me.id} names={data.names} canParticipate={published} onChange={reload} />

      {ev.forum_enabled && published ? (
        <Pressable onPress={() => router.push(`/event/${ev.id}/chat`)} accessibilityRole="link">
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

      <ErrorText error={error} />
      {canManage && published ? (
        <View style={{ padding: 12, borderRadius: radius.md, borderWidth: 1, borderColor: colors.line, gap: 8 }}>
          <T muted size={12}>Zone organisateur</T>
          <Button small variant="danger" label="Annuler l’événement" onPress={() => run(supabase.from('events').update({ status: 'cancelled' }).eq('id', ev.id))} />
        </View>
      ) : null}
      {ev.created_by === me.id && ['draft', 'pending', 'rejected'].includes(ev.status) ? (
        <Button
          variant="danger"
          label="Supprimer la proposition"
          onPress={async () => {
            await run(supabase.from('events').delete().eq('id', ev.id));
            router.back();
          }}
        />
      ) : null}
    </Screen>
  );
}
