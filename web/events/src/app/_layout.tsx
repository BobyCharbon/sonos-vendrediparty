import { BricolageGrotesque_800ExtraBold } from '@expo-google-fonts/bricolage-grotesque';
import { Figtree_400Regular, Figtree_500Medium, Figtree_600SemiBold, Figtree_700Bold } from '@expo-google-fonts/figtree';
import { useFonts } from 'expo-font';
import { DarkTheme, router, Stack, ThemeProvider, usePathname, type ErrorBoundaryProps, type Href } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { StatusBar } from 'expo-status-bar';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { Button, ErrorText, Loading, Screen, T, Title } from '@/components/ui';
import { AuthProvider, useAuth } from '@/lib/auth';
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

const intentKey = 'party-events-destination';
const validDestination = /^\/(?:event\/[a-f0-9-]{36}(?:\/chat|\/edit)?|admin(?:\/members|\/taxonomy|\/announcements)?|activity|announcements|settings\/(?:notifications|subscriptions))$/i;
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
  const { loading, session, profile, profileError, refreshProfile, signOut } = useAuth();
  const active = profile?.status === 'active' && profile.display_name.trim() !== '';
  const path = usePathname();
  const [initialIntent] = useState(initialDestination);
  const intent = useRef(initialIntent);
  useEffect(() => {
    if (!loading && active && !profileError && intent.current) {
      const target = intent.current;
      intent.current = null;
      try { sessionStorage.removeItem(intentKey); } catch { /* Stockage indisponible. */ }
      if (path !== target) requestAnimationFrame(() => router.replace(target as Href));
    }
  }, [loading, active, profileError, path]);

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
        <Stack.Screen name="admin/members" options={{ title: 'Membres' }} />
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
        <Stack.Screen name="settings/account" options={{ title: 'Mon compte' }} />
      </Stack.Protected>
      <Stack.Screen name="privacy" options={{ title: 'Confidentialité' }} />
    </Stack>
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
        <AuthProvider>{fontsLoaded ? <Gate /> : <Loading />}</AuthProvider>
      </ThemeProvider>
    </SafeAreaProvider>
  );
}
