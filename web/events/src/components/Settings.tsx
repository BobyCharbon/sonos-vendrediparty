import { router, type Href } from 'expo-router';
import { Pressable, View } from 'react-native';

import { useAuth } from '@/lib/auth';
import { discussionsOn } from '@/lib/features';
import { useShellFeedback } from '@/lib/shellFeedback';
import { hasCompleteIdentity } from '@/lib/profile';
import { roleName, roleRank } from '@/lib/roles';
import { AppInviteCard } from './AppInviteCard';
import { ZicouBubbleToggle } from './ZicouBubbleToggle';
import { IdentityForm } from './IdentityForm';
import { MoonBanner, MoonButton, usePause } from './NotificationPause';
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
  const { profile, signOut, can, rank, isAdmin, eventsOpen } = useAuth();
  const pause = usePause();
  const feedback = useShellFeedback();
  if (!profile) return null;
  const complete = hasCompleteIdentity(profile);
  const active = eventsOpen && complete;
  const status = profile.status === 'banned' ? 'Accès retiré' : rank >= 99 ? 'Root' : roleName(profile.role);

  return (
    <Screen edges={topInset ? ['top'] : []}>
      {/* Lune en haut à droite (avis de l'admin) : pause de toutes les notifications, sauf celles d'admin. */}
      <View style={{ zIndex: 20 }}>
        <Title>Réglages</Title>
        <MoonButton pause={pause} />
      </View>
      <MoonBanner pause={pause} />
      {/* Carte du compte : comme l'identifiant Apple en tête des Réglages, elle ouvre « Mon profil ». */}
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={`Mon profil : ${profile.display_name || 'profil à compléter'}`}
        disabled={!complete}
        onPress={() => router.push('/settings/profile')}
        style={({ pressed }) => [s.card, s.row, { gap: 14 }, pressed && { backgroundColor: colors.surface2 }]}
      >
        <Avatar id={profile.id} name={profile.display_name || '?'} photo={profile.avatar_url} size={60} profile={false} />
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
        {active ? <T muted size={14}>{can('events.view') ? `Tu fais partie du groupe Vendredi Party : événements, sondages${discussionsOn ? ' et discussions' : ''}.` : 'Tu vois les événements publics et ceux où on t’invite.'}</T> : null}
        {eventsOpen && !complete ? <T muted size={14}>Complète ton profil (prénom, nom et surnom) pour voir les événements.</T> : null}
        {profile.status === 'banned' ? <T muted size={14}>Ton accès a été retiré par un admin.</T> : null}
        {active ? <Button label="Voir les événements" variant="secondary" onPress={() => openPartyTab('events')} /> : null}
      </Section>

      {/* Inviter des amis dans Party (avis 84fab3987f68) : tout rôle qui a le droit « Inviter dans Party ». */}
      {complete && can('members.invite') ? <AppInviteCard /> : null}

      <Card style={{ gap: 0, paddingVertical: 4 }}>
        {active ? (
          <>
            <LinkRow icon="🔔" tint="#FF5A5F" label="Notifications" hint="Ce que tu reçois, quand ; catégories et tags suivis" onPress={() => router.push('/settings/notifications')} />
            <RowDivider />
            <LinkRow icon="👥" tint="#0A84FF" label="Groupes" hint="Les groupes dont tu fais partie ; crée les tiens" onPress={() => router.push('/groups')} />
            <RowDivider />
          </>
        ) : null}
        {isAdmin ? (
          <>
            <LinkRow icon="🛡️" tint="#5E5CE6" label="Administration" hint="Demandes, membres, rôles et droits" onPress={() => router.push('/admin')} />
            <RowDivider />
            {rank >= roleRank('admin') ? (
              <>
                {/* Avis 0abef7ffe7ba (13.11) : les connexions récentes en un toucher depuis les Réglages. */}
                <LinkRow icon="🕒" tint="#30B0C7" label="Connexions récentes" hint="Qui s’est connecté aujourd’hui, hier, cette semaine" onPress={() => router.push('/admin/users')} />
                <RowDivider />
              </>
            ) : null}
          </>
        ) : null}
        {can('party.admin') && can('party.settings') ? (
          <>
            {/* Page de Party (hors du module) : ce qui concerne toute la soirée, pas seulement la musique. */}
            <LinkRow icon="👥" tint="#0A84FF" label="Invités, messages et notifications" hint="Messages des invités, invités, bannis, notifications de l’hôte" onPress={() => openPartyTab('host')} />
            <RowDivider />
            {/* Avis eb710b132330 : un message pour tout le monde (maintenance, information, annonce), sur tous les onglets. */}
            <LinkRow icon="📣" tint="#FF9F0A" label="Annonce et maintenance" hint="Un message pour tout le monde, sur tous les onglets" onPress={() => openPartyTab('notice')} />
            <RowDivider />
            {/* Page admin de Party (hors du module) : entrée avec le compte, sans code PIN. Gardée en secours. */}
            <LinkRow icon="🎛️" tint="#636366" label="Admin de la soirée" hint="Musique, enceintes, joueurs, jeux et réglages du site" onPress={() => { window.top!.location.href = '/admin'; }} />
            <RowDivider />
          </>
        ) : null}
        {/* Page de Party (hors du module) : un onglet par jeu (Purify Test pour commencer), à montrer si on veut. */}
        <LinkRow icon="🏆" tint="#FF9F0A" label="Mes stats de jeu" hint="Purify Test : ton dernier score, ton radar et ton record" onPress={() => openPartyTab('stats')} />
        <RowDivider />
        {/* « Ton avis » : Guest+ et au-dessus (droit « Écrire un avis »), et l’hôte (« Retours »). Sorti de la barre
            d’onglets le 4.11 (onglet Zicou) : la pastille des avis à traiter / réponses reçues est sur cette ligne. */}
        {can('feedback.write') || feedback?.allowed ? (
          <>
            <LinkRow icon="💬" tint="#30D158" label={feedback?.label ?? 'Ton avis'}
              hint={feedback?.label === 'Retours' ? 'Les idées et bugs des invités ; ton avis aussi' : 'Une idée, un bug ? Écris à l’organisateur'}
              badge={feedback?.badge} onPress={() => openPartyTab('feedback')} />
            <RowDivider />
          </>
        ) : null}
        <LinkRow icon="🔒" tint="#0A84FF" label="Confidentialité" hint="Personnes bloquées, conditions d’utilisation, tes données" onPress={() => router.push('/settings/privacy')} />
        <RowDivider />
        <LinkRow icon="⚙️" tint="#636366" label="Gérer mon compte" hint="Suppression du compte" onPress={() => router.push('/settings/account')} />
      </Card>

      <ZicouBubbleToggle />

      <Button label="Se déconnecter" variant="danger" onPress={signOut} />
    </Screen>
  );
}
