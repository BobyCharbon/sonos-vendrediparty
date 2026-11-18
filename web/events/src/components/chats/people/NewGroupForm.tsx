import { router } from 'expo-router';
import { useState } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';
import { useSafeAreaInsets } from 'react-native-safe-area-context';

import { useTermsGate } from '@/components/TermsSheet';
import { useMe } from '@/lib/auth';
import { GROUP_COLOR_KEYS, GROUP_EMOJIS, coverGradient, gradient, palette, type GroupColor } from '@/lib/groups';
import { TERMS_PATH } from '@/lib/moderation';
import { duration, enter, pressTransition, transition } from '@/lib/motion';

import { Icon, K, Label, NeonButton, PersonFace, disp, txt, web } from './bits';
import { createChatGroup, goToGroupChat, namesList, sendEventCard, shortName, type Person } from './people';

const NAME_MAX = 40;

/**
 * Nouveau groupe à plusieurs (maquette 1-neon/2b, contrat §5) : aperçu vivant de la couverture, nom (filtré par la
 * base), 16 emojis, 6 couleurs, CGU. La base crée un groupe PRIVÉ (Root ne le lit pas) et invite seulement les personnes
 * à qui j'écris déjà ; les autres reçoivent d'abord un message (« écris-leur d'abord »).
 */
export function NewGroupForm({ members, event, onBack }: { members: Person[]; event?: string | null; onBack: () => void }) {
  const me = useMe();
  const insets = useSafeAreaInsets();
  const [name, setName] = useState('');
  const [emoji, setEmoji] = useState<string>('🪩');
  const [color, setColor] = useState<GroupColor>('pink');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<{ group: string; refused: Person[] } | null>(null);
  const terms = useTermsGate('Avant de créer le groupe');
  const clean = name.trim();
  const p = palette(color);
  const who = `Toi, ${namesList(members.map(shortName))}`;

  async function create() {
    if (!clean || busy) return;
    setError(null);
    if (!(await terms.ensure())) return;
    setBusy(true);
    try {
      const r = await createChatGroup(clean, emoji, color, members.map((m) => m.id));
      if (event) await sendEventCard('group', r.group, event, '').catch(() => undefined);
      const refused = members.filter((m) => r.refused.includes(m.id));
      if (refused.length) setDone({ group: r.group, refused });
      else goToGroupChat(r.group);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Le groupe n’a pas été créé. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    const names = namesList(done.refused.map(shortName));
    return (
      <View style={{ flex: 1, padding: 20, gap: 16, justifyContent: 'center' }} testID="group-refused">
        <Text style={[disp(26, 30), { textAlign: 'center' }]}>Ton groupe est prêt</Text>
        <Text style={[txt(16, '400', K.t2, 22), { textAlign: 'center' }]}>
          {names} {done.refused.length > 1 ? 'n’ont' : 'n’a'} pas reçu d’invitation : écris-{done.refused.length > 1 ? 'leur' : 'lui'} d’abord,
          puis invite-{done.refused.length > 1 ? 'les' : 'le·la'} depuis le groupe.
        </Text>
        <NeonButton label="Ouvrir le groupe" icon="users" onPress={() => goToGroupChat(done.group)} />
      </View>
    );
  }

  return (
    <View style={{ flex: 1 }}>
      {terms.sheet}
      <View style={st.navbar}>
        <Pressable accessibilityRole="button" accessibilityLabel="Retour au choix des personnes" onPress={onBack} style={st.back}>
          <Icon name="chevl" size={26} color={K.lav} />
        </Pressable>
        <Text accessibilityRole="header" style={[st.title, disp(18, 22)]}>Nouveau groupe</Text>
      </View>
      <ScrollView contentContainerStyle={{ paddingBottom: 180 + insets.bottom }} keyboardShouldPersistTaps="handled">
        {/* Aperçu vivant : la couverture du groupe (même dégradé que sa page) suit le nom, l'emoji et la couleur. */}
        <View style={[st.cover, coverGradient(color), web({ boxShadow: `0 0 0 1px rgba(255,255,255,.12) inset, 0 24px 50px -24px ${p.main}cc` }),
          transition('background-image, box-shadow', duration.base)]} accessibilityLabel={`Aperçu du groupe ${clean || 'sans nom'}`} testID="group-cover">
          <View style={[st.shine]} />
          <View key={`${emoji}-${color}`} style={[st.tile, gradient(color), enter('pop')]}><Text style={{ fontSize: 46, lineHeight: 56 }}>{emoji}</Text></View>
          <Text style={[disp(30, 32), st.gname]} numberOfLines={2}>{clean || 'Ton groupe'}</Text>
          <View style={st.gmembers}>
            <View style={{ flexDirection: 'row' }}>
              {[{ id: me.id, name: me.display_name || 'Moi', photo: me.avatar_url }, ...members.slice(0, 4)].map((m, i) => (
                <View key={m.id} style={{ marginLeft: i ? -8 : 0, borderRadius: 99, borderWidth: 2, borderColor: p.dim }}>
                  <PersonFace id={m.id} name={m.name} photo={m.photo} size={28} />
                </View>
              ))}
            </View>
            <Text style={[txt(14, '600', 'rgba(255,255,255,0.88)', 18), { flexShrink: 1 }]} numberOfLines={1}>{who}</Text>
          </View>
        </View>

        <Label style={{ paddingTop: 18 }}>Nom du groupe</Label>
        <View style={st.input}>
          <TextInput value={name} onChangeText={(v) => setName(v.slice(0, NAME_MAX))} maxLength={NAME_MAX} accessibilityLabel="Nom du groupe"
            placeholder="La bande du vendredi" placeholderTextColor={K.t3} autoFocus onSubmitEditing={() => void create()}
            style={[{ flex: 1, height: 50, color: K.t1, fontSize: 17 }, ({ outlineStyle: 'none', caretColor: K.pink } as object)]} />
          <Text style={[txt(13, '400', K.t3), { fontVariant: ['tabular-nums'] }]}>{name.length}/{NAME_MAX}</Text>
        </View>

        <Label>Emoji</Label>
        <View style={st.emojis} accessibilityRole="radiogroup" accessibilityLabel="Emoji du groupe">
          {GROUP_EMOJIS.map((e) => {
            const on = e === emoji;
            return (
              <Pressable key={e} accessibilityRole="radio" accessibilityState={{ checked: on }} aria-checked={on} accessibilityLabel={`Emoji ${e}`}
                onPress={() => setEmoji(e)} style={({ pressed }) => [st.emoji, on && st.emojiOn, pressTransition, pressed && { transform: [{ scale: 0.9 }] }]}>
                <Text style={{ fontSize: 25, lineHeight: 30 }}>{e}</Text>
              </Pressable>
            );
          })}
        </View>

        <Label>Couleur</Label>
        <View style={st.colors} accessibilityRole="radiogroup" accessibilityLabel="Couleur du groupe">
          {GROUP_COLOR_KEYS.map((c) => {
            const on = c === color;
            const cp = palette(c);
            return (
              <Pressable key={c} accessibilityRole="radio" accessibilityState={{ checked: on }} aria-checked={on} accessibilityLabel={cp.name}
                onPress={() => setColor(c)} style={({ pressed }) => [st.sw, gradient(c),
                  on && web({ boxShadow: `0 0 0 3px ${K.bg}, 0 0 0 5px ${cp.to}, 0 0 20px -2px ${cp.to}` }), pressTransition, pressed && { transform: [{ scale: 0.9 }] }]}>
                {on ? <Icon name="check" size={16} color="#1F0618" stroke={3} /> : null}
              </Pressable>
            );
          })}
        </View>
        <Text style={[txt(13, '400', K.t2), { paddingHorizontal: 18, paddingTop: 8 }]}>{p.name}</Text>
      </ScrollView>

      <View style={[st.actbar, { paddingBottom: 18 + insets.bottom }]}>
        <Text style={st.cgu}>
          Tu crées le groupe et tu le gères. En le créant, tu acceptes les{' '}
          <Text accessibilityRole="link" onPress={() => router.push(TERMS_PATH)} style={{ color: K.lav, fontWeight: '600' }}>règles de Party</Text>.
        </Text>
        {error ? <Text accessibilityRole="alert" style={[st.cgu, { color: K.danger }]}>{error}</Text> : null}
        <NeonButton testID="group-create" label="Créer le groupe" icon="sparkle" disabled={!clean} loading={busy} onPress={() => void create()} />
      </View>
    </View>
  );
}

const st = StyleSheet.create({
  navbar: { height: 52, flexDirection: 'row', alignItems: 'center', paddingHorizontal: 8 },
  back: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  title: { position: 'absolute', left: 60, right: 60, textAlign: 'center' },
  cover: { marginTop: 6, marginHorizontal: 16, height: 196, borderRadius: 26, overflow: 'hidden', padding: 18, justifyContent: 'flex-end' },
  shine: web({ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundImage: 'radial-gradient(40% 50% at 85% 30%, rgba(255,255,255,.18), transparent 70%)' }),
  tile: web({ position: 'absolute', right: 18, top: 18, width: 84, height: 84, borderRadius: 26, alignItems: 'center', justifyContent: 'center',
    boxShadow: 'inset 0 0 0 2px rgba(255,255,255,.35), 0 16px 30px -12px rgba(0,0,0,.5)', transform: 'rotate(6deg)' }),
  gname: web({ maxWidth: 230, textShadow: '0 2px 18px rgba(0,0,0,.35)' }),
  gmembers: { marginTop: 10, flexDirection: 'row', alignItems: 'center', gap: 8 },
  input: web({ marginHorizontal: 16, height: 52, borderRadius: 16, paddingHorizontal: 14, flexDirection: 'row', alignItems: 'center', gap: 8,
    backgroundColor: K.glass, borderWidth: 1, borderColor: 'rgba(185,167,255,0.35)', boxShadow: '0 0 0 4px rgba(123,108,246,.12)' }),
  emojis: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 12, rowGap: 2 },
  emoji: { width: '12.5%', height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  emojiOn: web({ backgroundColor: 'rgba(255,79,154,0.16)', boxShadow: `inset 0 0 0 2px ${K.pink}, 0 0 16px -4px ${K.pink}` }),
  colors: { flexDirection: 'row', justifyContent: 'space-between', paddingHorizontal: 18 },
  sw: web({ width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', boxShadow: 'inset 0 0 0 1.5px rgba(255,255,255,.28)' }),
  actbar: web({ position: 'absolute', left: 0, right: 0, bottom: 0, paddingTop: 12, paddingHorizontal: 16,
    backgroundImage: 'linear-gradient(180deg, rgba(14,10,31,0), rgba(14,10,31,.94) 22%)' }),
  cgu: { ...txt(13, '400', K.t2, 18), textAlign: 'center', marginHorizontal: 8, marginBottom: 12 },
});
