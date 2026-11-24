import { router } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import { useTermsGate } from '@/components/TermsSheet';
import { Button, Card, ErrorText, T, Title, Toast } from '@/components/ui';
import { useSignal } from '@/lib/data';
import { colors, font, radius } from '@/lib/theme';
import {
  CANCEL_SECONDS, canRetry, cancelPhoto, errorText, fetchCounter, hoursLeft, isTermsRefusal, MAX_POSES, nativeSouvenirs, noticeText,
  onSouvenirsChanged, posesLabel, remaining, revealWhen, uploadPhoto, type Counter,
} from '@/lib/souvenirs';

import { MySouvenirs } from './MySouvenirs';
import { RevealNow, ReviewSheet } from './ReviewSheet';
import { StoryViewer } from './StoryViewer';
import { SouvenirsTutorial, TUTORIAL_READY, useSouvenirsTutorial } from './SouvenirsTutorial';

const FILM = '#FFB547';
/** Relecture régulière : passage d'une phase à l'autre (ouverture, fin, dévoilement) sans signal de la base. */
const TICK_MS = 30_000;

type Undo = { id: string | null; left: number; seconds: number; state: 'sending' | 'sent' | 'cancelled' };

/**
 * Souvenirs sur la fiche d'un événement (maquette v2 validée le 24.11) : l'avis « 📸 Souvenirs actif », l'appareil jetable
 * (3 poses, jamais revues, « Annuler » 5 s), le compteur commun (le nombre seulement), le compte à rebours, la carte du
 * dévoilement, « Mes souvenirs », et « 👀 Relire les photos » pour l'organisation.
 * `open` : lien `?souvenirs=1` (story) ou `?souvenirs=review` (relecture), ouvert une fois l'état lu.
 * Temps réel : signal `event:<id>` ; l'app iPhone rappelle `window.PartySouvenirs.changed(id)`.
 */
export function SouvenirsCard({ eventId, title, open }: { eventId: string; title: string; open?: string }) {
  const [c, setC] = useState<Counter | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [story, setStory] = useState(false);
  const [review, setReview] = useState(false);
  const [undo, setUndo] = useState<Undo | null>(null);
  const [mineKey, setMineKey] = useState(0);
  const [note, setNote] = useState('');
  /** Photo qui n'est pas partie (réseau, délai) : « Réessayer » la renvoie, jamais montrée. */
  const [failed, setFailed] = useState<Blob | null>(null);
  const [, setTick] = useState(0);
  const input = useRef<HTMLInputElement | null>(null);
  const opened = useRef(false);
  const mineRef = useRef<View>(null);
  const gate = useTermsGate('Avant ta première photo');
  const tutorial = useSouvenirsTutorial(!open);   // ouvert par un lien (story, relecture, « native » : story de l'app iPhone) : pas d'office

  const load = useCallback(() => fetchCounter(eventId).then((x) => setC(x), () => setC((old) => old)), [eventId]);
  useEffect(() => { void load(); }, [load]);
  useSignal([`event:${eventId}`], load);
  useEffect(() => onSouvenirsChanged(eventId, () => { void load(); setMineKey((k) => k + 1); }), [eventId, load]);
  useEffect(() => {
    const t = setInterval(() => {
      setTick((n) => n + 1);
      const edges = [c?.take_from, c?.take_until, c?.reveal_at, c?.story_until].filter(Boolean).map((x) => new Date(x!).getTime());
      if (edges.some((e) => e <= Date.now() && e > Date.now() - TICK_MS)) void load();
    }, TICK_MS);
    return () => clearInterval(t);
  }, [c, load]);

  const native = nativeSouvenirs();
  const openStory = useCallback(() => {
    if (native?.story) { native.story(eventId); return; }
    setStory(true);
  }, [native, eventId]);

  // Lien de la notification : la story (?souvenirs=1) ou la relecture (?souvenirs=review), une seule fois.
  useEffect(() => {
    if (!c?.enabled || opened.current || !open) return;
    opened.current = true;
    const t = setTimeout(() => {
      router.setParams({ souvenirs: undefined });  // ouvert une fois : recharger la fiche ne le rouvre pas
      if (open === 'review' && c.staff) setReview(true);
      else if (open === '1' && c.phase === 'story' && (c.member || c.staff) && (c.keep || native?.story)) openStory();
    }, 0);
    return () => clearTimeout(t);
  }, [c, open, native, openStory]);

  // Compte à rebours d'« Annuler » : 5 s, puis la photo reste au labo.
  useEffect(() => {
    if (undo?.state !== 'sent') return undefined;
    if (undo.seconds <= 0) {
      const t = setTimeout(() => setUndo(null), 300);
      return () => clearTimeout(t);
    }
    const t = setTimeout(() => setUndo((u) => (u && u.state === 'sent' ? { ...u, seconds: u.seconds - 1 } : u)), 1000);
    return () => clearTimeout(t);
  }, [undo]);

  if (!c?.enabled || c.phase === 'off') return null;
  const phase = c.phase ?? 'soon';
  const left = c.left ?? 0;
  const count = c.count ?? 0;
  const circle = !!(c.member || c.staff);
  const before = phase === 'soon' || phase === 'open' || phase === 'waiting';
  const toReview = Math.max(0, count - (c.taken ?? 0));  // mes propres photos ne sont pas dans la relecture

  function shoot() {
    if (native?.camera) { native.camera(eventId); return; }
    input.current?.click();
  }

  async function send(file: Blob, retried = false) {
    setError(null);
    setFailed(null);
    setUndo({ id: null, left, seconds: CANCEL_SECONDS, state: 'sending' });
    try {
      const done = await uploadPhoto(eventId, file);
      setUndo({ id: done.id, left: done.left, seconds: CANCEL_SECONDS, state: 'sent' });
      void load();
    } catch (e) {
      setUndo(null);
      if (isTermsRefusal(e) && !retried && await gate.ensure()) return send(file, true);  // CGU acceptées : même photo, nouvel essai
      setError(errorText(e));
      if (canRetry(e)) setFailed(file);
      void load();
    }
  }

  function picked(e: { target: HTMLInputElement }) {
    const file = e.target.files?.[0];
    e.target.value = '';  // la photo n'est jamais montrée ; le même fichier peut repartir après un refus
    if (file) void send(file);
  }

  async function cancel() {
    if (!undo?.id) return;
    const id = undo.id;
    setUndo({ ...undo, state: 'cancelled' });
    try {
      await cancelPhoto(id);
      setTimeout(() => setUndo((u) => (u?.state === 'cancelled' ? null : u)), 1800);
    } catch (e) {
      setUndo(null);
      setError(errorText(e));
    }
    void load();
  }

  const goMine = () => {
    setMineKey((k) => k + 1);
    setTimeout(() => (mineRef.current as unknown as HTMLElement | null)?.scrollIntoView?.({ behavior: 'smooth', block: 'start' }), 350);
  };

  return (
    <View style={{ gap: 12 }} testID="souvenirs">
      {before ? (
        <View style={st.notice} accessibilityRole="summary">
          <View style={st.live} />
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={st.noticeTitle}>📸 Souvenirs actif</Text>
            <Text style={st.noticeText}>{noticeText(c)}</Text>
          </View>
        </View>
      ) : null}

      {phase === 'soon' || phase === 'open' ? (
        <Card style={{ gap: 12 }}>
          <View style={st.camcard}>
            <Camera />
            <View style={{ flex: 1, gap: 2 }}>
              <T weight="bold" size={16}>Ton appareil jetable</T>
              {!circle ? (
                <T muted size={13}>Réponds Présent ou Peut-être pour avoir tes 3 poses.</T>
              ) : phase === 'soon' ? (
                <T muted size={13}>S’ouvre au début de la soirée{c.take_from ? `, ${revealWhen(c.take_from)}` : ''}.</T>
              ) : (
                <T muted size={13}>Il te reste <Text style={{ color: FILM, ...font.bold }}>{posesLabel(left)}</Text></T>
              )}
              {circle ? (
                <View style={st.poses} accessibilityLabel={`${left} poses sur ${MAX_POSES}`}>
                  {Array.from({ length: MAX_POSES }, (_, i) => (
                    <View key={i} style={[st.pose, i >= (phase === 'soon' ? MAX_POSES : left) && st.poseUsed]}>
                      <Text style={[st.poseText, i >= (phase === 'soon' ? MAX_POSES : left) && { color: '#6d6394' }]}>{i + 1}</Text>
                    </View>
                  ))}
                </View>
              ) : null}
            </View>
          </View>

          {phase === 'open' && c.can_take ? (
            <>
              <Button label={`📸 Prendre une photo · ${left} restante${left > 1 ? 's' : ''}`} onPress={shoot}
                loading={undo?.state === 'sending'} disabled={undo?.state === 'sent'} />
              <T muted size={12} style={{ textAlign: 'center' }}>
                Une seule chance : pas d’aperçu, la photo part au labo.
                {c.keep === false ? '\n⚠️ Montrée 24 h dans la story, puis effacée : personne ne la garde.' : ''}
              </T>
            </>
          ) : phase === 'open' && c.member && left === 0 ? (
            <View style={st.done}>
              <Text style={{ fontSize: 28 }}>🎞️</Text>
              <View style={{ flex: 1 }}>
                <T weight="bold">Pellicule terminée</T>
                <T muted size={13}>Tes 3 photos sont au labo. Profite de la soirée, on s’occupe du reste ✨</T>
              </View>
            </View>
          ) : null}

          {undo ? <UndoBar undo={undo} onCancel={() => void cancel()} /> : null}
          {phase === 'open' ? (
            <T muted size={13} style={{ textAlign: 'center' }}>🧪 Au labo : <Text style={{ color: colors.text, ...font.bold }}>{count} photo{count > 1 ? 's' : ''}</Text> de la bande</T>
          ) : null}
          {Platform.OS === 'web' && !native?.camera ? (
            <input ref={input} type="file" accept="image/*" capture="environment" hidden aria-label="Prendre une photo"
              data-testid="souvenir-input" onChange={picked} />
          ) : null}
        </Card>
      ) : null}

      {phase === 'waiting' && circle ? (
        <View style={st.ticket}>
          <Text style={{ fontSize: 30 }}>🎟️</Text>
          <View style={{ flex: 1 }}>
            <T muted size={12}>Ticket du labo · {c.taken ?? 0} photo{(c.taken ?? 0) > 1 ? 's' : ''} à toi · {count} en tout</T>
            <Text style={st.big} accessibilityLabel={`Dévoilement dans ${remaining(c.reveal_at)}`}>{remaining(c.reveal_at)}</Text>
            <T muted size={12}>avant le dévoilement{c.reveal_at ? `, ${revealWhen(c.reveal_at)}, pour tout le monde en même temps` : ''}</T>
          </View>
        </View>
      ) : null}

      {phase === 'story' && circle ? (
        <Card style={st.premiere}>
          <Text style={{ fontSize: 34 }}>📸</Text>
          <Title size={20}>Les souvenirs sont arrivés</Title>
          <T size={13} color={colors.textSoft}>
            {count} photo{count > 1 ? 's' : ''} de « {title} »{c.story_until ? ` · Visible encore ${hoursLeft(c.story_until)} h` : ''}
            {c.keep === false ? ' · rien ne reste après' : ' · garde tes préférées ⭐'}
          </T>
          {c.keep === false && !native?.story ? (
            <View style={st.appOnly}>
              <T size={14} weight="semibold">📱 Cette story se regarde dans l’app iPhone (captures bloquées).</T>
              <T muted size={12}>L’organisation a choisi d’effacer les photos après la story : elles ne s’affichent pas dans le navigateur.</T>
            </View>
          ) : count > 0 ? (
            <Button label={c.seen ? '▶︎ Revoir la story' : '▶︎ Voir la story'} onPress={openStory} />
          ) : null}
        </Card>
      ) : null}

      {/* Passé « Pas présent » après coup : ses propres photos restent à lui (la carte se cache si la liste est vide). */}
      {(phase === 'story' || phase === 'after') && c.keep ? (
        <View ref={mineRef}>
          <MySouvenirs eventId={eventId} refreshKey={`${mineKey}|${c.count}`} hideWhenEmpty={!circle} />
        </View>
      ) : null}

      {phase === 'after' && c.keep === false && circle ? (
        <Card>
          <Title size={18}>📸 Souvenirs</Title>
          <View style={st.empty}>
            <View style={st.ill}><Text style={{ fontSize: 40 }}>📷</Text><View style={st.slash} /></View>
            <T weight="bold" size={17} style={{ textAlign: 'center', lineHeight: 23 }}>
              Les photos de cette soirée ne se gardent pas : elles n’étaient visibles que pendant les 24 h de la story.
            </T>
            <T muted size={13.5} style={{ textAlign: 'center' }}>
              L’organisation avait choisi d’effacer les photos après la story. Personne n’a pu les garder, et leurs fichiers sont effacés.
            </T>
            <View style={st.pastst}>
              <Text style={{ fontSize: 20 }}>⏳</Text>
              <T muted size={13} style={{ flex: 1 }}>
                Story terminée{c.story_until ? ` le ${revealWhen(c.story_until)}` : ''} · rien dans les souvenirs de personne.
              </T>
            </View>
          </View>
        </Card>
      ) : null}

      {/* Après la story, plus rien à relire (les photos ne sont plus signées) : le lien d'un signalement l'ouvre encore. */}
      {c.staff && phase !== 'soon' && phase !== 'after' ? (
        <View style={{ gap: 8 }}>
          <Pressable accessibilityRole="button" accessibilityLabel={`Relire les photos (${toReview}), organisation seulement`}
            onPress={() => setReview(true)} style={({ pressed }) => [st.revBtn, pressed && { opacity: 0.85 }]}>
            <T weight="semibold">👀 Relire les photos ({toReview})</T>
            <Text style={st.orgtag}>Organisation seulement</Text>
          </Pressable>
          {c.can_reveal_now ? <RevealNow eventId={eventId} onDone={(msg) => { setNote(msg); void load(); }} /> : null}
        </View>
      ) : null}

      {TUTORIAL_READY ? (
        <Pressable accessibilityRole="button" testID="souvenirs-tutorial-again" onPress={tutorial.show} style={{ alignSelf: 'flex-start', minHeight: 44, justifyContent: 'center' }}>
          <T size={13} color={colors.accentSoft}>❔ Comment ça marche</T>
        </Pressable>
      ) : null}
      <ErrorText error={error} />
      {failed && phase === 'open' ? <Button variant="secondary" label="↻ Réessayer" onPress={() => void send(failed)} /> : null}
      {note ? <Toast message={note} onHide={() => setNote('')} /> : null}

      {story ? <StoryViewer eventId={eventId} onMine={goMine} onClose={(changed) => { setStory(false); if (changed) setMineKey((k) => k + 1); void load(); }} /> : null}
      {review ? <ReviewSheet eventId={eventId} canRevealNow={!!c.can_reveal_now} onClose={(changed) => { setReview(false); if (changed) void load(); }} /> : null}
      {gate.sheet}
      {/* Didacticiel : d'office une seule fois par appareil, puis par « Comment ça marche ». */}
      <SouvenirsTutorial visible={tutorial.visible && !story && !review} staff={!!c.staff} keep={c.keep !== false}
        onSkip={tutorial.skip} onNever={tutorial.never} />
    </View>
  );
}

function Camera() {
  return (
    <View style={st.disp} accessibilityElementsHidden importantForAccessibility="no-hide-descendants">
      <View style={st.dispFlash} />
      <View style={st.dispLens} />
    </View>
  );
}

function UndoBar({ undo, onCancel }: { undo: Undo; onCancel: () => void }) {
  const leftAfter = undo.left;
  return (
    <View style={st.undo} accessibilityLiveRegion="polite" testID="souvenir-undo">
      <View style={{ flex: 1 }}>
        {undo.state === 'sending' ? (
          <><T weight="semibold" size={14}>🧪 Envoi au labo…</T><T muted size={12}>Tu ne la reverras qu’au dévoilement.</T></>
        ) : undo.state === 'cancelled' ? (
          <><T weight="semibold" size={14}>↩︎ Photo annulée</T><T muted size={12}>Effacée sans être montrée · pose rendue.</T></>
        ) : (
          <><T weight="semibold" size={14}>🧪 Partie au labo</T>
            <T muted size={12}>{leftAfter > 0 ? `Encore ${posesLabel(leftAfter)} · tu ne la reverras qu’au dévoilement.` : 'Dernière pose · tu ne la reverras qu’au dévoilement.'}</T></>
        )}
      </View>
      {undo.state === 'sent' && undo.seconds > 0 ? (
        <Pressable accessibilityRole="button" accessibilityLabel={`Annuler la photo, encore ${undo.seconds} secondes`} onPress={onCancel} style={st.undoBtn}>
          <Text style={st.undoBtnText}>↩︎ Annuler · {undo.seconds} s</Text>
        </Pressable>
      ) : null}
      {undo.state === 'sent' ? <View style={[st.undoBarLine, { width: `${(undo.seconds / CANCEL_SECONDS) * 100}%` }]} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  notice: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 11, paddingHorizontal: 14, borderRadius: radius.md, backgroundColor: 'rgba(255,79,154,0.12)', borderWidth: 1, borderColor: 'rgba(255,79,154,0.5)' },
  live: { width: 8, height: 8, borderRadius: 4, backgroundColor: colors.accent, marginTop: 6, boxShadow: `0 0 8px ${colors.accent}`, animationKeyframes: [{ '0%': { opacity: 1 }, '50%': { opacity: 0.3 }, '100%': { opacity: 1 } }], animationDuration: '1.6s', animationIterationCount: 'infinite' } as object,
  noticeTitle: { color: colors.text, fontSize: 14, lineHeight: 19, ...font.bold },
  noticeText: { color: colors.textSoft, fontSize: 13, lineHeight: 18, ...font.body },
  camcard: { flexDirection: 'row', gap: 14, alignItems: 'center' },
  disp: { width: 64, height: 48, borderRadius: 10, backgroundImage: 'linear-gradient(180deg, #FFB547, #ff8a3d)', boxShadow: 'inset 0 -6px 0 rgba(0,0,0,.2)' } as object,
  dispFlash: { position: 'absolute', width: 10, height: 6, backgroundColor: '#fff', borderRadius: 2, left: 8, top: 6 },
  dispLens: { position: 'absolute', width: 24, height: 24, borderRadius: 12, backgroundColor: '#1a0f33', borderWidth: 3, borderColor: 'rgba(255,255,255,0.2)', left: 20, top: 12 },
  poses: { flexDirection: 'row', gap: 6, marginTop: 6 },
  pose: { width: 26, height: 34, borderRadius: 5, backgroundColor: FILM, alignItems: 'center', justifyContent: 'center', boxShadow: '0 0 10px rgba(255,181,71,.4)' } as object,
  poseUsed: { backgroundColor: '#3A2F63', boxShadow: 'none' } as object,
  poseText: { color: '#3a2300', fontSize: 13, ...font.bold },
  done: { flexDirection: 'row', gap: 12, alignItems: 'center', padding: 12, borderRadius: radius.md, backgroundColor: colors.fill },
  undo: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 10, paddingLeft: 14, paddingRight: 10, borderRadius: 18, backgroundColor: 'rgba(21,16,42,0.94)', borderWidth: 1, borderColor: 'rgba(255,181,71,0.55)', overflow: 'hidden' },
  undoBtn: { minHeight: 44, paddingHorizontal: 14, borderRadius: 22, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
  undoBtnText: { color: FILM, fontSize: 14, ...font.bold },
  undoBarLine: { position: 'absolute', left: 0, bottom: 0, height: 3, backgroundColor: FILM, transitionProperty: 'width', transitionDuration: '1s', transitionTimingFunction: 'linear' } as object,
  ticket: { flexDirection: 'row', gap: 14, alignItems: 'center', padding: 16, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderStyle: 'dashed', borderColor: 'rgba(255,181,71,0.55)' },
  big: { color: colors.text, fontSize: 30, ...font.bold, letterSpacing: -0.5 },
  premiere: { gap: 10, borderColor: 'rgba(255,79,154,0.6)', backgroundImage: 'radial-gradient(circle at 20% 0%, rgba(255,181,71,.25), transparent 45%), radial-gradient(circle at 90% 30%, rgba(255,79,154,.3), transparent 50%), linear-gradient(135deg, #2c1a4f, #1a0f33)' } as object,
  appOnly: { gap: 4, padding: 12, borderRadius: radius.md, backgroundColor: 'rgba(0,0,0,0.3)' },
  empty: { alignItems: 'center', gap: 8, paddingTop: 6 },
  ill: { width: 96, height: 96, borderRadius: 48, backgroundColor: colors.bg, alignItems: 'center', justifyContent: 'center', marginBottom: 4 },
  slash: { position: 'absolute', width: 110, height: 3, backgroundColor: colors.muted, transform: [{ rotate: '-40deg' }], borderRadius: 2, opacity: 0.7 },
  pastst: { flexDirection: 'row', gap: 10, alignItems: 'center', alignSelf: 'stretch', backgroundColor: colors.bg, borderRadius: radius.md, paddingVertical: 10, paddingHorizontal: 12, marginTop: 6 },
  revBtn: { minHeight: 50, borderRadius: 25, paddingHorizontal: 16, backgroundColor: colors.surface2, flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8 },
  orgtag: { fontSize: 11, ...font.semibold, color: FILM, backgroundColor: 'rgba(255,181,71,0.15)', borderRadius: 9, paddingHorizontal: 8, paddingVertical: 2, overflow: 'hidden' },
});
