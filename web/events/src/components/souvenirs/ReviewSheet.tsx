import { useCallback, useEffect, useState } from 'react';
import { Image, Modal, Pressable, ScrollView, StyleSheet, Text, View } from 'react-native';

import { SheetClose, useSheetSignal, useSheetTop } from '@/components/SheetGesture';
import { Avatar, Button, ErrorText, Loading, T, Toast } from '@/components/ui';
import { colors, font } from '@/lib/theme';
import {
  errorText, fetchReview, reasonLabel, removePhoto, restorePhoto, revealNow, type Photo, type Review,
} from '@/lib/souvenirs';

const clock = new Intl.DateTimeFormat('fr-CH', { timeZone: 'Europe/Zurich', hour: '2-digit', minute: '2-digit' });

/**
 * « 👀 Relire les photos » (maquette v2, écran 2) : réservé à l'organisation (organisateur, co-organisateurs, admins), sans
 * réglage. ✕ retire une photo pour tout le monde (deux touchers). Les photos signalées passent en tête, floutées, avec le
 * motif (jamais qui a signalé) : Retirer (définitivement) ou Remettre. Mes propres photos n'y sont pas : je les découvre au
 * dévoilement, comme les autres. « Dévoiler maintenant » quand la soirée est finie.
 */
export function ReviewSheet({ eventId, canRevealNow, onClose }: { eventId: string; canRevealNow: boolean; onClose: (changed: boolean) => void }) {
  const [data, setData] = useState<Review | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState('');
  const [arm, setArm] = useState<string | null>(null);
  const [peek, setPeek] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [changed, setChanged] = useState(false);
  const top = useSheetTop();
  useSheetSignal(true);

  const load = useCallback(() => fetchReview(eventId).then((r) => { setData(r); setError(null); }, (e: unknown) => setError(errorText(e))), [eventId]);
  useEffect(() => { void load(); }, [load]);
  useEffect(() => {
    if (!arm) return undefined;
    const t = setTimeout(() => setArm(null), 3000);
    return () => clearTimeout(t);
  }, [arm]);

  async function run(key: string, action: () => Promise<unknown>, done: string) {
    setBusy(key);
    try {
      await action();
      setChanged(true);
      setToast(done);
      setArm(null);
      await load();
    } catch (e) {
      // Refus de la base (ex. « Remettre » d'une photo que seule la modération peut trancher) : la phrase, puis la liste à jour.
      setToast(errorText(e));
      setArm(null);
      await load();
    } finally {
      setBusy(null);
    }
  }

  const close = () => onClose(changed);
  // Mes photos n'y sont pas ; une photo sans lien (plus signée) ne ferait qu'une case grise.
  const photos = (data?.photos ?? []).filter((p) => !p.mine && p.url);
  const reported = data?.reported ?? [];
  const before = !data || data.phase === 'open' || data.phase === 'waiting' || data.phase === 'soon';

  return (
    <Modal visible animationType="slide" onRequestClose={close}>
      <View style={[st.page, { paddingTop: top }]} accessibilityViewIsModal accessibilityLabel="Relire les photos">
        <View style={st.nav}>
          <View style={{ flex: 1 }}>
            <Text style={st.title}>
              Relire les photos ({photos.length}){reported.length ? <Text style={{ color: colors.accent }}> · 🚩 {reported.length}</Text> : null}
            </Text>
            <T muted size={12}>Organisation seulement{before ? ' · avant le dévoilement' : ''}</T>
          </View>
          <SheetClose onPress={close} label="Fermer la relecture" />
        </View>
        <ScrollView contentContainerStyle={st.body}>
          <T muted size={13}>
            ✕ retire une photo pour tout le monde. Tes propres photos n’y sont pas : tu les découvriras au dévoilement, comme les autres.
          </T>
          <ErrorText error={error} />
          {!data && !error ? <Loading /> : null}
          {data && !photos.length && !reported.length ? <T muted style={{ textAlign: 'center', paddingVertical: 24 }}>Aucune photo pour l’instant.</T> : null}
          <View style={st.grid}>
            {reported.map((p) => (
              <View key={p.id} style={[st.tile, st.flagged]} testID="review-reported">
                {p.url ? <Image source={{ uri: p.url }} style={[st.img, peek !== p.id && st.blur]} accessibilityLabel="Photo signalée" /> : <View style={[st.img, st.ph]} />}
                <Pressable accessibilityRole="button" accessibilityLabel={peek === p.id ? 'Flouter la photo' : 'Voir la photo signalée'}
                  disabled={!p.url} onPress={() => setPeek(peek === p.id ? null : p.id)} style={st.flag}>
                  <Text style={st.flagTitle}>🚩 Signalée</Text>
                  {(p.reasons ?? []).map((r) => <Text key={r} style={st.flagWhy}>{reasonLabel(r)}</Text>)}
                </Pressable>
                <View style={st.flActs}>
                  <Pressable accessibilityRole="button" accessibilityLabel={`Retirer la photo de ${p.author?.name ?? '?'}`} disabled={!!busy}
                    onPress={() => void run(p.id, () => removePhoto(p.id), 'Photo retirée : personne ne la verra.')} style={st.flBtn}>
                    <Text style={[st.flBtnText, { color: colors.redSoft }]}>Retirer</Text>
                  </Pressable>
                  {p.can_restore !== false ? (
                    <Pressable accessibilityRole="button" accessibilityLabel={`Remettre la photo de ${p.author?.name ?? '?'}`} disabled={!!busy}
                      onPress={() => void run(p.id, () => restorePhoto(p.id), before ? 'Photo remise.' : 'Photo remise dans la story.')} style={st.flBtn}>
                      <Text style={st.flBtnText}>Remettre</Text>
                    </Pressable>
                  ) : (
                    <View style={[st.flBtn, st.flNote]} testID="review-moderation-decides">
                      <Text style={st.flNoteText}>La modération décide</Text>
                    </View>
                  )}
                </View>
                <By p={p} />
              </View>
            ))}
            {photos.map((p) => (
              <View key={p.id} style={st.tile} testID="review-photo">
                {p.url ? <Image source={{ uri: p.url }} style={st.img} accessibilityLabel={`Photo de ${p.author?.name ?? '?'}`} /> : <View style={[st.img, st.ph]} />}
                <Pressable accessibilityRole="button" disabled={!!busy}
                  accessibilityLabel={arm === p.id ? 'Retirer ?' : `Retirer la photo de ${p.author?.name ?? '?'} (${clock.format(new Date(p.taken_at))})`}
                  onPress={() => (arm === p.id ? void run(p.id, () => removePhoto(p.id), 'Photo retirée : personne ne la verra.') : setArm(p.id))}
                  style={[st.rm, arm === p.id && st.rmAsk]}>
                  <Text style={[st.rmText, arm === p.id && { fontSize: 13 }]}>{arm === p.id ? 'Retirer ?' : '✕'}</Text>
                </Pressable>
                <By p={p} />
              </View>
            ))}
          </View>
          {canRevealNow ? <RevealNow eventId={eventId} onDone={(msg) => { setChanged(true); setToast(msg); void load(); }} /> : null}
        </ScrollView>
        {toast ? <Toast message={toast} onHide={() => setToast('')} /> : null}
      </View>
    </Modal>
  );
}

/** « Dévoiler maintenant » (organisation, soirée finie) : deux touchers ; la base prévient tout le monde, une fois. */
export function RevealNow({ eventId, onDone }: { eventId: string; onDone: (message: string) => void }) {
  const [armed, setArmed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function go() {
    setBusy(true);
    try {
      await revealNow(eventId);
      setArmed(false);
      onDone('📸 Dévoilé : tout le monde est prévenu.');
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <View style={{ gap: 8, marginTop: 4 }}>
      <T muted size={13}>La soirée est finie : tu peux dévoiler les photos à tous maintenant, sans attendre 24 h.</T>
      {armed ? (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button small variant="secondary" label="Attendre" style={{ flex: 1 }} onPress={() => setArmed(false)} />
          <Button small label="Oui, dévoiler" style={{ flex: 1 }} loading={busy} onPress={() => void go()} />
        </View>
      ) : <Button label="Dévoiler maintenant" onPress={() => setArmed(true)} />}
      <ErrorText error={error} />
    </View>
  );
}

function By({ p }: { p: Photo }) {
  return (
    <View style={st.by} pointerEvents="none">
      {p.author ? <Avatar id={p.author.id} name={p.author.name} photo={p.author.avatar_url} size={22} profile={false} /> : null}
      <Text style={st.byName} numberOfLines={1}>{p.author?.name ?? '?'}</Text>
      <Text style={st.byTime}>{clock.format(new Date(p.taken_at))}</Text>
    </View>
  );
}

const st = StyleSheet.create({
  page: { flex: 1, backgroundColor: colors.bg },
  nav: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingHorizontal: 16, paddingBottom: 10 },
  title: { color: colors.text, fontSize: 18, ...font.bold },
  body: { paddingHorizontal: 16, paddingBottom: 60, gap: 10, maxWidth: 720, width: '100%', alignSelf: 'center' },
  grid: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  tile: { width: 'calc(50% - 4px)' as unknown as number, height: 190, borderRadius: 12, overflow: 'hidden', backgroundColor: colors.surface2 },
  flagged: { borderWidth: 2, borderColor: colors.accent },
  img: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, width: '100%', height: '100%' },
  blur: { filter: 'blur(12px)', opacity: 0.6 } as object,
  ph: { backgroundImage: 'radial-gradient(circle at 30% 25%, #FF4F9A88, transparent 55%), radial-gradient(circle at 75% 75%, #9B6BFF88, transparent 55%), #140b26' } as object,
  flag: { position: 'absolute', top: 6, left: 6, right: 6, backgroundColor: 'rgba(21,16,42,0.9)', borderRadius: 8, paddingHorizontal: 7, paddingVertical: 4 },
  flagTitle: { color: colors.accent, fontSize: 12, ...font.bold },
  flagWhy: { color: colors.text, fontSize: 11, ...font.medium },
  flActs: { position: 'absolute', left: 6, right: 6, bottom: 32, flexDirection: 'row', gap: 4 },
  flBtn: { flex: 1, minHeight: 44, borderRadius: 10, backgroundColor: 'rgba(21,16,42,0.92)', alignItems: 'center', justifyContent: 'center' },
  flBtnText: { color: colors.text, fontSize: 13, ...font.bold },
  flNote: { paddingHorizontal: 4 },
  flNoteText: { color: colors.text, fontSize: 11, lineHeight: 14, textAlign: 'center', ...font.medium },
  rm: { position: 'absolute', top: 4, right: 4, minWidth: 44, height: 44, borderRadius: 22, backgroundColor: 'rgba(0,0,0,0.6)', alignItems: 'center', justifyContent: 'center', paddingHorizontal: 10 },
  rmAsk: { backgroundColor: '#FF6B7A' },
  rmText: { color: '#fff', fontSize: 16, ...font.bold },
  by: { position: 'absolute', left: 0, right: 0, bottom: 0, paddingTop: 16, paddingBottom: 6, paddingHorizontal: 8, flexDirection: 'row', alignItems: 'center', gap: 6, backgroundImage: 'linear-gradient(transparent, rgba(0,0,0,.75))' } as object,
  byName: { flex: 1, color: '#fff', fontSize: 12, ...font.semibold },
  byTime: { color: 'rgba(255,255,255,0.8)', fontSize: 12, ...font.body },
});
