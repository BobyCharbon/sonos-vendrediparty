import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Avatar, Button, Card, Empty, ErrorText, Input, LinkRow, Screen, s, Section, T, ToggleRow } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { hasCompleteIdentity } from '@/lib/profile';
import { formatMessageTime, formatShort } from '@/lib/format';
import { must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import type { EventRow, GroupSettings, Profile } from '@/lib/types';

type Pending = EventRow & { author: { display_name: string } | null; date_options: { id: string }[]; polls: { id: string }[] };

export default function Admin() {
  const { isAdmin, can, rank } = useAuth();
  const [rejecting, setRejecting] = useState<string | null>(null);
  const [reason, setReason] = useState('');
  const [error, setError] = useState<string | null>(null);

  const { data, reload } = useQuery(async () => {
    const [events, requests, directory, settings] = await Promise.all([
      supabase
        .from('events')
        .select('*, author:profiles!events_created_by_fkey(display_name), date_options(id), polls(id)')
        .eq('status', 'pending')
        .order('created_at'),
      supabase.from('join_requests').select('user_id, message, created_at').eq('status', 'pending').order('created_at'),
      supabase.rpc('get_member_directory'),
      supabase.from('group_settings').select('*').single(),
    ]);
    return {
      events: must(events) as unknown as Pending[],
      // Demandes d'adhésion : le message et le profil de la personne (droit « Accepter les demandes »).
      requests: (requests.data as { user_id: string; message: string | null; created_at: string }[] | null ?? [])
        .map((r) => ({ ...r, who: (directory.data as Profile[] | null ?? []).find((p) => p.id === r.user_id) }))
        .filter((r): r is typeof r & { who: Profile } => !!r.who),
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
      <ErrorText error={error} />

      {can('events.approve') ? <Section title="Propositions à valider">
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
      </Section> : null}

      {can('members.approve') ? (
        <Section title="Demandes d’adhésion">
          {data?.requests.length === 0 ? <Empty>Aucune demande.</Empty> : null}
          {data?.requests.map(({ who: m, message, created_at }) => (
            <Card key={m.id} style={{ backgroundColor: colors.bg }}>
              <View style={s.row}>
                <Avatar id={m.id} name={m.display_name || '?'} photo={m.avatar_url} size={44} />
                <View style={{ flex: 1 }}>
                  <T weight="semibold">{m.display_name || 'Profil à compléter'}</T>
                  {m.first_name || m.last_name ? <T muted>{[m.first_name, m.last_name].filter(Boolean).join(' ')}</T> : null}
                  <T muted size={12}>{m.phone ? `+${m.phone.replace(/^\+/, '')} · ` : ''}{formatMessageTime(created_at)}</T>
                </View>
              </View>
              {message ? <T size={14}>« {message} »</T> : null}
              {!hasCompleteIdentity(m) ? <T muted size={13}>Nom, prénom, surnom et photo à compléter avant de pouvoir accepter.</T> : null}
              <View style={s.row}>
                <Button small label="Accepter" style={{ flex: 1 }} disabled={!hasCompleteIdentity(m)} onPress={() => run(supabase.rpc('decide_join_request', { member: m.id, accept: true }))} />
                <Button small variant="danger" label="Refuser" style={{ flex: 1 }} onPress={() => run(supabase.rpc('decide_join_request', { member: m.id, accept: false }))} />
              </View>
            </Card>
          ))}
        </Section>
      ) : null}

      {data && can('group.settings') ? (
        <Section title="Règles du groupe">
          <ToggleRow
            label="Validation obligatoire"
            hint="Les propositions des membres attendent ton accord"
            value={data.settings.require_approval}
            onChange={(v) => setSetting({ require_approval: v })}
          />
          <T muted size={13}>Qui publie sans validation, modifie le publié ou crée des tags : c’est maintenant dans « Rôles et droits ».</T>
        </Section>
      ) : null}

      <Card style={{ gap: 0, paddingVertical: 4 }}>
        {can('roles.manage') || rank >= 99 ? (
          <>
            <LinkRow label="Rôles et droits" hint="Ce que chaque rôle peut faire" onPress={() => router.push('/admin/roles')} />
            <View style={s.divider} />
          </>
        ) : null}
        {rank >= 4 ? (
          <>
            <LinkRow label="Utilisateurs" hint="Tous les inscrits : connexions, activité, tri" onPress={() => router.push('/admin/users')} />
            <View style={s.divider} />
          </>
        ) : null}
        {rank >= 4 || can('members.roles') || can('members.ban') || can('members.view_identity') ? (
          <>
            <LinkRow label="Membres" hint="Rôles, accès, identité" onPress={() => router.push('/admin/members')} />
            <View style={s.divider} />
          </>
        ) : null}
        {can('announcements.publish') ? (
          <>
            <LinkRow label="Annonces admin" hint="Publier un message obligatoire pour tout le groupe" onPress={() => router.push('/admin/announcements')} />
            <View style={s.divider} />
          </>
        ) : null}
        {can('taxonomy.manage') ? <LinkRow label="Catégories et tags" hint="Créer, renommer, archiver" onPress={() => router.push('/admin/taxonomy')} /> : null}
      </Card>
    </Screen>
  );
}
