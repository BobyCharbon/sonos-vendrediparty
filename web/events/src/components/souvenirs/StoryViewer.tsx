import { useCallback, useEffect, useRef, useState } from 'react';
import { ActivityIndicator, Image, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { ReportSheet } from '@/components/ReportSheet';
import { useSheetSignal } from '@/components/SheetGesture';
import { Avatar, Button } from '@/components/ui';
import { setBlocked, type ReportTarget } from '@/lib/moderation';
import { colors, font } from '@/lib/theme';
import {
  errorText, fetchStory, hoursLeft, keepPhoto, markSeen, PHOTO_REASONS, PHOTO_REPORT_THANKS, photoWhen, reportPhoto,
  unkeepPhoto, type Photo, type Story,
} from '@/lib/souvenirs';

const PHOTO_MS = 5000;
const FILM = '#FFB547';
const clock = new Intl.DateTimeFormat('fr-CH', { timeZone: 'Europe/Zurich', hour: '2-digit', minute: '2-digit' });

/**
 * Lecteur de story web (maquette v2, écran 6) : TOUTES les photos de la soirée, de la première à la dernière, 5 s chacune ;
 * toucher à gauche = précédente, à droite = suivante ; « ⭐ Garder dans mes souvenirs » sur les photos des autres
 * (`can_keep`) ; ⋯ Signaler (motif « Je suis sur la photo… ») et Bloquer. Ouvert seulement si l'enregistrement est autorisé
 * (`keep`) : sans enregistrement, la story se regarde dans l'app iPhone (captures bloquées), jamais ici.
 */
export function StoryViewer({ eventId, onClose, onMine }: { eventId: string; onClose: (changed: boolean) => void; onMine: () => void }) {
  const [story, setStory] = useState<Story | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [idx, setIdx] = useState(0);
  const [progress, setProgress] = useState(0);
  const [ended, setEnded] = useState(false);
  const [menu, setMenu] = useState(false);
  const [report, setReport] = useState<ReportTarget | null>(null);
  const [masked, setMasked] = useState<Record<string, string>>({});
  const [toast, setToast] = useState('');
  const [pop, setPop] = useState(0);
  const changed = useRef(false);
  const started = useRef(0);
  const paused = menu || !!report || ended;
  useSheetSignal(true);

  useEffect(() => {
    let live = true;
    fetchStory(eventId).then((s) => { if (live) setStory(s); }, (e: unknown) => { if (live) setError(errorText(e)); });
    void markSeen(eventId).catch(() => {});
    return () => { live = false; };
  }, [eventId]);

  const photos = story?.photos ?? [];
  const photo: Photo | undefined = photos[idx];
  const show = useCallback((i: number) => {
    setIdx(i);
    setProgress(0);
    started.current = Date.now();
  }, []);
  const next = useCallback(() => {
    if (idx < photos.length - 1) show(idx + 1);
    else setEnded(true);
  }, [idx, photos.length, show]);
  const prev = useCallback(() => show(Math.max(0, idx - 1)), [idx, show]);

  // Avance toute seule ; une pause (menu, signalement) reprend là où elle s'était arrêtée.
  useEffect(() => {
    if (!photos.length || paused) return undefined;
    started.current = Date.now() - progress * PHOTO_MS;
    const t = setInterval(() => {
      const f = Math.min(1, (Date.now() - started.current) / PHOTO_MS);
      setProgress(f);
      if (f >= 1) next();
    }, 60);
    return () => clearInterval(t);
  }, [photos.length, paused, next]);  // eslint-disable-line react-hooks/exhaustive-deps

  const close = useCallback(() => onClose(changed.current), [onClose]);
  // Message en haut de la photo (jamais sur « ⭐ Garder »), 2,4 s.
  useEffect(() => {
    if (!toast) return undefined;
    const t = setTimeout(() => setToast(''), 2400);
    return () => clearTimeout(t);
  }, [toast]);
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (menu || report) return;
      if (e.key === 'ArrowRight') next();
      else if (e.key === 'ArrowLeft') prev();
      else if (e.key === 'Escape') close();
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
  }, [next, prev, close, menu, report]);

  function patch(id: string, p: Partial<Photo>) {
    setStory((s) => (s ? { ...s, photos: s.photos.map((x) => (x.id === id ? { ...x, ...p } : x)) } : s));
  }
  async function toggleKeep() {
    if (!photo) return;
    const on = !photo.kept;
    patch(photo.id, { kept: on });
    setPop((n) => n + 1);
    changed.current = true;
    try {
      await (on ? keepPhoto(photo.id) : unkeepPhoto(photo.id));
      setToast(on ? '⭐ Gardée dans tes souvenirs' : 'Retirée de tes souvenirs');
    } catch (e) {
      patch(photo.id, { kept: !on });
      setToast(errorText(e));
    }
  }
  async function block() {
    if (!photo?.author) return;
    const author = photo.author;
    setMenu(false);
    try {
      await setBlocked(author.id, true);
      changed.current = true;
      setMasked((m) => ({ ...m, ...Object.fromEntries(photos.filter((p) => p.author?.id === author.id).map((p) => [p.id, `⛔ ${author.name} est bloqué·e`])) }));
      setToast('Vous ne verrez plus vos photos, dans les deux sens.');
    } catch (e) {
      setToast(errorText(e));
    }
  }

  const shown = photo && !masked[photo.id];
  const until = story?.until;
  const first = photos[0]?.taken_at;
  const last = photos[photos.length - 1]?.taken_at;

  return (
    <Modal visible transparent={false} animationType="fade" onRequestClose={close}>
      <View style={st.viewer} accessibilityViewIsModal accessibilityLabel="Story des souvenirs">
        {!story ? (
          <View style={st.center}>
            {error ? (
              <>
                <Text style={st.endText}>{error}</Text>
                <Button label="Fermer" onPress={close} style={{ maxWidth: 260, alignSelf: 'center' }} />
              </>
            ) : <ActivityIndicator color="#fff" />}
          </View>
        ) : !photos.length ? (
          <View style={st.center}>
            <Text style={st.endTitle}>📸</Text>
            <Text style={st.endText}>Aucune photo à voir dans cette story.</Text>
            <Button label="Fermer" onPress={close} style={{ maxWidth: 260, alignSelf: 'center' }} />
          </View>
        ) : (
          <>
            {photo?.url ? (
              <Image source={{ uri: photo.url }} resizeMode="contain" accessibilityLabel={`Photo de ${photo.author?.name ?? 'quelqu’un'}`}
                style={[st.photo, !shown && st.blurred]} testID="story-photo" />
            ) : null}
            <View pointerEvents="none" style={st.shadeTop} />
            <View pointerEvents="none" style={st.shadeBottom} />
            {photo && !shown ? <Text style={st.masked}>{masked[photo.id]}</Text> : null}

            <View style={st.bars} accessibilityLabel={`Photo ${idx + 1} sur ${photos.length}`}>
              {photos.map((p, i) => (
                <View key={p.id} style={st.bar}>
                  <View style={[st.barFill, { width: `${i < idx ? 100 : i === idx ? progress * 100 : 0}%` }]} />
                </View>
              ))}
            </View>
            <View style={st.head}>
              {photo?.author ? <Avatar id={photo.author.id} name={photo.author.name} photo={photo.author.avatar_url} size={36} profile={false} /> : null}
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text style={st.who} numberOfLines={1}>{photo?.mine ? 'Toi' : photo?.author?.name ?? '?'}</Text>
                <Text style={st.whoSmall}>{photo ? photoWhen(photo.taken_at) : ''}</Text>
              </View>
              {photo && !photo.mine && shown ? (
                <Pressable accessibilityRole="button" accessibilityLabel="Plus d’options" onPress={() => setMenu(true)} style={st.vbtn}>
                  <Text style={st.vbtnText}>⋯</Text>
                </Pressable>
              ) : null}
              <Pressable accessibilityRole="button" accessibilityLabel="Fermer la story" onPress={close} style={st.vbtn}>
                <Text style={st.vbtnText}>✕</Text>
              </Pressable>
            </View>

            <Pressable accessibilityRole="button" accessibilityLabel="Photo précédente" onPress={prev} style={[st.zone, { left: 0, width: '33%' }]} />
            <Pressable accessibilityRole="button" accessibilityLabel="Photo suivante" onPress={next} style={[st.zone, { right: 0, width: '67%' }]} />

            <View style={st.foot}>
              {photo && shown && photo.can_keep && story.keep ? (
                <Pressable key={pop} accessibilityRole="button" aria-pressed={!!photo.kept} accessibilityState={{ selected: !!photo.kept }}
                  onPress={() => void toggleKeep()} style={[st.keep, photo.kept && st.keepOn, pop > 0 && st.pop]}>
                  <Text style={[st.keepText, photo.kept && { color: '#3a2300' }]}>{photo.kept ? '⭐ Gardée' : '⭐ Garder dans mes souvenirs'}</Text>
                </Pressable>
              ) : null}
              {photo?.mine && story.keep ? <Text style={st.mineTag}>📸 Ta photo · déjà dans tes souvenirs</Text> : null}
              <View style={st.cnt}>
                <Text style={st.cntTitle} numberOfLines={1}>{story.title}</Text>
                <Text style={st.whoSmall}>{idx + 1} / {photos.length}</Text>
              </View>
              {until ? <Text style={st.until}>⏳ Visible encore {hoursLeft(until)} h</Text> : null}
            </View>

            {ended ? (
              <View style={st.end}>
                <Text style={{ fontSize: 54 }}>✨</Text>
                <Text style={st.endTitle}>C’était toute la soirée</Text>
                <Text style={st.endText}>
                  {photos.length} photo{photos.length > 1 ? 's' : ''}{first && last ? `, de ${clock.format(new Date(first))} à ${clock.format(new Date(last))}` : ''}.{'\n'}
                  {story.keep ? 'Tes photos et celles que tu as gardées t’attendent sur la fiche.' : 'Enregistrement désactivé : rien ne reste après la story.'}
                </Text>
                {story.keep ? <Button label="📸 Mes souvenirs" style={st.endBtn} onPress={() => { onMine(); close(); }} /> : null}
                <Button variant="secondary" label="↺ Revoir" style={st.endBtn} onPress={() => { setEnded(false); show(0); }} />
                <Button variant="ghost" label="Fermer" style={st.endBtn} onPress={close} />
              </View>
            ) : null}

            {menu && photo ? (
              <>
                <Pressable accessible={false} onPress={() => setMenu(false)} style={st.shade} />
                <View style={st.sheet} accessibilityRole="menu" accessibilityLabel="Options de la photo">
                  <View style={st.grab} />
                  <Pressable accessibilityRole="menuitem" style={st.opt}
                    onPress={() => { setMenu(false); setReport({ kind: 'souvenir', id: photo.id, label: 'cette photo' }); }}>
                    <Text style={st.optIcon}>🚩</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={st.optText}>Signaler</Text>
                      <Text style={st.optSmall}>La photo est masquée aussitôt, la modération décide.</Text>
                    </View>
                  </Pressable>
                  <Pressable accessibilityRole="menuitem" style={st.opt} onPress={() => void block()}>
                    <Text style={st.optIcon}>⛔</Text>
                    <View style={{ flex: 1 }}>
                      <Text style={[st.optText, { color: colors.redSoft }]}>Bloquer {photo.author?.name ?? ''}</Text>
                      <Text style={st.optSmall}>Vous ne verrez plus vos photos, dans les deux sens.</Text>
                    </View>
                  </Pressable>
                  <Button variant="secondary" label="Annuler" onPress={() => setMenu(false)} />
                </View>
              </>
            ) : null}
          </>
        )}
        {toast ? <Text accessibilityRole="alert" style={st.vtoast}>{toast}</Text> : null}
      </View>
      <ReportSheet target={report} reasons={PHOTO_REASONS} thanks={PHOTO_REPORT_THANKS}
        send={async (reason, comment) => {
          if (!report) return;
          await reportPhoto(report.id, reason, comment);
          changed.current = true;
          setMasked((m) => ({ ...m, [report.id]: '🚩 Photo signalée et masquée' }));
        }}
        onClose={() => setReport(null)} />
    </Modal>
  );
}

const st = StyleSheet.create({
  viewer: { flex: 1, backgroundColor: '#000', overflow: 'hidden' },
  center: { flex: 1, alignItems: 'center', justifyContent: 'center', gap: 16, padding: 30 },
  photo: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, width: '100%', height: '100%' },
  blurred: { filter: 'blur(28px)', opacity: 0.6 } as object,
  shadeTop: { position: 'absolute', top: 0, left: 0, right: 0, height: 150, backgroundImage: 'linear-gradient(rgba(0,0,0,.6), transparent)' } as object,
  shadeBottom: { position: 'absolute', bottom: 0, left: 0, right: 0, height: 220, backgroundImage: 'linear-gradient(transparent, rgba(0,0,0,.75))' } as object,
  masked: { position: 'absolute', left: 30, right: 30, top: '40%', zIndex: 4, textAlign: 'center', backgroundColor: 'rgba(0,0,0,0.6)', borderRadius: 16, padding: 14, color: '#fff', fontSize: 14, ...font.semibold },
  bars: { position: 'absolute', top: 'calc(env(safe-area-inset-top, 0px) + 12px)' as unknown as number, left: 10, right: 10, flexDirection: 'row', gap: 2, zIndex: 5 },
  bar: { flex: 1, height: 3, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.3)', overflow: 'hidden' },
  barFill: { height: '100%', backgroundColor: '#fff' },
  head: { position: 'absolute', top: 'calc(env(safe-area-inset-top, 0px) + 22px)' as unknown as number, left: 6, right: 4, flexDirection: 'row', alignItems: 'center', gap: 8, zIndex: 5, paddingHorizontal: 6 },
  who: { color: '#fff', fontSize: 14, ...font.semibold, textShadowColor: 'rgba(0,0,0,0.6)', textShadowRadius: 3 },
  whoSmall: { color: 'rgba(255,255,255,0.9)', fontSize: 12, ...font.body },
  vbtn: { width: 44, height: 44, alignItems: 'center', justifyContent: 'center' },
  vbtnText: { color: '#fff', fontSize: 22, ...font.bold, textShadowColor: 'rgba(0,0,0,0.6)', textShadowRadius: 3 },
  zone: { position: 'absolute', top: 120, bottom: 150, zIndex: 3 },
  foot: { position: 'absolute', bottom: 'calc(env(safe-area-inset-bottom, 0px) + 24px)' as unknown as number, left: 14, right: 14, zIndex: 5, alignItems: 'flex-start' },
  keep: { minHeight: 44, borderRadius: 22, paddingHorizontal: 16, backgroundColor: 'rgba(0,0,0,0.55)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.35)', justifyContent: 'center', marginBottom: 10, backdropFilter: 'blur(10px)' } as object,
  keepOn: { backgroundColor: FILM, borderColor: FILM },
  pop: { animationKeyframes: [{ '0%': { transform: [{ scale: 1 }] }, '40%': { transform: [{ scale: 1.12 }] }, '100%': { transform: [{ scale: 1 }] } }], animationDuration: '350ms' } as object,
  keepText: { color: '#fff', fontSize: 14, ...font.bold },
  mineTag: { color: '#fff', fontSize: 12.5, marginBottom: 10, backgroundColor: 'rgba(0,0,0,0.55)', borderRadius: 14, paddingHorizontal: 12, paddingVertical: 8, overflow: 'hidden', ...font.body },
  cnt: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'baseline', alignSelf: 'stretch', marginBottom: 6, gap: 10 },
  cntTitle: { color: '#fff', fontSize: 15, ...font.bold, flexShrink: 1 },
  until: { color: '#fff', backgroundColor: 'rgba(0,0,0,0.55)', borderRadius: 14, paddingHorizontal: 10, paddingVertical: 6, fontSize: 12.5, overflow: 'hidden', ...font.body },
  end: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, zIndex: 8, alignItems: 'center', justifyContent: 'center', padding: 30, gap: 12, backgroundImage: 'radial-gradient(circle at 50% 30%, #3a1d55, #0a0614 70%)' } as object,
  endTitle: { color: colors.text, fontSize: 26, ...font.bold, textAlign: 'center' },
  endText: { color: colors.muted, fontSize: 15, lineHeight: 21, textAlign: 'center', ...font.body },
  endBtn: { alignSelf: 'stretch', maxWidth: 260, marginHorizontal: 'auto' } as object,
  vtoast: { position: 'absolute', left: 24, right: 24, top: 130, zIndex: 9, backgroundColor: 'rgba(21,16,42,0.95)', borderWidth: 1, borderColor: colors.line, borderRadius: 16, paddingHorizontal: 14, paddingVertical: 12, color: colors.text, fontSize: 14, textAlign: 'center', overflow: 'hidden', ...font.semibold },
  shade: { position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, backgroundColor: 'rgba(0,0,0,0.5)', zIndex: 11 },
  sheet: { position: 'absolute', left: 0, right: 0, bottom: 0, zIndex: 12, backgroundColor: colors.surface, borderTopLeftRadius: 22, borderTopRightRadius: 22, paddingHorizontal: 12, paddingTop: 8, paddingBottom: 30, gap: 4, maxWidth: 560, marginHorizontal: 'auto' } as object,
  grab: { alignSelf: 'center', width: 40, height: 5, borderRadius: 3, backgroundColor: colors.lineStrong, marginBottom: 8 },
  opt: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingHorizontal: 8, paddingVertical: 6, borderRadius: 14 },
  optIcon: { fontSize: 20, width: 28, textAlign: 'center' },
  optText: { color: colors.text, fontSize: 16, ...font.semibold },
  optSmall: { color: colors.muted, fontSize: 12.5, ...font.body },
});
