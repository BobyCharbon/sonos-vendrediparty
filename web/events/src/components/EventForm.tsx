import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { useAuth, useMe } from '@/lib/auth';
import { fetchTaxonomy, useQuery } from '@/lib/data';
import { parseLocalDateTime, toLocalInput } from '@/lib/format';
import { check, must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import type { DateMode, EventRow, MemberGroup, Poll, PollOption, Reminder } from '@/lib/types';
import { UNLIMITED_PLUS_ONES } from '@/lib/types';

import { Button, Card, Chip, ErrorText, Field, Input, s, Screen, Section, Segmented, T, ToggleRow } from './ui';
import { AudiencePicker, audienceChildren, audienceError, audienceFromEvent, audienceToEvent, DEFAULT_AUDIENCE, type AudienceValue, type Person } from './AudiencePicker';
import { DateTimeField } from './DateTimeField';
import { PlaceSearch } from './PlaceSearch';

type PollDraft = {
  id?: string;
  question: string;
  options: { id?: string; label: string }[];
  multiple_choice: boolean;
  anonymous: boolean;
  members_can_add_options: boolean;
  results_after_vote: boolean;
};


type Draft = {
  title: string;
  description: string;
  category_id: string | null;
  tag_ids: string[];
  date_mode: DateMode;
  starts_at: string;
  ends_at: string;
  slots: { id?: string; text: string }[];
  poll_deadline: string;
  members_can_propose_dates: boolean;
  auto_fix_date: boolean;
  location_name: string;
  location_address: string;
  location_url: string;
  price_chf: string;
  payment_info: string;
  max_participants: string;
  waitlist_enabled: boolean;
  allow_plus_ones: boolean;
  max_plus_ones: string;
  allow_maybe: boolean;
  rsvp_deadline: string;
  who: AudienceValue;  // qui voit la sortie (AudiencePicker)
  organizers: string[];
  show_participants: boolean;
  forum_enabled: boolean;
  notify_on_publish: boolean;
  reminders: Reminder[];
  polls: PollDraft[];
  bring: { id?: string; label: string }[];
};

const emptyDraft: Draft = {
  title: '',
  description: '',
  category_id: null,
  tag_ids: [],
  date_mode: 'fixed',
  starts_at: '',
  ends_at: '',
  slots: [{ text: '' }, { text: '' }],
  poll_deadline: '',
  members_can_propose_dates: true,
  auto_fix_date: false,
  location_name: '',
  location_address: '',
  location_url: '',
  price_chf: '',
  payment_info: '',
  max_participants: '',
  waitlist_enabled: true,
  allow_plus_ones: false,
  max_plus_ones: '',
  allow_maybe: true,
  rsvp_deadline: '',
  who: DEFAULT_AUDIENCE,
  organizers: [],
  show_participants: true,
  forum_enabled: true,
  notify_on_publish: true,
  reminders: ['1d', '2h'],
  polls: [],
  bring: [],
};

const reminderLabels: Record<Reminder, string> = { '7d': 'J-7', '1d': 'J-1', '2h': 'H-2', '0h': 'Au début' };

async function loadDraft(eventId: string): Promise<Draft> {
  const res = await supabase
    .from('events')
    .select(
      '*, event_tags(tag_id), event_organizers(user_id), event_invites(user_id, via_group), event_groups(group_id), event_phone_invites(phone), date_options(id, starts_at), polls(*, poll_options(*)), bring_items(id, label, sort)',
    )
    .eq('id', eventId)
    .single();
  const e = must(res) as unknown as EventRow & {
    event_tags: { tag_id: string }[];
    event_organizers: { user_id: string }[];
    event_invites: { user_id: string; via_group: boolean }[];
    event_groups: { group_id: string }[];
    event_phone_invites: { phone: string }[];
    date_options: { id: string; starts_at: string }[];
    polls: (Poll & { poll_options: PollOption[] })[];
    bring_items: { id: string; label: string; sort: number }[];
  };
  return {
    title: e.title,
    description: e.description,
    category_id: e.category_id,
    tag_ids: e.event_tags.map((t) => t.tag_id),
    date_mode: e.date_mode,
    starts_at: toLocalInput(e.starts_at),
    ends_at: toLocalInput(e.ends_at),
    slots: e.date_options
      .sort((a, b) => a.starts_at.localeCompare(b.starts_at))
      .map((o) => ({ id: o.id, text: toLocalInput(o.starts_at) })),
    poll_deadline: toLocalInput(e.poll_deadline),
    members_can_propose_dates: e.members_can_propose_dates,
    auto_fix_date: e.auto_fix_date,
    location_name: e.location_name ?? '',
    location_address: e.location_address ?? '',
    location_url: e.location_url ?? '',
    price_chf: e.price_chf?.toString() ?? '',
    payment_info: e.payment_info ?? '',
    max_participants: e.max_participants?.toString() ?? '',
    waitlist_enabled: e.waitlist_enabled,
    allow_plus_ones: e.allow_plus_ones,
    max_plus_ones: e.max_plus_ones >= UNLIMITED_PLUS_ONES ? '' : e.max_plus_ones.toString(),
    allow_maybe: e.allow_maybe,
    rsvp_deadline: toLocalInput(e.rsvp_deadline),
    who: audienceFromEvent(e),
    organizers: e.event_organizers.map((o) => o.user_id),
    show_participants: e.show_participants,
    forum_enabled: e.forum_enabled,
    notify_on_publish: e.notify_on_publish,
    reminders: e.reminders,
    polls: e.polls
      .sort((a, b) => a.sort - b.sort)
      .map((p) => ({
        id: p.id,
        question: p.question,
        options: p.poll_options.sort((a, b) => a.sort - b.sort).map((o) => ({ id: o.id, label: o.label })),
        multiple_choice: p.multiple_choice,
        anonymous: p.anonymous,
        members_can_add_options: p.members_can_add_options,
        results_after_vote: p.results_after_vote,
      })),
    bring: e.bring_items.sort((a, b) => a.sort - b.sort).map((b) => ({ id: b.id, label: b.label })),
  };
}

export function EventForm({ eventId }: { eventId?: string }) {
  const me = useMe();
  const { can } = useAuth();
  const isAdmin = can('events.publish_direct');  // publie sans passer par la validation
  const [draft, setDraft] = useState<Draft | null>(eventId ? null : emptyDraft);
  const savedEventId = useRef(eventId);
  const saving = useRef(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newTag, setNewTag] = useState('');

  const { data: ctx, error: contextError, reload: reloadCtx } = useQuery(async () => {
    const [taxonomy, members, groups, settings, current] = await Promise.all([
      fetchTaxonomy(),
      supabase.from('profiles').select('id, display_name, role').eq('status', 'active').order('display_name'),
      supabase.from('member_groups').select('id, name, created_by, system_key, member_group_members(user_id)').order('name'),
      supabase.from('group_settings').select('require_approval').single(),
      eventId ? supabase.from('events').select('status').eq('id', eventId).single() : Promise.resolve(null),
    ]);
    if (eventId && !draft) {
      const loaded = await loadDraft(eventId);
      setDraft(loaded);
    }
    return {
      ...taxonomy,
      members: must(members) as Person[],
      groups: must(groups) as MemberGroup[],
      settings: must(settings) as { require_approval: boolean },
      status: current ? (must(current) as { status: EventRow['status'] }).status : null,
    };
  }, [eventId]);

  if (!draft || !ctx) return (
    <Screen edges={[]}>
      {contextError ? (
        <>
          <ErrorText error={contextError} />
          <Button label="Réessayer" onPress={reloadCtx} />
        </>
      ) : <T muted>Chargement de l’événement…</T>}
    </Screen>
  );

  const d = draft;
  const set = (patch: Partial<Draft>) => setDraft({ ...d, ...patch });
  const toggleIn = <K extends 'tag_ids' | 'organizers' | 'reminders'>(key: K, v: Draft[K][number]) => {
    const list = d[key] as string[];
    set({ [key]: list.includes(v) ? list.filter((x) => x !== v) : [...list, v] } as Partial<Draft>);
  };
  const setPoll = (i: number, patch: Partial<PollDraft>) => set({ polls: d.polls.map((p, j) => (j === i ? { ...p, ...patch } : p)) });

  async function createTag() {
    const name = newTag.trim().replace(/^#/, '').toLowerCase();
    if (!name) return;
    const { data, error } = await supabase.from('tags').insert({ name, created_by: me.id }).select('id').single();
    if (error) return setError(error.message.includes('duplicate') ? 'Ce tag existe déjà' : error.message);
    setNewTag('');
    await reloadCtx();
    set({ tag_ids: [...d.tag_ids, data.id] });
  }

  function validate(): { row: Record<string, unknown>; slots: { id?: string; iso: string }[] } | string {
    if (!d.title.trim()) return 'Il manque un titre';
    const errors: string[] = [];
    const date = (v: string, label: string, required = false): string | null => {
      if (!v.trim()) {
        if (required) errors.push(`${label} : obligatoire`);
        return null;
      }
      const iso = parseLocalDateTime(v);
      if (!iso) errors.push(`${label} : format attendu JJ.MM.AAAA HH:MM`);
      return iso;
    };
    const starts = d.date_mode === 'fixed' ? date(d.starts_at, 'Début', true) : null;
    const ends = d.date_mode === 'fixed' ? date(d.ends_at, 'Fin') : null;
    const deadline = d.date_mode === 'poll' ? date(d.poll_deadline, 'Fin du vote') : null;
    const rsvpDeadline = date(d.rsvp_deadline, 'Date limite de réponse');
    if (errors.length) return errors[0]!;
    if (starts && ends && ends <= starts) return 'La fin doit être après le début';
    if (starts && ends && ends < starts) return 'La fin est avant le début';

    const slots: { id?: string; iso: string }[] = [];
    if (d.date_mode === 'poll') {
      for (const sl of d.slots.filter((x) => x.text.trim())) {
        const iso = parseLocalDateTime(sl.text);
        if (!iso) return `Créneau « ${sl.text} » : format attendu JJ.MM.AAAA HH:MM`;
        slots.push({ id: sl.id, iso });
      }
      if (slots.length < 2 && !d.members_can_propose_dates) return 'Propose au moins deux créneaux';
    }
    const num = (v: string) => (v.trim() ? Number(v.replace(',', '.')) : null);
    const max = num(d.max_participants);
    if (max !== null && (!Number.isInteger(max) || max < 1)) return 'Nombre de places invalide';
    const price = num(d.price_chf);
    if (price !== null && (!Number.isFinite(price) || price < 0)) return 'Le prix doit être un montant positif ou zéro';
    if (d.location_url.trim()) {
      try {
        const url = new URL(d.location_url.trim());
        if (!['https:', 'http:'].includes(url.protocol)) return 'Le lien doit commencer par https:// ou http://';
      } catch {
        return 'Le lien doit être une adresse complète (ex. https://…)';
      }
    }
    const audienceProblem = audienceError(d.who);
    if (audienceProblem) return audienceProblem;
    for (const p of d.polls) {
      if (!p.question.trim()) return 'Un sondage n’a pas de question';
      if (p.options.filter((o) => o.label.trim()).length < 2 && !p.members_can_add_options) return `« ${p.question} » : au moins deux options`;
    }

    return {
      slots,
      row: {
        title: d.title.trim(),
        description: d.description.trim(),
        category_id: d.category_id,
        date_mode: d.date_mode,
        starts_at: d.date_mode === 'fixed' ? starts : null,
        ends_at: d.date_mode === 'fixed' ? ends : null,
        poll_deadline: deadline,
        members_can_propose_dates: d.members_can_propose_dates,
        auto_fix_date: d.auto_fix_date,
        location_name: d.location_name.trim() || null,
        location_address: d.location_address.trim() || null,
        location_url: d.location_url.trim() || null,
        price_chf: price,
        payment_info: d.payment_info.trim() || null,
        max_participants: max,
        waitlist_enabled: d.waitlist_enabled,
        allow_plus_ones: d.allow_plus_ones,
        max_plus_ones: d.max_plus_ones.trim() ? Math.max(1, Math.min(UNLIMITED_PLUS_ONES - 1, Number(d.max_plus_ones) || 1)) : UNLIMITED_PLUS_ONES,
        allow_maybe: d.allow_maybe,
        rsvp_deadline: rsvpDeadline,
        ...audienceToEvent(d.who),
        show_participants: d.show_participants,
        forum_enabled: d.forum_enabled,
        notify_on_publish: d.notify_on_publish,
        reminders: d.reminders,
      },
    };
  }

  async function syncChildren(id: string, slots: { id?: string; iso: string }[], snapshot: Draft, prev: Draft | null) {
    const d = snapshot;
    // Tags, organisateurs, invités : on remplace l'ensemble
    const replace = async (table: string, col: string, values: string[]) => {
      check(await supabase.from(table).delete().eq('event_id', id));
      if (values.length) check(await supabase.from(table).insert(values.map((v) => ({ event_id: id, [col]: v }))));
    };
    await replace('event_tags', 'tag_id', d.tag_ids);
    await replace('event_organizers', 'user_id', d.organizers.filter((u) => u !== me.id));
    // Invités : la base recopie les membres des groupes (via_group) ; ici seulement les groupes et les invités cochés un par un.
    const who = audienceChildren(d.who);
    const groupIds = who.group_ids;
    const staleGroups = supabase.from('event_groups').delete().eq('event_id', id);
    check(await (groupIds.length ? staleGroups.not('group_id', 'in', `(${groupIds.join(',')})`) : staleGroups));
    if (groupIds.length) {
      check(await supabase.from('event_groups').upsert(groupIds.map((group_id) => ({ event_id: id, group_id })), { ignoreDuplicates: true }));
    }
    check(await supabase.from('event_invites').delete().eq('event_id', id).eq('via_group', false));
    if (who.invitees.length) {
      check(await supabase.from('event_invites').upsert(who.invitees.map((user_id) => ({ event_id: id, user_id })), { ignoreDuplicates: true }));
    }
    // Numéros : on ne retire que ceux enlevés (pas de seconde invitation pour ceux déjà invités).
    const stalePhones = supabase.from('event_phone_invites').delete().eq('event_id', id);
    check(await (who.phones.length ? stalePhones.not('phone', 'in', `(${who.phones.join(',')})`) : stalePhones));
    if (who.phones.length) {
      check(await supabase.from('event_phone_invites').upsert(who.phones.map((phone) => ({ event_id: id, phone })), { ignoreDuplicates: true }));
    }

    // Créneaux : on garde les votes des créneaux existants
    if (d.date_mode === 'poll') {
      const keep = new Set(slots.filter((x) => x.id).map((x) => x.id!));
      const removed = (prev?.slots ?? []).filter((x) => x.id && !keep.has(x.id)).map((x) => x.id!);
      if (removed.length) check(await supabase.from('date_options').delete().in('id', removed));
      for (const sl of slots.filter((x) => x.id)) check(await supabase.from('date_options').update({ starts_at: sl.iso }).eq('id', sl.id!));
      const nonEmptySlots = d.slots.filter((sl) => sl.text.trim());
      for (const [index, sl] of slots.entries()) {
        if (sl.id) continue;
        const created = must(await supabase.from('date_options').insert({ event_id: id, starts_at: sl.iso, proposed_by: me.id }).select('id').single());
        nonEmptySlots[index]!.id = created.id as string;
      }
    } else {
      check(await supabase.from('date_options').delete().eq('event_id', id));
      d.slots = d.slots.map((sl) => ({ text: sl.text }));
    }

    // Sondages : suppression des retirés, ajout des nouveaux (les existants gardent leurs votes)
    const keptPolls = new Set(d.polls.filter((p) => p.id).map((p) => p.id!));
    const removedPolls = (prev?.polls ?? []).filter((p) => p.id && !keptPolls.has(p.id)).map((p) => p.id!);
    if (removedPolls.length) check(await supabase.from('polls').delete().in('id', removedPolls));
    for (const [i, p] of d.polls.entries()) {
      const row = {
        question: p.question.trim(), multiple_choice: p.multiple_choice, anonymous: p.anonymous,
        members_can_add_options: p.members_can_add_options, results_after_vote: p.results_after_vote, sort: i,
      };
      let pollId = p.id;
      if (pollId) {
        check(await supabase.from('polls').update(row).eq('id', pollId).eq('event_id', id));
        const previous = prev?.polls.find((poll) => poll.id === pollId);
        const keptOptions = new Set(p.options.filter((o) => o.label.trim()).map((o) => o.id));
        const removedOptions = (previous?.options ?? []).filter((o) => o.id && !keptOptions.has(o.id)).map((o) => o.id!);
        if (removedOptions.length) check(await supabase.from('poll_options').delete().eq('poll_id', pollId).in('id', removedOptions));
      } else {
        pollId = must(await supabase.from('polls').insert({ ...row, event_id: id, created_by: me.id }).select('id').single()).id as string;
        p.id = pollId;
      }
      for (const [sort, option] of p.options.filter((o) => o.label.trim()).entries()) {
        if (option.id) {
          check(await supabase.from('poll_options').update({ label: option.label.trim(), sort }).eq('id', option.id).eq('poll_id', pollId));
        } else {
          const created = must(await supabase.from('poll_options').insert({ poll_id: pollId, label: option.label.trim(), created_by: me.id, sort }).select('id').single());
          option.id = created.id as string;
        }
      }
    }

    // Qui amène quoi
    const keptItems = new Set(d.bring.filter((b) => b.id).map((b) => b.id!));
    const removedItems = (prev?.bring ?? []).filter((b) => b.id && !keptItems.has(b.id)).map((b) => b.id!);
    if (removedItems.length) check(await supabase.from('bring_items').delete().in('id', removedItems));
    for (const [sort, item] of d.bring.entries()) {
      if (item.id) check(await supabase.from('bring_items').update({ label: item.label.trim(), sort }).eq('id', item.id).eq('event_id', id));
    }
    for (const [sort, item] of d.bring.entries()) {
      if (item.id || !item.label.trim()) continue;
      const created = must(await supabase.from('bring_items').insert({ event_id: id, label: item.label.trim(), sort }).select('id').single());
      item.id = created.id as string;
    }
  }

  async function submit(asDraft: boolean) {
    if (saving.current) return;
    setError(null);
    const v = validate();
    if (typeof v === 'string') return setError(v);
    saving.current = true;
    setBusy(true);
    // Travailler sur une copie : conserver les identifiants reçus même en cas d'échec partiel.
    const snapshot = JSON.parse(JSON.stringify(d)) as Draft;
    try {
      let id = savedEventId.current;
      const previous = id ? await loadDraft(id) : null;
      if (!id) {
        // Créé en brouillon pour attacher tags/sondages AVANT la publication (et donc les notifications).
        id = must(await supabase.from('events').insert({ ...v.row, status: 'draft' }).select('id').single()).id as string;
        savedEventId.current = id;
      } else {
        check(await supabase.from('events').update(v.row).eq('id', id));
      }
      await syncChildren(id, v.slots, snapshot, previous);
      const status = ctx!.status;
      const needsSubmit = !eventId || status === 'draft' || status === 'rejected';
      if (needsSubmit && !asDraft) {
        check(await supabase.from('events').update({ status: isAdmin ? 'published' : 'pending' }).eq('id', id));
      }
      router.replace(`/event/${id}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setDraft(snapshot);
      saving.current = false;
      setBusy(false);
    }
  }

  const memberChips = (key: 'organizers') => (
    <View style={s.wrap}>
      {ctx.members
        .filter((m) => m.id !== me.id && m.role !== 'guest')  // co-organisateurs : membres seulement
        .map((m) => (
          <Chip key={m.id} label={m.display_name} selected={d[key].includes(m.id)} onPress={() => toggleIn(key, m.id)} />
        ))}
    </View>
  );

  const submitLabel = eventId && ctx.status === 'published'
    ? 'Enregistrer'
    : isAdmin || !ctx.settings.require_approval ? 'Publier' : 'Envoyer pour validation';

  return (
    <Screen edges={[]}>
      <View pointerEvents={busy ? 'none' : 'auto'} style={{ gap: 14 }}>
      <Card>
        <Field label="Titre" value={d.title} onChangeText={(title) => set({ title })} maxLength={120} placeholder="Karting, soirée raclette…" />
        <Field label="Description" value={d.description} onChangeText={(description) => set({ description })} multiline />
        <T muted size={13}>Catégorie</T>
        <View style={s.wrap}>
          {ctx.categories.map((c) => (
            <Chip
              key={c.id}
              label={c.name}
              color={c.color}
              selected={d.category_id === c.id}
              onPress={() => set({ category_id: d.category_id === c.id ? null : c.id })}
            />
          ))}
        </View>
        <T muted size={13}>Tags</T>
        <View style={s.wrap}>
          {ctx.tags.map((t) => (
            <Chip key={t.id} label={`#${t.name}`} color={t.color} selected={d.tag_ids.includes(t.id)} onPress={() => toggleIn('tag_ids', t.id)} />
          ))}
        </View>
        {can('taxonomy.manage') ? (
          <View style={s.row}>
            <Input placeholder="Nouveau tag" value={newTag} onChangeText={setNewTag} style={{ flex: 1 }} onSubmitEditing={createTag} />
            <Button small variant="secondary" label="Créer" onPress={createTag} disabled={!newTag.trim()} />
          </View>
        ) : null}
      </Card>

      <Section title="Date">
        <Segmented<DateMode>
          value={d.date_mode}
          onChange={(date_mode) => set({ date_mode })}
          options={[{ key: 'fixed', label: 'Date fixée' }, { key: 'poll', label: 'Date à définir' }]}
        />
        {d.date_mode === 'fixed' ? (
          <>
            <DateTimeField label="Début" value={d.starts_at} onChangeText={(starts_at) => set({ starts_at })} />
            <DateTimeField label="Fin (optionnel)" optional min={d.starts_at} value={d.ends_at} onChangeText={(ends_at) => set({ ends_at })} />
          </>
        ) : (
          <>
            <T muted size={12}>Chacun vote Oui / Si besoin / Non sur chaque créneau.</T>
            {d.slots.map((sl, i) => (
              <View key={sl.id ?? `new-${i}`} style={s.row}>
                <View style={{ flex: 1 }}>
                  <DateTimeField label={`Créneau ${i + 1}`} value={sl.text} onChangeText={(text) => set({ slots: d.slots.map((x, j) => (j === i ? { ...x, text } : x)) })} />
                </View>
                <Button small variant="secondary" label="✕" onPress={() => set({ slots: d.slots.filter((_, j) => j !== i) })} />
              </View>
            ))}
            <Button small variant="ghost" label="+ Ajouter un créneau" onPress={() => set({ slots: [...d.slots, { text: '' }] })} />
            <DateTimeField label="Fin du vote (optionnel)" optional value={d.poll_deadline} onChangeText={(poll_deadline) => set({ poll_deadline })} />
            <ToggleRow label="Les membres peuvent proposer des dates" value={d.members_can_propose_dates} onChange={(v) => set({ members_can_propose_dates: v })} />
            <ToggleRow
              label="Fixer la date automatiquement"
              hint="À la fin du vote, la date avec le plus de Oui est retenue"
              value={d.auto_fix_date}
              onChange={(v) => set({ auto_fix_date: v })}
            />
          </>
        )}
      </Section>

      <Section title="Lieu et prix">
        <PlaceSearch onPick={(p) => set({ location_name: p.name, location_address: p.address, location_url: p.url })} />
        <Field label="Lieu" placeholder="Chez Marco" value={d.location_name} onChangeText={(location_name) => set({ location_name })} />
        <Field label="Adresse" value={d.location_address} onChangeText={(location_address) => set({ location_address })} />
        <Field label="Lien (site, carte…)" autoCapitalize="none" keyboardType="url" value={d.location_url} onChangeText={(location_url) => set({ location_url })} />
        <View style={s.row}>
          <View style={{ flex: 1 }}>
            <Field label="Prix / pers. (CHF)" keyboardType="decimal-pad" value={d.price_chf} onChangeText={(price_chf) => set({ price_chf })} />
          </View>
          <View style={{ flex: 1 }}>
            <Field label="Paiement" placeholder="TWINT, sur place" value={d.payment_info} onChangeText={(payment_info) => set({ payment_info })} />
          </View>
        </View>
      </Section>

      <Section title="Participants">
        <Field
          label="Nombre de places (vide = illimité)"
          keyboardType="number-pad"
          value={d.max_participants}
          onChangeText={(max_participants) => set({ max_participants })}
        />
        {d.max_participants ? (
          <ToggleRow label="Liste d’attente" hint="Les suivants passent automatiquement quand une place se libère" value={d.waitlist_enabled} onChange={(v) => set({ waitlist_enabled: v })} />
        ) : null}
        <ToggleRow label="Réponse « Peut-être » autorisée" value={d.allow_maybe} onChange={(v) => set({ allow_maybe: v })} />
        <ToggleRow label="Accompagnants (+1)" value={d.allow_plus_ones} onChange={(v) => set({ allow_plus_ones: v })} />
        {d.allow_plus_ones ? (
          <Field label="Accompagnants max par personne (vide = illimité)" keyboardType="number-pad" value={d.max_plus_ones} onChangeText={(max_plus_ones) => set({ max_plus_ones })} />
        ) : null}
        <DateTimeField label="Date limite de réponse (optionnel)" optional value={d.rsvp_deadline} onChangeText={(rsvp_deadline) => set({ rsvp_deadline })} />
        <ToggleRow label="Liste des participants visible" value={d.show_participants} onChange={(v) => set({ show_participants: v })} />
        <AudiencePicker value={d.who} onChange={(who) => set({ who })} groups={ctx.groups} people={ctx.members} meId={me.id} allGroups={can('events.manage_all')} />
        <Button small variant="ghost" label="Gérer les groupes ›" onPress={() => router.push('/groups')} />
        <T muted size={13}>Co-organisateurs</T>
        {memberChips('organizers')}
      </Section>

      <Section title="Mini-sondages">
        {d.polls.map((p, i) => (
          <View key={p.id ?? `new-${i}`} style={{ gap: 12, paddingVertical: 12, borderTopWidth: i ? 1 : 0, borderTopColor: colors.line }}>
            <Field label={`Question du sondage ${i + 1}`} value={p.question} onChangeText={(question) => setPoll(i, { question })} maxLength={200} />
            {p.options.map((o, j) => (
              <View key={o.id ?? `new-${j}`} style={s.row}>
                <Input
                  accessibilityLabel={`Sondage ${i + 1}, option ${j + 1}`}
                  placeholder={`Option ${j + 1}`}
                  value={o.label}
                  onChangeText={(label) => setPoll(i, { options: p.options.map((x, k) => (k === j ? { ...x, label } : x)) })}
                  maxLength={120}
                  style={{ flex: 1 }}
                />
                <Button small variant="ghost" label="Retirer" onPress={() => setPoll(i, { options: p.options.filter((_, k) => k !== j) })} />
              </View>
            ))}
            {p.id ? <T muted size={13}>Les votes des options conservées restent enregistrés. Retirer une option supprime ses votes.</T> : null}
            <Button small variant="ghost" label="+ Ajouter une option" onPress={() => setPoll(i, { options: [...p.options, { label: '' }] })} />
            <View style={s.wrap}>
              <Chip label="Choix multiple" selected={p.multiple_choice} onPress={() => setPoll(i, { multiple_choice: !p.multiple_choice })} />
              <Chip label="Anonyme" selected={p.anonymous} onPress={() => setPoll(i, { anonymous: !p.anonymous })} />
              <Chip label="Options libres" selected={p.members_can_add_options} onPress={() => setPoll(i, { members_can_add_options: !p.members_can_add_options })} />
              <Chip label="Résultats après vote" selected={p.results_after_vote} onPress={() => setPoll(i, { results_after_vote: !p.results_after_vote })} />
            </View>
            <Button small variant="danger" label="Retirer ce sondage" onPress={() => set({ polls: d.polls.filter((_, j) => j !== i) })} />
          </View>
        ))}
        <Button
          small
          variant="ghost"
          label="+ Ajouter un sondage"
          onPress={() =>
            set({
              polls: [...d.polls, { question: '', options: [{ label: '' }, { label: '' }], multiple_choice: false, anonymous: false, members_can_add_options: false, results_after_vote: false }],
            })
          }
        />
      </Section>

      <Section title="Qui amène quoi">
        {d.bring.map((b, i) => (
          <View key={b.id ?? `new-${i}`} style={s.row}>
            <Input
              placeholder="Fromage, pain…"
              value={b.label}
              onChangeText={(label) => set({ bring: d.bring.map((x, j) => (j === i ? { ...x, label } : x)) })}
              style={{ flex: 1 }}
            />
            <Button small variant="secondary" label="✕" onPress={() => set({ bring: d.bring.filter((_, j) => j !== i) })} />
          </View>
        ))}
        <Button small variant="ghost" label="+ Ajouter un objet" onPress={() => set({ bring: [...d.bring, { label: '' }] })} />
      </Section>

      <Section title="Discussion et notifications">
        <ToggleRow label="Forum de l’événement" value={d.forum_enabled} onChange={(v) => set({ forum_enabled: v })} />
        <ToggleRow label="Prévenir le groupe à la publication" value={d.notify_on_publish} onChange={(v) => set({ notify_on_publish: v })} />
        <T muted size={13}>Rappels automatiques aux participants</T>
        <View style={s.wrap}>
          {(Object.keys(reminderLabels) as Reminder[]).map((r) => (
            <Chip key={r} label={reminderLabels[r]} selected={d.reminders.includes(r)} onPress={() => toggleIn('reminders', r)} />
          ))}
        </View>
      </Section>

      {!isAdmin && ctx.settings.require_approval && (!eventId || ctx.status !== 'published') ? (
        <View style={{ backgroundColor: colors.lavenderDim, padding: 14, borderRadius: 16 }}>
          <T size={13} color={colors.textSoft}>
            Un admin doit valider ta proposition. Il pourra modifier n’importe quel champ avant de la publier.
          </T>
        </View>
      ) : null}
      <ErrorText error={error} />
      <Button label={submitLabel} onPress={() => submit(false)} loading={busy} />
      {!eventId || ctx.status === 'draft' ? (
        <Button label="Enregistrer en brouillon" variant="secondary" onPress={() => submit(true)} disabled={busy} />
      ) : null}
      </View>
    </Screen>
  );
}
