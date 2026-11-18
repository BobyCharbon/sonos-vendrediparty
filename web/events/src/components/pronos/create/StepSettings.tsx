import { useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { DateTimeField } from '@/components/DateTimeField';
import { GroupTile } from '@/components/GroupBits';
import { KindIcon, kindLabel } from '@/components/pronos/Kit';
import { Avatar, ErrorText } from '@/components/ui';
import { formatLongDay, parseLocalDateTime, plural } from '@/lib/format';
import { gradient, groupName, type GroupOverview } from '@/lib/groups';
import { pressTransition } from '@/lib/motion';
import type { Face } from '@/lib/pronos';

import { endChoices, filledOptions, fixedReveal, inDays, patatesPossible, shownQuestion, type Award, type Draft, type Who } from './model';
import { Block, C, digits, Footer, nb, RadioCard, rounded, StepNav, StepScreen, Txt, web } from './ui';

export type Bag = { balance: number } | null;

/**
 * Étape 3 « Réglages » (maquette 2-3) : qui joue EN PREMIER (il décide si les patates sont possibles), la fin en puces
 * rapides, les patates (seulement dans un groupe ou une soirée, si la base les a allumées), les points, le dévoilement,
 * puis le résumé et « Lancer le prono ».
 */
export function StepSettings(props: {
  d: Draft; awards: Award[]; groups: GroupOverview[]; event: { id: string; title: string } | null; people: Face[];
  who: Who; setWho: (w: Who) => void; end: string; setEnd: (v: string) => void;
  bag: Bag | undefined; patates: boolean; setPatates: (v: boolean) => void;
  points: number; setPoints: (n: number) => void; reveal: 'close' | 'result'; setReveal: (r: 'close' | 'result') => void;
  busy: boolean; err: string | null; onBack: () => void; onLaunch: () => void;
}) {
  const { d, awards, groups, event, people, who, setWho, end, setEnd, bag, patates, setPatates, points, setPoints, reveal, setReveal } = props;
  const [others, setOthers] = useState(who.people.length > 0 || who.link);
  const [custom, setCustom] = useState(false);
  const choices = endChoices();
  const chosen = choices.find((c) => c.local === end);
  const iso = parseLocalDateTime(end);
  const group = groups.find((g) => g.id === who.group) ?? null;
  const terrain = !!(who.group || who.event);
  const canPatates = terrain && patatesPossible(d.kind) && !!bag;
  const withPatates = canPatates && patates;
  const ready = !!iso && !!(who.group || who.event || who.people.length || who.link);
  const forced = fixedReveal(d.kind);
  const bagOf = group ? groupName(group) : event?.title ?? '';

  const audience = group ? `${groupName(group)} · ${plural(group.members, 'membre')}`
    : event ? 'Les participants'
      : who.people.length ? plural(who.people.length, 'personne') : who.link ? 'Un lien' : 'Personne encore';
  const summary = [audience, iso ? `fin ${shortEnd(iso)}` : null, withPatates ? 'avec confettis 🎊' : 'pour l’honneur'].filter(Boolean).join('  ·  ');

  return (
    <StepScreen nav={<StepNav step={3} title="Réglages" icon="‹" onBack={props.onBack} backLabel="Retour à la question" />}
      footer={(
        <Footer label="🔮 Lancer le prono" onPress={props.onLaunch} disabled={!ready} loading={props.busy} testID="prono-launch"
          note={(
            <View style={{ gap: 6 }}>
              <ErrorText error={props.err} />
              <Txt size={15} color={C.t2} weight="600" style={{ textAlign: 'center' }}>{summary}</Txt>
            </View>
          )} />
      )}>
      <Pressable accessibilityRole="button" accessibilityLabel={`Modifier la question : ${shownQuestion(d, awards)}`} onPress={props.onBack} testID="prono-recap"
        style={({ pressed }) => [st.recap, pressTransition, pressed && { opacity: 0.85 }]}>
        <View style={[st.recapCover, gradient(group?.color ?? (event ? 'coral' : 'lavender'))]}><Text style={{ fontSize: 30 }}>{d.emoji}</Text></View>
        <View style={{ flex: 1, gap: 4, paddingVertical: 10 }}>
          <Text style={[rounded, { fontSize: 16, color: C.t1 }]} numberOfLines={1}>{nb(shownQuestion(d, awards))}</Text>
          <View style={{ flexDirection: 'row', alignItems: 'center', gap: 6 }}>
            <KindIcon kind={d.kind} />
            <Txt size={14} color={C.t2}>{kindLabel(d.kind)}{d.kind === 'choice' || d.kind === 'majority' ? ` · ${plural(filledOptions(d).length, 'réponse')}` : ''}</Txt>
          </View>
        </View>
        <Txt size={16} weight="600" color={C.lavText} style={{ paddingRight: 14 }}>Modifier</Txt>
      </Pressable>

      <Block label="QUI JOUE" index={1}>
        {event ? (
          <RadioCard on a11y={`Les participants de ${event.title}`} onPress={() => undefined}>
            <View style={[st.cover, gradient('coral')]}><Text style={{ fontSize: 24 }}>📅</Text></View>
            <View style={{ flex: 1, gap: 2 }}>
              <Txt size={17} weight="700" numberOfLines={1}>{event.title}</Txt>
              <Txt size={13} color={C.t2}>Les participants (Présent, Peut-être) sont prévenus</Txt>
            </View>
          </RadioCard>
        ) : (
          <>
            {groups.map((g) => {
              const on = who.group === g.id;
              return (
                <RadioCard key={g.id} on={on} a11y={`${groupName(g)}, ${plural(g.members, 'membre')}`} testID={`prono-who-group-${g.id}`}
                  onPress={() => setWho({ ...who, group: on ? null : g.id })}>
                  <GroupTile group={g} size={48} />
                  <View style={{ flex: 1, gap: 2 }}>
                    <Txt size={17} weight="700" numberOfLines={1}>{groupName(g)}</Txt>
                    <Txt size={13} color={C.t2}>{plural(g.members, 'membre')}, tous prévenus</Txt>
                  </View>
                </RadioCard>
              );
            })}
            {!groups.length ? <Txt size={14} color={C.t2}>Tu n’as pas encore de groupe : choisis des personnes ou un lien.</Txt> : null}
            <Pressable accessibilityRole="button" accessibilityState={{ expanded: others }} onPress={() => setOthers(!others)} testID="prono-who-others">
              <Txt size={16} color={C.t2}>Ou <Text style={{ color: C.lavText, fontWeight: '700' }}>des personnes choisies, un lien</Text> · pour l’honneur</Txt>
            </Pressable>
            {others ? (
              <View style={{ gap: 10 }}>
                <View style={st.people}>
                  {people.map((f) => {
                    const on = who.people.includes(f.id);
                    return (
                      <Pressable key={f.id} accessibilityRole="checkbox" accessibilityState={{ checked: on }} aria-checked={on} accessibilityLabel={f.name}
                        onPress={() => setWho({ ...who, people: on ? who.people.filter((x) => x !== f.id) : [...who.people, f.id] })}
                        style={({ pressed }) => [st.person, on && st.personOn, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
                        <Avatar id={f.id} name={f.name} photo={f.avatar_url} size={28} profile={false} />
                        <Txt size={15} numberOfLines={1} style={{ maxWidth: 130 }}>{f.name}</Txt>
                      </Pressable>
                    );
                  })}
                  {!people.length ? <Txt size={14} color={C.t2}>Personne croisée dans Party pour l’instant.</Txt> : null}
                </View>
                <RadioCard on={who.link} a11y="Un lien à partager" testID="prono-who-link" onPress={() => setWho({ ...who, link: !who.link })}>
                  <View style={[st.cover, gradient('lavender')]}><Text style={{ fontSize: 22 }}>🔗</Text></View>
                  <View style={{ flex: 1, gap: 2 }}>
                    <Txt size={17} weight="700">Un lien à partager</Txt>
                    <Txt size={13} color={C.t2}>Qui l’ouvre se connecte à Party, puis joue.</Txt>
                  </View>
                </RadioCard>
              </View>
            ) : null}
          </>
        )}
      </Block>

      <Block label="FIN DES RÉPONSES" index={2}>
        <View style={st.ends}>
          {choices.map((c) => {
            const on = !custom && c.local === end;
            return (
              <Pressable key={c.key} accessibilityRole="radio" accessibilityState={{ selected: on }} aria-checked={on} accessibilityLabel={`${c.label} ${c.time}`}
                testID={`prono-end-${c.key}`} onPress={() => { setCustom(false); setEnd(c.local); }}
                style={({ pressed }) => [st.end, on && st.endOn, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
                <Txt size={16} weight="700" color={on ? '#1D1530' : C.t1}>{c.label}</Txt>
                <Text style={[digits, { fontSize: 16, color: on ? '#1D1530' : C.t2 }]}>{c.time}</Text>
              </Pressable>
            );
          })}
          <Pressable accessibilityRole="radio" accessibilityState={{ selected: custom || !chosen }} aria-checked={custom || !chosen} testID="prono-end-custom"
            onPress={() => setCustom(true)} style={({ pressed }) => [st.end, (custom || !chosen) && st.endOn, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
            <Txt size={16} color={custom || !chosen ? '#1D1530' : C.t1}>📅</Txt>
            <Txt size={16} weight="700" color={custom || !chosen ? '#1D1530' : C.t1}>Choisir…</Txt>
          </Pressable>
        </View>
        {custom ? <DateTimeField label="Fin des réponses" value={end} onChangeText={setEnd} hint="Heure de Zurich. Plus personne ne joue après." /> : null}
        {iso ? (
          <View style={st.endRow}>
            <View style={st.clock}><Text style={{ fontSize: 20 }}>🕒</Text></View>
            <View style={{ flex: 1, gap: 2 }}>
              <Txt size={17} weight="700">{formatLongDay(iso)}</Txt>
              <Txt size={14} color={C.t2}>{inDays(end)}</Txt>
            </View>
            <Text style={[digits, { fontSize: 28, color: C.t1 }]}>{end.slice(11)}</Text>
          </View>
        ) : <Txt size={14} color={C.amber}>Choisis le jour et l’heure de fin.</Txt>}
      </Block>

      {canPatates ? (
        <Block label="CONFETTIS 🎊" right={`sac de ${bagOf}`} index={3}>
          <View style={st.pair}>
            <RadioCard on={patates} a11y="Avec confettis, de 0 à 20 chacun" testID="prono-patates-on" onPress={() => setPatates(true)} style={st.half} corner>
              <View style={{ gap: 6, flex: 1 }}>
                <Text style={{ fontSize: 30 }}>🎊</Text>
                <Txt size={18} weight="800">Avec confettis</Txt>
                <Txt size={14} color={C.t2}>De 0 à 20 chacun</Txt>
              </View>
            </RadioCard>
            <RadioCard on={!patates} a11y="Pour l’honneur, seulement des points" testID="prono-patates-off" onPress={() => setPatates(false)} style={st.half} corner>
              <View style={{ gap: 6, flex: 1 }}>
                <Text style={{ fontSize: 30 }}>🏅</Text>
                <Txt size={18} weight="800">Pour l’honneur</Txt>
                <Txt size={14} color={C.t2}>Seulement des points</Txt>
              </View>
            </RadioCard>
          </View>
          {patates ? (
            <View style={st.how}>
              <View style={st.steps}>
                {[['🎊', 'On lance', '0 à 20 de ton sac'], ['🪩', 'La piste', 'se remplit en secret'], ['🧺', 'On ramasse', 'pour qui a vu juste']].map(([e, t, s], i) => (
                  <View key={t} style={{ flex: 1, flexDirection: 'row', alignItems: 'center' }}>
                    {i > 0 ? <Txt size={18} color={C.t3}>›</Txt> : null}
                    <View style={{ flex: 1, alignItems: 'center', gap: 4 }}>
                      <View style={st.stepIcon}><Text style={{ fontSize: 24 }}>{e}</Text></View>
                      <Txt size={15} weight="700">{t}</Txt>
                      <Txt size={13} color={C.t2} style={{ textAlign: 'center' }}>{s}</Txt>
                    </View>
                  </View>
                ))}
              </View>
              <View style={st.rule} />
              <Txt size={14} color={C.t2}>
                <Text style={{ color: C.t1, fontWeight: '700' }}>ⓘ Les confettis n’ont aucune valeur : </Text>
                ils ne s’achètent pas, ne se vendent pas, ne s’échangent pas. Personne n’a vu juste ? Chacun récupère les siens.
              </Txt>
              {bag ? <Txt size={13} color={C.t3}>Ton sac ici : {bag.balance} 🎊</Txt> : null}
            </View>
          ) : null}
        </Block>
      ) : null}

      {d.kind !== 'award' ? (
        <Block label="POINTS AU CLASSEMENT" index={4}>
          <View style={st.pointsCard}>
            <View style={{ flexDirection: 'row', alignItems: 'baseline', gap: 12 }}>
              <Text style={[digits, { fontSize: 40, color: C.t1 }]}>{points}</Text>
              <Txt size={17} weight="600" color={C.t2}>point{points > 1 ? 's' : ''} pour qui voit juste</Txt>
            </View>
            <input type="range" min={1} max={10} step={1} value={points} aria-label="Points pour une bonne réponse" data-testid="prono-points"
              onChange={(e) => setPoints(Number(e.target.value))}
              style={{ width: '100%', height: 44, accentColor: C.lav, cursor: 'pointer', margin: 0 }} />
            <View style={{ flexDirection: 'row', justifyContent: 'space-between' }}>
              {['1', '5', '10'].map((n) => <Txt key={n} size={14} color={C.t2}>{n}</Txt>)}
            </View>
          </View>
        </Block>
      ) : null}

      {forced ? (
        <View style={st.note}>
          <Txt size={14} color={C.t2}>{d.kind === 'award'
            ? 'Dévoilement : seul le ou la gagnant·e est annoncé·e, dès 3 votes.'
            : d.kind === 'majority' ? 'Dévoilement à la fin : la réponse la plus choisie l’emporte toute seule.'
              : 'Dévoilement à la fin : tu lis les réponses, puis tu coches les bonnes.'}</Txt>
        </View>
      ) : (
        <Block label="DÉVOILEMENT" index={5}>
          <View style={st.pair}>
            <RadioCard on={reveal === 'close'} a11y="À la fin : tout s’ouvre seul à l’heure de fin" testID="prono-reveal-close" onPress={() => setReveal('close')} style={st.half} corner>
              <View style={{ gap: 6, flex: 1 }}>
                <View style={st.stepIcon}><Text style={{ fontSize: 22 }}>⏳</Text></View>
                <Txt size={18} weight="800">À la fin</Txt>
                <Txt size={14} color={C.t2}>Tout s’ouvre seul à l’heure de fin.</Txt>
              </View>
            </RadioCard>
            <RadioCard on={reveal === 'result'} a11y="Avec le résultat : tu dévoiles en donnant la bonne réponse" testID="prono-reveal-result" onPress={() => setReveal('result')} style={st.half} corner>
              <View style={{ gap: 6, flex: 1 }}>
                <View style={st.stepIcon}><Text style={{ fontSize: 22 }}>🎤</Text></View>
                <Txt size={18} weight="800">Avec le résultat</Txt>
                <Txt size={14} color={C.t2}>Tu dévoiles en donnant la bonne réponse.</Txt>
              </View>
            </RadioCard>
          </View>
        </Block>
      )}
    </StepScreen>
  );
}

const shortFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: 'Europe/Zurich', weekday: 'short', hour: '2-digit', minute: '2-digit' });
function shortEnd(iso: string): string {
  return shortFmt.format(new Date(iso));
}

const st = StyleSheet.create({
  recap: { flexDirection: 'row', alignItems: 'center', gap: 14, borderRadius: 18, overflow: 'hidden', backgroundColor: C.glass,
    borderWidth: 1, borderColor: C.lineStrong, minHeight: 68 },
  recapCover: { width: 68, alignSelf: 'stretch', alignItems: 'center', justifyContent: 'center' },
  cover: { width: 48, height: 48, borderRadius: 14, alignItems: 'center', justifyContent: 'center' },
  people: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  person: { flexDirection: 'row', alignItems: 'center', gap: 8, minHeight: 44, paddingHorizontal: 10, borderRadius: 22,
    backgroundColor: C.glass, borderWidth: 2, borderColor: C.line },
  personOn: { borderColor: C.lav, backgroundColor: 'rgba(123,108,246,0.22)' },
  ends: { flexDirection: 'row', gap: 8 },
  end: { flex: 1, minHeight: 62, borderRadius: 16, alignItems: 'center', justifyContent: 'center', gap: 2, backgroundColor: C.glass,
    borderWidth: 1, borderColor: C.line, paddingHorizontal: 4 },
  endOn: web({ backgroundColor: '#F4F1FF', borderColor: '#F4F1FF', boxShadow: '0 6px 20px rgba(185,167,255,0.3)' }),
  endRow: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, borderRadius: 20, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line },
  clock: { width: 44, height: 44, borderRadius: 12, backgroundColor: 'rgba(255,179,71,0.14)', alignItems: 'center', justifyContent: 'center' },
  pair: { flexDirection: 'row', gap: 12 },
  half: { flex: 1, alignItems: 'flex-start', minHeight: 98 },
  how: { gap: 14, padding: 16, borderRadius: 22, backgroundColor: 'rgba(255,179,71,0.06)', borderWidth: 1, borderColor: 'rgba(255,179,71,0.22)' },
  steps: { flexDirection: 'row', alignItems: 'flex-start' },
  stepIcon: { width: 48, height: 48, borderRadius: 14, backgroundColor: 'rgba(255,255,255,0.07)', alignItems: 'center', justifyContent: 'center' },
  rule: { height: 1, backgroundColor: C.line },
  pointsCard: { padding: 18, gap: 8, borderRadius: 24, backgroundColor: C.glass, borderWidth: 1, borderColor: C.line },
  note: { padding: 14, borderRadius: 16, backgroundColor: 'rgba(185,167,255,0.08)', borderWidth: 1, borderColor: 'rgba(185,167,255,0.22)' },
});
