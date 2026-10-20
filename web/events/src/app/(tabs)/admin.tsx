import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Avatar, Button, Card, Empty, ErrorText, Input, LinkRow, Screen, s, Section, T, Title, ToggleRow } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { hasCompleteIdentity } from '@/lib/profile';
import { formatMessageTime, formatShort } from '@/lib/format';
import { must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import type { EventRow, GroupSettings, Profile } from '@/lib/types';

type Pending = EventRow & { author: { display_name: string } | null; date_options: { id: string }[]; polls: { id: string }[] };

export default function Admin() {
  const { isAdmin } = useAuth();
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const { data, reload } = useQuery(async () => {
    const [events, members, settings] = await Promise.all([
      supabase
        .from('events')
        .select('*, author:profiles!events_created_by_fkey(display_name), date_options(id), polls(id)')
        .eq('status', 'pending')
        .order('created_at'),
      supabase.rpc('get_member_directory').eq('status', 'pending').order('created_at'),
      supabase.from('group_settings').select('*').single(),
    ]);
    return {
      events: must(events) as unknown as Pending[],
      members: must(members) as Profile[],
      settings: must(settings) as GroupSettings,
    };
  }, []);

  if (!isAdmin) return <Redirect href="/" />;

  async function run(p: PromiseLike<{ error: { message: string } | null }>) {
    const { error } = await p;
    setError(error?.message.includes('profile_incomplete') ? 'Ce membre doit d’abord renseigner son nom, son prénom, son surnom et sa photo.' : error?.message ?? null);
    reload();
  }

  const setSetting = (patch: Partial<GroupSettings>) => run(supabase.from('group_settings').update(patch).eq('id', true));

  return (
    <Screen edges={[]}>
      <Title>Administration</Title>
      <ErrorText error={error} />

      <Section title="Propositions à valider">
        {data?.events.length === 0 ? <Empty>Rien à valider.</Empty> : null}
        {data?.events.map((e) => (
          <Card key={e.id} style={{ backgroundColor: colors.bg }}>
            <View style={s.rowBetween}>
              <View style={{ flex: 1 }}>
                <T weight="bold" size={17}>{e.title}</T>
                <T muted size={12}>par {e.author?.display_name ?? '?'} · {formatMessageTime(e.created_at)}</T>
              </View>
              <Button small variant="ghost" label="Voir" onPress={() => router.push(`/event/${e.id}`)} />
            </View>
            <T muted size={14}>
              {e.date_mode === 'poll' ? `Date à définir · ${e.date_options.length} créneau(x)` : formatShort(e.starts_at)}
              {e.polls.length ? ` · ${e.polls.length} sondage(s)` : ''}
              {e.max_participants ? ` · ${e.max_participants} places` : ''}
            </T>
            {rejecting === e.id ? (
              <View style={{ gap: 8 }}>
                <Input placeholder="Message pour l’organisateur (optionnel)" value={reason} onChangeText={setReason} />
                <View style={s.row}>
                  <Button small variant="secondary" label="Annuler" onPress={() => setRejecting(null)} style={{ flex: 1 }} />
                  <Button
                    small
                    variant="danger"
                    label="Confirmer le refus"
                    style={{ flex: 1 }}
                    onPress={() => {
                      setRejecting(null);
                      run(supabase.rpc('reject_event', { e: e.id, reason: reason.trim() || null }));
                      setReason('');
                    }}
                  />
                </View>
              </View>
            ) : (
              <View style={s.row}>
                <Button small label="Approuver" style={{ flex: 1 }} onPress={() => run(supabase.rpc('approve_event', { e: e.id }))} />
                <Button small variant="secondary" label="Modifier" style={{ flex: 1 }} onPress={() => router.push(`/event/${e.id}/edit`)} />
                <Button small variant="danger" label="Refuser" style={{ flex: 1 }} onPress={() => setRejecting(e.id)} />
              </View>
            )}
          </Card>
        ))}
      </Section>

      <Section title="Demandes d’accès">
        {data?.members.length === 0 ? <Empty>Aucune demande.</Empty> : null}
        {data?.members.map((m) => (
          <View key={m.id} style={s.rowBetween}>
            <Avatar id={m.id} name={m.display_name || '?'} photo={m.avatar_url} />
            <View style={{ flex: 1 }}>
              <T weight="semibold">{m.display_name || 'Profil à compléter'}</T>
              {m.first_name || m.last_name ? <T muted>{[m.first_name, m.last_name].filter(Boolean).join(' ')}</T> : null}
              <T muted size={12}>{hasCompleteIdentity(m) ? m.phone : 'Nom, prénom, surnom et photo à compléter avant validation.'}</T>
            </View>
            <Button small label="Accepter" disabled={!hasCompleteIdentity(m)} onPress={() => run(supabase.from('profiles').update({ status: 'active' }).eq('id', m.id))} />
            <Button small variant="danger" label="Refuser" onPress={() => run(supabase.from('profiles').update({ status: 'banned' }).eq('id', m.id))} />
          </View>
        ))}
      </Section>

      {data ? (
        <Section title="Règles du groupe">
          <ToggleRow
            label="Validation obligatoire"
            hint="Les propositions des membres attendent ton accord"
            value={data.settings.require_approval}
            onChange={(v) => setSetting({ require_approval: v })}
          />
          <ToggleRow
            label="Les co-admins publient directement"
            value={data.settings.coadmins_skip_approval}
            onChange={(v) => setSetting({ coadmins_skip_approval: v })}
          />
          <ToggleRow
            label="Modifier après publication"
            hint="L’organisateur peut encore changer son événement"
            value={data.settings.organizers_can_edit_published}
            onChange={(v) => setSetting({ organizers_can_edit_published: v })}
          />
          <ToggleRow
            label="Les membres créent des tags"
            value={data.settings.members_can_create_tags}
            onChange={(v) => setSetting({ members_can_create_tags: v })}
          />
        </Section>
      ) : null}

      <Card style={{ gap: 0, paddingVertical: 4 }}>
        <LinkRow label="Annonces admin" hint="Publier un message obligatoire pour tout le groupe" onPress={() => router.push('/admin/announcements')} />
        <View style={s.divider} />
        <LinkRow label="Membres et rôles" hint="Co-admins, retirer un accès" onPress={() => router.push('/admin/members')} />
        <View style={s.divider} />
        <LinkRow label="Catégories et tags" hint="Créer, renommer, archiver" onPress={() => router.push('/admin/taxonomy')} />
      </Card>
    </Screen>
  );
}
