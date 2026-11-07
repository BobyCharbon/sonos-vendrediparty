import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react';
import { FlatList, KeyboardAvoidingView, Platform, Pressable, View, type TextInput } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { LinkedText } from '@/components/LinkedText';
import { MentionSuggestions } from '@/components/MentionSuggestions';
import { ReportSheet } from '@/components/ReportSheet';
import { useTermsGate } from '@/components/TermsSheet';
import { Avatar, Button, ErrorText, HeaderBack, Input, s, T } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { insertMention, mentionQuery, mentionSuggestions } from '@/lib/chats';
import { useContactNames, withContactNames } from '@/lib/contactNames';
import { useQuery, useRealtime } from '@/lib/data';
import { formatMessageTime } from '@/lib/format';
import { enter } from '@/lib/motion';
import { dbMessage, type ReportTarget } from '@/lib/moderation';
import { check, must, supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';
import type { Message } from '@/lib/types';

/** Hauteur du champ de saisie : une ligne au repos, puis il suit le texte (padding compris) jusqu'à 5 lignes environ. */
const COMPOSER_MIN = 48;
const COMPOSER_MAX = 132;
/** Bordure du champ (1,5 px en haut et en bas), hors de la hauteur du contenu mesurée. */
const COMPOSER_BORDERS = 3;
const composerHeightFor = (content: number) => Math.min(COMPOSER_MAX, Math.max(COMPOSER_MIN, Math.ceil(content) + COMPOSER_BORDERS));

/** Zone de toucher agrandie des petits liens sous un message (Épingler, Supprimer, Signaler), sans changer leur taille visible. */
const ACTION_SLOP = { top: 12, bottom: 12, left: 6, right: 6 };
/** Texte affiché à la place d'un message d'une personne que j'ai bloquée (Réglages › Confidentialité). */
const BLOCKED_TEXT = 'Message masqué (personne bloquée)';

export default function ChatRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <Chat key={id} id={id} />;
}

function Chat({ id }: { id: string }) {
  const me = useMe();
  const { can } = useAuth();
  const isAdmin = can('events.manage_all');
  const [text, setText] = useState('');
  // Place du curseur (suggestions de l'@ en cours de frappe) et champ, pour y revenir après un choix.
  const [cursor, setCursor] = useState(0);
  const input = useRef<TextInput>(null);
  const [composerHeight, setComposerHeight] = useState(COMPOSER_MIN);
  // Fonction stable : react-native-web relit la taille du contenu à chaque nouvelle fonction (boucle de rendus sinon).
  const onComposerSize = useCallback((e: { nativeEvent: { contentSize: { height: number } } }) => {
    const next = composerHeightFor(e.nativeEvent.contentSize.height);
    setComposerHeight((h) => (Math.abs(h - next) < 2 ? h : next));
  }, []);
  const [replyTo, setReplyTo] = useState<Message | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const sendingRef = useRef(false);
  // Modération commune : « Signaler » un message, CGU acceptées avant le premier message.
  const [reportTarget, setReportTarget] = useState<ReportTarget | null>(null);
  const terms = useTermsGate();
  const [older, setOlder] = useState<Message[]>([]);
  const [olderMore, setOlderMore] = useState<boolean | null>(null);
  const [loadingOlder, setLoadingOlder] = useState(false);
  const loadingOlderRef = useRef(false);
  const followLatest = useRef(true);
  const list = useRef<FlatList<Message>>(null);

  const { data, error: loadError, loading, reload } = useQuery(async () => {
    const [ev, msgs, members, pins, blocks] = await Promise.all([
      supabase.from('events').select('title, created_by, event_organizers(user_id)').eq('id', id).single(),
      supabase.from('messages').select('*').eq('event_id', id).order('created_at', { ascending: false }).order('id', { ascending: false }).limit(101),
      supabase.from('profiles').select('id, display_name').eq('status', 'active'),
      supabase.from('messages').select('*').eq('event_id', id).eq('pinned', true).is('deleted_at', null).order('created_at'),
      // Mes blocages (lus seulement par moi) : leurs messages sont masqués ici, comme dans les discussions.
      supabase.from('direct_blocks').select('blocked_id'),
    ]);
    const event = must(ev) as { title: string; created_by: string; event_organizers: { user_id: string }[] };
    return {
      event,
      messages: (must(msgs) as Message[]).slice(0, 100),
      hasMore: msgs.data!.length > 100,
      pinned: must(pins) as Message[],
      members: must(members) as { id: string; display_name: string }[],
      blocked: new Set(((blocks.data as { blocked_id: string }[] | null) ?? []).map((b) => b.blocked_id)),
      canModerate: isAdmin || event.created_by === me.id || event.event_organizers.some((o) => o.user_id === me.id),
    };
  }, [id]);

  useRealtime(`chat-${id}`, [{ table: 'messages', filter: `event_id=eq.${id}` }], reload);

  // Affichage : app iPhone, « Nom du contact · pseudo » (les @ restent sur les pseudos).
  const contacts = useContactNames();
  const names = useMemo(() => withContactNames(new Map((data?.members ?? []).map((m) => [m.id, m.display_name])), contacts), [data?.members, contacts]);
  const messages = useMemo(() => {
    const unique = new Map([...older, ...(data?.messages ?? [])].map((m) => [m.id, m]));
    return [...unique.values()].filter((m) => !m.deleted_at).sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id));
  }, [older, data?.messages]);
  const byId = useMemo(() => new Map(messages.map((m) => [m.id, m])), [messages]);
  // Messages présents à l'ouverture (et plus anciens chargés ensuite) : affichés tels quels ;
  // seuls les plus récents (le mien envoyé, ceux reçus) montent.
  const [openedUpTo, setOpenedUpTo] = useState<string | null>(null);
  if (data && openedUpTo === null) setOpenedUpTo(data.messages[0]?.created_at ?? '');
  const blocked = data?.blocked;
  const isBlocked = (uid: string) => Boolean(blocked?.has(uid));
  const bodyOf = (m: Message) => (isBlocked(m.user_id) ? BLOCKED_TEXT : m.body);
  const pinned = (data?.pinned ?? []).filter((m) => !isBlocked(m.user_id));
  // « @ pour citer » : les membres (moi et les personnes bloquées exceptés) dont le surnom commence par les lettres tapées.
  const typing = mentionQuery(text, cursor);
  const suggestions = useMemo(() => (typing === null ? [] : mentionSuggestions(typing,
    (data?.members ?? []).filter((m) => m.id !== me.id && !blocked?.has(m.id)), { everyone: false, announce: false }, contacts)),
  [typing, data?.members, blocked, me.id, contacts]);

  function pickMention(label: string) {
    const next = insertMention(text, cursor, label);
    setText(next.text);
    setCursor(next.cursor);
    input.current?.focus();
  }

  async function loadOlder() {
    if (loadingOlderRef.current || !data) return;
    const cursor = [...older, ...data.messages].sort((a, b) => a.created_at.localeCompare(b.created_at) || a.id.localeCompare(b.id))[0];
    if (!cursor) return;
    loadingOlderRef.current = true;
    followLatest.current = false;
    setLoadingOlder(true);
    setError(null);
    try {
      const page = must(await supabase.from('messages').select('*').eq('event_id', id)
        .or(`created_at.lt.${cursor.created_at},and(created_at.eq.${cursor.created_at},id.lt.${cursor.id})`)
        .order('created_at', { ascending: false }).order('id', { ascending: false }).limit(101)) as Message[];
      setOlder((previous) => [...previous, ...data.messages, ...page.slice(0, 100)]);
      setOlderMore(page.length > 100);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      loadingOlderRef.current = false;
      setLoadingOlder(false);
    }
  }

  async function send() {
    const body = text.trim();
    if (!body || sendingRef.current) return;
    // Garde posée AVANT l'attente des CGU : un double toucher pendant cette attente n'envoie pas deux messages.
    sendingRef.current = true;
    if (!terms.accepted && !(await terms.ensure())) {
      sendingRef.current = false;
      return;
    }
    setSending(true);
    setError(null);
    // « @Prénom » dans le texte -> mention (notifiée même en mode « Mentions »)
    const mentions = (data?.members ?? [])
      .filter((m) => m.display_name && body.toLowerCase().includes(`@${m.display_name.toLowerCase()}`))
      .map((m) => m.id);
    try {
      check(await supabase.from('messages').insert({ event_id: id, user_id: me.id, body, reply_to: replyTo?.id ?? null, mentions }));
      setText('');
      setCursor(0);
      setReplyTo(null);
      followLatest.current = true;
      await reload();
    } catch (e) {
      setError(dbMessage(e instanceof Error ? e.message : String(e), 'Le message n’a pas pu être envoyé. Réessaie.'));
    } finally {
      sendingRef.current = false;
      setSending(false);
    }
  }

  async function togglePin(m: Message) {
    const { error } = await supabase.from('messages').update({ pinned: !m.pinned }).eq('id', m.id);
    setError(error?.message ?? null);
    reload();
  }

  async function remove(m: Message) {
    const { error } = await supabase.from('messages').update({ deleted_at: new Date().toISOString() }).eq('id', m.id);
    setError(error?.message ?? null);
    if (!error) setOlder((previous) => previous.filter((row) => row.id !== m.id));
    reload();
  }

  return (
    <SafeAreaView style={s.screen} edges={['bottom']}>
      <Stack.Screen options={{
        title: data?.event.title ?? 'Discussion',
        // Ouverte par un lien ou une notification (rien derrière) : ‹ Événement ramène à sa fiche.
        ...(router.canGoBack() ? {} : { headerLeft: () => <HeaderBack iconOnly label="Événement" onPress={() => router.replace(`/event/${id}`)} /> }),
      }} />
      <KeyboardAvoidingView style={{ flex: 1 }} behavior={Platform.OS === 'ios' ? 'padding' : undefined} keyboardVerticalOffset={90}>
        {pinned.map((m) => (
          <View key={m.id} style={[{ margin: 12, marginBottom: 0, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface }, enter('drop')]}>
            <T size={13} color={colors.textSoft}>
              <T size={13} weight="bold" color={colors.accent}>Épinglé · </T>
              {names.get(m.user_id)} : {bodyOf(m)}
            </T>
          </View>
        ))}
        <FlatList
          ref={list}
          data={messages}
          keyExtractor={(m) => m.id}
          contentContainerStyle={{ padding: 16, gap: 14 }}
          onContentSizeChange={() => { if (followLatest.current) list.current?.scrollToEnd({ animated: false }); }}
          onScroll={(event) => {
            const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
            followLatest.current = contentSize.height - contentOffset.y - layoutMeasurement.height < 100;
          }}
          scrollEventThrottle={100}
          ListHeaderComponent={(olderMore ?? data?.hasMore) ? <Button small variant="secondary" label="Messages précédents" onPress={loadOlder} loading={loadingOlder} /> : null}
          renderItem={({ item: m }) => {
            const mine = m.user_id === me.id;
            const quoted = m.reply_to ? byId.get(m.reply_to) : null;
            const hidden = isBlocked(m.user_id);
            return (
              <ArrivingRow fresh={openedUpTo !== null && m.created_at > openedUpTo} mine={mine}>
              <Pressable
                onLongPress={() => { if (!hidden) setReplyTo(m); }}
                accessibilityHint="Appui long pour répondre"
                style={{ flexDirection: 'row', gap: 8, alignItems: 'flex-end', justifyContent: mine ? 'flex-end' : 'flex-start' }}
              >
                {!mine ? <Avatar id={m.user_id} name={names.get(m.user_id) ?? '?'} /> : null}
                <View style={{ maxWidth: '78%', gap: 4, alignItems: mine ? 'flex-end' : 'flex-start' }}>
                  {!mine ? (
                    <Pressable accessibilityRole="button" accessibilityLabel={`Profil de ${names.get(m.user_id) ?? '?'}`}
                      onPress={() => router.push(`/member/${m.user_id}`)}>
                      <T size={12} weight="bold" color={colors.lavender}>{names.get(m.user_id) ?? '?'}</T>
                    </Pressable>
                  ) : null}
                  <View style={{ padding: 10, borderRadius: 16, backgroundColor: mine ? colors.accent : colors.surface, gap: 6 }}>
                    {quoted ? (
                      <View style={{ padding: 6, borderRadius: 8, backgroundColor: mine ? 'rgba(0,0,0,0.14)' : colors.surface2 }}>
                        <T size={12} color={mine ? colors.onAccent : colors.muted} numberOfLines={2}>
                          ↪ {names.get(quoted.user_id)} : {bodyOf(quoted)}
                        </T>
                      </View>
                    ) : null}
                    {hidden
                      ? <T size={14} muted style={{ fontStyle: 'italic' }}>{BLOCKED_TEXT}</T>
                      : <LinkedText size={15} color={mine ? colors.onAccent : colors.text} linkColor={mine ? colors.onAccent : colors.accent} text={m.body} />}
                  </View>
                  {/* Passe à la ligne sur un écran étroit : sinon cette ligne élargit la bulle au-delà de l'écran. */}
                  <View style={[s.row, { flexWrap: 'wrap', rowGap: 2 }]}>
                    <T muted size={11}>{formatMessageTime(m.created_at)}</T>
                    {data?.canModerate && !hidden ? (
                      <Pressable onPress={() => togglePin(m)} accessibilityRole="button" hitSlop={ACTION_SLOP}>
                        <T muted size={11}>{m.pinned ? 'Désépingler' : 'Épingler'}</T>
                      </Pressable>
                    ) : null}
                    {mine || can('chat.moderate') ? (
                      <Pressable onPress={() => remove(m)} accessibilityRole="button" hitSlop={ACTION_SLOP}>
                        <T muted size={11}>Supprimer</T>
                      </Pressable>
                    ) : null}
                    {!mine && !hidden ? (
                      <Pressable onPress={() => setReportTarget({ kind: 'event_message', id: m.id, label: `le message de ${names.get(m.user_id) ?? '?'}` })}
                        accessibilityRole="button" hitSlop={ACTION_SLOP} accessibilityLabel={`Signaler le message de ${names.get(m.user_id) ?? '?'}`}>
                        <T muted size={11}>Signaler</T>
                      </Pressable>
                    ) : null}
                  </View>
                </View>
              </Pressable>
              </ArrivingRow>
            );
          }}
          ListEmptyComponent={<T muted style={{ textAlign: 'center', marginTop: 40 }}>{loading ? 'Chargement…' : loadError ? 'La discussion n’a pas pu être chargée.' : 'Aucun message pour l’instant.'}</T>}
        />
        <ErrorText error={error ?? loadError} />
        {loadError ? <Button small label="Réessayer" variant="secondary" onPress={reload} /> : null}
        {replyTo ? (
          <View style={[s.rowBetween, { paddingHorizontal: 12, paddingTop: 8 }, enter('drop')]}>
            <T muted size={12} numberOfLines={1} style={{ flex: 1 }}>↪ Réponse à {names.get(replyTo.user_id)} : {replyTo.body}</T>
            <Button small variant="ghost" label="✕" onPress={() => setReplyTo(null)} />
          </View>
        ) : null}
        <MentionSuggestions suggestions={suggestions} onPick={(sug) => pickMention(sug.label)} />
        <View style={[s.row, { padding: 12, borderTopWidth: 1, borderTopColor: colors.line }]}>
          <Input
            inputRef={input}
            accessibilityLabel="Message"
            placeholder="Message (@ pour citer)"
            value={text}
            onChangeText={(v) => { setText(v); setCursor(v.length); }}
            onSelectionChange={(e) => setCursor(e.nativeEvent.selection.end)}
            multiline
            editable={!sending}
            maxLength={4000}
            // Le champ grandit avec le texte (jusqu'à COMPOSER_MAX) : à hauteur fixe, la 2e ligne rognait le haut du texte.
            onContentSizeChange={onComposerSize}
            style={{ flex: 1, height: text ? composerHeight : COMPOSER_MIN, paddingTop: 12, paddingBottom: 12 }}
          />
          <Button label="Envoyer" onPress={send} disabled={!text.trim() || !data} loading={sending} small />
        </View>
      </KeyboardAvoidingView>
      <ReportSheet target={reportTarget} onClose={() => setReportTarget(null)} />
      {terms.sheet}
    </SafeAreaView>
  );
}

/** Ligne de message : monte depuis le bas (côté de l'auteur) si elle arrive pendant que la discussion est ouverte.
 * L'animation est fixée à l'apparition (un rechargement ou un défilement ne la rejoue pas). */
function ArrivingRow({ fresh, mine, children }: { fresh: boolean; mine: boolean; children: ReactNode }) {
  const [arrive] = useState(() => (fresh ? enter(mine ? 'bubbleMine' : 'bubbleTheirs') : undefined));
  return <View style={arrive}>{children}</View>;
}
