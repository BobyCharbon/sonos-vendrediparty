import { router, useLocalSearchParams } from 'expo-router';
import { Linking, View } from 'react-native';

import { Avatar, Button, Card, Empty, ErrorText, Loading, Screen, Section, T, Title } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { supabase } from '@/lib/supabase';
import { roleLabel, type MemberRole } from '@/lib/types';

const MEMBER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type MemberCard = {
  id: string;
  display_name: string;
  avatar_url: string | null;
  role: MemberRole;
  root: boolean;
  me: boolean;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  groups: string[];
};

/** Fiche profil d'un membre : photo, surnom, rôle, groupes en commun ; nom et numéro selon les choix de la personne
 * (la base applique ces choix : rien n'arrive ici qu'on n'ait pas le droit de voir). */
export default function MemberScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const valid = typeof id === 'string' && MEMBER_ID.test(id);
  const { data, error, loading } = useQuery(async () => {
    if (!valid) return null;
    const { data, error } = await supabase.rpc('member_card', { target: id });
    if (error) throw new Error(error.message);
    return (data as MemberCard | null) ?? null;
  }, [id]);

  if (loading) return <Loading />;
  if (!data) {
    return (
      <Screen>
        <ErrorText error={error} />
        <Empty>Ce profil n’est pas disponible.</Empty>
        <Button variant="secondary" label="Fermer" onPress={() => router.back()} />
      </Screen>
    );
  }

  const fullName = [data.first_name, data.last_name].filter(Boolean).join(' ');
  const phone = data.phone ? `+${data.phone.replace(/^\+/, '')}` : null;
  return (
    <Screen>
      <View style={{ alignItems: 'center', gap: 8 }}>
        <Avatar id={data.id} name={data.display_name} photo={data.avatar_url} size={112} profile={false} />
        <Title>{data.display_name || 'Profil à compléter'}</Title>
        {fullName ? <T muted size={17}>{fullName}</T> : null}
        <T muted size={13}>{data.root ? '👑 Root' : roleLabel[data.role] ?? data.role}{data.me ? ' · c’est toi' : ''}</T>
      </View>
      {phone ? (
        <Card>
          <T muted size={13}>Numéro</T>
          <T weight="bold" size={17}>{phone}</T>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button small label="Appeler" style={{ flex: 1 }} onPress={() => void Linking.openURL(`tel:${phone}`)} />
            <Button small variant="secondary" label="Message" style={{ flex: 1 }} onPress={() => void Linking.openURL(`sms:${phone}`)} />
          </View>
        </Card>
      ) : null}
      {data.groups.length ? (
        <Section title={data.me ? 'Mes groupes' : 'Groupes en commun'}>
          <T>{data.groups.join(' · ')}</T>
        </Section>
      ) : null}
      {data.me ? (
        <T muted size={13}>Ton nom et ton numéro restent cachés tant que tu ne choisis pas de les montrer (Mon profil, Groupes).</T>
      ) : null}
    </Screen>
  );
}
