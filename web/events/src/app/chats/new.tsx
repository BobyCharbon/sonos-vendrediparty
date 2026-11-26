import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { ChatsOff } from '@/components/ChatsOff';
import { termsLater, useTermsGate } from '@/components/TermsSheet';
import { DateTile, K, NeonButton, PersonFace, disp, txt, web } from '@/components/chats/people/bits';
import { NewGroupForm } from '@/components/chats/people/NewGroupForm';
import { PeoplePicker } from '@/components/chats/people/PeoplePicker';
import {
  fetchEventCard, goToGroupChat, groupWith, namesList, nativeOpenDirect, openDirect, refusal, sendEventCard, shortName,
  type EventCard, type Person,
} from '@/components/chats/people/people';
import { discussionsOn } from '@/lib/features';
import { formatShort } from '@/lib/format';
import { enter } from '@/lib/motion';

const EVENT_ID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * Nouveau message (maquette 1-neon/2, contrat §8) : « À : » + puces, recherche, Croisés récemment, Dans tes groupes.
 * 1 personne → « Écrire à Léa » (demande de message si la base le dit) ; plusieurs → le groupe existant avec exactement
 * ces personnes, sinon « Créer un groupe avec … » (maquette 2b). `?event=<id>` (« Envoyer à un ami » d'une fiche) : la
 * carte de la soirée part avec le premier message.
 */
export default function NewMessage() {
  const params = useLocalSearchParams<{ event?: string }>();
  const event = typeof params.event === 'string' && EVENT_ID.test(params.event) ? params.event : null;
  const insets = useSafeAreaInsets();
  const [selected, setSelected] = useState<Person[]>([]);
  const [step, setStep] = useState<'pick' | 'group'>('pick');
  const [card, setCard] = useState<EventCard | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const terms = useTermsGate('Avant d’écrire');

  useEffect(() => {
    if (!event) return undefined;
    let live = true;
    void fetchEventCard(event).then((c) => { if (live) setCard(c); });
    return () => { live = false; };
  }, [event]);

  if (!discussionsOn) return <ChatsOff />;

  const cancel = () => (router.canGoBack() ? router.back() : router.replace('/chats'));
  const toggle = (p: Person) => {
    setError(null);
    setSelected((list) => (list.some((x) => x.id === p.id) ? list.filter((x) => x.id !== p.id) : [...list, p]));
  };
  const one = selected.length === 1 ? selected[0] : null;
  const first = one ? shortName(one) : '';
  const names = namesList(selected.map(shortName));
  // Une demande de message est un texte seul (contrat §2) : la carte part quand la personne aura accepté.
  const cardGoes = !!card && !(one && one.link === 'request');

  async function writeTo(p: Person) {
    if (!cardGoes && nativeOpenDirect(p.id)) return;
    setBusy(true);
    setError(null);
    try {
      let r = await openDirect(p.id);
      if (r.reason === 'terms_required') {
        if (!(await terms.ensure())) return setError(termsLater('écrire'));
        r = await openDirect(p.id);
      }
      if (!r.chat) return setError(refusal(r.reason));
      if (cardGoes && event && r.status === 'active') await sendEventCard('direct', r.chat, event, '');
      if (!nativeOpenDirect(p.id)) router.replace(`/chats/${r.chat}`);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La discussion n’a pas pu s’ouvrir. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  async function group() {
    setBusy(true);
    setError(null);
    const existing = await groupWith(selected.map((p) => p.id));
    setBusy(false);
    if (!existing) return setStep('group');
    if (event) await sendEventCard('group', existing, event, '').catch(() => undefined);
    goToGroupChat(existing);
  }

  if (step === 'group') {
    return (
      <View style={st.screen}>
        <Stack.Screen options={{ headerShown: false, title: 'Nouveau groupe' }} />
        <NewGroupForm members={selected} event={cardGoes ? event : null} onBack={() => setStep('pick')} />
      </View>
    );
  }

  const asks = selected.filter((p) => p.link === 'request');
  return (
    <View style={st.screen}>
      <Stack.Screen options={{ headerShown: false, title: 'Nouveau message' }} />
      {terms.sheet}
      <View style={st.navbar}>
        <Pressable accessibilityRole="button" onPress={cancel} style={st.txtbtn}><Text style={txt(17, '500', K.lav)}>Annuler</Text></Pressable>
        <Text accessibilityRole="header" style={[st.title, disp(18, 22)]}>Nouveau message</Text>
      </View>
      <ScrollView contentContainerStyle={{ paddingBottom: 170 + insets.bottom }} keyboardShouldPersistTaps="handled">
        {card ? (
          <View style={st.card} testID="new-message-event" accessibilityLabel={`Carte jointe : ${card.title}`}>
            <DateTile iso={card.start} />
            <View style={{ flex: 1, minWidth: 0 }}>
              <Text style={txt(15, '600', K.t1, 19)} numberOfLines={1}>{card.title}</Text>
              <Text style={txt(13, '400', K.t2, 17)} numberOfLines={1}>
                {cardGoes ? 'Jointe à ton message' : 'Tu pourras l’envoyer une fois la demande acceptée'}{card.start ? ` · ${formatShort(card.start)}` : ''}
              </Text>
            </View>
          </View>
        ) : null}
        <PeoplePicker selected={selected} onToggle={toggle} />
      </ScrollView>

      {selected.length ? (
        <View style={[st.actbar, { paddingBottom: 18 + insets.bottom }, enter('rise')]} testID="new-message-action">
          {one ? (
            one.link === 'request' ? <Text style={st.hint}>Ce sera une demande de message : {first} choisit de l’accepter.</Text> : null
          ) : (
            <View style={st.hintRow}>
              <View style={{ flexDirection: 'row' }}>
                {selected.slice(0, 3).map((p, i) => (
                  <View key={p.id} style={{ marginLeft: i ? -8 : 0, borderRadius: 99, borderWidth: 2, borderColor: K.bg }}>
                    <PersonFace id={p.id} name={p.name} photo={p.photo} size={28} />
                  </View>
                ))}
              </View>
              <Text style={[txt(14, '400', K.t2, 19), { flexShrink: 1 }]}>
                {asks.length ? `${namesList(asks.map(shortName))} : écris-${asks.length > 1 ? 'leur' : 'lui'} d’abord pour l’inviter.`
                  : `${selected.length} personnes : ce sera un groupe`}
              </Text>
            </View>
          )}
          {error ? <Text accessibilityRole="alert" style={[st.hint, { color: K.danger }]}>{error}</Text> : null}
          <NeonButton testID="new-message-go" loading={busy} icon={one ? 'chat' : 'users'}
            label={one ? `Écrire à ${first}` : `Créer un groupe avec ${names}`}
            onPress={() => void (one ? writeTo(one) : group())} />
        </View>
      ) : null}
    </View>
  );
}

const st = StyleSheet.create({
  screen: web({ flex: 1, backgroundColor: K.bg,
    backgroundImage: 'radial-gradient(120% 46% at 92% -12%, rgba(123,108,246,.30), transparent 60%), radial-gradient(80% 34% at -18% 2%, rgba(255,79,154,.12), transparent 62%)' }),
  navbar: { height: 52, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8 },
  txtbtn: { height: 44, paddingHorizontal: 10, justifyContent: 'center', zIndex: 1 },
  title: { position: 'absolute', left: 90, right: 90, textAlign: 'center' },
  card: { flexDirection: 'row', alignItems: 'center', gap: 12, marginHorizontal: 16, marginBottom: 10, padding: 9, paddingRight: 12, borderRadius: 16,
    backgroundColor: K.glass, borderWidth: 1, borderColor: K.glassLine },
  actbar: web({ position: 'absolute', left: 0, right: 0, bottom: 0, paddingTop: 14, paddingHorizontal: 16,
    backgroundImage: 'linear-gradient(180deg, rgba(14,10,31,0), rgba(14,10,31,.94) 22%)' }),
  hint: { ...txt(14, '400', K.t2, 19), textAlign: 'center', marginBottom: 10 },
  hintRow: { flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 8, marginBottom: 10 },
});
