import { BricolageGrotesque_800ExtraBold } from '@expo-google-fonts/bricolage-grotesque';
import { Figtree_400Regular, Figtree_500Medium, Figtree_600SemiBold, Figtree_700Bold } from '@expo-google-fonts/figtree';
import { useFonts } from 'expo-font';
import { DarkTheme, Stack, ThemeProvider, type ErrorBoundaryProps } from 'expo-router';
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

function Gate() {
  const { loading, session, profile, profileError, refreshProfile, signOut } = useAuth();
  const active = profile?.status === 'active' && profile.display_name.trim() !== '';

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
