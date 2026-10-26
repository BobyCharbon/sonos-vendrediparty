import { router, type Href } from 'expo-router';
import { Pressable, View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { hasCompleteIdentity } from '@/lib/profile';
import { roleLabel } from '@/lib/types';
import { IdentityForm } from './IdentityForm';
import { SignedIn } from './SignedIn';
import { Avatar, Button, Card, LinkRow, RowDivider, s, Screen, Section, T, Title } from './ui';
import { colors } from '@/lib/theme';

/** Demande à la page Party qui entoure le module d'ouvrir un de ses onglets (Ton avis, Événements…). */
export function openPartyTab(tab: string, path?: string) {
  if (typeof window === 'undefined') return;
  if (window.parent !== window) window.parent.postMessage({ type: 'party-events:open-tab', tab, path }, location.origin);
  else if (path) router.push(path as Href);
}

/** Réglages du compte Party : profil (prénom, nom, surnom, photo), accès aux événements, notifications, compte. */
export function Settings({ topInset = false }: { topInset?: boolean }) {
  const { profile, signOut, can, rank, isAdmin, eventsOpen, eventsSoon } = useAuth();
  if (!profile) return null;
  const complete = hasCompleteIdentity(profile);
  const active = eventsOpen && complete;
  const status = profile.status === 'banned' ? 'Accès retiré' : rank >= 99 ? 'Root' : roleLabel[profile.role];

  return (
    <Screen edges={topInset ? ['top'] : []}>
      <Title>Réglages</Title>
      {/* Carte du compte : comme l'identifiant Apple en tête des Réglages, elle ouvre « Mon profil ». */}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Mon profil : ${profile.display_name || 'profil à compléter'}`}
        disabled={!complete}
        onPress={() => router.push('/settings/profile')}
        style={({ pressed }) => [s.card, s.row, { gap: 14 }, pressed && { backgroundColor: colors.surface2 }]}
      >
        <Avatar id={profile.id} name={profile.display_name || '?'} photo={profile.avatar_url} size={60} />
        <View style={{ flex: 1, gap: 2 }}>
          <T weight="bold" size={19}>{profile.display_name || 'Profil à compléter'}</T>
          <T muted size={13}>{status}{profile.phone ? ` · +${profile.phone.replace(/^\+/, '')}` : ''}</T>
          {complete ? <T muted size={13}>Mon profil : surnom, photo, prénom et nom</T> : null}
        </View>
        {complete ? <View style={{ width: 8, height: 8, borderRightWidth: 2, borderTopWidth: 2, borderColor: colors.muted, opacity: 0.7, transform: [{ rotate: '45deg' }] }} /> : null}
      </Pressable>

      {/* Profil incomplet : le formulaire reste ici, c'est la seule chose à faire. */}
      {!complete ? (
        <Section title="Complète ton profil">
          <T muted size={14}>Ton surnom et ta photo apparaîtront dans les jeux et les événements.</T>
          <IdentityForm profile={profile} submitLabel="Enregistrer" />
        </Section>
      ) : null}

      <Section title="Événements du groupe">
        {active ? <T muted size={14}>{can('events.view') ? 'Tu fais partie du groupe Vendredi Party : événements, sondages et discussions.' : 'Tu vois les événements publics et ceux où on t’invite.'}</T> : null}
        {eventsOpen && !complete ? <T muted size={14}>Complète ton profil (prénom, nom, surnom et photo) pour voir les événements.</T> : null}
        {profile.status === 'banned' ? <T muted size={14}>Ton accès a été retiré par un admin.</T> : null}
        {active ? <Button label="Voir les événements" variant="secondary" onPress={() => openPartyTab('events')} /> : eventsSoon && profile.status !== 'banned' ? <SignedIn /> : null}
      </Section>

      <Card style={{ gap: 0, paddingVertical: 4 }}>
        {active ? (
          <>
            <LinkRow icon="🔔" tint="#FF5A5F" label="Notifications et abonnements" hint="Ce que tu reçois, quand, et les catégories ou tags que tu suis" onPress={() => router.push('/settings/notifications')} />
            <RowDivider />
          </>
        ) : null}
        {isAdmin ? (
          <>
            <LinkRow icon="🛡️" tint="#5E5CE6" label="Administration" hint="Demandes, membres, rôles et droits" onPress={() => router.push('/admin')} />
            <RowDivider />
          </>
        ) : null}
        {can('party.admin') && can('party.settings') ? (
          <>
            {/* Page de Party (hors du module) : ce qui concerne toute la soirée, pas seulement la musique. */}
            <LinkRow icon="👥" tint="#0A84FF" label="Invités, messages et notifications" hint="Messages des invités, invités, bannis, notifications de l’hôte" onPress={() => openPartyTab('host')} />
            <RowDivider />
            {/* Page admin de Party (hors du module) : entrée avec le compte, sans code PIN. Gardée en secours. */}
            <LinkRow icon="🎛️" tint="#636366" label="Admin de la soirée" hint="Musique, enceintes, joueurs, jeux et réglages du site" onPress={() => { window.top!.location.href = '/admin'; }} />
            <RowDivider />
          </>
        ) : null}
        {/* Page de Party (hors du module) : un onglet par jeu (Purify Test pour commencer), à montrer si on veut. */}
        <LinkRow icon="🏆" tint="#FF9F0A" label="Mes stats de jeu" hint="Purify Test : ton dernier score, ton radar et ton record" onPress={() => openPartyTab('stats')} />
        <RowDivider />
        <LinkRow icon="💬" tint="#30D158" label="Ton avis" hint="Une idée, un bug ? Écris à l’organisateur" onPress={() => openPartyTab('feedback')} />
        <RowDivider />
        <LinkRow icon="🔒" tint="#0A84FF" label="Confidentialité" hint="Tes données et tes choix" onPress={() => router.push('/privacy')} />
        <RowDivider />
        <LinkRow icon="⚙️" tint="#636366" label="Gérer mon compte" hint="Suppression du compte" onPress={() => router.push('/settings/account')} />
      </Card>

      <Button label="Se déconnecter" variant="danger" onPress={signOut} />
    </Screen>
  );
}
