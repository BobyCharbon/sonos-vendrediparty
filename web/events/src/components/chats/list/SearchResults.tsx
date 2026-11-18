import { useEffect, useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { chatFont, useNeon } from '../neon';
import { ChatFace, PersonFace } from './Faces';
import { listTime } from './format';
import { usePersonText } from '@/components/PersonName';
import { fold, searchMessages, searchPeople, type ChatItem, type ChatPerson, type MessageHit } from '@/lib/chatList';
import { enter } from '@/lib/motion';

/**
 * Recherche (contrat §8) : Personnes (prénom, nom, surnom ; jamais par numéro ; seulement celles à qui je peux écrire),
 * Discussions (mes titres, sans accents), Messages (dans mes conversations seulement). Dès 2 caractères pour la base.
 */
export function SearchResults({ q, chats, onPerson, onChat, onMessage }: {
  q: string; chats: ChatItem[];
  onPerson: (p: ChatPerson) => void; onChat: (c: ChatItem) => void; onMessage: (m: MessageHit) => void;
}) {
  const c = useNeon();
  const personText = usePersonText();
  const query = q.trim();
  const [res, setRes] = useState<{ q: string; people: ChatPerson[]; messages: MessageHit[] } | null>(null);

  useEffect(() => {
    if (query.length < 2) return undefined;
    let live = true;
    const timer = setTimeout(() => {
      void Promise.all([searchPeople(query), searchMessages(query)]).then(([p, m]) => {
        if (live) setRes({ q: query, people: p, messages: m });
      });
    }, 250);
    return () => { live = false; clearTimeout(timer); };
  }, [query]);

  const fresh = query.length >= 2 && res?.q === query ? res : null;
  const people = fresh?.people ?? [];
  const messages = fresh?.messages ?? [];
  const busy = query.length >= 2 && !fresh;

  const f = fold(query);
  const found = f ? chats.filter((ch) => fold(ch.kind === 'direct' && ch.user_id ? personText(ch.user_id, ch.title) : ch.title).includes(f)).slice(0, 8) : [];
  const nothing = query.length >= 2 && !busy && !people.length && !messages.length && !found.length;

  return (
    <View style={{ paddingBottom: 24 }} aria-live="polite">
      {query.length < 2 ? (
        <Text style={[chatFont.text, st.hint, { color: c.t2 }]}>Cherche une personne par son prénom, son nom ou son surnom, une discussion ou un message.</Text>
      ) : null}
      {people.length ? (
        <Section title="Personnes">
          {people.map((p, i) => (
            <Pressable key={p.id} accessibilityRole="button" accessibilityLabel={`${personText(p.id, p.name)}${p.link === 'request' ? ', demande de message' : ''}`}
              onPress={() => onPerson(p)} style={({ pressed }) => [st.row, enter('rise', i), pressed && { backgroundColor: c.glass }]}>
              <PersonFace id={p.id} name={p.name} photo={p.photo} size={44} />
              <View style={{ flex: 1, minWidth: 0 }}>
                <Text numberOfLines={1} style={[chatFont.semibold, { color: c.t1, fontSize: 17 }]}>
                  {personText(p.id, p.name)}{p.nickname && p.nickname !== p.name ? <Text style={[chatFont.medium, { color: c.t3 }]}> · {p.nickname}</Text> : null}
                </Text>
                <Text numberOfLines={1} style={[chatFont.text, { color: c.t2, fontSize: 14 }]}>
                  {p.sub || (p.met_count ? `Déjà vu ${p.met_count} fois` : p.link === 'request' ? 'Ce sera une demande de message' : 'Membre de Party')}
                </Text>
              </View>
            </Pressable>
          ))}
        </Section>
      ) : null}
      {found.length ? (
        <Section title="Discussions">
          {found.map((ch, i) => (
            <Pressable key={`${ch.kind}:${ch.id}`} accessibilityRole="button" accessibilityLabel={`Ouvrir ${ch.kind === 'direct' && ch.user_id ? personText(ch.user_id, ch.title) : ch.title}`}
              onPress={() => onChat(ch)} style={({ pressed }) => [st.row, enter('rise', i), pressed && { backgroundColor: c.glass }]}>
              <ChatFace chat={ch} size={44} />
              <Text numberOfLines={1} style={[chatFont.semibold, { flex: 1, color: c.t1, fontSize: 17 }]}>
                {ch.kind === 'direct' && ch.user_id ? personText(ch.user_id, ch.title) : ch.title}
              </Text>
            </Pressable>
          ))}
        </Section>
      ) : null}
      {messages.length ? (
        <Section title="Messages">
          {messages.map((m, i) => (
            <Pressable key={m.message_id} accessibilityRole="button" accessibilityLabel={`Message dans ${m.title} : ${m.excerpt}`}
              onPress={() => onMessage(m)} style={({ pressed }) => [st.msg, enter('rise', i), pressed && { backgroundColor: c.glass }]}>
              <View style={{ flexDirection: 'row', gap: 8, alignItems: 'center' }}>
                <Text numberOfLines={1} style={[chatFont.semibold, { flex: 1, color: c.t1, fontSize: 16 }]}>{m.title}</Text>
                <Text style={[chatFont.num, { color: c.t3, fontSize: 13 }]}>{listTime(m.at)}</Text>
              </View>
              <Text numberOfLines={2} style={[chatFont.text, { color: c.t2, fontSize: 15, lineHeight: 20 }]}>
                <Highlight text={m.excerpt} q={query} color={c.pinkInk} />
              </Text>
            </Pressable>
          ))}
        </Section>
      ) : null}
      {busy && !people.length && !messages.length ? <Text style={[chatFont.text, st.hint, { color: c.t3 }]}>Recherche…</Text> : null}
      {nothing ? <Text style={[chatFont.text, st.hint, { color: c.t2 }]}>Rien trouvé pour « {query} ».</Text> : null}
    </View>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const c = useNeon();
  return (
    <View>
      <Text role="heading" aria-level={2} style={[chatFont.label, { color: c.t3, paddingHorizontal: 16, paddingTop: 20, paddingBottom: 8 }]}>{title}</Text>
      {children}
    </View>
  );
}

/** Le mot cherché en rose dans l'extrait (sans accents ni casse). */
function Highlight({ text, q, color }: { text: string; q: string; color: string }) {
  const at = fold(text).indexOf(fold(q));
  if (at < 0 || !q) return <>{text}</>;
  return <>{text.slice(0, at)}<Text style={[chatFont.semibold, { color }]}>{text.slice(at, at + q.length)}</Text>{text.slice(at + q.length)}</>;
}

const st = StyleSheet.create({
  hint: { fontSize: 15, lineHeight: 20, paddingHorizontal: 16, paddingTop: 20, textAlign: 'center' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 60, paddingHorizontal: 16 },
  msg: { paddingHorizontal: 16, paddingVertical: 10, gap: 2, minHeight: 60 },
});
