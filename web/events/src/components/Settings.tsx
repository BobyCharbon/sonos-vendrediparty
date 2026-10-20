import { router } from 'expo-router';
import { View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { hasCompleteIdentity } from '@/lib/profile';
import { IdentityForm } from './IdentityForm';
import { Avatar, Button, Card, LinkRow, s, Screen, Section, T, Title } from './ui';

const roleLabel = { admin: 'Admin', coadmin: 'Co-admin', member: 'Membre' } as const;

/** Demande à la page Party qui entoure le module d'ouvrir un de ses onglets (Ton avis, Événements…). */
export function openPartyTab(tab: string) {
  if (typeof window !== 'undefined' && window.parent !== window) window.parent.postMessage({ type: 'party-events:open-tab', tab }, location.origin);
}

/** Réglages du compte Party : profil (prénom, nom, surnom, photo), accès aux événements, notifications, compte. */
export function Settings({ topInset = false }: { topInset?: boolean }) {
  const { profile, signOut } = useAuth();
  if (!profile) return null;
  const active = profile.status === 'active';
  const complete = hasCompleteIdentity(profile);
  const status = profile.status === 'banned' ? 'Accès retiré' : active ? roleLabel[profile.role] : 'En attente de validation';

  return (
    <Screen edges={topInset ? ['top'] : []}>
      <Title>Réglages</Title>
      <Card>
        <View style={s.row}>
          <Avatar id={profile.id} name={profile.display_name || '?'} photo={profile.avatar_url} size={56} />
          <View style={{ flex: 1 }}>
            <T weight="bold" size={18}>{profile.display_name || 'Profil à compléter'}</T>
            <T muted size={13}>{status}{profile.phone ? ` · +${profile.phone.replace(/^\+/, '')}` : ''}</T>
          </View>
        </View>
      </Card>

      <Section title={complete ? 'Mon profil' : 'Complète ton profil'}>
        {!complete ? <T muted size={14}>Ton surnom et ta photo apparaîtront dans les jeux et les sorties.</T> : null}
        <IdentityForm profile={profile} submitLabel="Enregistrer" />
      </Section>

      <Section title="Événements du groupe">
        <T muted size={14}>{active
          ? 'Tu fais partie du groupe : sorties, sondages et discussions.'
          : profile.status === 'banned' ? 'Ton accès aux événements a été retiré.' : 'Un admin doit valider ton accès avant que tu voies les sorties.'}</T>
        {active ? <Button label="Voir les sorties" variant="secondary" onPress={() => openPartyTab('events')} /> : null}
      </Section>

      <Card style={{ gap: 0, paddingVertical: 4 }}>
        {active ? (
          <>
            <LinkRow label="Notifications" hint="Ce que tu reçois, et quand" onPress={() => router.push('/settings/notifications')} />
            <View style={s.divider} />
            <LinkRow label="Mes abonnements" hint="Catégories et tags qui t’intéressent" onPress={() => router.push('/settings/subscriptions')} />
            <View style={s.divider} />
          </>
        ) : null}
        <LinkRow label="Ton avis" hint="Une idée, un bug ? Écris à l’organisateur" onPress={() => openPartyTab('feedback')} />
        <View style={s.divider} />
        <LinkRow label="Confidentialité" hint="Tes données et tes choix" onPress={() => router.push('/privacy')} />
        <View style={s.divider} />
        <LinkRow label="Gérer mon compte" hint="Suppression du compte" onPress={() => router.push('/settings/account')} />
      </Card>

      <Button label="Se déconnecter" variant="danger" onPress={signOut} />
    </Screen>
  );
}
