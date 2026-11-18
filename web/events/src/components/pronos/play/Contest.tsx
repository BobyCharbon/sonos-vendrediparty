import { useEffect, useRef, useState } from 'react';
import { Modal, Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetSignal, useSheetTop } from '@/components/SheetGesture';
import { Avatar, ErrorText } from '@/components/ui';
import { GlassCard, PrimaryButton } from '@/components/pronos/Kit';
import { pressTransition } from '@/lib/motion';

import { C, leftText, meName, rounded, webView, wide, withPatates, type Contest, type PronoV2 } from './model';

/**
 * Contestation (maquette 3-5) : 12 h après le résultat, un joueur peut contester une fois, avec une raison (3 à 140
 * caractères, filtrée par la base) ; les joueurs votent alors 24 h, l'organisateur ne vote pas. « Pas juste » majoritaire
 * ou égalité : prono annulé, tout est rendu. Jamais de rouge : contester n'est pas une faute.
 */

const HOUR = 3600_000;

function useMinute() {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 30_000);
    return () => clearInterval(t);
  }, []);
  return now;
}

export function ContestBanner({ c }: { c: Contest }) {
  const now = useMinute();
  const left = Math.max(0, new Date(c.until).getTime() - now);
  const span = (c.contested ? 24 : 12) * HOUR;
  return (
    <View style={st.banner} accessibilityRole="summary">
      <View style={st.bannerIcon}><Text style={{ fontSize: 18 }} accessibilityElementsHidden>⚖️</Text></View>
      <View style={{ flex: 1, gap: 4 }}>
        <Text style={rounded(17, '800')}>{c.contested ? 'Résultat contesté' : 'Résultat donné'}</Text>
        <Text style={{ color: C.amber, fontSize: 15, fontWeight: '600' }}>
          {c.contested ? `Vote ouvert encore ${leftText(c.until, now)}` : `${leftText(c.until, now)} pour contester`}
        </Text>
        <View style={st.track}><View style={[st.fill, { width: `${Math.min(100, (left / span) * 100)}%` }]} /></View>
      </View>
    </View>
  );
}

export function ContestAsk({ onOpen }: { onOpen: () => void }) {
  return (
    <View style={st.ask}>
      <Text style={[st.help, { flex: 1 }]}>Un souci avec ce résultat ?</Text>
      <Pressable accessibilityRole="button" onPress={onOpen} testID="prono-contest"
        style={({ pressed }) => [st.askBtn, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
        <Text style={{ color: C.amber, fontSize: 16, fontWeight: '700' }}>Contester</Text>
      </Pressable>
    </View>
  );
}

export function ContestSheet({ open, organizer, onClose, onSend }: {
  open: boolean; organizer: string; onClose: () => void; onSend: (reason: string) => Promise<string | null>;
}) {
  const [reason, setReason] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const top = useSheetTop();
  const close = () => { setReason(''); setErr(null); onClose(); };
  useSheetDrag(open, close, card, overlay);
  useSheetSignal(open);
  const text = reason.trim();
  async function send() {
    setBusy(true);
    setErr(null);
    const error = await onSend(text);
    setBusy(false);
    if (error) setErr(error);
    else close();
  }
  return (
    <Modal visible={open} transparent animationType="fade" onRequestClose={close}>
      <View ref={overlay} style={[st.overlay, { paddingTop: top }]}>
        <SheetBackdrop onPress={close} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Contester le résultat">
          <SheetTop onClose={close} />
          <Text style={rounded(24, '800')}>Contester le résultat</Text>
          <Text style={st.help}>Les joueurs votent pendant 24 h pour dire si le résultat est juste. {organizer}, qui l’a donné, ne vote pas.</Text>
          <View style={st.field}>
            <TextInput value={reason} onChangeText={setReason} maxLength={140} multiline autoFocus placeholder="Pourquoi ? En une phrase."
              placeholderTextColor={C.t3} accessibilityLabel="Pourquoi ? En une phrase." style={st.input} testID="prono-contest-reason" />
            <View style={{ flexDirection: 'row' }}>
              <Text style={[st.small, { flex: 1 }]}>Pourquoi ? En une phrase.</Text>
              <Text style={wide(14, C.t2)}>{reason.length}/140</Text>
            </View>
          </View>
          <ErrorText error={err} />
          <PrimaryButton label="Envoyer la contestation" disabled={text.length < 3} loading={busy} onPress={() => void send()} />
          <Text style={[st.small, { textAlign: 'center' }]}>Tu ne peux contester qu’une fois.</Text>
        </View>
      </View>
    </Modal>
  );
}

export function ContestVote({ p, c, result, onVote, busy }: {
  p: PronoV2; c: Contest; result: string; onVote: (fair: boolean) => void; busy: boolean;
}) {
  // Votants : ceux qui ont joué, sauf l'organisateur s'il a joué.
  const voters = Math.max(0, p.answered.length - (p.answered.some((f) => f.id === p.creator.id) ? 1 : 0));
  const missing = Math.max(0, voters - c.fair - c.unfair);
  const total = Math.max(1, c.fair + c.unfair + missing);
  return (
    <GlassCard style={st.vote}>
      {c.reason ? (
        <View style={st.quote}>
          {c.by ? <Avatar id={c.by.id} name={c.by.name} photo={c.by.avatar_url} size={36} profile={false} /> : null}
          <View style={{ flex: 1, gap: 2 }}>
            <Text style={{ color: C.t2, fontSize: 14, fontWeight: '700' }}>{c.by ? `${meName(c.by)} conteste` : 'Contestation'}</Text>
            <Text style={{ color: C.t1, fontSize: 16, lineHeight: 22 }}>« {c.reason} »</Text>
          </View>
        </View>
      ) : null}
      <Text style={rounded(24, '800')}>Le résultat est-il juste ?</Text>
      <Text style={st.help}>Résultat donné : <Text style={{ color: C.t1, fontWeight: '700' }}>{result}</Text></Text>
      {c.can_vote ? (
        <View style={{ flexDirection: 'row', gap: 10 }} accessibilityRole="radiogroup">
          <VoteBtn label="Oui" glyph="✓" round color={C.sky} on={c.my_vote === true} disabled={busy} onPress={() => onVote(true)} />
          <VoteBtn label="Non" glyph="✕" color={C.pink} on={c.my_vote === false} disabled={busy} onPress={() => onVote(false)} />
        </View>
      ) : null}
      <View style={st.seg} accessibilityLabel={`Oui ${c.fair}, Non ${c.unfair}, ${missing} pas encore`}>
        {c.fair ? <View style={{ flex: c.fair / total, backgroundColor: C.sky }} /> : null}
        {c.unfair ? <View style={{ flex: c.unfair / total, backgroundColor: C.pink }} /> : null}
        {missing ? <View style={{ flex: missing / total, backgroundColor: 'rgba(255,255,255,0.10)' }} /> : null}
      </View>
      <View style={{ flexDirection: 'row', alignItems: 'center', gap: 16 }}>
        <Text style={st.legend}><Text style={{ color: C.sky }}>● </Text>Oui <Text style={wide(15)}>{c.fair}</Text></Text>
        <Text style={st.legend}><Text style={{ color: C.pink }}>■ </Text>Non <Text style={wide(15)}>{c.unfair}</Text></Text>
        <Text style={[st.legend, { flex: 1, textAlign: 'right' }]}>{missing} pas encore</Text>
      </View>
      <View style={st.sep} />
      <Text style={st.small}>Si le Non l’emporte, ou en cas d’égalité, le prono est annulé{withPatates(p) ? ' et tous les confettis sont rendus' : ''}.</Text>
      <Text style={st.small}>
        {p.mine ? 'Tu as donné le résultat : tu ne votes pas.' : `${p.creator.name} ne vote pas.${c.can_vote ? ' Tu peux changer ton vote jusqu’à la fin.' : ''}`}
      </Text>
    </GlassCard>
  );
}

function VoteBtn({ label, glyph, color, on, round, disabled, onPress }: {
  label: string; glyph: string; color: string; on: boolean; round?: boolean; disabled: boolean; onPress: () => void;
}) {
  return (
    <Pressable accessibilityRole="radio" accessibilityLabel={label} accessibilityState={{ selected: on, disabled }} aria-checked={on}
      disabled={disabled} onPress={onPress}
      style={({ pressed }) => [st.voteBtn, on && webView({ borderColor: color, backgroundImage: `linear-gradient(160deg, ${color}40, ${color}10)` }),
        pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
      <View style={[st.voteGlyph, { borderRadius: round ? 15 : 8, backgroundColor: on ? color : `${color}30` }]}>
        <Text style={{ color: on ? C.bg : color, fontSize: 14, fontWeight: '900' }}>{glyph}</Text>
      </View>
      <Text style={rounded(20, '800')}>{label}</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  banner: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 16, minHeight: 64, borderRadius: 24, borderWidth: 1,
    borderColor: 'rgba(255,179,71,0.45)', backgroundColor: 'rgba(255,179,71,0.09)' },
  bannerIcon: { width: 40, height: 40, borderRadius: 12, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,179,71,0.18)' },
  track: { height: 4, borderRadius: 2, backgroundColor: 'rgba(255,255,255,0.1)', overflow: 'hidden', marginTop: 2 },
  fill: { height: 4, borderRadius: 2, backgroundColor: C.amber },
  ask: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  askBtn: { minHeight: 44, paddingHorizontal: 18, borderRadius: 16, justifyContent: 'center', borderWidth: 1.5, borderColor: 'rgba(255,179,71,0.6)',
    backgroundColor: C.glass },
  overlay: webView({ flex: 1, backgroundColor: 'rgba(10,6,22,0.88)', alignItems: 'center', justifyContent: 'flex-end', padding: 12, overflowY: 'auto' }),
  sheet: { width: '100%', maxWidth: 480, gap: 14, padding: 20, borderRadius: 30, backgroundColor: C.s1, borderWidth: 1, borderColor: C.glassLine },
  field: { gap: 8, padding: 16, borderRadius: 20, borderWidth: 1.5, borderColor: C.lav, backgroundColor: 'rgba(255,255,255,0.04)' },
  input: webView({ minHeight: 56, color: C.t1, fontSize: 18, lineHeight: 24, outlineStyle: 'none', caretColor: C.accent }),
  vote: { gap: 14, padding: 18, borderRadius: 24 },
  quote: { flexDirection: 'row', gap: 12, padding: 14, borderRadius: 18, backgroundColor: 'rgba(255,255,255,0.05)' },
  voteBtn: webView({ flex: 1, height: 64, borderRadius: 20, flexDirection: 'row', alignItems: 'center', justifyContent: 'center', gap: 12,
    borderWidth: 1.5, borderColor: C.glassLine, backgroundColor: C.glass }),
  voteGlyph: { width: 30, height: 30, alignItems: 'center', justifyContent: 'center' },
  seg: { flexDirection: 'row', height: 12, borderRadius: 6, overflow: 'hidden', gap: 3, backgroundColor: 'rgba(255,255,255,0.06)' },
  legend: { color: C.t2, fontSize: 15 },
  sep: { height: 1, backgroundColor: C.line },
  help: { color: C.t2, fontSize: 15, lineHeight: 21 },
  small: { color: C.t3, fontSize: 13.5, lineHeight: 19 },
});
