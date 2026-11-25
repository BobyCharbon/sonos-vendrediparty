import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { Image, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { PhotoCropper } from './PhotoCropper';
import { SheetBackdrop, SheetTop, useSheetDrag, useSheetTop } from './SheetGesture';
import { useTermsGate } from './TermsSheet';
import { Button, ConfirmButton, ErrorText, T, Toast } from './ui';
import {
  chooseCover, coverTipSeen, creditHref, errorText, hideCoverTip, isTerms, officialCover, posterCover, removeCover, suggestCovers, uploadCover,
  type Official, type Saved, type Suggestions,
} from '@/lib/eventCover';
import { MAX_SOURCE_PHOTO } from '@/lib/photos';
import { pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

type Tab = 'mine' | 'free' | 'official' | 'poster';
const TABS: { key: Tab; label: string }[] = [
  { key: 'mine', label: '📷 Ma photo' },
  { key: 'free', label: '🔎 Proposées' },
  { key: 'official', label: '🌐 Officielle' },
  { key: 'poster', label: '🎨 Affiche' },
];

/**
 * « Changer la couverture » (25.11) : ma photo (recadrée en 16:9), des photos libres de droits proposées (Pexels ou
 * Openverse, choisies et triées par l'IA quand elle est permise), l'image officielle de l'événement (page de
 * l'organisateur, de la salle ou de la billetterie), ou l'affiche Party. Jamais d'image générée par un modèle d'image.
 * Toute image passe par le serveur (réencodée chez Party) ; la fiche des autres se met à jour en direct.
 */
export function CoverSheet({ eventId, visible, hasCover, onClose, onSaved }: {
  eventId: string; visible: boolean; hasCover: boolean; onClose: () => void; onSaved: (saved: Saved) => void;
}) {
  const [tab, setTab] = useState<Tab>('mine');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [found, setFound] = useState<Suggestions | null>(null);
  const [official, setOfficial] = useState<Official | null>(null);
  const [chosen, setChosen] = useState<string | null>(null);
  const card = useRef<View>(null);
  const scroller = useRef<ScrollView>(null);
  const gallery = useRef<HTMLInputElement>(null);
  const camera = useRef<HTMLInputElement>(null);
  const sheetTop = useSheetTop();
  const terms = useTermsGate('Avant de publier une image');
  useSheetDrag(visible && !source, onClose, card, scroller);

  /** Une écriture : CGU d'abord si la base les exige (feuille puis nouvel essai), puis la fiche se relit. */
  async function save(what: string, work: () => Promise<Saved>, needsTerms = true) {
    setBusy(what);
    setError(null);
    try {
      if (needsTerms && !(await terms.ensure())) return;
      let saved: Saved;
      try {
        saved = await work();
      } catch (e) {
        if (!isTerms(e) || !(await terms.ensure())) throw e;
        saved = await work();
      }
      onSaved(saved);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  async function search() {
    setBusy('search');
    setError(null);
    setChosen(null);
    try {
      setFound(await suggestCovers(eventId));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  async function findOfficial() {
    setBusy('official');
    setError(null);
    try {
      setOfficial(await officialCover(eventId));
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(null);
    }
  }

  function picked(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = '';
    if (!file) return;
    setError(null);
    if (file.type && !file.type.startsWith('image/')) return setError('Choisis une image (photo, capture d’écran…).');
    if (file.size > MAX_SOURCE_PHOTO) return setError('Cette photo dépasse 30 Mo. Choisis-en une plus légère.');
    setSource(URL.createObjectURL(file));
  }

  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={onClose} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Changer la couverture" testID="cover-sheet">
          <SheetTop onClose={onClose} />
          <ScrollView ref={scroller} contentContainerStyle={{ gap: 12, paddingBottom: 8 }}>
            <T weight="bold" size={20}>Couverture de l’événement</T>
            {/* 4 sources en grille 2 × 2 : en une ligne, les libellés étaient coupés (« Ma p… ») sur un iPhone. */}
            <View style={st.tabs} accessibilityRole="tablist">
              {TABS.map((t) => (
                <Pressable key={t.key} accessibilityRole="tab" accessibilityState={{ selected: tab === t.key }} accessibilityLabel={t.label}
                  onPress={() => { setTab(t.key); setError(null); }}
                  style={({ pressed }) => [st.tab, pressTransition, tab === t.key && st.tabOn, pressed && { opacity: 0.85 }]}>
                  <T size={14} weight="semibold" color={tab === t.key ? colors.text : colors.textSoft}>{t.label}</T>
                </Pressable>
              ))}
            </View>

            {tab === 'mine' ? (
              <View style={{ gap: 10 }}>
                <T muted size={14}>Une photo à toi, recadrée en format large. Tout le monde la voit sur la fiche ; elle peut être signalée comme tout contenu.</T>
                <input ref={gallery} type="file" accept="image/*,.heic,.heif" hidden onChange={picked} data-testid="cover-photo-input" />
                <input ref={camera} type="file" accept="image/*" capture="environment" hidden onChange={picked} />
                <Button label="🖼️  Choisir une photo" loading={busy === 'photo'} onPress={() => gallery.current?.click()} />
                <Button variant="secondary" label="📷  Prendre une photo" disabled={!!busy} onPress={() => camera.current?.click()} />
              </View>
            ) : null}

            {tab === 'free' ? (
              <View style={{ gap: 10 }}>
                <T muted size={14}>Des photos libres de droits qui collent à ton événement. L’auteur est crédité sous la couverture.</T>
                <Button label={found ? '↻ Proposer d’autres photos' : '🔎 Proposer des photos'} variant={found ? 'secondary' : 'primary'}
                  loading={busy === 'search'} disabled={!!busy && busy !== 'search'} onPress={() => void search()} />
                {found && !found.photos.length ? <T muted size={14}>Aucune photo trouvée. Réessaie dans un instant ou choisis une autre source.</T> : null}
                {found?.photos.length ? (
                  <View style={st.grid} testID="cover-suggestions">
                    {found.photos.map((p, i) => (
                      <Pressable key={p.pick} accessibilityRole="radio" accessibilityState={{ checked: chosen === p.pick }}
                        accessibilityLabel={`Photo ${i + 1}${p.alt ? ` : ${p.alt}` : ''}`} onPress={() => setChosen(p.pick)}
                        style={({ pressed }) => [st.thumbBox, pressTransition, chosen === p.pick && st.thumbOn, pressed && { opacity: 0.85 }]}>
                        <Image source={{ uri: p.thumb }} style={st.thumb} resizeMode="cover" />
                        <T size={11} muted numberOfLines={1} style={{ paddingHorizontal: 6, paddingVertical: 4 }}>{p.credit.replace(/^Photo : /, '')}</T>
                      </Pressable>
                    ))}
                  </View>
                ) : null}
                {found ? (
                  <T size={12} muted>
                    {found.source === 'pexels' ? 'Photos Pexels (licence Pexels).' : 'Photos Openverse (CC0, domaine public ou CC BY).'}
                    {found.ai ? ' Choisies par l’IA de Party, sans boisson.' : found.ai_note === 'consent'
                      ? ' Choisies sans l’IA : donne ton accord dans Réglages › Confidentialité pour un meilleur choix.' : ''}
                  </T>
                ) : null}
                {chosen ? <Button label="Utiliser cette photo" loading={busy === 'choose'} onPress={() => void save('choose', () => chooseCover(eventId, chosen))} /> : null}
              </View>
            ) : null}

            {tab === 'official' ? (
              <View style={{ gap: 10 }}>
                <T muted size={14}>Concert, festival, soirée en club… L’IA de Party cherche la page officielle (organisateur, salle ou billetterie) et reprend son image. Jamais une image prise au hasard sur Internet.</T>
                <Button label={official ? '↻ Chercher à nouveau' : '🌐 Chercher l’image officielle'} variant={official ? 'secondary' : 'primary'}
                  loading={busy === 'official'} disabled={!!busy && busy !== 'official'} onPress={() => void findOfficial()} />
                {official && !official.found ? <View testID="cover-official-none"><T size={14}>{official.message}</T></View> : null}
                {official?.found ? (
                  <View style={{ gap: 8 }} testID="cover-official">
                    <Image source={{ uri: official.thumb }} style={st.preview} resizeMode="cover" accessibilityLabel="Image officielle trouvée" />
                    <CoverCredit credit={`Visuel : ${official.domain}`} url={official.page} />
                    <Button label="Utiliser cette image" loading={busy === 'official-use'} onPress={() => void save('official-use', () => chooseCover(eventId, official.pick))} />
                  </View>
                ) : null}
              </View>
            ) : null}

            {tab === 'poster' ? (
              <View style={{ gap: 10 }}>
                <T muted size={14}>L’affiche Party : le titre, la date et le lieu sur un dégradé de soirée. Elle suit le titre et la date.</T>
                <Button label="🎨 Utiliser l’affiche Party" loading={busy === 'poster'} onPress={() => void save('poster', () => posterCover(eventId), false)} />
              </View>
            ) : null}

            <ErrorText error={error} />
            {error?.startsWith('Accord requis') ? (
              <Button small variant="secondary" label="Donner mon accord · Réglages › Confidentialité"
                onPress={() => { onClose(); router.push('/settings/privacy'); }} />
            ) : null}
            {hasCover ? (
              <ConfirmButton small label="Retirer la couverture" confirmLabel="Retirer"
                onConfirm={() => save('remove', () => removeCover(eventId), false)} />
            ) : null}
          </ScrollView>
        </View>
      </View>
      {source ? (
        <PhotoCropper src={source} aspect={16 / 9} label="Recadrer la couverture"
          onCancel={() => { URL.revokeObjectURL(source); setSource(null); }}
          onDone={(uri) => { URL.revokeObjectURL(source); setSource(null); void save('photo', () => uploadCover(eventId, uri)); }} />
      ) : null}
      {terms.sheet}
    </Modal>
  );
}

/**
 * La couverture en haut de la fiche : l'image, son crédit, et pour l'organisation « 🖼️ Changer la couverture » avec la
 * bulle « Nouveau » (didacticiel : une seule fois par appareil, « Compris » ou ✕ la ferme pour de bon).
 */
export function EventCover({ eventId, url, credit, creditUrl, canEdit, onChanged }: {
  eventId: string; url: string | null; credit?: string | null; creditUrl?: string | null; canEdit: boolean; onChanged: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [tip, setTip] = useState(() => canEdit && !coverTipSeen());
  const [note, setNote] = useState('');
  const shown = url?.startsWith('https://') ? url : null;
  const closeTip = () => { hideCoverTip(); setTip(false); };
  return (
    <View style={{ gap: 6, marginBottom: shown || canEdit ? 14 : 0 }}>
      {shown ? <Image source={{ uri: shown }} style={st.cover} resizeMode="cover" accessibilityLabel="Affiche de l’événement" /> : null}
      {shown && credit ? <CoverCredit credit={credit} url={creditUrl} /> : null}
      {canEdit ? (
        <View style={{ gap: 8 }}>
          {tip ? (
            <View style={st.tip} accessibilityRole="alert" testID="cover-tip">
              <View style={{ flex: 1, gap: 2 }}>
                <T size={13} weight="bold" color={colors.accentSoft}>Nouveau</T>
                <T size={14}>Change la couverture quand tu veux : ta photo, des photos libres de droits choisies pour toi, ou l’image officielle de l’événement.</T>
              </View>
              <Button small variant="secondary" label="Compris" onPress={closeTip} />
            </View>
          ) : null}
          <Button small variant="secondary" label={shown ? '🖼️  Changer la couverture' : '🖼️  Ajouter une couverture'}
            onPress={() => { closeTip(); setOpen(true); }} style={{ alignSelf: 'flex-start' }} />
        </View>
      ) : null}
      {open ? (
        <CoverSheet eventId={eventId} visible hasCover={!!url} onClose={() => setOpen(false)}
          onSaved={(saved) => {
            setOpen(false);
            setNote(saved.status === 'pending' ? 'Couverture changée : l’événement repasse en validation.' : saved.cover_url ? 'Couverture changée' : 'Couverture retirée');
            onChanged();
          }} />
      ) : null}
      {note ? <Toast message={note} onHide={() => setNote('')} /> : null}
    </View>
  );
}

/** Crédit discret sous la couverture (« Photo : Nom / Pexels », « Visuel : domaine »), lien vers la source si https. */
export function CoverCredit({ credit, url }: { credit: string; url?: string | null }) {
  const href = creditHref(url);
  // react-native-web : href + hrefAttrs rendent un vrai <a> (nouvel onglet, la fiche reste ouverte).
  const link = href ? ({ href, hrefAttrs: { target: '_blank', rel: 'noopener noreferrer' } } as object) : {};
  return (
    <Text {...link} accessibilityRole={href ? 'link' : undefined} numberOfLines={1}
      style={{ color: colors.muted, fontSize: 12, ...font.body, textDecorationLine: href ? 'underline' : 'none' }}>{credit}</Text>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.88)', justifyContent: 'flex-end', alignItems: 'center' },
  sheet: { width: '100%', maxWidth: 520, maxHeight: '92%', gap: 8, padding: 18, paddingBottom: 24, borderTopLeftRadius: radius.lg,
    borderTopRightRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  cover: { width: '100%', aspectRatio: 16 / 9, borderRadius: radius.md, backgroundColor: colors.surface2 },
  tip: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: radius.md, backgroundColor: colors.accentDim,
    borderWidth: 1, borderColor: colors.accent },
  tabs: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tab: { width: '48.5%' as unknown as number, minHeight: 44, alignItems: 'center', justifyContent: 'center', borderRadius: radius.md,
    backgroundColor: colors.fill, borderWidth: 1.5, borderColor: 'transparent' },
  tabOn: { backgroundColor: colors.accentDim, borderColor: colors.accent },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  thumbBox: { width: '48.5%' as unknown as number, borderRadius: radius.md, overflow: 'hidden', backgroundColor: colors.surface2,
    borderWidth: 2, borderColor: 'transparent' },
  thumbOn: { borderColor: colors.accent },
  thumb: { width: '100%', aspectRatio: 16 / 9 },
  preview: { width: '100%', aspectRatio: 16 / 9, borderRadius: radius.md, backgroundColor: colors.surface2 },
});
