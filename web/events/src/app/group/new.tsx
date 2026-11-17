import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Image, StyleSheet, View } from 'react-native';

import { ColorPicker, EmojiPicker, FloatingEmojis, GroupTile } from '@/components/GroupBits';
import { GroupInvitePanel } from '@/components/GroupInvite';
import { GroupPhotoField } from '@/components/GroupPhotoField';
import { useTermsGate } from '@/components/TermsSheet';
import { Button, ErrorText, HeaderAction, HeaderBack, Input, Screen, T } from '@/components/ui';
import { useMe } from '@/lib/auth';
import { GROUP_COLOR_KEYS, GROUP_EMOJIS, coverGradient, saveGroupPhoto, type GroupColor } from '@/lib/groups';
import { dbMessage } from '@/lib/moderation';
import { duration, enter, transition } from '@/lib/motion';
import { supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';

const NAME_MAX = 60;

/**
 * Nouveau groupe en 2 étapes (maquette A, 17.11) : 1. nom + emoji + couleur (+ photo facultative), avec l'aperçu de sa couverture ;
 * 2. Inviter (lien du groupe : WhatsApp / Copier / Autre, code QR, personnes déjà croisées) ou « Plus tard ».
 * Le groupe est créé en quittant l'étape 1 (CGU d'abord : son nom est un contenu ; nom filtré par la base) ;
 * « Retour » depuis l'étape 2 le modifie. Ensuite, la page du groupe s'ouvre.
 */
export default function NewGroup() {
  const me = useMe();
  const params = useLocalSearchParams<{ name?: string; emoji?: string; color?: string }>();
  const [name, setName] = useState(typeof params.name === 'string' ? params.name.slice(0, NAME_MAX) : '');
  const [emoji, setEmoji] = useState(GROUP_EMOJIS.includes(params.emoji as never) ? (params.emoji as string) : '🪩');
  const [color, setColor] = useState<GroupColor>(GROUP_COLOR_KEYS.includes(params.color as GroupColor) ? (params.color as GroupColor) : 'pink');
  const [created, setCreated] = useState<string | null>(null);
  const [photo, setPhoto] = useState<string | null>(null);  // photo recadrée (facultative), envoyée une fois le groupe créé
  const [savedPhoto, setSavedPhoto] = useState<{ uri: string; path: string } | null>(null);
  const [step, setStep] = useState<1 | 2>(1);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const terms = useTermsGate();
  const clean = name.trim();

  const openGroup = (id: string) => router.replace(`/group/${id}`);
  const cancel = () => (router.canGoBack() ? router.back() : router.replace('/groups'));

  /** Envoie (ou retire) la photo si elle a changé ; false, avec l'erreur affichée, si ça n'a pas marché. */
  async function sendPhoto(id: string): Promise<boolean> {
    if (photo === (savedPhoto?.uri ?? null)) return true;
    try {
      await saveGroupPhoto(id, photo, savedPhoto?.path ?? null);
      if (!photo) {
        setSavedPhoto(null);
        return true;
      }
      const row = await supabase.from('member_groups').select('photo_path').eq('id', id).single();
      setSavedPhoto({ uri: photo, path: (row.data?.photo_path as string) ?? '' });
      return true;
    } catch (e) {
      setError(e instanceof Error && !('code' in e) ? e.message : dbMessage((e as { message?: string }).message, 'La photo n’a pas été enregistrée. Réessaie.'));
      return false;
    }
  }

  async function next() {
    if (!clean || busy) return;
    setError(null);
    if (!(await terms.ensure())) return;
    setBusy(true);
    if (created) {
      const { error: failed } = await supabase.from('member_groups').update({ name: clean, emoji, color }).eq('id', created);
      if (failed) {
        setBusy(false);
        return setError(dbMessage(failed.message, 'Le groupe n’a pas été modifié. Réessaie.'));
      }
      const sent = await sendPhoto(created);
      setBusy(false);
      if (sent) setStep(2);
      return;
    }
    const { data, error: failed } = await supabase.from('member_groups')
      .insert({ name: clean, emoji, color, created_by: me.id }).select('id').single();
    if (failed || !data) {
      setBusy(false);
      // Nom refusé par le filtre de la base (modération commune) : la phrase dit pourquoi.
      return setError(dbMessage(failed?.message, 'Le groupe n’a pas été créé. Réessaie.'));
    }
    const id = data.id as string;
    // Le créateur en fait partie d'office (la base l'ajoute aussi : member_groups_creator_joins).
    const { error: joinError } = await supabase.from('member_group_members').insert({ group_id: id, user_id: me.id });
    if (joinError && !joinError.message.includes('duplicate')) {
      setBusy(false);
      return setError('Le groupe est créé, mais tu n’as pas pu y être ajouté. Réessaie depuis sa page.');
    }
    setCreated(id);
    const sent = await sendPhoto(id);
    setBusy(false);
    if (sent) setStep(2);
  }

  return (
    <Screen edges={[]}>
      {terms.sheet}
      <Stack.Screen options={step === 1
        ? { title: 'Nouveau groupe', headerLeft: () => (created ? null : <HeaderAction label="Annuler" onPress={cancel} />),
            headerRight: () => (created ? <HeaderAction label="Plus tard" onPress={() => openGroup(created)} /> : null) }
        : { title: 'Inviter', headerLeft: () => <HeaderBack label="Retour" onPress={() => setStep(1)} />,
            headerRight: () => <HeaderAction label="Plus tard" prominent onPress={() => openGroup(created!)} /> }} />

      {/* Étapes : deux traits, le second s'allume à l'étape Inviter. */}
      <View style={st.steps} accessibilityLabel={`Étape ${step} sur 2`}>
        <View style={[st.stepBar, { backgroundColor: colors.accent }]} />
        <View style={st.stepTrack}>
          <View style={[st.stepFill, transition('transform', duration.slow), { transform: [{ scaleX: step === 2 ? 1 : 0 }] }]} />
        </View>
      </View>

      {step === 1 ? (
        <View key="one" style={[{ gap: 16 }, enter('slideIn')]}>
          {/* Aperçu vivant de la couverture : couleur, emoji et nom suivent la saisie. */}
          <View style={st.preview} testID="group-preview">
            <View style={[st.previewCover, coverGradient(color), transition('background-color', duration.base)]}>
              {photo ? <Image source={{ uri: photo }} style={StyleSheet.absoluteFill} resizeMode="cover" /> : <FloatingEmojis items={[
                { emoji, top: 10, left: 22, size: 18, opacity: 0.35 },
                { emoji, top: 22, left: '58%', size: 16, opacity: 0.3, delay: 600 },
                { emoji, top: 46, right: 30, size: 18, opacity: 0.35, delay: 1100 },
              ]} />}
            </View>
            <View style={st.previewBody}>
              <View key={`${emoji}-${color}`} style={[st.previewTile, enter('pop')]}><GroupTile group={{ emoji, color }} src={photo} size={60} /></View>
              <View style={{ flex: 1, minWidth: 0, paddingTop: 22 }}>
                <T weight="bold" size={19} numberOfLines={1}>{clean || 'Ton groupe'}</T>
                <T muted size={13}>1 membre · toi</T>
              </View>
            </View>
          </View>

          <View style={{ gap: 8 }}>
            <View style={st.labelRow}>
              <T size={14} weight="semibold" color={colors.textSoft}>Nom du groupe</T>
              <T size={13} muted>{name.length}/{NAME_MAX}</T>
            </View>
            <Input accessibilityLabel="Nom du groupe" placeholder="Ex. Soirées du vendredi" value={name} maxLength={NAME_MAX}
              onChangeText={setName} autoFocus onSubmitEditing={() => void next()} />
          </View>
          <View style={{ gap: 8 }}>
            <T size={14} weight="semibold" color={colors.textSoft}>Un emoji</T>
            <EmojiPicker value={emoji} onChange={setEmoji} />
          </View>
          <View style={{ gap: 8 }}>
            <T size={14} weight="semibold" color={colors.textSoft}>Une couleur</T>
            <ColorPicker value={color} onChange={(c) => setColor(c as GroupColor)} colorsList={GROUP_COLOR_KEYS} />
          </View>
          <GroupPhotoField has={!!photo} disabled={busy} onPicked={setPhoto} onRemove={() => setPhoto(null)} />
          <ErrorText error={error} />
          <Button label={created ? 'Enregistrer et continuer' : 'Continuer'} disabled={!clean} loading={busy} onPress={() => void next()} />
          <T muted size={13} style={{ textAlign: 'center' }}>Ensuite : inviter ta bande (ou plus tard).</T>
        </View>
      ) : (
        <View key="two" style={[{ gap: 16 }, enter('slideIn')]}>
          <GroupInvitePanel fresh group={{ id: created!, name: clean, emoji, color, system: false }} />
          <Button label="Ouvrir le groupe" variant="secondary" onPress={() => openGroup(created!)} />
        </View>
      )}
    </Screen>
  );
}

const st = StyleSheet.create({
  steps: { flexDirection: 'row', gap: 6 },
  stepBar: { flex: 1, height: 4, borderRadius: 2 },
  stepTrack: { flex: 1, height: 4, borderRadius: 2, backgroundColor: colors.lineStrong, overflow: 'hidden' },
  stepFill: { height: '100%', backgroundColor: colors.accent, transformOrigin: 'left' },
  preview: { borderRadius: radius.lg, overflow: 'hidden', backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  previewCover: { height: 82 },
  previewBody: { flexDirection: 'row', gap: 12, paddingHorizontal: 16, paddingBottom: 14, marginTop: -30 },
  previewTile: { borderRadius: 20, borderWidth: 3, borderColor: colors.surface },
  labelRow: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline' },
});
