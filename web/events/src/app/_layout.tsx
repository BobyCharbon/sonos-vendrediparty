import { BricolageGrotesque_800ExtraBold } from '@expo-google-fonts/bricolage-grotesque';
import { useFonts } from 'expo-font';
import { DarkTheme, router, Stack, ThemeProvider, usePathname, type ErrorBoundaryProps, type Href } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { PendingInviteClaim } from '@/components/AppJoinScreen';
import { Button, ErrorText, HeaderBack, Loading, Screen, T, Title } from '@/components/ui';
import { useEdgeSwipeBack } from '@/lib/edgeSwipe';
import { usePendingSync } from '@/lib/pending';
import { hasCompleteIdentity } from '@/lib/profile';
import { AuthProvider, useAuth } from '@/lib/auth';
import { enableWebPush } from '@/lib/push';
import { sweepNativeCalendar } from '@/lib/calendar';
import { ShellSafeArea } from '@/lib/shellInsets';
import { colors, font } from '@/lib/theme';

const theme = {
  ...DarkTheme,
  colors: { ...DarkTheme.colors, background: colors.bg, card: colors.bg, text: colors.text, primary: colors.accent, border: colors.line },
};

export function ErrorBoundary({ retry }: ErrorBoundaryProps) {
  return (
    <SafeAreaProvider>
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
        <Title>La page n’a pas pu s’ouvrir</Title>
        <T muted>Réessaie pour reprendre ta navigation. Si tu venais d’enregistrer, vérifie ton événement avant de recommencer.</T>
        <Button label="Réessayer" onPress={retry} />
      </Screen>
    </SafeAreaProvider>
  );
}

/** Réponses attendues : calculées tant que le membre a accès aux sorties, quel que soit l’écran ouvert. */
function PendingSync({ me }: { me: string }) {
  usePendingSync(me);
  return null;
}

/** Titre de l’écran précédent pour le bouton ‹ (les onglets internes s’appellent « Événements »). */
function backLabel(label?: string) {
  return label && !label.startsWith('(') ? label : label?.startsWith('(') ? 'Événements' : 'Retour';
}

const intentKey = 'party-events-destination';
// Dans la page Party, l'onglet porte déjà le grand titre (« Discussions ») : pas d'en-tête en double.
function inPartyShell(): boolean {
  return typeof window !== 'undefined' && window.parent !== window;
}

const validDestination = /^\/(?:event\/[a-f0-9-]{36}(?:\/chat|\/edit|\/invite|\/gifts|\/scan(?:\/[a-f0-9]{64})?)?|share\/[a-f0-9-]{36}|invite\/[a-f0-9-]{36}|group-invite\/[a-f0-9-]{36}|join\/[a-f0-9-]{36}|admin(?:\/members|\/journal|\/users|\/roles|\/taxonomy|\/announcements)?|groups|chats(?:\/[a-f0-9-]{36})?|activity|announcements|account|admin\/reports|terms|settings\/(?:notifications|subscriptions|profile|privacy))$/i;
/** Pages de passage (accueil du module, connexion, « Faisons connaissance ») : seules à reprendre l'intention gardée. */
const transitPath = /^\/?(?:sign-in|welcome)?$/i;

/** Page demandée à l'ouverture. L'adresse ouverte prime toujours : une autre page précise (/share/B, /privacy…)
 * remplace ou efface l'intention gardée (campagne 2, 07.11 : le lien A ressortait à la place de B, « Lien indisponible »
 * en boucle). /share/<id> est gardée (10.11) : après la connexion SMS, on revient sur l'événement au lieu de l'accueil. */
function initialDestination(): string | null {
  if (typeof window === 'undefined') return null;
  const path = location.pathname.replace(/^\/events(?=\/|$)/, '');
  try {
    if (validDestination.test(path)) { sessionStorage.setItem(intentKey, path); return path; }
    if (!transitPath.test(path)) { sessionStorage.removeItem(intentKey); return null; }
    const previous = sessionStorage.getItem(intentKey);
    return previous && validDestination.test(previous) ? previous : null;
  } catch { return validDestination.test(path) ? path : null; }
}

/** Intention servie : elle ne ressert plus à la prochaine ouverture (elle reste en mémoire pour l'après-connexion). */
function forgetStoredIntent() {
  try { sessionStorage.removeItem(intentKey); } catch { /* Stockage indisponible. */ }
}

function Gate() {
  const { loading, session, profile, profileError, refreshProfile, signOut, eventsOpen } = useAuth();
  // Tout compte actif au profil complet ouvre les sorties qu'il voit (Guests : publiques et invitations) ;
  // hors bêta ou profil incomplet : page d'accueil, Réglages ouverts.
  const active = eventsOpen && hasCompleteIdentity(profile);
  const path = usePathname();
  const [initialIntent] = useState(initialDestination);
  const intent = useRef(initialIntent);
  const [asked, setAsked] = useState(0);
  const shared = useRef<string | null>(null);
  useEdgeSwipeBack();
  // App iPhone : dates de sondage « À confirmer » dans le calendrier ; une fois par connexion, le ménage des sondages
  // tranchés ou annulés depuis (avis 9ddbdea7fe8f).
  const sweptFor = useRef<string | null>(null);
  useEffect(() => {
    const uid = session?.user.id ?? null;
    if (!uid || !active || sweptFor.current === uid) return;
    sweptFor.current = uid;
    void sweepNativeCalendar();
  }, [session?.user.id, active]);
  // Page Party autour du module : elle demande une page (onglet Événements ou Réglages) et suit la connexion.
  useEffect(() => {
    if (typeof window === 'undefined' || window.parent === window) return;
    const onMessage = (e: MessageEvent) => {
      if (e.origin !== location.origin || e.data?.type !== 'party-shell:navigate') return;
      const target = String(e.data.path || '/');
      if (target !== '/' && !validDestination.test(target)) return;
      intent.current = target;
      setAsked((n) => n + 1);
    };
    window.addEventListener('message', onMessage);
    window.parent.postMessage({ type: 'party-events:ready', path: location.pathname.replace(/^\/events(?=\/|$)/, '') || '/' }, location.origin);
    return () => window.removeEventListener('message', onMessage);
  }, []);
  // Party a appris un changement d'accès (bêta-testeur coché ou retiré) : on relit les droits tout de suite.
  useEffect(() => {
    if (typeof window === 'undefined') return;
    const onRefresh = (e: MessageEvent) => {
      if (e.origin === location.origin && e.data?.type === 'party-shell:refresh') void refreshProfile();
      // Accueil de Zicou (pet/zicou-home.js) : la page a déjà obtenu l’autorisation, on abonne cet appareil au compte.
      if (e.origin === location.origin && e.data?.type === 'party-shell:enable-push') void enableWebPush().catch(() => undefined);
    };
    window.addEventListener('message', onRefresh);
    return () => window.removeEventListener('message', onRefresh);
  }, [refreshProfile]);
  useEffect(() => {
    if (typeof window !== 'undefined' && window.parent !== window) window.parent.postMessage({ type: 'party-events:account' }, location.origin);
  }, [session?.user.id, profile?.display_name, profile?.avatar_url, profile?.status]);
  useEffect(() => {
    // Réglages : ouverts à tout compte connecté ; le reste attend la validation du membre.
    // Réglages, liens d'invitation et lien public : ouverts dès la connexion (ils demandent eux-mêmes le profil complet).
    const open = intent.current === '/account' || /^\/(?:(?:group-)?invite|join|share)\//.test(intent.current ?? '');
    if (!loading && session && (active || open) && !profileError && intent.current) {
      const target = intent.current;
      intent.current = null;
      forgetStoredIntent();
      if (path !== target) requestAnimationFrame(() => router.replace(target as Href));
    }
  }, [loading, session, active, profileError, path, asked]);

  useEffect(() => {
    // Lien d'un événement ouvert par un visiteur ou un invité : la page publique (une fois par connexion,
    // pour laisser aller à la connexion SMS ; l'intention reste en mémoire jusqu'à l'entrée dans le groupe).
    const id = intent.current?.match(/^\/event\/([a-f0-9-]{36})$/i)?.[1];
    const key = `${session?.user.id ?? ''}|${id}`;
    if (loading || profileError || active || !id || shared.current === key) return;
    shared.current = key;
    forgetStoredIntent();
    requestAnimationFrame(() => router.replace(`/share/${id}` as Href));
  }, [loading, session, active, profileError, asked]);

  // Invitation à un événement (v2) : la connexion par SMS se fait sur la page même ; on ne démonte pas l'écran pendant
  // que le profil se charge (sinon la réponse en cours est perdue et le routeur repart ailleurs).
  if (loading && !(session && /^\/invite\//.test(path))) return <Loading />;
  if (profileError && session) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center' }}>
        <Title>Connexion interrompue</Title>
        <ErrorText error={profileError} />
        <Button label="Réessayer" onPress={refreshProfile} />
        <Button label="Se déconnecter" variant="ghost" onPress={signOut} />
      </Screen>
    );
  }

  return (
    <>
    {session && active && profile ? <PendingSync me={profile.id} /> : null}
    {session && hasCompleteIdentity(profile) ? <PendingInviteClaim key={session.user.id} /> : null}
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerTitleStyle: { ...font.bold },
        headerShadowVisible: false,
        headerTitleAlign: 'center',
        contentStyle: { backgroundColor: colors.bg },
        // ‹ et nom de l’écran précédent, comme sur iPhone (la liste s’appelle « Événements »).
        headerLeft: ({ canGoBack, label }) => (canGoBack
          ? <HeaderBack label={backLabel(label)} onPress={() => router.back()} />
          : undefined),
      }}
    >
      <Stack.Protected guard={!!session && active}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="event/new" options={{ title: 'Proposer un événement', presentation: 'modal' }} />
        <Stack.Screen name="event/[id]/index" options={{ title: '' }} />
        <Stack.Screen name="event/[id]/edit" options={{ title: 'Modifier', presentation: 'modal' }} />
        <Stack.Screen name="event/[id]/chat" options={{ title: 'Discussion' }} />
        <Stack.Screen name="event/[id]/scan/index" options={{ title: 'Entrée' }} />
        <Stack.Screen name="event/[id]/scan/[token]" options={{ title: 'Entrée' }} />
        <Stack.Screen name="event/[id]/gifts" options={{ title: 'Cadeaux de l’événement' }} />
        {/* Étape 2 de l'assistant IA : connecté seulement (sinon la page plantait au lieu de demander la connexion). */}
        <Stack.Screen name="event/[id]/invite" options={{ title: 'Qui est invité' }} />
        <Stack.Screen name="settings/notifications" options={{ title: 'Notifications et abonnements' }} />
        <Stack.Screen name="settings/subscriptions" options={{ title: 'Notifications et abonnements' }} />
        <Stack.Screen name="groups" options={{ title: 'Groupes' }} />
        <Stack.Screen name="chats/index" options={{ title: 'Discussions', headerShown: !inPartyShell() }} />
        <Stack.Screen name="chats/[id]" options={{ title: 'Discussion' }} />
        <Stack.Screen name="member/[id]" options={{ title: 'Profil', presentation: 'modal' }} />
        <Stack.Screen name="admin/index" options={{ title: 'Administration' }} />
        <Stack.Screen name="admin/members" options={{ title: 'Membres' }} />
        <Stack.Screen name="admin/journal" options={{ title: 'Journal des membres' }} />
        <Stack.Screen name="admin/users" options={{ title: 'Utilisateurs' }} />
        <Stack.Screen name="admin/roles" options={{ title: 'Rôles et droits' }} />
        <Stack.Screen name="admin/taxonomy" options={{ title: 'Catégories et tags' }} />
        <Stack.Screen name="admin/announcements" options={{ title: 'Annonces admin' }} />
        <Stack.Screen name="admin/reports" options={{ title: 'Signalements' }} />
        <Stack.Screen name="announcements" options={{ title: 'Annonces admin' }} />
      </Stack.Protected>
      <Stack.Protected guard={!!session && !active}>
        <Stack.Screen name="welcome" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Protected guard={!session}>
        <Stack.Screen name="sign-in" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Protected guard={!!session}>
        <Stack.Screen name="account" options={{ headerShown: false, title: 'Réglages' }} />
        <Stack.Screen name="settings/profile" options={{ title: 'Mon profil' }} />
        <Stack.Screen name="settings/account" options={{ title: 'Mon compte' }} />
        <Stack.Screen name="settings/privacy" options={{ title: 'Confidentialité' }} />
      </Stack.Protected>
      <Stack.Screen name="share/[id]" options={{ title: '' }} />
      {/* Liens d'invitation (événement sur invitation, groupe) : lisibles avant connexion. */}
      <Stack.Screen name="invite/[token]" options={{ title: 'Invitation' }} />
      <Stack.Screen name="group-invite/[token]" options={{ title: 'Invitation' }} />
      {/* Lien personnel d'invitation dans Party (« X t'invite sur Party ») : lisible avant connexion. */}
      <Stack.Screen name="join/[token]" options={{ title: 'Invitation' }} />
      <Stack.Screen name="privacy" options={{ title: 'Confidentialité' }} />
      {/* Conditions d'utilisation : lisibles par tous, même sans compte (Apple 1.2, Google UGC). */}
      <Stack.Screen name="terms" options={{ title: 'Conditions d’utilisation' }} />
    </Stack>
    </>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({ BricolageGrotesque_800ExtraBold });

  return (
    <SafeAreaProvider>
      <ThemeProvider value={theme}>
        <StatusBar style="light" />
        <ShellSafeArea>
          <AuthProvider>{fontsLoaded ? <Gate /> : <Loading />}</AuthProvider>
        </ShellSafeArea>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
