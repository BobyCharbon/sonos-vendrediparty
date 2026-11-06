import { router, Stack } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { AIEventSteps } from './AIEventSteps';
import { audienceFromEvent, audienceToEvent, choosableGroups, mayUseVip, saveAudience } from './AudiencePicker';
import { Button, Card, ErrorText, HeaderBack, Loading, Screen, T, Title } from './ui';
import { PublishChoice, VISIBILITIES, withVisibility, type Visibility } from './VisibilityChoice';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { invitesV2On } from '@/lib/features';
import { dbMessage } from '@/lib/moderation';
import { check, must, supabase } from '@/lib/supabase';
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

export type Preset = { visibility: Visibility; groups: string[]; suggested: string[] };

type Draft = Pick<EventRow, 'id' | 'title' | 'status' | 'created_by' | 'starts_at' | 'ends_at' | 'all_day' | 'visibility' | 'public_link'> & {
  event_groups: { group_id: string }[];
  event_invites: { user_id: string; via_group: boolean }[];
  event_phone_invites: { phone: string }[];
};

/**
 * Après la publication : où aller. Sur invitation (v2) : la fiche ouvre aussitôt la feuille « Inviter », lien prêt, personnes
 * citées cochées ; un groupe ou les Membres : la fiche, carte « Invités » en avant ; public : la fiche. Proposé (validation) :
 * la fiche, qui dit que le lien arrive après la validation. v1 (invitations v2 éteintes) : la fiche et sa carte du lien.
 */
export function afterPublish(id: string, kind: Visibility, published: boolean, suggested: string[], v2: boolean): string {
  const base = `/event/${id}?step=online`;
  if (!published || !v2) return base;
  if (kind === 'invite') return `${base}&invite=link${suggested.length ? `&suggested=${suggested.join(',')}` : ''}`;
  if (kind === 'vip' || kind === 'group') return `${base}&invite=more`;
  return base;
}

/**
 * Étape 2 « Qui est invité » de « Créer avec l'IA » (retours de l'admin, 06.11) : l'événement est un brouillon. Un toucher
 * sur « qui voit » le publie (ou l'envoie pour validation) ; on invite ENSUITE, l'événement en ligne, avec le lien prêt.
 * Jamais de lien « pas encore disponible ». La fiche s'ouvre ensuite (étape 3).
 */
export function InviteStep({ eventId, preset }: { eventId: string; preset: Preset }) {
  const me = useMe();
  const { can } = useAuth();
  const direct = can('events.publish_direct');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const { data, error: loadError, reload } = useQuery(async () => {
    const [ev, allGroups, settings, kept] = await Promise.all([
      supabase.from('events').select('id, title, status, created_by, starts_at, ends_at, all_day, visibility, public_link, event_groups(group_id), event_invites(user_id, via_group), event_phone_invites(phone)')
        .eq('id', eventId).single(),
      supabase.from('member_groups').select('id, name, created_by, system_key, member_group_members(user_id)').order('name'),
      supabase.from('group_settings').select('require_approval').single(),
      // Personnes citées à l'IA, gardées avec le brouillon (étape rouverte depuis la fiche) ; base sans la colonne : rien.
      supabase.from('events').select('ai_suggested').eq('id', eventId).maybeSingle(),
    ]);
    const event = must(ev) as unknown as Draft;
    const every = must(allGroups) as MemberGroup[];
    const groups = choosableGroups(every, me.id, can('events.manage_all'));
    const vipOk = mayUseVip(every, me.id, can('events.manage_all'));
    const stored = ((kept.data as { ai_suggested?: string[] } | null)?.ai_suggested ?? []).filter((id) => parseIds(id).length);
    return { event, groups, vipOk, stored, approval: !!(must(settings) as { require_approval: boolean }).require_approval };
  }, [eventId]);

  if (!data) {
    return (
      <Screen edges={[]}>
        {loadError ? <><ErrorText error={loadError} /><Button label="Réessayer" variant="secondary" onPress={reload} /></> : <Loading />}
      </Screen>
    );
  }

  const ev = data.event;
  const proposing = !direct && data.approval;
  const openEvent = () => router.replace(`/event/${ev.id}`);
  // Pré-réglage dit à l'IA, seulement s'il est permis (ses groupes, Vendredi Party s'il en fait partie).
  const knownGroups = preset.groups.filter((id) => data.groups.some((g) => g.id === id));
  const allowed = (preset.visibility !== 'group' || knownGroups.length) && (preset.visibility !== 'vip' || data.vipOk);
  const suggested: Visibility = allowed ? preset.visibility : 'public';
  const named = (preset.suggested.length ? preset.suggested : data.stored).filter((id) => id !== me.id);

  /** Qui voit, puis le statut (publié, ou proposé sans le droit « publier sans validation »), puis la fiche. */
  async function publish(kind: Visibility, groupIds: string[]) {
    setBusy(true);
    setError(null);
    try {
      const who = withVisibility(audienceFromEvent(ev), kind, groupIds);
      check(await supabase.from('events').update(audienceToEvent(who)).eq('id', ev.id));
      await saveAudience(ev.id, { ...who, invitees: [], phones: [] }, { people: false });
      const status = proposing ? 'pending' : 'published';
      check(await supabase.from('events').update({ status }).eq('id', ev.id));
      // Publié : les personnes citées ne servent plus (elles sont cochées dans la feuille « Inviter », jamais invitées).
      if (data!.stored.length) await supabase.from('events').update({ ai_suggested: [] }).eq('id', ev.id);
      router.replace(afterPublish(ev.id, kind, status === 'published', named, invitesV2On) as never);
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
        <T muted size={13}>
          {proposing ? 'Un toucher l’envoie pour validation : un admin le valide avant qu’il soit visible.'
            : 'Un toucher le publie. Tu invites ensuite, l’événement en ligne, avec le lien à partager.'}
        </T>
        <PublishChoice groups={data.groups} vipOk={data.vipOk} suggested={suggested} suggestedGroups={knownGroups}
          proposing={proposing} busy={busy} onPublish={(kind, ids) => void publish(kind, ids)} />
        <ErrorText error={error} />
      </Card>

      <Button variant="ghost" small label="Ouvrir l’événement (finir à la main)" disabled={busy} onPress={openEvent} />
    </Screen>
  );
}
