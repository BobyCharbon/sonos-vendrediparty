import { useEffect, useState, type ReactNode } from 'react';
import { Platform, Pressable, Share, StyleSheet, Text, TextInput, View } from 'react-native';

import { DateTimeField } from '@/components/DateTimeField';
import { goBack } from '@/components/agenda/Bits';
import { Avatar, Button, ConfirmButton } from '@/components/ui';
import { PrimaryButton, ShapeMark } from '@/components/pronos/Kit';
import { addDays, dayKey, zdate } from '@/lib/agenda';
import { formatShort, parseLocalDateTime, plural, toLocalInput } from '@/lib/format';
import { pressTransition, transition } from '@/lib/motion';
import { rpc } from '@/lib/pronos';

import { C, hhmm, meName, rounded, shapeAt, webView, wide, withPatates, type PronoV2 } from './model';

type Act = (fn: string, args: Record<string, unknown>) => Promise<boolean>;

/**
 * Organisation (maquette 3-4), REPLIÉE par défaut et placée après la réponse (l'organisateur joue comme les autres) :
 * « C'est arrivé ! » (prono « heure »), lien pour inviter, déplacer la fin, donner le résultat à la main, fermer,
 * annuler. Rien de tout ça ne montre une réponse : la base les cache aussi à l'organisateur.
 */
export function Organizer({ p, busy, act }: { p: PronoV2; busy: boolean; act: Act }) {
  const [open, setOpen] = useState(false);
  const live = p.state === 'open' || p.state === 'closed';
  if (!live) {
    return p.state === 'cancelled' || !p.answered.length
      ? <ConfirmButton label="Supprimer ce prono" confirmLabel="Oui, supprimer" onConfirm={() => void rpc('prono_delete', { id: p.id }).then(() => goBack('/pronos'))} />
      : null;
  }
  return (
    <View style={[st.panel, open && st.panelOpen]} testID="prono-organizer">
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: open }} aria-expanded={open} onPress={() => setOpen((o) => !o)}
        style={st.head}>
        <View style={st.headIcon}><Text style={{ color: C.t1, fontSize: 18 }} accessibilityElementsHidden>⚙︎</Text></View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={rounded(19, '800')}>Organisation</Text>
          <Text style={st.help}>{open ? 'Toi seul vois ces réglages' : 'Lien, fin, résultat, annulation'}</Text>
        </View>
        <Text style={[st.chev, open && webView({ transform: 'rotate(180deg)' }), transition('transform', 350, 'cubic-bezier(.34,1.56,.64,1)')]}>⌄</Text>
      </Pressable>
      {open ? (
        <View style={{ gap: 4 }}>
          <View style={st.lock}>
            <Text style={{ fontSize: 16 }} accessibilityElementsHidden>🔒</Text>
            <Text style={[st.help, { flex: 1, color: C.t1 }]}>Toi non plus, tu ne vois pas les réponses avant la fin. C’est ce qui rend le prono juste.</Text>
          </View>
          {p.kind === 'when' && p.can_happen ? <Happened busy={busy} onHappened={() => act('prono_result', { id: p.id, body: { time: new Date().toISOString() } })} /> : null}
          {p.state === 'open' ? <LinkRow p={p} busy={busy} act={act} /> : null}
          {p.can_move_end && !(p.reveal === 'close' && p.revealed) ? <MoveEnd p={p} act={act} /> : null}
          {p.kind === 'when' && p.can_result ? <WhenByHand p={p} busy={busy} act={act} /> : null}
          {p.state === 'open' ? (
            <Row icon="🔒" title="Fermer les réponses" hint="Plus personne ne peut répondre ni changer.">
              <SmallBtn label="Fermer" onPress={() => void act('prono_close_now', { id: p.id })} />
            </Row>
          ) : null}
          {p.locked ? <Text style={[st.small, { paddingVertical: 6 }]}>Quelqu’un a joué : la question et les choix ne changent plus.</Text> : null}
          <View style={{ paddingTop: 10, gap: 8 }}>
            <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
              <View style={[st.rowIcon, { backgroundColor: 'rgba(255,122,138,0.14)' }]}><Text style={{ color: C.soft, fontSize: 18 }}>✕</Text></View>
              <View style={{ flex: 1 }}>
                <Text style={[rounded(17, '800'), { color: C.soft }]}>Annuler le prono</Text>
                <Text style={st.help}>{withPatates(p) ? 'Toutes les patates sont rendues.' : 'Aucun point n’est compté.'} Confirmation demandée.</Text>
              </View>
            </View>
            <ConfirmButton label={p.state === 'closed' ? 'Pas de résultat : annuler' : 'Annuler le prono'}
              confirmLabel={withPatates(p) ? 'Oui, annuler et tout rendre' : 'Oui, annuler'} onConfirm={() => void act('prono_cancel', { id: p.id })} />
          </View>
        </View>
      ) : null}
    </View>
  );
}

function Row({ icon, title, hint, children, below }: { icon: string; title: string; hint: string; children?: ReactNode; below?: ReactNode }) {
  return (
    <View style={st.row}>
      <View style={{ flexDirection: 'row', gap: 12, alignItems: 'center' }}>
        <View style={st.rowIcon}><Text style={{ color: C.t1, fontSize: 18 }} accessibilityElementsHidden>{icon}</Text></View>
        <View style={{ flex: 1, gap: 2 }}>
          <Text style={rounded(17, '800')}>{title}</Text>
          <Text style={st.help}>{hint}</Text>
        </View>
        {children}
      </View>
      {below}
    </View>
  );
}

function SmallBtn({ label, onPress }: { label: string; onPress: () => void }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress}
      style={({ pressed }) => [st.small44, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
      <Text style={{ color: C.t1, fontSize: 16, fontWeight: '700' }}>{label}</Text>
    </Pressable>
  );
}

function useClock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const t = setInterval(() => setNow(new Date()), 1000);
    return () => clearInterval(t);
  }, []);
  return now;
}

/** « C'est arrivé ! » : l'heure exacte est notée (prono_result avec maintenant), puis tout se dévoile. */
function Happened({ busy, onHappened }: { busy: boolean; onHappened: () => Promise<boolean> }) {
  const now = useClock();
  const [armed, setArmed] = useState(false);
  return (
    <View style={st.happen}>
      <View style={{ flexDirection: 'row', alignItems: 'center' }}>
        <Text style={[rounded(20, '800'), { flex: 1 }]}>C’est arrivé ?</Text>
        <Text style={wide(24, C.mint)} accessibilityLabel={`Il est ${hhmm(now.toISOString())}`}>{hhmm(now.toISOString())}</Text>
      </View>
      <Text style={st.help}>Touche au moment où ça arrive : l’heure exacte est notée, puis tout se dévoile.</Text>
      {armed ? (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button variant="secondary" label="Pas encore" style={{ flex: 1 }} onPress={() => setArmed(false)} />
          <Pressable accessibilityRole="button" disabled={busy} onPress={() => void onHappened().then(() => setArmed(false))}
            style={({ pressed }) => [st.mintBtn, { flex: 1.4 }, pressed && { transform: [{ scale: 0.97 }] }]}>
            <Text style={st.mintText}>Oui, à {hhmm(now.toISOString())}</Text>
          </Pressable>
        </View>
      ) : (
        <Pressable accessibilityRole="button" onPress={() => setArmed(true)} testID="prono-happened"
          style={({ pressed }) => [st.mintBtn, pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
          <Text style={st.mintText}>🕘 C’est arrivé !</Text>
        </Pressable>
      )}
    </View>
  );
}

function LinkRow({ p, busy, act }: { p: PronoV2; busy: boolean; act: Act }) {
  const [copied, setCopied] = useState(false);
  const url = p.link?.path && typeof location !== 'undefined' ? `${location.origin}${p.link.path}` : null;
  async function share() {
    if (!url) return;
    if (Platform.OS === 'web' && typeof navigator !== 'undefined' && 'share' in navigator) {
      await (navigator as Navigator).share({ title: 'Un prono pour toi', text: p.question, url }).catch(() => undefined);
    } else await Share.share({ message: `${p.question} ${url}` }).catch(() => undefined);
  }
  async function copy() {
    if (!url) return;
    await navigator.clipboard?.writeText(url).catch(() => undefined);
    setCopied(true);
    setTimeout(() => setCopied(false), 1800);
  }
  return (
    <Row icon="🔗" title="Lien pour inviter" hint="Qui l’ouvre se connecte à Party, puis joue. Il s’arrête à la fin."
      below={url ? (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button small label="Partager" style={{ flex: 1 }} onPress={() => void share()} />
          <Button small variant="secondary" label={copied ? 'Copié ✓' : 'Copier'} style={{ flex: 1 }} onPress={() => void copy()} />
          <Button small variant="danger" label="Arrêter" onPress={() => void act('prono_set_link', { id: p.id, active: false })} />
        </View>
      ) : <Button small variant="secondary" label="🔗 Créer un lien" loading={busy} onPress={() => void act('prono_set_link', { id: p.id, active: true })} />} />
  );
}

function MoveEnd({ p, act }: { p: PronoV2; act: Act }) {
  const [choose, setChoose] = useState(false);
  const [end, setEnd] = useState(toLocalInput(p.closes_at));
  // À partir de la fin actuelle, ou de maintenant si elle est passée (calculé au toucher).
  const from = () => Math.max(Date.now(), new Date(p.closes_at).getTime());
  const move = (iso: string) => void act('prono_update', { id: p.id, body: { closes_at: iso } });
  const later = (ms: number) => move(new Date(from() + ms).toISOString());
  return (
    <Row icon="⏱" title="Déplacer la fin" hint={`Aujourd’hui : ${formatShort(p.closes_at)}`}
      below={(
        <View style={{ gap: 8 }}>
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Chip label="+30 min" onPress={() => later(30 * 60_000)} />
            <Chip label="+1 h" onPress={() => later(3600_000)} />
            <Chip label="Minuit" onPress={() => move(zdate(addDays(dayKey(new Date(from())), 1), 0).toISOString())} />
            <Chip label="Choisir…" on={choose} onPress={() => setChoose((c) => !c)} />
          </View>
          {choose ? (
            <View style={{ gap: 8 }}>
              <DateTimeField label="Fin des réponses" value={end} onChangeText={setEnd} />
              <Button small variant="secondary" label="Déplacer la fin" disabled={!parseLocalDateTime(end) || end === toLocalInput(p.closes_at)}
                onPress={() => { const iso = parseLocalDateTime(end); if (iso) { move(iso); setChoose(false); } }} />
            </View>
          ) : null}
        </View>
      )} />
  );
}

function Chip({ label, onPress, on }: { label: string; onPress: () => void; on?: boolean }) {
  return (
    <Pressable accessibilityRole="button" onPress={onPress}
      style={({ pressed }) => [st.chip, on && { borderColor: C.lav, backgroundColor: 'rgba(185,167,255,0.16)' }, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
      <Text style={{ color: C.t1, fontSize: 15, fontWeight: '700' }} numberOfLines={1}>{label}</Text>
    </Pressable>
  );
}

function WhenByHand({ p, busy, act }: { p: PronoV2; busy: boolean; act: Act }) {
  const [open, setOpen] = useState(false);
  const [at, setAt] = useState(toLocalInput(new Date().toISOString()));
  return (
    <Row icon="✎" title="Donner le résultat" hint="Saisir l’heure à la main"
      below={open ? (
        <View style={{ gap: 8 }}>
          <DateTimeField label="Heure exacte" value={at} onChangeText={setAt} />
          <Button small label="🎉 Dévoiler le résultat" loading={busy} disabled={!parseLocalDateTime(at)}
            onPress={() => { const iso = parseLocalDateTime(at); if (iso) void act('prono_result', { id: p.id, body: { time: iso } }); }} />
        </View>
      ) : null}>
      <SmallBtn label={open ? 'Fermer' : 'Saisir'} onPress={() => setOpen((o) => !o)} />
    </Row>
  );
}

// ───────── Fermé : l'organisateur donne le résultat ─────────

export function ResultPicker({ p, busy, onResult }: { p: PronoV2; busy: boolean; onResult: (body: Record<string, unknown>) => Promise<boolean> }) {
  const [opt, setOpt] = useState<string | null>(null);
  const [person, setPerson] = useState<string | null>(null);
  const [num, setNum] = useState('');
  const [winners, setWinners] = useState<Set<string>>(new Set());
  if (p.kind === 'majority' || p.kind === 'award') {
    return <Text style={st.help}>Le résultat se calcule tout seul à la fin{p.kind === 'award' ? ', s’il y a au moins 3 votes' : ''}.</Text>;
  }
  if (p.kind === 'when') return null;   // « C'est arrivé ! » ou l'heure à la main, dans l'organisation
  if (!p.answered.length) {
    return <Text style={st.help}>Personne n’a joué : tu peux annuler ce prono ou rouvrir les réponses en déplaçant la fin.</Text>;
  }
  const isOption = ['choice', 'yesno', 'overunder'].includes(p.kind);
  const n = Number(num.replace(',', '.'));
  const ready = isOption ? !!opt : p.kind === 'person' ? !!person : p.kind === 'number' ? num.trim() !== '' && Number.isFinite(n) : true;
  const body = isOption ? { option_id: opt } : p.kind === 'person' ? { person_id: person } : p.kind === 'number' ? { number: n } : { winners: [...winners] };
  return (
    <View style={{ gap: 10 }} testID="prono-result">
      <Text style={rounded(24, '800')}>Quel est le résultat&nbsp;?</Text>
      <Text style={st.help}>{plural(p.answered.length, 'personne a joué', 'personnes ont joué')}. Tout le monde verra le résultat dès que tu valides.</Text>
      {isOption ? p.options.map((o, i) => {
        const s = shapeAt(i);
        const on = opt === o.id;
        return (
          <Pressable key={o.id} accessibilityRole="radio" accessibilityState={{ selected: on }} aria-checked={on} onPress={() => setOpt(o.id)}
            testID={`prono-result-${i}`} style={({ pressed }) => [st.res, on && webView({ borderColor: s.color, backgroundImage: `linear-gradient(120deg, ${s.color}38, ${s.color}0F)` }),
              pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
            <ShapeMark shape={s.key} color={s.color} size={28} filled={on} />
            <Text style={[rounded(18, '700'), { flex: 1 }]}>{o.label}</Text>
            {o.count != null ? <Text style={st.help}>{plural(o.count, 'réponse')}</Text> : null}
          </Pressable>
        );
      }) : null}
      {p.kind === 'person' ? (
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {(p.candidates ?? []).map((c, i) => (
            <Pressable key={c.id} testID={`prono-result-${i}`} accessibilityRole="radio" accessibilityLabel={meName(c)} accessibilityState={{ selected: person === c.id }}
              onPress={() => setPerson(c.id)} style={[st.person, person === c.id && { borderColor: C.lav }]}>
              <Avatar id={c.id} name={c.name} photo={c.avatar_url} size={48} profile={false} />
              <Text style={{ color: C.t1, fontSize: 13, fontWeight: '600' }} numberOfLines={1}>{meName(c)}</Text>
            </Pressable>
          ))}
        </View>
      ) : null}
      {p.kind === 'number' ? (
        <TextInput value={num} onChangeText={setNum} placeholder="Le vrai résultat" placeholderTextColor={C.t3} inputMode="decimal"
          accessibilityLabel="Le vrai résultat" style={st.input} />
      ) : null}
      {p.kind === 'text' ? (p.answers ?? []).map((a) => {
        const on = winners.has(a.user.id);
        return (
          <Pressable key={a.user.id} accessibilityRole="checkbox" accessibilityState={{ checked: on }} aria-checked={on}
            onPress={() => setWinners((w) => { const next = new Set(w); if (on) next.delete(a.user.id); else next.add(a.user.id); return next; })}
            style={({ pressed }) => [st.res, on && { borderColor: C.mint }, pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
            <View style={[st.box, on && { backgroundColor: C.mint, borderColor: C.mint }]}>{on ? <Text style={{ color: C.bg, fontWeight: '900' }}>✓</Text> : null}</View>
            <Avatar id={a.user.id} name={a.user.name} photo={a.user.avatar_url} size={30} profile={false} />
            <View style={{ flex: 1 }}>
              <Text style={{ color: C.t1, fontSize: 16, fontWeight: '700' }}>{a.hidden ? 'Réponse masquée' : a.text}</Text>
              <Text style={st.small}>{meName(a.user)}</Text>
            </View>
          </Pressable>
        );
      }) : null}
      <PrimaryButton label={p.kind === 'text' ? `🎉 Dévoiler · ${plural(winners.size, 'bonne réponse', 'bonnes réponses')}` : '🎉 Dévoiler le résultat'} disabled={!ready} loading={busy}
        onPress={() => void onResult(body)} />
    </View>
  );
}

const st = StyleSheet.create({
  panel: { borderRadius: 24, backgroundColor: C.glass, borderWidth: 1, borderColor: C.glassLine, padding: 12 },
  panelOpen: { backgroundColor: C.s1, padding: 16, gap: 10 },
  head: { flexDirection: 'row', alignItems: 'center', gap: 14, minHeight: 44 },
  headIcon: { width: 40, height: 40, borderRadius: 13, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.08)' },
  chev: { color: C.t2, fontSize: 22, fontWeight: '700', paddingHorizontal: 6 },
  lock: { flexDirection: 'row', gap: 12, alignItems: 'center', padding: 14, borderRadius: 16, backgroundColor: 'rgba(185,167,255,0.16)', marginVertical: 6 },
  happen: webView({ gap: 10, padding: 18, borderRadius: 22, borderWidth: 1, borderColor: 'rgba(91,227,166,0.5)', marginVertical: 6,
    backgroundImage: 'linear-gradient(160deg, rgba(91,227,166,0.20), rgba(91,227,166,0.04))' }),
  mintBtn: { height: 56, borderRadius: 18, alignItems: 'center', justifyContent: 'center', backgroundColor: C.mint },
  mintText: { color: C.bg, fontSize: 19, fontWeight: '800' },
  row: { gap: 10, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: C.line },
  rowIcon: { width: 44, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.08)' },
  small44: { minHeight: 44, paddingHorizontal: 16, borderRadius: 14, justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.07)', borderWidth: 1,
    borderColor: C.glassLine },
  chip: { flex: 1, height: 44, borderRadius: 14, alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255,255,255,0.07)', borderWidth: 1,
    borderColor: C.glassLine, paddingHorizontal: 4 },
  res: webView({ flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, borderRadius: 20, paddingHorizontal: 14, paddingVertical: 8,
    backgroundColor: C.glass, borderWidth: 1.5, borderColor: C.glassLine }),
  box: { width: 26, height: 26, borderRadius: 8, borderWidth: 2, borderColor: 'rgba(255,255,255,0.3)', alignItems: 'center', justifyContent: 'center' },
  person: { width: 92, alignItems: 'center', gap: 6, paddingVertical: 12, borderRadius: 18, backgroundColor: C.glass, borderWidth: 2, borderColor: 'transparent' },
  input: { height: 56, borderRadius: 16, paddingHorizontal: 16, backgroundColor: C.glass, color: C.t1, fontSize: 22, fontWeight: '700', borderWidth: 1,
    borderColor: C.glassLine },
  help: { color: C.t2, fontSize: 15, lineHeight: 21 },
  small: { color: C.t3, fontSize: 13, lineHeight: 18 },
});
