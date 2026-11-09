import { router, Stack } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Linking, View } from 'react-native';

import { IdentityForm } from '@/components/IdentityForm';
import { openPartyTab } from '@/components/Settings';
import { Avatar, Button, ErrorText, Loading, Screen, T, Title } from '@/components/ui';
import { appDownload, claimInvite, finalClaimError, forgetInvite, INVITE_TOKEN, pendingInvite, previewInvite, rememberInvite, type InvitePreview } from '@/lib/appInvite';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { hasCompleteIdentity } from '@/lib/profile';
import { discussionsOn } from '@/lib/features';
import { colors } from '@/lib/theme';

/** Lien personnel d'invitation dans Party (/events/join/<lien>), avis 84fab3987f68 :
 * 1. avant connexion : « Ludo t'invite sur Party » (surnom et photo seulement), l'app à télécharger, ou « Continuer
 *    sur le web » (inscription par SMS, le lien est gardé) ;
 * 2. connecté au profil incomplet : prénom, nom, surnom ici même (photo facultative) ;
 * 3. profil complet : le lien est réclamé une fois (la base vérifie : nouveau compte, pas soi-même) et l'inviteur prévenu.
 * Le lien ne donne aucun droit : le compte reste Guest. */
export function AppJoinScreen({ token }: { token: string | undefined }) {
  const { session, profile, refreshProfile } = useAuth();
  const valid = typeof token === 'string' && INVITE_TOKEN.test(token);
  const { data: preview, loading, error } = useQuery(async () => (valid ? previewInvite(token!) : null), [token]);

  if (!valid) return <Unavailable />;
  if (loading) return <Loading />;
  if (!preview) return <Unavailable error={error} />;
  if (!session) return <Welcome token={token!} preview={preview} />;
  if (!profile) return <Loading />;
  if (!hasCompleteIdentity(profile)) {
    return (
      <Screen contentStyle={{ gap: 20 }}>
        <Stack.Screen options={{ title: 'Invitation' }} />
        <View style={{ gap: 8 }}>
          <Title size={30}>Complète ton profil</Title>
          <T muted>Ton prénom, ton nom et ton surnom (une photo si tu veux) : {preview.inviter || 'ton ami'} te reconnaîtra tout de suite.</T>
        </View>
        <IdentityForm profile={profile} submitLabel="Continuer" onSaved={() => void refreshProfile()} />
      </Screen>
    );
  }
  return <Claim token={token!} preview={preview} />;
}

function Inviter({ preview }: { preview: InvitePreview }) {
  const name = preview.inviter || 'Un ami';
  return (
    <View style={{ alignItems: 'center', gap: 14 }}>
      <View style={{ borderRadius: 999, borderWidth: 3, borderColor: colors.accent, padding: 3 }}>
        <Avatar id="inviter" name={name} photo={preview.avatar_url} size={96} profile={false} />
      </View>
      <Title size={30} style={{ textAlign: 'center' }}>{`${name} t’invite sur Party`}</Title>
    </View>
  );
}

function Welcome({ token, preview }: { token: string; preview: InvitePreview }) {
  const download = appDownload();
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 22 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Inviter preview={preview} />
      <T muted style={{ textAlign: 'center' }}>
        {discussionsOn ? 'Événements, discussions de groupe, jeux et musique de la soirée' : 'Événements, jeux et musique de la soirée'} : rejoins tes amis sur Party.
        Il suffit de ton numéro de téléphone.
      </T>
      <View style={{ gap: 10 }}>
        <Button label={download.label} onPress={() => { rememberInvite(token); void Linking.openURL(download.url); }} />
        <Button label="Continuer sur le web" variant="secondary" onPress={() => { rememberInvite(token); router.push('/sign-in'); }} />
      </View>
      <T muted size={13} style={{ textAlign: 'center' }}>
        Après avoir installé l’app, rouvre ce lien : il t’emmène directement dans Party.
      </T>
    </Screen>
  );
}

/** Profil complet : réclamé une seule fois, puis « Bienvenue ». Un compte déjà ancien voit simplement Party. */
function Claim({ token, preview }: { token: string; preview: InvitePreview }) {
  const [state, setState] = useState<{ done: boolean; error: string | null }>({ done: false, error: null });
  const started = useRef(false);

  useEffect(() => {
    if (started.current) return;
    started.current = true;
    claimInvite(token)
      .then(() => { forgetInvite(); setState({ done: true, error: null }); })
      .catch((e: Error) => {
        if (finalClaimError(e.message)) forgetInvite();
        setState({ done: true, error: e.message });
      });
  }, [token]);

  if (!state.done) return <Loading />;
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 22 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Inviter preview={preview} />
      {state.error ? <ErrorText error={state.error} /> : (
        <T muted style={{ textAlign: 'center' }}>Bienvenue sur Party ! Ton compte est prêt.</T>
      )}
      <Button label="Ouvrir Party" onPress={() => openPartyTab('events', '/')} />
    </Screen>
  );
}

function Unavailable({ error }: { error?: string | null }) {
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Title>Lien indisponible</Title>
      <T muted>Ce lien d’invitation n’est plus valable : la personne qui l’a partagé l’a peut-être remplacé. Demande-lui son nouveau lien.</T>
      <ErrorText error={error ?? null} />
    </Screen>
  );
}

/** Inscription commencée par « Continuer sur le web » ailleurs que sur la page du lien (bienvenue, Réglages) : dès que
 * le profil est complet, le lien gardé est réclamé une fois, sans rien afficher. Erreur passagère : réessayé plus tard. */
export function PendingInviteClaim() {
  const started = useRef(false);
  useEffect(() => {
    const token = pendingInvite();
    const onJoinPage = typeof location !== 'undefined' && /\/join\//.test(location.pathname);
    if (!token || onJoinPage || started.current) return;
    started.current = true;
    claimInvite(token).then(forgetInvite).catch((e: Error) => { if (finalClaimError(e.message)) forgetInvite(); });
  }, []);
  return null;
}
