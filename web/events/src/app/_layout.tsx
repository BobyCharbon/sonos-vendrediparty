import { BricolageGrotesque_800ExtraBold } from '@expo-google-fonts/bricolage-grotesque';
import { Figtree_400Regular, Figtree_500Medium, Figtree_600SemiBold, Figtree_700Bold } from '@expo-google-fonts/figtree';
import { useFonts } from 'expo-font';
import { DarkTheme, router, Stack, ThemeProvider, usePathname, type ErrorBoundaryProps, type Href } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { Button, ErrorText, Loading, Screen, T, Title } from '@/components/ui';
import { usePendingSync } from '@/lib/pending';
import { hasCompleteIdentity } from '@/lib/profile';
import { AuthProvider, useAuth } from '@/lib/auth';
import { ShellSafeArea } from '@/lib/shellInsets';
import { colors, fonts } from '@/lib/theme';

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

const intentKey = 'party-events-destination';
const validDestination = /^\/(?:event\/[a-f0-9-]{36}(?:\/chat|\/edit)?|admin(?:\/members|\/journal|\/roles|\/taxonomy|\/announcements)?|groups|activity|announcements|account|settings\/(?:notifications|subscriptions))$/i;
function initialDestination() {
  if (typeof window === 'undefined') return null;
  const path = location.pathname.replace(/^\/events(?=\/|$)/, '');
  try {
    if (validDestination.test(path)) { sessionStorage.setItem(intentKey, path); return path; }
    const previous = sessionStorage.getItem(intentKey);
    return previous && validDestination.test(previous) ? previous : null;
  } catch { return validDestination.test(path) ? path : null; }
}

function Gate() {
  const { loading, session, profile, profileError, refreshProfile, signOut, can, eventsSoon } = useAuth();
  // Membre du groupe : droit « Voir les événements » et profil complet ; les autres comptes ont les Réglages.
  const active = profile?.status === 'active' && hasCompleteIdentity(profile) && can('events.view');
  const path = usePathname();
  const [initialIntent] = useState(initialDestination);
  const intent = useRef(initialIntent);
  const [asked, setAsked] = useState(0);
  const shared = useRef<string | null>(null);
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
    };
    window.addEventListener('message', onRefresh);
    return () => window.removeEventListener('message', onRefresh);
  }, [refreshProfile]);
  useEffect(() => {
    if (typeof window !== 'undefined' && window.parent !== window) window.parent.postMessage({ type: 'party-events:account' }, location.origin);
  }, [session?.user.id, profile?.display_name, profile?.avatar_url, profile?.status, eventsSoon]);  // accès bêta compris
  useEffect(() => {
    // Réglages : ouverts à tout compte connecté ; le reste attend la validation du membre.
    if (!loading && session && (active || intent.current === '/account') && !profileError && intent.current) {
      const target = intent.current;
      intent.current = null;
      try { sessionStorage.removeItem(intentKey); } catch { /* Stockage indisponible. */ }
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
    requestAnimationFrame(() => router.replace(`/share/${id}` as Href));
  }, [loading, session, active, profileError, asked]);

  if (loading) return <Loading />;
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
    <Stack
      screenOptions={{
        headerStyle: { backgroundColor: colors.bg },
        headerTintColor: colors.text,
        headerTitleStyle: { fontFamily: fonts.bold },
        headerShadowVisible: false,
        contentStyle: { backgroundColor: colors.bg },
        headerBackTitle: 'Retour',
      }}
    >
      <Stack.Protected guard={!!session && active}>
        <Stack.Screen name="(tabs)" options={{ headerShown: false }} />
        <Stack.Screen name="event/new" options={{ title: 'Proposer un événement', presentation: 'modal' }} />
        <Stack.Screen name="event/[id]/index" options={{ title: '' }} />
        <Stack.Screen name="event/[id]/edit" options={{ title: 'Modifier', presentation: 'modal' }} />
        <Stack.Screen name="event/[id]/chat" options={{ title: 'Discussion' }} />
        <Stack.Screen name="settings/notifications" options={{ title: 'Notifications' }} />
        <Stack.Screen name="settings/subscriptions" options={{ title: 'Mes abonnements' }} />
        <Stack.Screen name="groups" options={{ title: 'Groupes' }} />
        <Stack.Screen name="admin/index" options={{ title: 'Administration' }} />
        <Stack.Screen name="admin/members" options={{ title: 'Membres' }} />
        <Stack.Screen name="admin/journal" options={{ title: 'Journal des membres' }} />
        <Stack.Screen name="admin/roles" options={{ title: 'Rôles et droits' }} />
        <Stack.Screen name="admin/taxonomy" options={{ title: 'Catégories et tags' }} />
        <Stack.Screen name="admin/announcements" options={{ title: 'Annonces admin' }} />
        <Stack.Screen name="announcements" options={{ title: 'Annonces admin' }} />
      </Stack.Protected>
      <Stack.Protected guard={!!session && !active}>
        <Stack.Screen name="welcome" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Protected guard={!session}>
        <Stack.Screen name="sign-in" options={{ headerShown: false }} />
      </Stack.Protected>
      <Stack.Protected guard={!!session}>
        <Stack.Screen name="account" options={{ headerShown: false }} />
        <Stack.Screen name="settings/account" options={{ title: 'Mon compte' }} />
      </Stack.Protected>
      <Stack.Screen name="share/[id]" options={{ title: '' }} />
      <Stack.Screen name="privacy" options={{ title: 'Confidentialité' }} />
    </Stack>
    </>
  );
}

export default function RootLayout() {
  const [fontsLoaded] = useFonts({
    BricolageGrotesque_800ExtraBold,
    Figtree_400Regular,
    Figtree_500Medium,
    Figtree_600SemiBold,
    Figtree_700Bold,
  });

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
