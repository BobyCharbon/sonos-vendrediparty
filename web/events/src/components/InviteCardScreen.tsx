import { Stack } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Image, Linking, Pressable, StyleSheet, View } from 'react-native';

import { CalendarButton } from './CalendarButton';
import { Button, ErrorText, Field, Input, Loading, Screen, T, Title } from './ui';
import { appDownload } from '@/lib/appInvite';
import { useAuth } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { avatarColor, formatLongDay, formatTime, initials } from '@/lib/format';
import { acceptInvite, fetchInviteCard, type Accepted, type InviteCard } from '@/lib/invites';
import { enter, pressTransition } from '@/lib/motion';
import { safeHref } from '@/lib/links';
import { acceptTermsIfNeeded, dbMessage, TERMS_PATH } from '@/lib/moderation';
import { parseLoginPhone } from '@/lib/phone';
import { supabase } from '@/lib/supabase';
import { colors, radius, rsvpColors } from '@/lib/theme';
import type { RsvpStatus } from '@/lib/types';

const TOKEN = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CODE_LENGTH = 6;
const ANSWERS: { key: RsvpStatus; label: string }[] = [
  { key: 'yes', label: 'Je viens !' }, { key: 'maybe', label: 'Peut-être' }, { key: 'no', label: 'Je ne peux pas' },
];
const DONE_WORDS: Record<RsvpStatus, string> = { yes: 'Tu viens à', maybe: 'Tu viens peut-être à', no: 'Tu ne viens pas à' };
/** Conditions d'utilisation, ouvertes à côté (l'invitation reste là où elle en est). */
const termsUrl = () => (typeof location !== 'undefined' ? `${location.origin}/events${TERMS_PATH}` : `https://party.bobycharbon.ch/events${TERMS_PATH}`);
const CLOSED: Record<string, string> = {
  full: 'Ce lien a déjà servi : toutes ses places sont prises. Demande ton propre lien à la personne qui t’a invité.',
  expired: 'Ce lien n’est plus valable (date limite passée). Demande un nouveau lien à la personne qui t’a invité.',
  revoked: 'La personne qui t’a invité a arrêté ce lien. Demande-lui un nouveau lien.',
};

/**
 * Invitation à un événement, lisible SANS compte (bêta invites_v2, maquette C 5 à 7) : qui invite, quand, où, qui vient
 * déjà → « Je viens » → prénom et numéro → code SMS (rempli tout seul par l'iPhone) → c'est noté, avec calendrier,
 * itinéraire et l'app proposée sans obligation ni récompense. Rouvrir le même lien permet de changer sa réponse.
 */
export function InviteCardScreen({ token }: { token: string | undefined }) {
  const valid = typeof token === 'string' && TOKEN.test(token);
  const { session } = useAuth();
  const opened = useRef(false);
  const { data: card, loading, error, reload } = useQuery(async () => {
    if (!valid) return null;
    const first = !opened.current;
    opened.current = true;
    return fetchInviteCard(token!, first);  // première lecture : « A ouvert » chez l'organisateur
  }, [token, session?.user.id]);
  const [answer, setAnswer] = useState<RsvpStatus | null>(null);
  const [done, setDone] = useState<Accepted | null>(null);
  const [firstName, setFirstName] = useState<string | null>(null);

  if (!valid) return <Closed text="Ce lien d’invitation n’est pas complet. Copie-le en entier depuis le message reçu." />;
  if (loading && !card) return <Loading />;
  if (!card) return <Closed text="Ce lien d’invitation n’existe plus." error={error} />;
  if (done) return <Done card={card} done={done} name={firstName} onChange={() => { setDone(null); setAnswer(null); reload(); }} />;
  if (answer) {
    return <Identify token={token!} card={card} answer={answer} onBack={() => setAnswer(null)}
      onDone={(a, name) => { setFirstName(name); setDone(a); }} />;
  }
  return <Card card={card} onAnswer={setAnswer} />;
}

function Closed({ text, error }: { text: string; error?: string | null }) {
  return (
    <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 12 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Title>Lien indisponible</Title>
      <T muted>{text}</T>
      <ErrorText error={error ?? null} />
    </Screen>
  );
}

function when(card: Pick<InviteCard, 'starts_at' | 'all_day' | 'date_mode'>): string | null {
  if (card.date_mode === 'poll' || !card.starts_at) return 'Date à définir';
  const day = formatLongDay(card.starts_at);
  return card.all_day ? day : `${day} · ${formatTime(card.starts_at)}`;
}

function Host({ card }: { card: InviteCard }) {
  const name = card.inviter || 'Un ami';
  return (
    <View style={st.host}>
      <View style={[st.hostAvatar, { backgroundColor: avatarColor(name) }]}>
        <T weight="bold" color={colors.onAccent}>{initials(name)}</T>
      </View>
      <View style={{ flex: 1 }}>
        <T weight="bold" size={15}>{name} t’invite{card.label ? `, ${card.label}` : ''}</T>
        <T muted size={12}>{card.places_left != null ? `Lien pour plusieurs · reste ${card.places_left} ${card.places_left > 1 ? 'places' : 'place'}` : 'Seulement toi, avec ce lien'}</T>
      </View>
    </View>
  );
}

function Card({ card, onAnswer }: { card: InviteCard; onAnswer: (a: RsvpStatus) => void }) {
  const closed = card.state === 'full' || card.state === 'expired' || card.state === 'revoked';
  const cancelled = card.status === 'cancelled';
  const names = card.going_names;
  const others = Math.max(card.going - names.length, 0);
  const coming = names.length
    ? `${names.join(', ')}${others ? ` et ${others} ${others > 1 ? 'autres' : 'autre'}` : ''} ${card.going > 1 ? 'viennent' : 'vient'}`
    : card.going ? `${card.going} ${card.going > 1 ? 'personnes viennent' : 'personne vient'}` : 'Sois le premier à répondre';
  const answers = ANSWERS.filter((a) => a.key !== 'maybe' || card.allow_maybe);
  return (
    <Screen contentStyle={{ gap: 18 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <Host card={card} />
      <View style={[st.invite, enter('rise')]}>
        {card.cover_url ? (
          <Image source={{ uri: card.cover_url }} style={st.cover} resizeMode="cover" accessibilityLabel="Affiche de l’événement" />
        ) : (
          <View style={[st.cover, st.coverEmpty]}><T size={44}>🎉</T></View>
        )}
        <View style={{ padding: 18, gap: 14 }}>
          <Title size={30} style={{ lineHeight: 34 }}>{card.title}</Title>
          <Line icon="📅" title={when(card) ?? ''} />
          {card.location_name ? <Line icon="📍" title={card.location_name} hint={card.mine ? undefined : 'L’adresse exacte après ta réponse'} /> : null}
          {card.description ? <T size={14} color={colors.textSoft} numberOfLines={5}>{card.description}</T> : null}
          <View style={st.coming}>
            <View style={{ flexDirection: 'row' }}>
              {names.map((n, i) => (
                <View key={`${n}${i}`} style={[st.face, { backgroundColor: avatarColor(n + i), marginLeft: i ? -8 : 0 }]}>
                  <T size={11} weight="bold" color={colors.onAccent}>{initials(n)}</T>
                </View>
              ))}
            </View>
            <T size={13} weight="semibold" color={colors.textSoft} style={{ flex: 1 }}>{coming}</T>
          </View>
        </View>
      </View>
      {cancelled ? (
        <View style={st.notice}><T weight="bold" color={colors.coralSoft}>Cet événement est annulé.</T></View>
      ) : closed ? (
        <View style={st.notice}><T color={colors.coralSoft}>{CLOSED[card.state]}</T></View>
      ) : card.closed ? (
        <View style={st.notice}><T color={colors.coralSoft}>Les réponses sont fermées pour cet événement.</T></View>
      ) : (
        <View style={{ gap: 10 }}>
          {card.mine ? <T weight="semibold" style={{ textAlign: 'center' }}>Ta réponse : {ANSWERS.find((a) => a.key === card.mine)?.label}. Tu peux la changer.</T> : null}
          {answers.map((a) => (
            <Pressable key={a.key} accessibilityRole="button" accessibilityState={{ selected: card.mine === a.key }} onPress={() => onAnswer(a.key)}
              style={({ pressed }) => [st.answer, a.key === 'yes' ? st.answerYes : null, card.mine === a.key && { borderColor: rsvpColors[a.key] },
                pressTransition, pressed && { transform: [{ scale: 0.97 }] }]}>
              <T weight="bold" size={17} color={a.key === 'yes' ? colors.onAction : colors.text}>{a.label}</T>
            </Pressable>
          ))}
          <T muted size={13} style={{ textAlign: 'center' }}>Pas besoin d’installer l’app.</T>
        </View>
      )}
    </Screen>
  );
}

function Line({ icon, title, hint }: { icon: string; title: string; hint?: string }) {
  return (
    <View style={st.line}>
      <View style={st.lineIcon}><T size={16}>{icon}</T></View>
      <View style={{ flex: 1 }}>
        <T weight="bold" size={16}>{title}</T>
        {hint ? <T muted size={12}>{hint}</T> : null}
      </View>
    </View>
  );
}

/** Prénom, numéro (+41 d'office), code SMS ; déjà connecté : on enregistre tout de suite (le prénom si le compte n'en a pas). */
function Identify({ token, card, answer, onBack, onDone }: {
  token: string; card: InviteCard; answer: RsvpStatus; onBack: () => void; onDone: (a: Accepted, name: string | null) => void;
}) {
  const { session, refreshProfile } = useAuth();
  const [name, setName] = useState('');
  const [phone, setPhone] = useState('');
  const [code, setCode] = useState('');
  const [sentTo, setSentTo] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const started = useRef(false);
  const named = card.me_named;

  async function accept(first: string | null) {
    setBusy(true);
    setError(null);
    try {
      // Le prénom est vu des autres invités : CGU acceptées d'abord (exigées en prod), par le geste « Confirmer »
      // sous la phrase « En répondant, j'accepte les conditions d'utilisation » (Apple 1.2, Google UGC).
      if (first) await acceptTermsIfNeeded();
      const done = await acceptInvite(token, answer, first);
      await refreshProfile();
      onDone(done, first);
    } catch (e) {
      const message = e instanceof Error ? e.message : String(e);
      setError(dbMessage(message, message));
      started.current = false;
    } finally {
      setBusy(false);
    }
  }

  // Déjà connecté avec un prénom : rien à demander.
  useEffect(() => {
    if (session && named && !started.current) {
      started.current = true;
      void accept(null);
    }
  });

  async function sendCode() {
    setError(null);
    if (!name.trim()) return setError('Écris ton prénom.');
    const parsed = parseLoginPhone(phone, 'CH');
    if (!parsed) return setError('Vérifie ton numéro (ex. 079 123 45 67, ou +33 6 12 34 56 78 depuis l’étranger).');
    setBusy(true);
    const { error } = await supabase.auth.signInWithOtp({ phone: parsed.number });
    setBusy(false);
    if (error) return setError('Le code n’a pas pu être envoyé. Réessaie dans une minute.');
    setSentTo(parsed.number);
  }

  async function verify() {
    if (!sentTo) return;
    setBusy(true);
    setError(null);
    const { error } = await supabase.auth.verifyOtp({ phone: sentTo, token: code.trim(), type: 'sms' });
    setBusy(false);
    if (error) return setError('Code incorrect ou expiré.');
    await accept(name.trim());
  }

  if (session && named) {
    return (
      <Screen contentStyle={{ flexGrow: 1, justifyContent: 'center', gap: 16 }}>
        <Stack.Screen options={{ title: 'Invitation' }} />
        {error ? <><ErrorText error={error} /><Button label="Retour à l’invitation" variant="secondary" onPress={onBack} /></> : <Loading />}
      </Screen>
    );
  }

  const host = card.inviter || 'L’organisateur';
  return (
    <Screen contentStyle={{ gap: 18 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <View style={[{ gap: 6 }, enter('slideIn')]}>
        <Title size={30}>{answer === 'no' ? 'Dommage !' : answer === 'maybe' ? 'Peut-être, c’est noté' : 'Super, tu viens ! 🎉'}</Title>
        <T muted>{session ? `Ton prénom, pour que ${host} sache que c’est toi.` : `Deux infos pour que ${host} sache que c’est toi.`}</T>
      </View>
      <Field label="Prénom" value={name} onChangeText={setName} autoComplete="given-name" textContentType="givenName" autoCapitalize="words"
        maxLength={40} editable={!busy && !sentTo} placeholder="Ton prénom" />
      {session ? (
        <>
        <TermsConsent />
        <Button label="Confirmer" loading={busy} disabled={!name.trim()} onPress={() => void accept(name.trim())} />
        </>
      ) : !sentTo ? (
        <>
          <View style={{ gap: 6 }}>
            <T weight="semibold">Numéro de portable</T>
            <View style={st.phoneRow}>
              <View style={st.prefix}><T weight="semibold">🇨🇭 +41</T></View>
              <Input accessibilityLabel="Numéro de portable" placeholder="079 123 45 67" keyboardType="phone-pad" autoComplete="tel"
                textContentType="telephoneNumber" value={phone} onChangeText={setPhone} editable={!busy} onSubmitEditing={() => void sendCode()} style={{ flex: 1 }} />
            </View>
            <T muted size={12}>Depuis l’étranger : commence par +33, +34…</T>
          </View>
          <Button label="Recevoir mon code par SMS" loading={busy} disabled={!name.trim() || !phone.trim()} onPress={() => void sendCode()} />
        </>
      ) : (
        <View style={[{ gap: 10 }, enter('slideIn')]}>
          <Field label={`Code reçu par SMS au ${sentTo}`} placeholder="123456" keyboardType="number-pad" autoComplete="one-time-code"
            textContentType="oneTimeCode" maxLength={CODE_LENGTH} value={code} onChangeText={setCode} autoFocus onSubmitEditing={() => void verify()} />
          <TermsConsent />
          <Button label="Confirmer" loading={busy} disabled={code.trim().length < CODE_LENGTH} onPress={() => void verify()} />
          <Button small variant="ghost" label="Changer de numéro" onPress={() => { setSentTo(null); setCode(''); }} />
        </View>
      )}
      <ErrorText error={error} />
      <T muted size={12}>Ton numéro sert seulement à te reconnaître et à te prévenir si la soirée change. {host} ne le voit pas.</T>
      <Button small variant="ghost" label="‹ Retour à l’invitation" onPress={onBack} />
    </Screen>
  );
}

/** Acceptation des conditions dans le geste : la phrase est juste au-dessus de « Confirmer », avec le lien. */
function TermsConsent() {
  return (
    <View style={{ gap: 2 }}>
      <T muted size={13}>En répondant, j’accepte les conditions d’utilisation de Party.</T>
      <Pressable accessibilityRole="link" accessibilityLabel="Lire les conditions d’utilisation" hitSlop={8}
        onPress={() => void Linking.openURL(termsUrl())} style={{ alignSelf: 'flex-start', minHeight: 32, justifyContent: 'center' }}>
        <T size={13} weight="semibold" color={colors.accent}>Lire les conditions d’utilisation</T>
      </Pressable>
    </View>
  );
}

function Done({ card, done, name, onChange }: { card: InviteCard; done: Accepted; name: string | null; onChange: () => void }) {
  const { profile } = useAuth();
  const [later, setLater] = useState(false);
  const first = (name ?? profile?.display_name ?? '').split(' ')[0];
  const host = card.inviter || 'L’organisateur';
  const place = done.location_address ?? done.location_name;
  const maps = safeHref(done.location_url) ?? (place ? `https://maps.apple.com/?q=${encodeURIComponent(place)}` : null);
  const download = appDownload();
  const coming = done.status !== 'no';
  return (
    <Screen contentStyle={{ gap: 18 }}>
      <Stack.Screen options={{ title: 'Invitation' }} />
      <View style={[{ alignItems: 'center', gap: 10 }, enter('rise')]}>
        <View style={[st.check, { backgroundColor: coming ? colors.mint : colors.surface2 }]}>
          <T size={30} weight="bold" color={coming ? colors.onMint : colors.text}>{coming ? '✓' : '👋'}</T>
        </View>
        <Title size={30} style={{ textAlign: 'center' }}>C’est noté{first ? `, ${first}` : ''} !</Title>
        <T style={{ textAlign: 'center' }} color={colors.textSoft}>
          {DONE_WORDS[done.status]} <T weight="bold">{done.title}</T>{done.starts_at ? `, ${when({ ...done, date_mode: done.date_mode as InviteCard['date_mode'] })?.toLowerCase()}` : ''}.
        </T>
        <T muted>{host} est prévenu.</T>
        {done.waitlisted ? <T size={13} color={colors.coralSoft} style={{ textAlign: 'center' }}>C’est complet pour l’instant : tu es sur la liste d’attente.</T> : null}
      </View>
      {coming ? (
        <View style={{ gap: 10 }}>
          {place ? <Line icon="📍" title={done.location_name ?? place} hint={done.location_address && done.location_name ? done.location_address : undefined} /> : null}
          <View style={{ flexDirection: 'row', gap: 10 }}>
            {done.starts_at ? (
              <View style={{ flex: 1 }}>
                <CalendarButton event={{ id: done.event_id, title: done.title, description: done.description ?? '', starts_at: done.starts_at,
                  ends_at: done.ends_at, location_name: done.location_name, location_address: done.location_address }} />
              </View>
            ) : null}
            {maps ? <Button label="📍 Itinéraire" variant="secondary" style={{ flex: 1 }} onPress={() => void Linking.openURL(maps)} /> : null}
          </View>
        </View>
      ) : null}
      {!later ? (
        <View style={st.appCard}>
          <View style={st.appIcon}><T weight="bold" color={colors.onAction}>P!</T></View>
          <T weight="bold" size={17}>Reçois les nouvelles de la soirée</T>
          <T size={14} color={colors.textSoft}>
            Si l’heure change, ce que chacun amène, la musique en direct. Installer Party est facultatif : avec ton numéro, tu y retrouves ton invitation.
          </T>
          <View style={{ flexDirection: 'row', gap: 10 }}>
            <Button label="Installer Party" style={{ flex: 1 }} onPress={() => void Linking.openURL(download.url)} />
            <Button label="Plus tard" variant="secondary" style={{ flex: 1 }} onPress={() => setLater(true)} />
          </View>
        </View>
      ) : null}
      <T muted size={13} style={{ textAlign: 'center' }}>Un empêchement ? Rouvre ce même lien pour changer ta réponse.</T>
      <Button small variant="ghost" label="Changer ma réponse" onPress={onChange} />
    </Screen>
  );
}

const st = StyleSheet.create({
  host: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  hostAvatar: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center' },
  invite: { borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line, overflow: 'hidden' },
  cover: { width: '100%', aspectRatio: 16 / 9, backgroundColor: colors.surface2 },
  coverEmpty: { aspectRatio: 3, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.accentDim },
  line: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  lineIcon: { width: 40, height: 40, borderRadius: radius.sm, backgroundColor: colors.bg, borderWidth: 1, borderColor: colors.line, alignItems: 'center', justifyContent: 'center' },
  coming: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingTop: 12, borderTopWidth: 1, borderTopColor: colors.line },
  face: { width: 28, height: 28, borderRadius: 14, alignItems: 'center', justifyContent: 'center', borderWidth: 2, borderColor: colors.surface },
  answer: { minHeight: 54, borderRadius: radius.md, backgroundColor: colors.fillStrong, alignItems: 'center', justifyContent: 'center', borderWidth: 1.5, borderColor: 'transparent' },
  answerYes: { backgroundColor: colors.action },
  notice: { padding: 14, borderRadius: radius.md, backgroundColor: colors.coralDim },
  phoneRow: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  prefix: { height: 48, paddingHorizontal: 12, borderRadius: 12, backgroundColor: colors.fill, justifyContent: 'center' },
  check: { width: 64, height: 64, borderRadius: 32, alignItems: 'center', justifyContent: 'center' },
  appCard: { gap: 10, padding: 16, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  appIcon: { width: 44, height: 44, borderRadius: 12, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center' },
});
