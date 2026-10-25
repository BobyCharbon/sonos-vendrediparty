import { Redirect, router } from 'expo-router';
import { useState } from 'react';
import { View } from 'react-native';

import { Avatar, Button, Chip, ErrorText, Input, Screen, s, Section, T } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { hasCompleteIdentity } from '@/lib/profile';
import { check, supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';
import { roleLabel } from '@/lib/types';
import { arrangeUsers, defaultDescending, USER_FILTERS, USER_SORTS, type UserFilter, type UserRow, type UserSort } from '@/lib/users';

const FULL_ACCESS_RANK = 4;  // Root et Admin
const DAY = 86_400_000;

function ago(iso: string | null): string {
  if (!iso) return 'jamais';
  const days = Math.floor((Date.now() - Date.parse(iso)) / DAY);
  return days <= 0 ? 'aujourd’hui' : days === 1 ? 'hier' : `il y a ${days} j`;
}

/** Utilisateurs (Root, Admin) : toutes les personnes inscrites par SMS, avec leurs connexions et leur activité,
 * triables et filtrables. La gestion (rôle, bêta, accès, suppression) reste dans « Membres ». */
export default function Users() {
  const { rank } = useAuth();
  const [search, setSearch] = useState('');
  const [filter, setFilter] = useState<UserFilter>('all');
  const [sort, setSort] = useState<UserSort>('last_sign_in');
  const [descending, setDescending] = useState(true);
  const { data, error, loading, reload } = useQuery(async () => {
    const res = await supabase.rpc('admin_member_list');
    if (res.error && /admin_member_list|PGRST202|42883/.test(`${res.error.code} ${res.error.message}`)) return null;  // base pas encore à jour
    check(res);
    return (res.data ?? []) as UserRow[];
  }, []);

  if (rank < FULL_ACCESS_RANK) return <Redirect href="/" />;
  const rows = data ? arrangeUsers(data, { search, filter, sort, descending }) : [];
  const chooseSort = (key: UserSort) => {
    if (key === sort) setDescending((d) => !d);
    else { setSort(key); setDescending(defaultDescending(key)); }
  };
  const direction = sort === 'name' ? (descending ? 'Z → A' : 'A → Z') : descending ? 'Plus récent / plus grand d’abord' : 'Plus ancien / plus petit d’abord';

  return (
    <Screen edges={[]}>
      <ErrorText error={error} />
      {error ? <Button label="Réessayer" variant="secondary" onPress={reload} /> : null}
      {loading && !data ? <T muted>Chargement des utilisateurs…</T> : null}
      {data === null && !loading && !error ? <T muted>Cette liste s’ouvrira après la mise à jour de la base (en préparation).</T> : null}
      {data ? (
        <>
          <T muted size={13}>{data.length} personne(s) inscrite(s) avec leur numéro · ouverture notée dans le journal</T>
          <Input placeholder="Rechercher (surnom, prénom, nom, numéro)" value={search} onChangeText={setSearch} accessibilityLabel="Rechercher un utilisateur" />
          <Section title="Trier par">
            <View style={s.wrap}>
              {USER_SORTS.map((o) => <Chip key={o.key} label={o.key === sort ? `${o.label} ${descending ? '↓' : '↑'}` : o.label} selected={o.key === sort} onPress={() => chooseSort(o.key)} />)}
            </View>
            <T muted size={12}>{direction} · touche à nouveau pour inverser</T>
          </Section>
          <Section title="Afficher">
            <View style={s.wrap}>
              {USER_FILTERS.map((o) => <Chip key={o.key} label={o.label} selected={o.key === filter} onPress={() => setFilter(o.key)} />)}
            </View>
          </Section>
          <Section title={`Utilisateurs (${rows.length})`}>
            {rows.length ? rows.map((u) => <UserCard key={u.id} user={u} />) : <T muted>Personne ne correspond.</T>}
          </Section>
        </>
      ) : null}
    </Screen>
  );
}

function UserCard({ user: u }: { user: UserRow }) {
  const tags = [
    u.status === 'banned' ? '⛔ Accès retiré' : roleLabel[u.role],
    u.beta ? '🧪 Bêta' : null,
    !hasCompleteIdentity(u) ? 'Profil incomplet' : null,
    ...u.groups.map((g) => `👥 ${g}`),
  ].filter(Boolean).join(' · ');
  return (
    <View accessibilityLabel={`Utilisateur ${u.display_name || 'sans surnom'}`} style={{ gap: 6, paddingVertical: 10, borderBottomWidth: 1, borderBottomColor: colors.line }}>
      <View style={s.row}>
        <Avatar id={u.id} name={u.display_name || '?'} photo={u.avatar_url} />
        <View style={{ flex: 1 }}>
          <T weight="semibold">{u.display_name || 'Profil à compléter'}</T>
          {u.first_name || u.last_name ? <T muted size={13}>{[u.first_name, u.last_name].filter(Boolean).join(' ')}</T> : null}
          <T muted size={12}>{u.phone ? `+${u.phone.replace(/^\+/, '')}` : 'Numéro inconnu'}</T>
        </View>
      </View>
      <T size={13}>{tags}</T>
      <T muted size={12}>Inscrit le {formatMessageTime(u.created_at)}</T>
      <T muted size={12}>1re connexion : {u.first_sign_in_at ? formatMessageTime(u.first_sign_in_at) : 'jamais'}</T>
      <T muted size={12}>Dernière connexion : {u.last_sign_in_at ? `${formatMessageTime(u.last_sign_in_at)} (${ago(u.last_sign_in_at)})` : 'jamais'}</T>
      <T muted size={12}>{u.sign_in_count} connexion(s) notée(s){u.last_device ? ` · dernier appareil : ${u.last_device.slice(0, 60)}` : ''}</T>
      <T muted size={12}>{u.rsvp_count} sortie(s) « je viens » · {u.message_count} message(s)</T>
      <View style={s.wrap}>
        <Chip label="📜 Journal" onPress={() => router.push({ pathname: '/admin/journal', params: { member: u.id, name: u.display_name } })} />
        <Chip label="Gérer dans Membres" onPress={() => router.push('/admin/members')} />
      </View>
    </View>
  );
}
