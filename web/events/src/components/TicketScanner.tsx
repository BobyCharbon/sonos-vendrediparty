import { createElement, useCallback, useEffect, useRef, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { enter } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';
import type { ScanResult, TicketPerson } from '@/lib/tickets';
import { formatTime, plural } from '@/lib/format';

import { PersonName, usePersonText } from './PersonName';
import { Avatar, Button, Card, Input, T } from './ui';

/** Lecteur natif de l'app iPhone (VisionKit) : rend le texte du premier QR lu, ou null si l'on ferme. */
type NativeScan = { scan?: { qr?: () => Promise<string | null> } };
type Detector = { detect: (source: HTMLVideoElement) => Promise<{ rawValue: string }[]> };
type DetectorClass = new (opts: { formats: string[] }) => Detector;

const DETECT_EVERY_MS = 250;

export function nativeScanner(): (() => Promise<string | null>) | null {
  const native = (globalThis as { PartyNative?: NativeScan }).PartyNative;
  return native?.scan?.qr ? () => native.scan!.qr!() : null;
}

function webDetector(): DetectorClass | null {
  const D = (globalThis as { BarcodeDetector?: DetectorClass }).BarcodeDetector;
  return typeof D === 'function' && !!navigator.mediaDevices?.getUserMedia ? D : null;
}

/** Caméra du navigateur (Chrome Android, ordinateurs) : lecture continue, en pause pendant l'affichage d'un résultat. */
function WebCamera({ paused, onCode, onError }: { paused: boolean; onCode: (text: string) => void; onError: (msg: string) => void }) {
  const video = useRef<HTMLVideoElement | null>(null);
  const pausedRef = useRef(paused);
  const onCodeRef = useRef(onCode);
  useEffect(() => { pausedRef.current = paused; onCodeRef.current = onCode; }, [paused, onCode]);

  useEffect(() => {
    const Detector = webDetector();
    if (!Detector) return;
    const detector = new Detector({ formats: ['qr_code'] });
    let stream: MediaStream | null = null;
    let timer: ReturnType<typeof setInterval> | null = null;
    let busy = false;
    let stopped = false;
    void navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' }, audio: false }).then((s) => {
      if (stopped) { s.getTracks().forEach((t) => t.stop()); return; }
      stream = s;
      if (video.current) { video.current.srcObject = s; void video.current.play().catch(() => {}); }
      timer = setInterval(async () => {
        if (busy || pausedRef.current || !video.current || video.current.readyState < 2) return;
        busy = true;
        try {
          const found = await detector.detect(video.current);
          if (found[0]?.rawValue && !pausedRef.current) onCodeRef.current(found[0].rawValue);
        } catch { /* Image pas encore prête : on réessaie au tour suivant. */ }
        busy = false;
      }, DETECT_EVERY_MS);
    }).catch(() => onError('Caméra indisponible ou refusée : autorise-la dans les réglages du navigateur, ou tape le code du billet.'));
    return () => {
      stopped = true;
      if (timer) clearInterval(timer);
      stream?.getTracks().forEach((t) => t.stop());
    };
  }, [onError]);

  return (
    <View style={st.camera}>
      {createElement('video', { ref: video, muted: true, playsInline: true, 'aria-label': 'Caméra : vise le QR du billet',
        style: { width: '100%', height: '100%', objectFit: 'cover', display: 'block' } })}
      <View pointerEvents="none" style={st.frame} />
    </View>
  );
}

const verdicts = {
  ok: { icon: '✓', title: 'Bienvenue !', fg: colors.onMint, bg: colors.mint },
  already: { icon: '!', title: 'Déjà scanné', fg: colors.onCoral, bg: colors.coral },
  waitlist: { icon: '⏳', title: 'Sur liste d’attente', fg: colors.onAccent, bg: colors.lavender },
  not_registered: { icon: '✕', title: 'Pas inscrit·e comme présent·e', fg: colors.onRed, bg: colors.red },
  not_issued: { icon: '✕', title: 'Billet pas encore remis', fg: colors.onRed, bg: colors.red },
  tickets_off: { icon: '✕', title: 'Billets QR désactivés', fg: colors.onRed, bg: colors.red },
  other_event: { icon: '✕', title: 'Billet d’un autre événement', fg: colors.onRed, bg: colors.red },
  unknown: { icon: '✕', title: 'Billet inconnu ou remplacé', fg: colors.onRed, bg: colors.red },
  invalid: { icon: '?', title: 'Ce QR n’est pas un billet Party', fg: colors.onRed, bg: colors.red },
} as const;

export type Verdict = ScanResult | { result: 'invalid' };

const statusLabel = { yes: 'Présent', maybe: 'Peut-être', no: 'Absent' } as const;

/** Résultat d'un scan : grande pastille de couleur, puis la personne (photo, accompagnants, payé). */
export function ScanVerdict({ verdict, onPaid, onConfirm, onIssue, onNext }: {
  verdict: Verdict;
  onPaid?: (p: TicketPerson, paid: boolean) => void;
  /** « J'ai payé » en attente : l'organisateur confirme reçu ou pas reçu (la personne est prévenue). */
  onConfirm?: (p: TicketPerson, received: boolean) => void;
  /** Billet pas encore remis : l'organisateur peut le remettre sur place (la personne est prévenue). */
  onIssue?: (p: TicketPerson) => void;
  onNext: () => void;
}) {
  const v = verdicts[verdict.result];
  const person = 'person' in verdict ? verdict.person : null;
  const detail = verdict.result === 'ok' && person?.checked_in_at ? `Arrivée enregistrée à ${formatTime(person.checked_in_at)}`
    : verdict.result === 'already' && person?.checked_in_at ? `Arrivé·e à ${formatTime(person.checked_in_at)} : ne laisse pas entrer deux fois`
      : verdict.result === 'not_registered' && person ? (person.status ? `Réponse : ${statusLabel[person.status]}` : 'N’a pas répondu')
        : verdict.result === 'other_event' ? verdict.event_title
          : verdict.result === 'waitlist' ? 'Pas encore de place pour cette personne'
            : verdict.result === 'not_issued' ? 'L’organisateur ne lui a pas encore remis son billet : ne pas faire entrer sur ce QR'
              : verdict.result === 'tickets_off' ? 'Active « Billets QR » dans l’événement pour scanner les billets'
                : null;
  const priced = person && person.price_chf != null && person.price_chf > 0;
  const personText = usePersonText();
  return (
    <Card style={[st.verdict, { borderColor: v.bg }, enter('pop')]}>
      <View accessibilityRole="alert" accessibilityLabel={`${v.title}${person ? `, ${personText(person.user_id, person.display_name)}` : ''}${detail ? `. ${detail}` : ''}`} style={[st.banner, { backgroundColor: v.bg }]}>
        <T size={22} weight="bold" color={v.fg}>{v.icon}</T>
        <View style={{ flex: 1 }}>
          <T size={18} weight="bold" color={v.fg}>{v.title}</T>
          {detail ? <T size={13} weight="semibold" color={v.fg}>{detail}</T> : null}
        </View>
      </View>
      {person ? (
        <View style={st.person}>
          <Avatar id={person.user_id} name={person.display_name} photo={person.avatar_url} size={64} profile={false} />
          <View style={{ flex: 1, gap: 2 }}>
            <PersonName id={person.user_id} pseudo={person.display_name} size={20} style={{ ...font.display }} numberOfLines={2} />
            <T muted size={14}>{person.plus_ones ? `+ ${plural(person.plus_ones, 'accompagnant')} · ${person.plus_ones + 1} personnes` : 'Seul·e'}</T>
            {priced ? (
              <T size={14} weight="bold" color={person.paid ? colors.mint : colors.coral}>
                {person.paid ? '✓ Payé' : person.pay_pending ? `Dit avoir payé · à confirmer (${person.price_chf} CHF)` : `✗ Pas payé · ${person.price_chf} CHF`}
              </T>
            ) : null}
          </View>
        </View>
      ) : null}
      <View style={st.actions}>
        {person && verdict.result === 'not_issued' && onIssue ? (
          <Button small label="Remettre le billet" onPress={() => onIssue(person)} style={{ flex: 1 }} />
        ) : null}
        {person && priced && person.pay_pending && onConfirm ? (
          <>
            <Button small label="Reçu ✓" onPress={() => onConfirm(person, true)} style={{ flex: 1 }} />
            <Button small variant="ghost" label="Pas reçu" onPress={() => onConfirm(person, false)} />
          </>
        ) : person && priced && onPaid ? (
          <Button small variant={person.paid ? 'secondary' : 'primary'} label={person.paid ? 'Annuler « payé »' : 'Marquer payé'} onPress={() => onPaid(person, !person.paid)} style={{ flex: 1 }} />
        ) : null}
        <Button small variant="secondary" label="Billet suivant" onPress={onNext} style={{ flex: 1 }} />
      </View>
    </Card>
  );
}

/**
 * Zone de scan : caméra native (app iPhone), caméra du navigateur si elle sait lire les QR, et toujours le code court
 * à taper. Sans caméra intégrée (Safari) : l'appareil photo du téléphone ouvre directement le billet ici.
 */
export function ScanControls({ paused, onScanned }: { paused: boolean; onScanned: (raw: string) => void }) {
  const [code, setCode] = useState('');
  const [cameraError, setCameraError] = useState<string | null>(null);
  const native = nativeScanner();
  const web = !native && webDetector();
  const onError = useCallback((msg: string) => setCameraError(msg), []);

  async function scanNative() {
    try {
      const text = await native!();
      if (text) onScanned(text);
    } catch (e) {
      setCameraError(e instanceof Error ? e.message : 'Caméra indisponible : tape le code du billet.');
    }
  }

  return (
    <View style={{ gap: 12 }}>
      {native ? <Button label="📷 Scanner un billet" onPress={scanNative} /> : null}
      {web && !cameraError ? <WebCamera paused={paused} onCode={onScanned} onError={onError} /> : null}
      {!native && !web ? (
        <T muted size={13}>Ouvre l’appareil photo du téléphone et vise le QR du billet : il s’ouvre directement ici et l’arrivée est notée.</T>
      ) : null}
      {cameraError ? <T size={13} color={colors.coralSoft}>{cameraError}</T> : null}
      <View style={st.manual}>
        <Input
          value={code}
          onChangeText={(t) => setCode(t.toUpperCase())}
          placeholder="Code du billet (ex. K7M 2QX)"
          autoCapitalize="characters"
          autoCorrect={false}
          accessibilityLabel="Code du billet"
          onSubmitEditing={() => { if (code.trim()) { onScanned(code); setCode(''); } }}
          style={{ flex: 1 }}
        />
        <Button small label="Valider" disabled={!code.trim()} onPress={() => { onScanned(code); setCode(''); }} />
      </View>
    </View>
  );
}


const st = StyleSheet.create({
  camera: { width: '100%', aspectRatio: 1, maxWidth: 420, alignSelf: 'center', borderRadius: radius.lg, overflow: 'hidden', backgroundColor: '#000' },
  frame: { position: 'absolute', top: '18%', left: '18%', right: '18%', bottom: '18%', borderWidth: 3, borderColor: 'rgba(255,255,255,0.85)', borderRadius: radius.md },
  verdict: { gap: 12, borderWidth: 2, padding: 0, overflow: 'hidden' },
  banner: { flexDirection: 'row', alignItems: 'center', gap: 12, paddingHorizontal: 16, paddingVertical: 14 },
  person: { flexDirection: 'row', alignItems: 'center', gap: 14, paddingHorizontal: 16 },
  actions: { flexDirection: 'row', flexWrap: 'wrap', gap: 10, paddingHorizontal: 16, paddingBottom: 16 },
  manual: { flexDirection: 'row', alignItems: 'center', gap: 8 },
});
