import { router, Stack } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { AIEventSteps } from './AIEventSteps';
import { AudiencePicker, audienceError, audienceFromEvent, audienceToEvent, saveAudience, type AudienceValue, type Person } from './AudiencePicker';
import { InviteSheet } from './InviteSheet';
import { Button, Card, ErrorText, HeaderBack, Loading, Screen, T, Title } from './ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { invitesV2On } from '@/lib/features';
import { fetchGuestList, ruleSentence } from '@/lib/invites';
import { dbMessage } from '@/lib/moderation';
import { check, must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { EventRow, MemberGroup } from '@/lib/types';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_SUGGESTED = 50;

/** « ?suggested=id1,id2 » (personnes citées à l'IA) → identifiants sûrs, jamais autre chose. */
export function parseSuggested(raw: string | string[] | undefined): string[] {
  const text = Array.isArray(raw) ? raw.join(',') : raw ?? '';
  return [...new Set(text.split(',').map((x) => x.trim()).filter((x) => UUID.test(x)))].slice(0, MAX_SUGGESTED);
}

type Draft = Pick<EventRow, 'id' | 'title' | 'status' | 'created_by' | 'starts_at' | 'ends_at' | 'all_day' | 'visibility' | 'public_link'> & {
  event_groups: { group_id: string }[];
  event_invites: { user_id: string; via_group: boolean }[];
  event_phone_invites: { phone: string }[];
};

/**
 * Étape 2 « Les invités » de « Créer avec l'IA » (demande de l'admin, 06.11) : l'événement est déjà un brouillon ;
 * la personne choisit elle-même qui voit et qui est invité, puis publie. Invitations v2 : la feuille « Inviter »
 * s'ouvre tout de suite (personnes citées à l'IA déjà cochées) ; sinon le sélecteur du formulaire (AudiencePicker).
 * « Publier » ouvre la fiche (étape 3), où tout se modifie.
 */
export function InviteStep({ eventId, suggested }: { eventId: string; suggested: string[] }) {
  const me = useMe();
  const { can } = useAuth();
  const direct = can('events.publish_direct');
  const [who, setWho] = useState<AudienceValue | null>(null);
  const [sheet, setSheet] = useState(invitesV2On);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, error: loadError, reload } = useQuery(async () => {
    const [ev, members, groups, settings, list] = await Promise.all([
      supabase.from('events').select('id, title, status, created_by, starts_at, ends_at, all_day, visibility, public_link, event_groups(group_id), event_invites(user_id, via_group), event_phone_invites(phone)')
        .eq('id', eventId).single(),
      supabase.from('profiles').select('id, display_name, role').eq('status', 'active').order('display_name'),
      supabase.from('member_groups').select('id, name, created_by, system_key, member_group_members(user_id)').order('name'),
      supabase.from('group_settings').select('require_approval').single(),
      invitesV2On ? fetchGuestList(eventId) : Promise.resolve(null),
    ]);
    const event = must(ev) as unknown as Draft;
    const people = must(members) as Person[];
    // Une seule fois : ce que l'IA a compris (public, groupe…) et, sans invitations v2, les personnes citées cochées.
    setWho((current) => current ?? (() => {
      const start = audienceFromEvent(event);
      const known = suggested.filter((id) => id !== me.id && people.some((p) => p.id === id));
      return invitesV2On || !known.length ? start : { ...start, invitees: [...new Set([...start.invitees, ...known])] };
    })());
    return { event, people, groups: must(groups) as MemberGroup[], approval: !!(must(settings) as { require_approval: boolean }).require_approval, list };
  }, [eventId]);

  if (!data || !who) {
    return (
      <Screen edges={[]}>
        {loadError ? <><ErrorText error={loadError} /><Button label="Réessayer" variant="secondary" onPress={reload} /></> : <Loading />}
      </Screen>
    );
  }

  const ev = data.event;
  const proposing = !direct && data.approval;
  const publishLabel = proposing ? 'Envoyer pour validation' : 'Publier';
  const openEvent = () => router.replace(`/event/${ev.id}`);
  const peopleNote = 'Les personnes en plus (même hors du groupe) : « Ajouter des gens de Party » ci-dessous. Le lien à partager arrive avec la publication.';

  async function publish(withInvites: boolean) {
    const wrong = withInvites && !invitesV2On ? audienceError(who!) : null;
    if (wrong) return setError(wrong);
    setBusy(true);
    setError(null);
    try {
      if (withInvites) {
        check(await supabase.from('events').update(audienceToEvent(who!)).eq('id', ev.id));
        await saveAudience(ev.id, who!, { people: !invitesV2On });
      }
      // Comme le formulaire : publié directement (droit « publier sans validation »), sinon proposé.
      check(await supabase.from('events').update({ status: direct ? 'published' : 'pending' }).eq('id', ev.id));
      router.replace(`/event/${ev.id}?step=online`);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(dbMessage(message, message));
    } finally {
      setBusy(false);
    }
  }

  if (ev.status !== 'draft') {
    return (
      <Screen edges={[]}>
        <Stack.Screen options={{ title: '', headerLeft: () => <HeaderBack label="Événements" onPress={() => router.replace('/')} /> }} />
        <AIEventSteps current={3} />
        <T>{ev.status === 'pending' ? 'Cet événement attend déjà sa validation.' : 'Cet événement est déjà publié.'}</T>
        <Button label="Ouvrir l’événement" onPress={openEvent} />
      </Screen>
    );
  }

  return (
    <Screen edges={[]}>
      <Stack.Screen options={{ title: 'Les invités', headerLeft: () => <HeaderBack label="Événements" onPress={() => router.replace('/')} /> }} />
      <AIEventSteps current={2} />
      <View style={{ gap: 4 }}>
        <T muted size={13}>Brouillon enregistré · encore invisible pour les autres</T>
        <Title size={26}>{ev.title}</Title>
      </View>

      <Card>
        <T weight="bold" size={17}>Qui voit l’événement ?</T>
        <AudiencePicker value={who} onChange={setWho} groups={data.groups} people={data.people} meId={me.id}
          allGroups={can('events.manage_all')} peopleNote={peopleNote} />
      </Card>

      {invitesV2On && data.list ? (
        <Card>
          <T weight="bold" size={17}>Ajouter des gens de Party</T>
          <T weight="semibold">{ruleSentence(data.list)}</T>
          <T muted size={13}>Même hors du groupe, sans y entrer. Prévenus dans Party à la publication.</T>
          <Button variant="secondary" label="＋ Inviter des personnes" onPress={() => setSheet(true)} />
        </Card>
      ) : null}

      <View style={st.publish}>
        {proposing ? <T muted size={13}>Un admin doit valider ta proposition avant qu’elle soit visible.</T> : null}
        <ErrorText error={error} />
        <Button label={publishLabel} loading={busy} onPress={() => void publish(true)} />
        <Button variant="secondary" label={proposing ? 'Envoyer sans inviter pour l’instant' : 'Publier sans inviter pour l’instant'}
          disabled={busy} onPress={() => void publish(false)} />
        <Button variant="ghost" small label="Ouvrir l’événement (finir à la main)" disabled={busy} onPress={openEvent} />
      </View>

      {invitesV2On && data.list ? (
        <InviteSheet visible={sheet} draft initialPeople={suggested} event={ev} me={{ id: me.id, display_name: me.display_name ?? '' }}
          list={data.list} onClose={() => setSheet(false)} onInvited={reload} />
      ) : null}
    </Screen>
  );
}

const st = StyleSheet.create({
  publish: { gap: 10, padding: 14, borderRadius: radius.md, backgroundColor: colors.surface },
});
