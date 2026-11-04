import { router, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Linking, View } from 'react-native';

import { InvitedBySection } from '@/components/InvitedBy';
import { ReportSheet } from '@/components/ReportSheet';
import { ZicouOnProfile } from '@/components/ZicouOnProfile';
import { Avatar, Button, Card, Cascade, ConfirmButton, Empty, ErrorText, Loading, Reveal, Screen, Section, T, Title } from '@/components/ui';
import { personLabel, useContactNames } from '@/lib/contactNames';
import { useQuery } from '@/lib/data';
import { discussionsOn } from '@/lib/features';
import { supabase } from '@/lib/supabase';
import { roleName } from '@/lib/roles';
import { type MemberRole } from '@/lib/types';
import { addToContacts } from '@/lib/vcard';
import { setBlocked, type ReportTarget } from '@/lib/moderation';

const MEMBER_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;

type MemberCard = {
  id: string;
  display_name: string;
  avatar_url: string | null;
  role: MemberRole;
  /** Nom du rôle (rôles personnalisés, migration custom_roles) ; absent sur une base plus ancienne. */
  role_label?: string | null;
  root: boolean;
  me: boolean;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  groups: string[];
  /** Ce membre m'a bloqué : fiche réduite au surnom (modération commune). */
  restricted?: boolean;
  /** Je l'ai bloqué. */
  blocked?: boolean;
};

/** Fiche profil d'un membre : photo, surnom, rôle, groupes en commun ; nom et numéro selon les choix de la personne
 * (la base applique ces choix : rien n'arrive ici qu'on n'ait pas le droit de voir). */
export default function MemberScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const valid = typeof id === 'string' && MEMBER_ID.test(id);
  const { data, error, loading, reload } = useQuery(async () => {
    if (!valid) return null;
    const { data, error } = await supabase.rpc('member_card', { target: id });
    if (error) throw new Error(error.message);
    return (data as MemberCard | null) ?? null;
  }, [id]);
  const contacts = useContactNames();
  const [writeError, setWriteError] = useState<string | null>(null);
  const [opening, setOpening] = useState(false);
  const [report, setReport] = useState<ReportTarget | null>(null);
  const [blockError, setBlockError] = useState<string | null>(null);

  /** Blocage commun à toute l'app : plus de message direct, de citation, d'invitation ni de fiche détaillée. */
  async function toggleBlock(next: boolean) {
    setBlockError(null);
    try {
      await setBlocked(id, next);
      reload();
    } catch (e) {
      setBlockError(e instanceof Error ? e.message : 'Le blocage n’a pas pu être enregistré.');
    }
  }

  /** « Écrire » : la conversation privée à deux avec ce membre (créée au besoin, une seule par paire). */
  async function write() {
    setWriteError(null);
    setOpening(true);
    const { data: chat, error } = await supabase.rpc('start_direct_chat', { target: id });
    setOpening(false);
    if (error || typeof chat !== 'string') {
      return setWriteError('Tu ne peux pas écrire à cette personne (il faut un groupe ou un événement en commun).');
    }
    router.push(`/chats/${chat}`);
  }

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
  const known = personLabel(contacts, data.me ? null : data.id, data.display_name);
  const inContacts = !!known.secondary || (!data.me && !!contacts[data.id]);
  return (
    <Screen>
      {/* Fiche : la photo se pose, puis le reste monte en cascade. */}
      <Cascade>
      <View style={{ alignItems: 'center', gap: 8 }}>
        <Reveal kind="pop"><Avatar id={data.id} name={data.display_name} photo={data.avatar_url} size={112} profile={false} /></Reveal>
        {/* App iPhone : le nom de mon répertoire en titre, le pseudo dessous (avis f780431defe7). */}
        <Title>{known.primary || 'Profil à compléter'}</Title>
        {known.secondary ? <T muted size={15}>{known.secondary} · dans tes contacts</T> : null}
        {fullName ? <T muted size={17}>{fullName}</T> : null}
        <T muted size={13}>{data.root ? '👑 Root' : (data.role_label ?? roleName(data.role))}{data.me ? ' · c’est toi' : ''}</T>
        {/* Message direct : seulement quand les Discussions existent (site de test ; absentes en production). */}
        {!data.me && discussionsOn && !data.blocked && !data.restricted ? (
          <Button small label="💬 Écrire" loading={opening}
            onPress={() => void write()} />
        ) : null}
        <ErrorText error={writeError} />
      </View>
      {/* Son Zicou (bêta) : vedette s'il en a un, œuf terne sinon ; rien si bloqué ou Zicou éteint. */}
      {!data.restricted && !data.blocked ? <ZicouOnProfile memberId={data.id} /> : null}
      {phone ? (
        <Card>
          <T muted size={13}>Numéro</T>
          <T weight="bold" size={17}>{phone}</T>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button small label="Appeler" style={{ flex: 1 }} onPress={() => void Linking.openURL(`tel:${phone}`)} />
            <Button small variant="secondary" label="Message" style={{ flex: 1 }} onPress={() => void Linking.openURL(`sms:${phone}`)} />
          </View>
          {!data.me && !inContacts ? (
            // vCard préremplie (numéro, nom public sinon pseudo) ; dans l'app iPhone, la fiche Contacts d'Apple.
            <Button small variant="ghost" label="Ajouter aux contacts"
              onPress={() => void addToContacts({ phone, firstName: data.first_name, lastName: data.last_name, nickname: data.display_name })} />
          ) : null}
        </Card>
      ) : !data.me && !data.restricted ? (
        <T muted size={13}>{data.display_name || 'Ce membre'} ne montre pas son numéro dans vos groupes : impossible de l’ajouter aux contacts depuis Party.</T>
      ) : null}
      {data.groups.length ? (
        <Section title={data.me ? 'Mes groupes' : 'Groupes en commun'}>
          <T>{data.groups.join(' · ')}</T>
        </Section>
      ) : null}
      {/* Qui l'a invité (lien Party, groupe, événement) : admins seulement (droit « Voir qui a invité qui »). */}
      {!data.me ? <InvitedBySection id={data.id} /> : null}
      {!data.me ? (
        <Section title="Confidentialité">
          {data.blocked ? (
            <Button small variant="secondary" label={`Débloquer ${data.display_name || 'ce membre'}`} onPress={() => void toggleBlock(false)} />
          ) : (
            <ConfirmButton small label={`Bloquer ${data.display_name || 'ce membre'}`} confirmLabel="Confirmer le blocage" onConfirm={() => toggleBlock(true)} />
          )}
          <T muted size={12}>Une personne bloquée ne peut plus t’écrire, te citer, t’inviter ni voir ta fiche ; elle n’en est pas prévenue.</T>
          <View style={{ flexDirection: 'row', gap: 8, flexWrap: 'wrap' }}>
            <Button small variant="ghost" label="Signaler le profil" onPress={() => setReport({ kind: 'profile', id: data.id, label: data.display_name || 'ce profil' })} />
            {data.avatar_url ? (
              <Button small variant="ghost" label="Signaler la photo" onPress={() => setReport({ kind: 'profile_photo', id: data.id, label: 'la photo de profil' })} />
            ) : null}
          </View>
          <ErrorText error={blockError} />
        </Section>
      ) : null}
      <ReportSheet target={report} onClose={() => setReport(null)} />
      {data.me ? (
        <T muted size={13}>Ton nom et ton numéro restent cachés tant que tu ne choisis pas de les montrer (Mon profil, Groupes).</T>
      ) : null}
      </Cascade>
    </Screen>
  );
}
