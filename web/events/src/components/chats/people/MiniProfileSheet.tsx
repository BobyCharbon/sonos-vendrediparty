import { router, type Href } from 'expo-router';
import { useCallback, useEffect, useRef, useState } from 'react';
import { Modal, Pressable, ScrollView, StyleSheet, Text, View, useWindowDimensions, type GestureResponderEvent } from 'react-native';

import { GroupTile } from '@/components/GroupBits';
import { PhotoTap } from '@/components/ProfilePhotoViewer';
import { ReportSheet } from '@/components/ReportSheet';
import { SheetBackdrop, useSheetDrag, useSheetTop } from '@/components/SheetGesture';
import { useTermsGate } from '@/components/TermsSheet';
import { Skeleton } from '@/components/ui';
import { faceLook } from '@/components/pronos/KitTheme';
import { discussionsOn } from '@/lib/features';
import { relativeDay } from '@/lib/format';
import { setBlocked, type ReportTarget } from '@/lib/moderation';
import { duration, ease, reducedMotion, transition } from '@/lib/motion';

import { DateTile, Icon, K, Label, NeonButton, PersonFace, disp, txt, web } from './bits';
import { fetchMini, metLabel, nativeOpenDirect, openDirect, refusal, shortName, type Answer, type Mini, type MiniEvent } from './people';

/**
 * Mini-profil (maquette 1-neon/3, contrat §4 et §8) : feuille à deux hauteurs (moitié, plein ; glisser vers le haut ou
 * faire défiler l'agrandit, glisser vers le bas la ferme, ✕, fond qui ferme). Couverture à la couleur de la personne,
 * grande photo, nom, « Jamais rencontré » / « Déjà vu N fois », « Envoyer un message » (désactivé avec sa raison si la
 * base dit « none ») + Fiche, en commun (groupes), 3 dernières soirées ensemble, à venir ensemble, Bloquer · Signaler.
 */
export function MiniProfileSheet({ userId, onClose }: { userId: string; onClose: () => void }) {
  const [mini, setMini] = useState<Mini | null>(null);
  const [version, setVersion] = useState(0);
  const [full, setFull] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [confirmBlock, setConfirmBlock] = useState(false);
  const [report, setReport] = useState<ReportTarget | null>(null);
  const sheet = useRef<View>(null);
  const scroller = useRef<ScrollView>(null);
  const touchY = useRef<number | null>(null);
  const terms = useTermsGate('Avant d’écrire');
  const { height } = useWindowDimensions();
  const top = useSheetTop();
  const maxH = height - top;
  const halfH = Math.min(maxH, Math.max(520, Math.round(height * 0.75)));

  const close = useCallback(() => onClose(), [onClose]);
  useSheetDrag(true, close, sheet, scroller);

  useEffect(() => {
    let live = true;
    fetchMini(userId).then((m) => {
      if (!live) return;
      // Base sans mini-profil (ou réponse inattendue) : la fiche complète, comme avant.
      if (!m) { onClose(); router.push(`/member/${userId}`); return; }
      setMini(m);
    }, () => { if (live) { onClose(); router.push(`/member/${userId}`); } });
    return () => { live = false; };
  }, [userId, version, onClose]);

  const go = (path: string) => { close(); router.push(path as Href); };

  async function write() {
    if (!mini) return;
    setError(null);
    if (nativeOpenDirect(mini.id)) return close();
    setBusy(true);
    try {
      let r = await openDirect(mini.id);
      if (r.reason === 'terms_required') {
        if (!(await terms.ensure())) return;
        r = await openDirect(mini.id);
      }
      if (r.chat) go(`/chats/${r.chat}`);
      else setError(refusal(r.reason));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La discussion n’a pas pu s’ouvrir. Réessaie.');
    } finally {
      setBusy(false);
    }
  }

  async function block(next: boolean) {
    if (!mini) return;
    if (next && !confirmBlock) return setConfirmBlock(true);
    setError(null);
    try {
      await setBlocked(mini.id, next);
      setConfirmBlock(false);
      setVersion((v) => v + 1);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Le blocage n’a pas pu être enregistré.');
    }
  }

  // Glisser vers le haut depuis la couverture : pleine hauteur ; vers le bas (déjà pleine) : moitié.
  const onTouchStart = (e: GestureResponderEvent) => { touchY.current = e.nativeEvent.pageY; };
  const onTouchEnd = (e: GestureResponderEvent) => {
    const dy = touchY.current == null ? 0 : e.nativeEvent.pageY - touchY.current;
    touchY.current = null;
    if (dy < -30) setFull(true);
    else if (dy > 30 && full) setFull(false);
  };

  const look = faceLook(userId);
  const name = mini?.name ?? '';
  const first = mini ? shortName(mini) : '';
  const restricted = !!mini?.blocked_me;
  const handle = mini ? [mini.nickname && mini.nickname !== mini.name ? mini.nickname : null, mini.since ? `sur Party depuis ${monthYear(mini.since)}` : null]
    .filter(Boolean).join(' · ') : '';

  return (
    <Modal visible transparent animationType="none" onRequestClose={close}>
      <View style={st.overlay}>
        <SheetBackdrop onPress={close} />
        <View ref={sheet} testID="mini-profile" accessibilityViewIsModal accessibilityLabel={name ? `Profil de ${name}` : 'Profil'}
          {...({ role: 'dialog', 'aria-modal': true } as object)}
          style={[st.sheet, { height: full ? maxH : halfH }, transition('height', duration.slow, ease.out), reducedMotion ? null : st.rise]}>
          {/* Couverture à la couleur de la personne : deux lueurs qui se fondent dans la feuille. */}
          <View style={[st.cover, web({ backgroundImage: `radial-gradient(90% 120% at 18% 0%, ${look.from}d9, transparent 60%), radial-gradient(70% 90% at 95% 20%, rgba(123,108,246,.7), transparent 65%), linear-gradient(180deg, ${look.to} 0%, ${look.dim} 70%, ${K.sheet} 100%)` })]}
            onTouchStart={onTouchStart} onTouchEnd={onTouchEnd} />
          <Pressable accessibilityRole="button" accessibilityLabel={full ? 'Réduire le profil' : 'Agrandir le profil'} onPress={() => setFull((f) => !f)}
            onTouchStart={onTouchStart} onTouchEnd={onTouchEnd} style={st.grabZone}>
            <View style={st.grabber} />
          </Pressable>
          <Pressable accessibilityRole="button" accessibilityLabel="Fermer" onPress={close} style={({ pressed }) => [st.x, pressed && { opacity: 0.7 }]}>
            <Icon name="x" size={22} color="#fff" />
          </Pressable>

          <ScrollView ref={scroller} style={{ flex: 1 }} contentContainerStyle={{ paddingBottom: 28 }} scrollEventThrottle={32}
            onScroll={(e) => { if (!full && e.nativeEvent.contentOffset.y > 8) setFull(true); }}>
            <View style={st.pid}>
              <View style={[st.pav, web({ boxShadow: `0 0 0 1px rgba(255,255,255,.08), 0 0 40px -6px ${look.main}99` })]}>
                <PhotoTap photo={mini?.photo} name={name || 'cette personne'}><PersonFace id={userId} name={name || '?'} photo={mini?.photo} size={104} /></PhotoTap>
              </View>
              {mini ? (
                <>
                  <Text accessibilityRole="header" style={[disp(30, 34), { textAlign: 'center', marginTop: 10 }]} numberOfLines={2}>{name}</Text>
                  {handle ? <Text style={[txt(15, '400', K.t2, 20), { marginTop: 2, textAlign: 'center' }]}>{handle}</Text> : null}
                  {!restricted ? (
                    <View style={st.met} testID="mini-met">
                      <Icon name="sparkle" size={13} color={K.lav} stroke={2.4} />
                      <Text style={txt(13, '700', K.lav, 17)}>{metLabel(mini.met_count)}</Text>
                    </View>
                  ) : null}
                </>
              ) : (
                <View style={{ alignItems: 'center', gap: 10, marginTop: 14 }}>
                  <Skeleton width={180} height={28} />
                  <Skeleton width={120} height={16} />
                </View>
              )}
            </View>

            {mini ? (
              <>
                <View style={st.actions}>
                  {discussionsOn ? (
                    <NeonButton testID="mini-write" label="Envoyer un message" icon="chat" style={{ flex: 1 }} loading={busy}
                      disabled={mini.link === 'none'} onPress={() => void write()} />
                  ) : null}
                  <NeonButton tone="glass" label="Fiche" icon="person" accessibilityLabel={`Voir la fiche de ${first}`}
                    style={discussionsOn ? { flexShrink: 0 } : { flex: 1 }} onPress={() => go(`/member/${mini.id}`)} />
                </View>
                {discussionsOn && mini.link === 'none' ? (
                  <Text style={st.note} testID="mini-why">{mini.blocked ? `Tu as bloqué ${first}.` : `Tu ne peux pas écrire à ${first} pour l’instant.`}</Text>
                ) : discussionsOn && mini.link === 'request' ? (
                  <Text style={st.note}>Ce sera une demande de message : {first} choisit de l’accepter.</Text>
                ) : null}
                {error ? <Text accessibilityRole="alert" style={[st.note, { color: K.danger }]}>{error}</Text> : null}

                {!restricted && mini.groups.length ? (
                  <>
                    <Label>En commun</Label>
                    <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: 20 }}
                      style={web({ maskImage: 'linear-gradient(90deg, #000 85%, transparent)', WebkitMaskImage: 'linear-gradient(90deg, #000 85%, transparent)' })}>
                      {mini.groups.map((g) => (
                        <Pressable key={g.id} accessibilityRole="link" accessibilityLabel={`Groupe ${g.name}`} onPress={() => go(`/group/${g.id}`)}
                          style={({ pressed }) => [st.chip, pressed && { opacity: 0.7 }]}>
                          <GroupTile group={{ emoji: g.emoji, color: g.color, photo: g.photo }} size={28} />
                          <Text style={txt(15, '600', K.t1, 19)} numberOfLines={1}>{g.name}</Text>
                        </Pressable>
                      ))}
                    </ScrollView>
                  </>
                ) : null}

                {!restricted && mini.met.length ? (
                  <>
                    <Label>{mini.met.length > 1 ? `Vos ${mini.met.length} dernières soirées` : 'Votre dernière soirée'}</Label>
                    {mini.met.slice(0, 3).map((e) => (
                      <EventRow key={e.id} e={e} tone="lav" sub={e.start ? relativeDay(e.start) : 'Ensemble'} onPress={() => go(`/event/${e.id}`)} />
                    ))}
                  </>
                ) : null}

                {!restricted && mini.events.length ? (
                  <>
                    <Label>À venir ensemble</Label>
                    {mini.events.map((e) => (
                      <EventRow key={e.id} e={e} tone={e.mine === 'yes' ? 'mint' : 'coral'} sub={together(e, first)} onPress={() => go(`/event/${e.id}`)} />
                    ))}
                  </>
                ) : null}

                <View style={st.discreet}>
                  {mini.blocked ? (
                    <Pressable accessibilityRole="button" onPress={() => void block(false)} style={st.dBtn}>
                      <Icon name="block" size={16} color={K.t3} stroke={2.1} />
                      <Text style={txt(15, '500', K.t3)}>Débloquer</Text>
                    </Pressable>
                  ) : (
                    <Pressable accessibilityRole="button" accessibilityLabel={confirmBlock ? `Confirmer le blocage de ${first}` : `Bloquer ${first}`}
                      onPress={() => void block(true)} style={st.dBtn}>
                      <Icon name="block" size={16} color={confirmBlock ? K.danger : K.t3} stroke={2.1} />
                      <Text style={txt(15, confirmBlock ? '700' : '500', confirmBlock ? K.danger : K.t3)}>{confirmBlock ? 'Confirmer le blocage' : 'Bloquer'}</Text>
                    </Pressable>
                  )}
                  <Text aria-hidden style={txt(15, '500', K.t3)}>·</Text>
                  <Pressable accessibilityRole="button" accessibilityLabel={`Signaler ${first}`} style={st.dBtn}
                    onPress={() => setReport({ kind: 'profile', id: mini.id, label: name || 'ce profil' })}>
                    <Icon name="flag" size={16} color={K.t3} stroke={2.1} />
                    <Text style={txt(15, '500', K.t3)}>Signaler</Text>
                  </Pressable>
                </View>
                {confirmBlock ? (
                  <Text style={[st.note, { marginTop: 0 }]}>{first} ne pourra plus t’écrire, te citer ni t’inviter ; {first} n’en est pas prévenu·e.</Text>
                ) : null}
              </>
            ) : null}
          </ScrollView>
        </View>
      </View>
      <ReportSheet target={report} onClose={() => setReport(null)} />
      {terms.sheet}
    </Modal>
  );
}

function EventRow({ e, sub, tone, onPress }: { e: MiniEvent; sub: string; tone: 'coral' | 'mint' | 'lav'; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="link" accessibilityLabel={`${e.title}, ${sub}`} onPress={onPress}
      style={({ pressed }) => [st.cev, pressed && { opacity: 0.75 }]}>
      <DateTile iso={e.start} tone={tone} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={txt(15, '600', K.t1, 19)} numberOfLines={1}>{e.title}</Text>
        <Text style={txt(13, '400', K.t2, 17)} numberOfLines={1}>{sub}</Text>
      </View>
      <Icon name="chevr" size={16} color={K.t3} stroke={2.1} />
    </Pressable>
  );
}

const THEIRS: Record<NonNullable<Answer>, string> = { yes: 'vient', maybe: 'peut-être', no: 'ne vient pas', invited: 'invité·e', organizer: 'organise' };
const MINE: Record<NonNullable<Answer>, string> = { yes: 'tu viens', maybe: 'toi : peut-être', no: 'tu ne viens pas', invited: 'toi : invité·e', organizer: 'tu organises' };

/** « Vous venez tous les deux », « Noé vient · toi : peut-être ». */
function together(e: MiniEvent, first: string): string {
  if (e.mine === 'yes' && e.theirs === 'yes') return 'Vous venez tous les deux';
  const parts = [e.theirs ? `${first} ${THEIRS[e.theirs]}` : null, e.mine ? MINE[e.mine] : null].filter(Boolean);
  return parts.length ? parts.join(' · ') : e.start ? relativeDay(e.start) : 'Date à définir';
}

const monthFmt = new Intl.DateTimeFormat('fr-CH', { month: 'long', year: 'numeric', timeZone: 'Europe/Zurich' });
function monthYear(iso: string): string {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? '' : monthFmt.format(d);
}

const st = StyleSheet.create({
  overlay: { flex: 1, justifyContent: 'flex-end', backgroundColor: 'rgba(6,3,16,0.62)' },
  sheet: web({ width: '100%', maxWidth: 520, alignSelf: 'center', backgroundColor: K.sheet, borderTopLeftRadius: 34, borderTopRightRadius: 34,
    overflow: 'hidden', boxShadow: '0 -1px 0 rgba(255,255,255,.08) inset, 0 -30px 60px -20px rgba(0,0,0,.7)' }),
  rise: web({ animationKeyframes: [{ from: { transform: 'translateY(100%)' }, to: { transform: 'none' } }], animationDuration: '380ms',
    animationTimingFunction: ease.out, animationFillMode: 'backwards' }),
  cover: { position: 'absolute', left: 0, right: 0, top: 0, height: 132 },
  grabZone: { position: 'absolute', top: 0, left: '50%', marginLeft: -40, width: 80, height: 24, alignItems: 'center', zIndex: 3 },
  grabber: { width: 40, height: 5, borderRadius: 3, marginTop: 8, backgroundColor: 'rgba(255,255,255,0.4)' },
  x: web({ position: 'absolute', top: 14, right: 14, zIndex: 3, width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center',
    backgroundColor: 'rgba(14,10,31,0.45)', borderWidth: 1, borderColor: 'rgba(255,255,255,0.14)', backdropFilter: 'blur(12px)' }),
  pid: { marginTop: 70, paddingHorizontal: 20, alignItems: 'center' },
  pav: { borderRadius: 999, padding: 4, backgroundColor: K.sheet },
  met: { marginTop: 10, flexDirection: 'row', alignItems: 'center', gap: 6, height: 28, paddingHorizontal: 12, borderRadius: 14,
    backgroundColor: 'rgba(185,167,255,0.12)', borderWidth: 1, borderColor: 'rgba(185,167,255,0.2)' },
  actions: { flexDirection: 'row', gap: 10, paddingTop: 20, paddingHorizontal: 20 },
  note: { ...txt(13, '400', K.t2, 18), paddingHorizontal: 22, marginTop: 10, textAlign: 'center' },
  chip: { flexDirection: 'row', alignItems: 'center', gap: 8, height: 44, paddingLeft: 8, paddingRight: 14, borderRadius: 22,
    backgroundColor: K.glass, borderWidth: 1, borderColor: K.glassLine },
  cev: { flexDirection: 'row', alignItems: 'center', gap: 12, marginTop: 10, marginHorizontal: 20, paddingVertical: 8, paddingLeft: 9, paddingRight: 12,
    borderRadius: 16, backgroundColor: K.glass, borderWidth: 1, borderColor: K.glassLine, minHeight: 58 },
  discreet: { flexDirection: 'row', justifyContent: 'center', alignItems: 'center', gap: 6, marginTop: 26 },
  dBtn: { height: 44, paddingHorizontal: 12, flexDirection: 'row', alignItems: 'center', gap: 6 },
});
