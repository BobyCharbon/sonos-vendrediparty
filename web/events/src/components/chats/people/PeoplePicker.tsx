import { useEffect, useMemo, useRef, useState } from 'react';
import { Pressable, StyleSheet, Text, TextInput, View } from 'react-native';

import { Skeleton } from '@/components/ui';
import { fold } from '@/lib/chats';
import { enter, pressTransition } from '@/lib/motion';

import { CheckCircle, Icon, K, Label, PersonFace, txt, web } from './bits';
import { fetchSuggestions, metLabel, searchPeople, shortName, type Person, type Suggestions } from './people';

export const MAX_PEOPLE = 50;

/**
 * Choix des personnes de « Nouveau message » (maquette 1-neon/2) : « À : » avec les puces choisies et la recherche
 * (prénom, nom, surnom ; jamais un numéro), puis Croisés récemment, Dans tes groupes, Tes discussions récentes. Seulement
 * des personnes avec qui la base permet d'écrire (direct ou demande) : jamais tout le site.
 */
export function PeoplePicker({ selected, onToggle }: { selected: Person[]; onToggle: (p: Person) => void }) {
  const [sugg, setSugg] = useState<Suggestions | null>(null);
  const [failed, setFailed] = useState<string | null>(null);
  const [q, setQ] = useState('');
  const [found, setFound] = useState<{ q: string; people: Person[] } | null>(null);
  const [allCrossed, setAllCrossed] = useState(false);
  const input = useRef<TextInput>(null);
  const chosen = useMemo(() => new Set(selected.map((p) => p.id)), [selected]);

  useEffect(() => {
    let live = true;
    fetchSuggestions().then((s) => { if (live) setSugg(s); }, (e: Error) => { if (live) { setFailed(e.message); setSugg({ recent: [], crossed: [], groups: [] }); } });
    return () => { live = false; };
  }, []);

  const query = q.trim();
  useEffect(() => {
    if (query.length < 2) return undefined;
    let live = true;
    const timer = setTimeout(() => {
      searchPeople(query).then((people) => { if (live) setFound({ q: query, people }); }, () => { if (live) setFound({ q: query, people: [] }); });
    }, 220);
    return () => { live = false; clearTimeout(timer); };
  }, [query]);

  // Une personne n'apparaît qu'une fois, dans la première section qui la propose.
  const sections = useMemo(() => {
    const seen = new Set<string>();
    const keep = (list: Person[]) => list.filter((p) => !seen.has(p.id) && p.link !== 'none' && seen.add(p.id));
    return sugg ? { crossed: keep(sugg.crossed), groups: keep(sugg.groups), recent: keep(sugg.recent) } : null;
  }, [sugg]);

  function toggle(p: Person) {
    if (!chosen.has(p.id) && selected.length >= MAX_PEOPLE) return;
    onToggle(p);
    if (query) { setQ(''); setFound(null); }
    input.current?.focus();
  }

  const searching = query.length >= 2;
  const results = found && found.q === query ? found.people.filter((p) => p.link !== 'none') : null;
  const crossed = sections?.crossed ?? [];

  return (
    <View>
      <Pressable accessible={false} onPress={() => input.current?.focus()} style={st.to}>
        <Text style={txt(15, '700', K.t3)}>À</Text>
        {selected.map((p) => (
          <Pressable key={p.id} accessibilityRole="button" accessibilityLabel={`Retirer ${p.name}`} onPress={() => onToggle(p)}
            style={({ pressed }) => [st.pchip, enter('pop'), pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
            <PersonFace id={p.id} name={p.name} photo={p.photo} size={28} />
            <Text style={txt(15, '600', '#120B26', 20)} numberOfLines={1}>{shortName(p)}</Text>
            <View style={{ opacity: 0.7 }}><Icon name="x" size={13} color="#120B26" stroke={2.4} /></View>
          </Pressable>
        ))}
        <TextInput ref={input} value={q} onChangeText={setQ} autoFocus accessibilityLabel="Ajouter quelqu’un" placeholder="Ajouter quelqu’un…"
          placeholderTextColor={K.t3} autoCorrect={false} autoCapitalize="none"
          onKeyPress={(e) => { if (e.nativeEvent.key === 'Backspace' && !q && selected.length) onToggle(selected[selected.length - 1]); }}
          style={[st.toInput, ({ outlineStyle: 'none', caretColor: K.pink } as object)]} />
      </Pressable>
      {selected.length >= MAX_PEOPLE ? <Text style={[txt(13, '400', K.t2), { paddingHorizontal: 18, paddingTop: 8 }]}>50 personnes au plus.</Text> : null}

      {searching ? (
        <View style={st.results} testID="people-results">
          {results == null ? <View style={{ padding: 16, gap: 10 }}><Skeleton height={40} /><Skeleton height={40} /></View>
            : results.length ? results.map((p, i) => <Row key={p.id} p={p} on={chosen.has(p.id)} onPress={() => toggle(p)} mark={query} first={!i} />)
              : <Text style={[txt(15, '400', K.t2, 20), { padding: 16 }]}>Personne trouvée pour « {query} ». Cherche un prénom, un nom ou un surnom de quelqu’un que tu as croisé.</Text>}
        </View>
      ) : !sections ? (
        <View style={{ padding: 16, gap: 12 }}><Skeleton height={90} /><Skeleton height={56} /><Skeleton height={56} /></View>
      ) : (
        <>
          {crossed.length ? (
            <>
              <Label icon="sparkle" right={crossed.length > 4 ? (
                <Pressable accessibilityRole="button" onPress={() => setAllCrossed((a) => !a)} style={{ minHeight: 44, justifyContent: 'center' }}>
                  <Text style={txt(15, '600', K.lav)}>{allCrossed ? 'Moins' : 'Tout voir'}</Text>
                </Pressable>
              ) : undefined} style={{ paddingTop: 12, paddingBottom: 4 }}>Croisés récemment</Label>
              <View style={st.recent}>
                {(allCrossed ? crossed : crossed.slice(0, 4)).map((p) => <Tile key={p.id} p={p} on={chosen.has(p.id)} onPress={() => toggle(p)} />)}
              </View>
            </>
          ) : null}
          {sections.groups.length ? (
            <>
              <Label icon="users">Dans tes groupes</Label>
              {sections.groups.map((p, i) => <Row key={p.id} p={p} on={chosen.has(p.id)} onPress={() => toggle(p)} first={!i} />)}
            </>
          ) : null}
          {sections.recent.length ? (
            <>
              <Label icon="chat">Tes discussions récentes</Label>
              {sections.recent.map((p, i) => <Row key={p.id} p={p} on={chosen.has(p.id)} onPress={() => toggle(p)} first={!i} />)}
            </>
          ) : null}
          {!crossed.length && !sections.groups.length && !sections.recent.length ? (
            <Text style={[txt(15, '400', K.t2, 21), { padding: 20, textAlign: 'center' }]}>
              {failed ?? 'Les personnes croisées à une soirée ou dans tes groupes apparaîtront ici. Tu peux aussi chercher un prénom ou un surnom.'}
            </Text>
          ) : null}
        </>
      )}
    </View>
  );
}

function subOf(p: Person): string {
  return p.sub || (p.met_count ? metLabel(p.met_count) : p.link === 'request' ? 'Demande de message' : '');
}

/** Ligne d'une personne : visage, nom (texte trouvé surligné), sous-titre, rond de sélection. */
function Row({ p, on, onPress, mark, first }: { p: Person; on: boolean; onPress: () => void; mark?: string; first?: boolean }) {
  const sub = subOf(p);
  return (
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: on }} aria-checked={on} accessibilityLabel={`${p.name}${sub ? `, ${sub}` : ''}`}
      onPress={onPress} style={({ pressed }) => [st.row, pressed && { backgroundColor: K.glass }]}>
      {!first ? <View style={st.sep} /> : null}
      <PersonFace id={p.id} name={p.name} photo={p.photo} size={40} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <Text style={txt(17, '600', K.t1, 22)} numberOfLines={1}>
          {mark ? highlight(p.name, mark) : p.name}
          {p.nickname && p.nickname !== p.name ? <Text style={{ color: K.t3, fontWeight: '500' }}> · {mark ? highlight(p.nickname, mark) : p.nickname}</Text> : null}
        </Text>
        {sub ? <Text style={txt(14, '400', K.t2, 19)} numberOfLines={1}>{sub}</Text> : null}
      </View>
      <CheckCircle on={on} />
    </Pressable>
  );
}

/** Grand visage de « Croisés récemment » : anneau néon et ✓ rose quand la personne est choisie. */
function Tile({ p, on, onPress }: { p: Person; on: boolean; onPress: () => void }) {
  const sub = subOf(p);
  return (
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: on }} aria-checked={on} accessibilityLabel={`${p.name}${sub ? `, ${sub}` : ''}`}
      onPress={onPress} style={({ pressed }) => [st.rp, pressTransition, pressed && { transform: [{ scale: 0.95 }] }]}>
      <View style={[st.ring, on && web({ backgroundImage: `conic-gradient(from 200deg, ${K.pink}, ${K.lavB}, ${K.lavA}, ${K.pink})`, boxShadow: '0 0 18px -2px rgba(255,79,154,.55)' })]}>
        <View style={st.ringInner}><PersonFace id={p.id} name={p.name} photo={p.photo} size={64} /></View>
        {on ? <View style={[st.ck, enter('pop')]}><Icon name="check" size={13} color={K.onPink} stroke={3.2} /></View> : null}
      </View>
      <Text style={[txt(14, '600', K.t1, 18), { marginTop: 5, textAlign: 'center' }]} numberOfLines={1}>{shortName(p)}</Text>
      {sub ? <Text style={[txt(12, '400', K.t3, 16), { textAlign: 'center' }]} numberOfLines={1}>{sub}</Text> : null}
    </Pressable>
  );
}

/** Le texte cherché en rose dans le nom (insensible aux accents et à la casse). */
function highlight(name: string, q: string) {
  const at = fold(name).indexOf(fold(q));
  if (at < 0) return name;
  return <>{name.slice(0, at)}<Text style={{ color: K.pinkInk, fontWeight: '700' }}>{name.slice(at, at + q.length)}</Text>{name.slice(at + q.length)}</>;
}

const st = StyleSheet.create({
  to: web({ marginTop: 4, marginHorizontal: 16, minHeight: 52, paddingVertical: 7, paddingHorizontal: 10, borderRadius: 16, backgroundColor: K.glass,
    borderWidth: 1, borderColor: 'rgba(185,167,255,0.35)', boxShadow: '0 0 0 4px rgba(123,108,246,.12)', flexDirection: 'row', flexWrap: 'wrap',
    alignItems: 'center', gap: 6, ...({ cursor: 'text' } as object) }),
  pchip: web({ height: 36, flexDirection: 'row', alignItems: 'center', gap: 7, paddingLeft: 4, paddingRight: 10, borderRadius: 18, maxWidth: 200,
    backgroundColor: K.lav, backgroundImage: `linear-gradient(135deg, ${K.lavA}, ${K.lav})` }),
  toInput: { flex: 1, minWidth: 140, height: 36, paddingHorizontal: 4, color: K.t1, fontSize: 17 },
  results: { marginTop: 10, marginHorizontal: 16, borderRadius: 18, backgroundColor: K.s1, borderWidth: 1, borderColor: K.line, overflow: 'hidden' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 64, paddingHorizontal: 16 },
  sep: { position: 'absolute', top: 0, left: 66, right: 0, height: 1, backgroundColor: K.line },
  recent: { flexDirection: 'row', flexWrap: 'wrap', paddingHorizontal: 8, rowGap: 12 },
  rp: { width: '25%', alignItems: 'center', paddingHorizontal: 2 },
  ring: { padding: 3, borderRadius: 999, position: 'relative' },
  ringInner: { padding: 2, borderRadius: 999, backgroundColor: K.bg },
  ck: { position: 'absolute', right: -2, bottom: -2, width: 24, height: 24, borderRadius: 12, alignItems: 'center', justifyContent: 'center',
    backgroundColor: K.pink, borderWidth: 3, borderColor: K.bg },
});
