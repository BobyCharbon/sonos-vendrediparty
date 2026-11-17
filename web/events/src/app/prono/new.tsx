import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { DateTimeField } from '@/components/DateTimeField';
import { goBack, TopBar } from '@/components/agenda/Bits';
import { GroupTile } from '@/components/GroupBits';
import { HonourNote } from '@/components/pronos/Bits';
import { useTermsGate } from '@/components/TermsSheet';
import { Avatar, Button, ErrorText, Input, Loading, Screen, Segmented, T, ToggleRow } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { parseLocalDateTime, plural, toLocalInput } from '@/lib/format';
import { fetchMyGroups, groupName } from '@/lib/groups';
import { enter, pressTransition } from '@/lib/motion';
import { errorText, isTerms, KINDS, nativePronos, pointsLabel, rpc, type Face, type Prono, type PronoKind, type Reveal } from '@/lib/pronos';
import { supabase } from '@/lib/supabase';
import { colors, font, radius } from '@/lib/theme';

/** Demain 20:00 : une fin raisonnable par défaut. */
function defaultEnd(): string {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  d.setHours(20, 0, 0, 0);
  return toLocalInput(d.toISOString());
}

/**
 * « Nouveau prono » (maquette du 17.11, écran 2) : la question, le type de réponse (choix, une personne, nombre, libre),
 * qui joue (un de mes groupes, des personnes croisées dans Party, et / ou un lien), la fin, le dévoilement et les points
 * (1 à 10). Ouvert depuis un groupe ou un événement : il est déjà choisi. Pour l'honneur : aucun champ d'enjeu.
 */
export default function NewProno() {
  const params = useLocalSearchParams<{ group?: string; event?: string }>();
  const fixedGroup = typeof params.group === 'string' ? params.group : null;
  const fixedEvent = typeof params.event === 'string' ? params.event : null;
  const native = nativePronos();
  useEffect(() => {
    if (native?.create) { native.create({ group: fixedGroup ?? undefined, event: fixedEvent ?? undefined }); goBack(fixedGroup ? `/group/${fixedGroup}` : fixedEvent ? `/event/${fixedEvent}` : '/'); }
  }, [native]);
  const terms = useTermsGate('Avant de lancer un prono');
  const { data, loading } = useQuery(async () => {
    const [groups, people, event] = await Promise.all([
      fetchMyGroups(),
      rpc<Face[]>('prono_suggestions').catch((): Face[] => []),
      fixedEvent ? supabase.from('events').select('id, title').eq('id', fixedEvent).maybeSingle().then((r) => r.data as { id: string; title: string } | null)
        : Promise.resolve(null),
    ]);
    return { groups: groups.filter((g) => !g.system && g.member), people, event };
  }, [fixedEvent]);

  const [question, setQuestion] = useState('');
  const [kind, setKind] = useState<PronoKind>('choice');
  const [options, setOptions] = useState<string[]>(['', '']);
  const [points, setPoints] = useState(3);
  const [end, setEnd] = useState(defaultEnd);
  const [reveal, setReveal] = useState<Reveal>('close');
  const [group, setGroup] = useState<string | null>(fixedGroup);
  const [people, setPeople] = useState<Set<string>>(new Set());
  const [link, setLink] = useState(false);
  const [showPeople, setShowPeople] = useState(false);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const filled = options.map((o) => o.trim()).filter(Boolean);
  const who = !!(group || fixedEvent || people.size || link);
  const iso = parseLocalDateTime(end);
  const ready = question.trim().length >= 3 && who && !!iso && (kind !== 'choice' || filled.length >= 2);
  const groupRow = useMemo(() => data?.groups.find((g) => g.id === group) ?? null, [data, group]);

  async function create(): Promise<void> {
    if (!iso) return;
    setBusy(true);
    setErr(null);
    try {
      const p = await rpc<Prono>('prono_create', { body: {
        question: question.trim(), kind, options: kind === 'choice' ? filled : [], points, closes_at: iso,
        reveal: kind === 'text' ? 'close' : reveal, group_id: group, event_id: fixedEvent, people: [...people], link,
      } });
      router.replace(`/prono/${p.id}`);
    } catch (e) {
      if (isTerms(e) && (await terms.ensure())) return create();
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <Loading />;
  return (
    <Screen contentStyle={{ gap: 14, paddingBottom: 48 }}>
      <Stack.Screen options={{ headerShown: false, title: 'Nouveau prono' }} />
      <TopBar back="Pronos" fallback={fixedGroup ? `/group/${fixedGroup}/pronos` : '/pronos'} title="Nouveau prono"
        subtitle="Une question, des réponses cachées jusqu’au dévoilement, des points pour qui voit juste." />

      <Input value={question} onChangeText={setQuestion} placeholder="Qui marque le premier but samedi ?" maxLength={200}
        accessibilityLabel="La question" style={{ fontSize: 18 }} testID="prono-question" />

      <Segmented options={KINDS.map((k) => ({ key: k.key, label: k.label }))} value={kind} onChange={setKind} />
      <T size={13} muted>{KINDS.find((k) => k.key === kind)?.hint}</T>

      {kind === 'choice' ? (
        <View style={{ gap: 6 }}>
          {options.map((o, i) => (
            <View key={i} style={[st.opt, enter('rise', i)]}>
              <Text style={st.num}>{i + 1}</Text>
              <Input value={o} onChangeText={(v) => setOptions((all) => all.map((x, j) => (j === i ? v : x)))} placeholder={`Choix ${i + 1}`}
                maxLength={60} accessibilityLabel={`Choix ${i + 1}`} style={{ flex: 1 }} />
              {options.length > 2 ? (
                <Pressable accessibilityRole="button" accessibilityLabel={`Retirer le choix ${i + 1}`} onPress={() => setOptions((all) => all.filter((_, j) => j !== i))}
                  style={st.remove}><Text style={{ color: colors.muted, fontSize: 18 }}>✕</Text></Pressable>
              ) : null}
            </View>
          ))}
          {options.length < 8 ? (
            <Pressable accessibilityRole="button" onPress={() => setOptions((all) => [...all, ''])} style={({ pressed }) => [st.add, pressTransition, pressed && { opacity: 0.7 }]}>
              <T weight="semibold" color={colors.accentSoft}>＋ Ajouter un choix</T>
            </Pressable>
          ) : null}
        </View>
      ) : null}

      <T size={13} weight="bold" color={colors.muted} style={st.label}>QUI JOUE</T>
      {fixedEvent ? (
        <View style={st.fixed}><T weight="semibold">📅 Les participants de « {data?.event?.title ?? 'l’événement'} »</T></View>
      ) : (
        <View style={{ gap: 8 }}>
          {data?.groups.length ? (
            <View style={st.groups}>
              {data.groups.map((g) => {
                const on = group === g.id;
                return (
                  <Pressable key={g.id} accessibilityRole="radio" accessibilityState={{ selected: on }} aria-checked={on} onPress={() => setGroup(on ? null : g.id)}
                    style={({ pressed }) => [st.group, on && st.on, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
                    <GroupTile group={g} size={30} />
                    <T size={14} weight="semibold" numberOfLines={1} style={{ maxWidth: 150 }}>{groupName(g)}</T>
                  </Pressable>
                );
              })}
            </View>
          ) : <T size={13} muted>Tu n’as pas encore de groupe : invite des personnes ou crée un lien.</T>}
          <Pressable accessibilityRole="button" onPress={() => setShowPeople(!showPeople)} style={st.fixed}>
            <T weight="semibold">👤 Des personnes{people.size ? ` · ${people.size}` : ''}</T>
            <T size={13} muted>Croisées à un événement ou dans tes groupes</T>
          </Pressable>
          {showPeople ? (
            <View style={st.groups}>
              {(data?.people ?? []).map((f) => {
                const on = people.has(f.id);
                return (
                  <Pressable key={f.id} accessibilityRole="checkbox" accessibilityState={{ checked: on }} aria-checked={on}
                    onPress={() => setPeople((s) => { const n = new Set(s); if (on) n.delete(f.id); else n.add(f.id); return n; })}
                    style={({ pressed }) => [st.group, on && st.on, pressTransition, pressed && { transform: [{ scale: 0.96 }] }]}>
                    <Avatar id={f.id} name={f.name} photo={f.avatar_url} size={26} profile={false} />
                    <T size={14} numberOfLines={1} style={{ maxWidth: 130 }}>{f.name}</T>
                  </Pressable>
                );
              })}
              {!data?.people.length ? <T size={13} muted>Personne pour l’instant.</T> : null}
            </View>
          ) : null}
          <ToggleRow label="🔗 Un lien à partager" hint="Qui l’ouvre se connecte à Party, puis joue." value={link} onChange={setLink} />
        </View>
      )}
      {groupRow ? <T size={13} muted>Tout le groupe « {groupName(groupRow)} » sera prévenu.</T> : null}

      <T size={13} weight="bold" color={colors.muted} style={st.label}>RÉGLAGES</T>
      <DateTimeField label="Fin des pronos" value={end} onChangeText={setEnd} hint="Plus personne ne joue après." />
      {kind !== 'text' ? (
        <View style={{ gap: 6 }}>
          <T weight="semibold">Dévoiler les réponses</T>
          <Segmented options={[{ key: 'close', label: 'À la fin' }, { key: 'result', label: 'Avec le résultat' }]} value={reveal} onChange={(v) => setReveal(v as Reveal)} />
          <T size={12} muted>Avant : chacun voit seulement qui a joué, jamais quoi (toi compris).</T>
        </View>
      ) : <T size={12} muted>Réponse libre : les réponses se dévoilent à la fin, puis tu coches les bonnes.</T>}
      <View style={st.points}>
        <T weight="semibold" style={{ flex: 1 }}>Points pour une bonne réponse</T>
        <Pressable accessibilityRole="button" accessibilityLabel="Un point de moins" disabled={points <= 1} onPress={() => setPoints(points - 1)} style={st.step}><Text style={st.stepText}>−</Text></Pressable>
        <Text style={st.pts} accessibilityLabel={pointsLabel(points)}>{points}</Text>
        <Pressable accessibilityRole="button" accessibilityLabel="Un point de plus" disabled={points >= 10} onPress={() => setPoints(points + 1)} style={st.step}><Text style={st.stepText}>＋</Text></Pressable>
      </View>
      <HonourNote points={points} />
      <ErrorText error={err} />
      <Button label={group || fixedEvent || people.size ? `Publier et prévenir${people.size && !group ? ` ${plural(people.size, 'personne')}` : ''}` : 'Publier'}
        disabled={!ready} loading={busy} onPress={() => void create()} />
      {terms.sheet}
    </Screen>
  );
}

const st = StyleSheet.create({
  opt: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  num: { width: 22, color: colors.muted, textAlign: 'center', ...font.bold },
  remove: { width: 36, height: 36, alignItems: 'center', justifyContent: 'center' },
  add: { height: 44, borderRadius: 12, borderWidth: 1.5, borderStyle: 'dashed', borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  label: { letterSpacing: 0.8, marginTop: 6 },
  fixed: { padding: 12, borderRadius: 14, backgroundColor: colors.surface, gap: 2 },
  groups: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  group: { flexDirection: 'row', alignItems: 'center', gap: 8, paddingVertical: 6, paddingHorizontal: 10, borderRadius: radius.pill,
    backgroundColor: colors.surface, borderWidth: 2, borderColor: 'transparent' },
  on: { borderColor: colors.accent, backgroundColor: colors.accentDim },
  points: { flexDirection: 'row', alignItems: 'center', gap: 10, padding: 12, borderRadius: 14, backgroundColor: colors.surface },
  step: { width: 38, height: 38, borderRadius: 19, backgroundColor: colors.fill, alignItems: 'center', justifyContent: 'center' },
  stepText: { color: colors.text, fontSize: 20, ...font.bold },
  pts: { minWidth: 28, textAlign: 'center', color: '#FFE27A', fontSize: 22, ...font.display },
});
