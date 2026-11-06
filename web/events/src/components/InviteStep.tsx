import { router, Stack } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { AIEventSteps } from './AIEventSteps';
import { audienceError, audienceFromEvent, audienceToEvent, choosableGroups, mayUseVip, PeoplePicker, saveAudience, type AudienceValue, type Person } from './AudiencePicker';
import { InviteSheet } from './InviteSheet';
import { Button, Card, ErrorText, HeaderBack, Loading, Screen, T, Title } from './ui';
import { VisibilityChoice, VISIBILITIES, withVisibility, type Visibility } from './VisibilityChoice';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { invitesV2On } from '@/lib/features';
import { fetchGuestList } from '@/lib/invites';
import { dbMessage } from '@/lib/moderation';
import { check, must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { EventRow, MemberGroup } from '@/lib/types';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const MAX_IDS = 50;

/** « ?suggested=id1,id2 » (personnes citées à l'IA) ou « ?groups=… » → identifiants sûrs, jamais autre chose. */
export function parseIds(raw: string | string[] | undefined): string[] {
  const text = Array.isArray(raw) ? raw.join(',') : raw ?? '';
  return [...new Set(text.split(',').map((x) => x.trim()).filter((x) => UUID.test(x)))].slice(0, MAX_IDS);
}

/** « ?audience=vip » : ce que la personne a dit spontanément à l'IA (pré-réglage) ; sinon le défaut, public + lien. */
export function parseVisibility(raw: string | string[] | undefined): Visibility {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return (VISIBILITIES as readonly string[]).includes(value ?? '') ? (value as Visibility) : 'public';
}

/** Les personnes déjà ajoutées par la feuille « Inviter » (la règle « qui voit » est choisie juste au-dessus). */
export function invitedLine(names: string[]): string {
  if (!names.length) return 'Personne en plus pour l’instant';
  return `${names.length > 1 ? 'Invités en plus' : 'Invité en plus'} : ${names.join(', ')}`;
}

export type Preset = { visibility: Visibility; groups: string[]; suggested: string[] };

type Draft = Pick<EventRow, 'id' | 'title' | 'status' | 'created_by' | 'starts_at' | 'ends_at' | 'all_day' | 'visibility' | 'public_link'> & {
  event_groups: { group_id: string }[];
  event_invites: { user_id: string; via_group: boolean }[];
  event_phone_invites: { phone: string }[];
};

/**
 * Départ de l'étape : le pré-réglage dit à l'IA, seulement s'il est permis (ses groupes, Vendredi Party s'il en fait
 * partie ; sinon le défaut, public + lien), et les personnes citées cochées (sans invitations v2).
 */
function startValue(event: Draft, preset: Preset, groups: MemberGroup[], vipOk: boolean, people: Person[], meId: string): AudienceValue {
  const known = preset.groups.filter((id) => groups.some((g) => g.id === id));
  const allowed = (preset.visibility !== 'group' || known.length) && (preset.visibility !== 'vip' || vipOk);
  const kind = allowed ? preset.visibility : 'public';
  const base = withVisibility(audienceFromEvent(event), kind, known);
  const named = preset.suggested.filter((id) => id !== meId && people.some((p) => p.id === id));
  return invitesV2On || !named.length ? base : { ...base, invitees: [...new Set([...base.invitees, ...named])] };
}

/**
 * Étape 2 « Qui est invité » de « Créer avec l'IA » (retour de l'admin, 06.11) : l'événement est un brouillon
 * (public + lien en attendant). En haut, qui le voit (public + lien par défaut, en surbrillance) ; puis les invités
 * (feuille « Inviter » des invitations v2, sinon le sélecteur actuel) ; puis Publier. La fiche s'ouvre ensuite (étape 3).
 */
export function InviteStep({ eventId, preset }: { eventId: string; preset: Preset }) {
  const me = useMe();
  const { can } = useAuth();
  const direct = can('events.publish_direct');
  const [who, setWho] = useState<AudienceValue | null>(null);
  const [sheet, setSheet] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, error: loadError, reload } = useQuery(async () => {
    const [ev, members, allGroups, settings, list] = await Promise.all([
      supabase.from('events').select('id, title, status, created_by, starts_at, ends_at, all_day, visibility, public_link, event_groups(group_id), event_invites(user_id, via_group), event_phone_invites(phone)')
        .eq('id', eventId).single(),
      supabase.from('profiles').select('id, display_name, role').eq('status', 'active').order('display_name'),
      supabase.from('member_groups').select('id, name, created_by, system_key, member_group_members(user_id)').order('name'),
      supabase.from('group_settings').select('require_approval').single(),
      invitesV2On ? fetchGuestList(eventId) : Promise.resolve(null),
    ]);
    const event = must(ev) as unknown as Draft;
    const people = must(members) as Person[];
    const every = must(allGroups) as MemberGroup[];
    const groups = choosableGroups(every, me.id, can('events.manage_all'));
    const vipOk = mayUseVip(every, me.id, can('events.manage_all'));
    setWho((current) => current ?? startValue(event, preset, groups, vipOk, people, me.id));
    return { event, people, groups, vipOk, approval: !!(must(settings) as { require_approval: boolean }).require_approval, list };
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
  const openEvent = () => router.replace(`/event/${ev.id}`);
  const named = data.people.filter((p) => preset.suggested.includes(p.id) && p.id !== me.id).map((p) => p.display_name.split(' ')[0]);

  /** Qui voit est toujours enregistré ; withInvites : les personnes ajoutées une à une aussi (sans invitations v2). */
  async function publish(withInvites: boolean) {
    const wrong = withInvites && !invitesV2On ? audienceError(who!) : null;
    if (wrong) return setError(wrong);
    setBusy(true);
    setError(null);
    try {
      check(await supabase.from('events').update(audienceToEvent(who!)).eq('id', ev.id));
      await saveAudience(ev.id, withInvites ? who! : { ...who!, invitees: [], phones: [] }, { people: withInvites && !invitesV2On });
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
      <Stack.Screen options={{ title: 'Qui est invité', headerLeft: () => <HeaderBack label="Événements" onPress={() => router.replace('/')} /> }} />
      <AIEventSteps current={2} />
      <View style={{ gap: 4 }}>
        <T muted size={13}>Brouillon enregistré · encore invisible pour les autres</T>
        <Title size={26}>{ev.title}</Title>
      </View>

      <Card>
        <T weight="bold" size={17}>Qui voit l’événement ?</T>
        <VisibilityChoice value={who} onChange={setWho} groups={data.groups} vipOk={data.vipOk} />
      </Card>

      <Card>
        <T weight="bold" size={17}>Les invités</T>
        {invitesV2On && data.list ? (
          <>
            <T weight="semibold">{invitedLine(data.list.people.filter((p) => p.source === 'person').map((p) => p.name.split(' ')[0]))}</T>
            <T muted size={13}>Des gens de Party, même hors du groupe, sans y entrer. Prévenus dans Party à la publication ; le lien à partager arrive avec la publication.</T>
            <Button variant="secondary" label={named.length ? `＋ Inviter ${named.join(', ')}…` : '＋ Inviter des personnes'} onPress={() => setSheet(true)} />
          </>
        ) : who.audience === 'public' ? (
          <T muted size={13}>Public : pas besoin d’inviter, tout le monde le voit. Partage le lien depuis la fiche, une fois publié.</T>
        ) : (
          <PeoplePicker value={who} onChange={setWho} people={data.people} meId={me.id} />
        )}
      </Card>

      <View style={st.publish}>
        {proposing ? <T muted size={13}>Un admin doit valider ta proposition avant qu’elle soit visible.</T> : null}
        <ErrorText error={error} />
        <Button label={proposing ? 'Envoyer pour validation' : 'Publier'} loading={busy} onPress={() => void publish(true)} />
        <Button variant="secondary" label={proposing ? 'Envoyer sans inviter pour l’instant' : 'Publier sans inviter pour l’instant'}
          disabled={busy} onPress={() => void publish(false)} />
        <Button variant="ghost" small label="Ouvrir l’événement (finir à la main)" disabled={busy} onPress={openEvent} />
      </View>

      {invitesV2On && data.list ? (
        <InviteSheet visible={sheet} draft initialPeople={preset.suggested} event={ev} me={{ id: me.id, display_name: me.display_name ?? '' }}
          list={data.list} onClose={() => setSheet(false)} onInvited={reload} />
      ) : null}
    </Screen>
  );
}

const st = StyleSheet.create({
  publish: { gap: 10, padding: 14, borderRadius: radius.md, backgroundColor: colors.surface },
});
