import { router, type Href } from 'expo-router';
import { View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { hasCompleteIdentity } from '@/lib/profile';
import { roleLabel } from '@/lib/types';
import { IdentityForm } from './IdentityForm';
import { JoinRequest } from './JoinRequest';
import { Avatar, Button, Card, LinkRow, s, Screen, Section, T, Title } from './ui';

/** Demande à la page Party qui entoure le module d'ouvrir un de ses onglets (Ton avis, Événements…). */
export function openPartyTab(tab: string, path?: string) {
  if (typeof window === 'undefined') return;
  if (window.parent !== window) window.parent.postMessage({ type: 'party-events:open-tab', tab, path }, location.origin);
  else if (path) router.push(path as Href);
}

/** Réglages du compte Party : profil (prénom, nom, surnom, photo), accès aux événements, notifications, compte. */
export function Settings({ topInset = false }: { topInset?: boolean }) {
  const { profile, signOut, can, rank, isAdmin, eventsSoon } = useAuth();
  if (!profile) return null;
  const active = can('events.view');
  const complete = hasCompleteIdentity(profile);
  const status = profile.status === 'banned' ? 'Accès retiré' : rank >= 99 ? 'Root' : roleLabel[profile.role];

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
        {active ? <T muted size={14}>Tu fais partie du groupe : sorties, sondages et discussions.</T> : null}
        {profile.status === 'banned' ? <T muted size={14}>Ton accès a été retiré par un admin.</T> : null}
        {eventsSoon ? <T muted size={14}>Tu fais partie du groupe. Les sorties arrivent bientôt : elles sont pour l’instant réservées aux bêta-testeurs.</T> : null}
        {active ? <Button label="Voir les sorties" variant="secondary" onPress={() => openPartyTab('events')} /> : eventsSoon ? null : <JoinRequest />}
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
        {isAdmin ? (
          <>
            <LinkRow label="Administration" hint="Demandes, membres, rôles et droits" onPress={() => router.push('/admin')} />
            <View style={s.divider} />
          </>
        ) : null}
        {can('party.admin') && can('party.settings') ? (
          <>
            {/* Page de Party (hors du module) : ce qui concerne toute la soirée, pas seulement la musique. */}
            <LinkRow label="👥 Invités, messages et notifications" hint="Messages des invités, invités, bannis, notifications de l’hôte" onPress={() => openPartyTab('host')} />
            <View style={s.divider} />
            {/* Page admin de Party (hors du module) : entrée avec le compte, sans code PIN. Gardée en secours. */}
            <LinkRow label="🎛️ Admin de la soirée" hint="Musique, enceintes, joueurs, jeux et réglages du site" onPress={() => { window.top!.location.href = '/admin'; }} />
            <View style={s.divider} />
          </>
        ) : null}
        {/* Page de Party (hors du module) : dernier test et profil d'impureté, à montrer si on veut. */}
        <LinkRow label="😈 Mes stats Purify Test" hint="Ton dernier score d’impureté, ton radar et ton record" onPress={() => openPartyTab('purity')} />
        <View style={s.divider} />
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
