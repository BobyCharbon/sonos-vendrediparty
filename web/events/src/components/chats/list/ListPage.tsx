import { router, Stack } from 'expo-router';
import type { ReactNode } from 'react';
import { ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { chatFont, glow, useNeon } from '../neon';
import { ListHeader } from './Bits';
import { Icon, type IconName } from './Icons';

/** Page secondaire des Discussions (Demandes, Archivées) : ‹ Discussions, grand titre, texte d'aide, contenu. */
export function ListPage({ title, intro, children, overlay }: { title: string; intro?: string; children: ReactNode; overlay?: ReactNode }) {
  const c = useNeon();
  const insets = useSafeAreaInsets();
  const back = () => (router.canGoBack() ? router.back() : router.replace('/chats'));
  return (
    <View style={[st.screen, { backgroundColor: c.bg }]}>
      <Stack.Screen options={{ headerShown: false, title }} />
      <View style={glow(c)} />
      <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={{ paddingTop: insets.top + 4, paddingBottom: insets.bottom + 48 }}>
        <ListHeader title={title} back={{ label: 'Discussions', onPress: back }} />
        {intro ? <Text style={[chatFont.text, st.intro, { color: c.t2 }]}>{intro}</Text> : null}
        {children}
      </ScrollView>
      {overlay}
    </View>
  );
}

/** Rien à montrer : une icône, une phrase. */
export function Nothing({ icon, title, text }: { icon: IconName; title: string; text: string }) {
  const c = useNeon();
  return (
    <View style={st.nothing}>
      <View style={[st.nothingIco, { backgroundColor: c.glass, borderColor: c.glassLine }]}><Icon name={icon} size={30} color={c.lav} /></View>
      <Text style={[chatFont.display, { color: c.t1, fontSize: 22, lineHeight: 26, textAlign: 'center' }]}>{title}</Text>
      <Text style={[chatFont.text, { color: c.t2, fontSize: 15, lineHeight: 20, textAlign: 'center' }]}>{text}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  screen: { flex: 1, position: 'relative', overflow: 'hidden' },
  intro: { fontSize: 15, lineHeight: 20, paddingHorizontal: 16, paddingTop: 10, paddingBottom: 6 },
  nothing: { alignItems: 'center', gap: 10, paddingHorizontal: 32, paddingTop: 56 },
  nothingIco: { width: 72, height: 72, borderRadius: 24, borderWidth: 1, alignItems: 'center', justifyContent: 'center', marginBottom: 6 },
});
