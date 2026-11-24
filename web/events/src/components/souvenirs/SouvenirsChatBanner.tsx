import { router } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { useSignal } from '@/lib/data';
import { enter, pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import { fetchCounter, hoursLeft, nativeSouvenirs, type Counter } from '@/lib/souvenirs';

/**
 * « 📸 Les souvenirs sont arrivés » en haut de la discussion d'un événement (maquette v2, écran 5 bis), pendant les 24 h de
 * la story seulement (`souvenir_counter` : le nombre, jamais qui ni quoi). Un toucher ouvre la story : native dans l'app
 * iPhone, sinon la fiche avec `?souvenirs=1` (qui l'ouvre, ou dit qu'elle se regarde dans l'app quand rien ne se garde).
 * Aucune photo n'est montrée ici.
 */
export function SouvenirsChatBanner({ eventId }: { eventId: string }) {
  const [c, setC] = useState<Counter | null>(null);
  const load = useCallback(() => fetchCounter(eventId).then(setC, () => {}), [eventId]);
  useEffect(() => { void load(); }, [load]);
  useSignal([`event:${eventId}`], load);

  const count = c?.count ?? 0;
  if (!c?.enabled || c.phase !== 'story' || !(c.member || c.staff) || count < 1) return null;
  const native = nativeSouvenirs();
  const until = c.story_until ? ` · Visible encore ${hoursLeft(c.story_until)} h` : '';
  const open = () => {
    if (native?.story) native.story(eventId);
    else router.push(`/event/${eventId}?souvenirs=1`);
  };
  return (
    <View style={[st.wrap, enter('drop')]}>
      <Pressable accessibilityRole="button" testID="souvenirs-chat-banner" onPress={open}
        accessibilityLabel={`Les souvenirs sont arrivés : ${count} photo${count > 1 ? 's' : ''}${until}. Voir la story`}
        style={({ pressed }) => [st.card, pressTransition, pressed && { opacity: 0.85 }]}>
        <View style={[st.ring, !c.seen && st.ringNew]}><Text style={{ fontSize: 20 }}>📸</Text></View>
        <View style={{ flex: 1, gap: 1 }}>
          <Text style={st.title} numberOfLines={1}>Les souvenirs sont arrivés</Text>
          <Text style={st.sub} numberOfLines={1}>{count} photo{count > 1 ? 's' : ''}{until}</Text>
        </View>
        <View style={st.go}><Text style={st.goText}>{c.seen ? '▶︎ Revoir' : '▶︎ Voir'}</Text></View>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  wrap: { paddingHorizontal: 12, paddingTop: 8, zIndex: 2 },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 64, paddingVertical: 10, paddingHorizontal: 12, borderRadius: radius.lg,
    borderWidth: 1, borderColor: 'rgba(255,79,154,0.55)', backgroundColor: '#1d1036',
    backgroundImage: 'radial-gradient(circle at 10% 0%, rgba(255,181,71,.22), transparent 45%), radial-gradient(circle at 90% 40%, rgba(255,79,154,.28), transparent 55%)',
    boxShadow: '0 0 28px -10px rgba(255,79,154,.7)' } as object,
  ring: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.surface2, borderWidth: 2, borderColor: colors.lineStrong },
  ringNew: { borderColor: colors.accent, boxShadow: `0 0 10px ${colors.accent}` } as object,
  title: { color: colors.text, fontSize: 15, ...font.bold },
  sub: { color: colors.textSoft, fontSize: 13, ...font.body },
  go: { minHeight: 44, paddingHorizontal: 14, borderRadius: 22, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center' },
  goText: { color: colors.onAction, fontSize: 14, ...font.bold },
});
