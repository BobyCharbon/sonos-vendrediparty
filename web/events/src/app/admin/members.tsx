import { Redirect, router } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { DeleteMember } from '@/components/DeleteMember';
import { Avatar, Button, Card, Chip, ErrorText, Input, LinkRow, Screen, s, Section, T } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { hasCompleteIdentity } from '@/lib/profile';
import { check, must, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import { ROLE_ORDER, roleLabel, roleRank, type MemberRole, type Profile } from '@/lib/types';

const ROOT_ID = '298ff6e0-07b2-4127-bb69-d254dd63a3d5';
const FULL_ACCESS_RANK = 4;  // Root (99) et Admin (4) : tous les inscrits, numéros, suppression, journal

type Member = Profile & { beta?: boolean; last_sign_in_at?: string | null };

/** Root et Admin : liste complète (numéros, dernière connexion, bêta), consultation journalisée par la base.
 * Tant que la migration n'est pas appliquée (fonction absente), on retombe sur l'annuaire habituel. */
async function loadMembers(full: boolean): Promise<{ people: Member[]; beta: Set<string>; full: boolean }> {
  if (full) {
    const list = await supabase.rpc('admin_member_list');
    if (!list.error) {
      const people = (list.data ?? []) as Member[];
      return { people, beta: new Set(people.filter((p) => p.beta).map((p) => p.id)), full: true };
    }
    if (!/admin_member_list|PGRST202|42883/.test(`${list.error.code} ${list.error.message}`)) throw new Error(list.error.message);
  }
  const [people, beta] = await Promise.all([
    supabase.rpc('get_member_directory').order('display_name'),
    supabase.from('beta_testers').select('user_id'),
  ]);
  return { people: must(people) as Member[], beta: new Set((must(beta) as { user_id: string }[]).map((b) => b.user_id)), full: false };
}

/** Membres : rôles et accès. On ne touche qu'aux comptes d'un rôle inférieur au sien, et on ne donne qu'un rôle inférieur au sien. */
export default function Members() {
  const me = useMe();
  const { can, rank } = useAuth();
  const [search, setSearch] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const updating = useRef(false);
  const fullAccess = rank >= FULL_ACCESS_RANK;
  const { data, error: loadError, loading, reload } = useQuery(() => loadMembers(fullAccess), [fullAccess]);

  if (!(fullAccess || can('members.roles') || can('members.ban') || can('members.view_identity'))) return <Redirect href="/" />;

  async function update(id: string, patch: Partial<Profile> & { beta?: boolean }) {
    if (updating.current) return;
    updating.current = true;
    setBusy(true);
    setError(null);
    try {
      const { beta, ...fields } = patch;
      check(await (beta === undefined
        ? supabase.from('profiles').update(fields).eq('id', id)
        : supabase.rpc('set_beta_tester', { member: id, enabled: beta })));
      await reload();
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(message.includes('last_admin') ? 'Désigne d’abord un autre administrateur actif.'
        : message.includes('profile_incomplete') ? 'Ce compte doit d’abord renseigner son nom, son prénom, son surnom et sa photo.'
        : message.replace(/^forbidden: /, ''));
    } finally {
      updating.current = false;
      setBusy(false);
    }
  }

  const q = search.trim().toLowerCase();
  const rows = (data?.people ?? []).filter((p) => !q || [p.display_name, p.first_name, p.last_name, p.phone].some((value) => value?.toLowerCase().includes(q)));
  const byRole = (r: MemberRole) => rows.filter((p) => p.status === 'active' && p.role === r);
  const banned = rows.filter((p) => p.status === 'banned');
  const waiting = rows.filter((p) => p.status !== 'active' && p.status !== 'banned');
  const canDelete = !!data?.full;
  const row = (person: Member) => <MemberRow key={person.id} person={person} beta={!!data?.beta.has(person.id)} me={me} myRank={rank}
    canRoles={fullAccess || can('members.roles')} canBan={fullAccess || can('members.ban')} canDelete={canDelete} busy={busy} onUpdate={update} onDeleted={reload} />;

  return (
    <Screen edges={[]}>
      {fullAccess ? (
        <Card style={{ gap: 0, paddingVertical: 4 }}>
          <LinkRow label="👤 Utilisateurs" hint="Tous les inscrits : première et dernière connexion, activité, tri" onPress={() => router.push('/admin/users')} />
          <View style={s.divider} />
          <LinkRow label="📜 Journal des membres" hint="Inscriptions, connexions, rôles, bêta, groupes, suppressions, consultations" onPress={() => router.push('/admin/journal')} />
        </Card>
      ) : null}
      {data ? <T muted size={13}>{data.people.length} compte(s) inscrit(s){data.full ? '' : ' · liste complète et suppression après la mise à jour de la base'}</T> : null}
      <Input placeholder="Rechercher (surnom, prénom, nom, numéro)" value={search} onChangeText={setSearch} />
      <ErrorText error={error ?? loadError} />
      {loadError ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}
      {loading ? <T muted>Chargement des membres…</T> : null}
      {[...ROLE_ORDER].reverse().map((r) => {
        const list = byRole(r);
        return list.length ? <Section key={r} title={`${roleLabel[r]} (${list.length})`}>{list.map(row)}</Section> : null;
      })}
      {waiting.length ? <Section title={`En attente (${waiting.length})`}>{waiting.map(row)}</Section> : null}
      {banned.length ? <Section title={`Accès retiré (${banned.length})`}>{banned.map(row)}</Section> : null}
    </Screen>
  );
}

function MemberRow({ person: p, beta, me, myRank, canRoles, canBan, canDelete, busy, onUpdate, onDeleted }: {
  person: Member; beta: boolean; me: Profile; myRank: number; canRoles: boolean; canBan: boolean; canDelete: boolean; busy: boolean;
  onUpdate: (id: string, patch: Partial<Profile> & { beta?: boolean }) => Promise<void>;
  onDeleted: () => void;
}) {
  const root = p.id === ROOT_ID;
  const below = !root && p.id !== me.id && roleRank(p.role) < myRank;
  const roles = ROLE_ORDER.filter((r) => roleRank(r) < myRank);
  return (
    <View style={{ gap: 8, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.line }}>
      <View style={s.row}>
        <Avatar id={p.id} name={p.display_name || '?'} photo={p.avatar_url} />
        <View style={{ flex: 1 }}>
          <T weight="semibold">{p.display_name || 'Profil à compléter'}{p.id === me.id ? ' (toi)' : ''}</T>
          {p.first_name || p.last_name ? <T muted>{[p.first_name, p.last_name].filter(Boolean).join(' ')}</T> : null}
          <T muted size={12}>{root ? '👑 Root' : roleLabel[p.role]}{beta ? ' · 🧪 Bêta-testeur' : ''}{p.phone ? ` · +${p.phone.replace(/^\+/, '')}` : ''}</T>
          {canDelete ? <T muted size={12}>Inscrit le {formatMessageTime(p.created_at)}{p.last_sign_in_at ? ` · connecté le ${formatMessageTime(p.last_sign_in_at)}` : ''}</T> : null}
        </View>
      </View>
      {/* Bêta-testeur : voit les Événements en production avant tout le monde (les admins d'office). */}
      {canRoles && p.status === 'active' ? (
        <View style={s.wrap}>
          <Chip label="🧪 Bêta-testeur" selected={beta} disabled={busy} onPress={() => onUpdate(p.id, { beta: !beta })} />
          {beta && p.role === 'guest' ? <T muted size={13}>Encore Guest : l’onglet s’ouvre, mais il faut aussi l’ajouter au groupe Vendredi Party (Groupes) pour qu’il voie les événements.</T> : null}
        </View>
      ) : null}
      {below && (canRoles || canBan) ? (
        <View style={s.wrap}>
          {p.status === 'active' && canRoles
            ? roles.map((r) => (
                <Chip key={r} label={roleLabel[r]} selected={p.role === r} disabled={busy || (roleRank(r) > 0 && !hasCompleteIdentity(p))} onPress={() => onUpdate(p.id, { role: r })} />
              ))
            : null}
          {canBan ? (
            p.status === 'active'
              ? <Chip label="Retirer l’accès" color={colors.coral} disabled={busy} onPress={() => onUpdate(p.id, { status: 'banned' })} />
              : <Chip label="Réintégrer" disabled={busy} onPress={() => onUpdate(p.id, { status: 'active' })} />
          ) : null}
          {p.status === 'active' && canRoles && !hasCompleteIdentity(p) ? <T muted size={13}>Profil incomplet : il reste Guest tant qu’il manque nom, prénom, surnom ou photo.</T> : null}
        </View>
      ) : null}
      {canDelete ? (
        <View style={s.wrap}>
          <Chip label="📜 Journal" onPress={() => router.push({ pathname: '/admin/journal', params: { member: p.id, name: p.display_name } })} />
          {below ? <DeleteMember id={p.id} name={p.display_name} onDeleted={onDeleted} /> : null}
        </View>
      ) : null}
    </View>
  );
}
