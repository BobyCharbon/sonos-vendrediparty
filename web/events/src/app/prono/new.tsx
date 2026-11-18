import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';

import { goBack } from '@/components/agenda/Bits';
import { AWARDS, createBody, draftFrom, endChoices, patatesPossible, type Award, type Draft, type Template, type Who } from '@/components/pronos/create/model';
import type { Place } from '@/components/pronos/create/PreviewCard';
import { StepLaunched } from '@/components/pronos/create/StepLaunched';
import { StepQuestion } from '@/components/pronos/create/StepQuestion';
import { StepSettings, type Bag } from '@/components/pronos/create/StepSettings';
import { StepTemplate } from '@/components/pronos/create/StepTemplate';
import { useTermsGate } from '@/components/TermsSheet';
import { Loading } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { parseLocalDateTime, plural } from '@/lib/format';
import { fetchMyGroups, groupName } from '@/lib/groups';
import { errorText, isTerms, nativePronos, rpc, type Face } from '@/lib/pronos';
import { supabase } from '@/lib/supabase';

/**
 * « Nouveau prono » en 4 étapes (Pronos v2, maquettes 2-1 à 2-4 du 18.11) : 1 un modèle (prono_templates) ou « Partir
 * de zéro » ; 2 la question avec l'aperçu en direct de la carte ; 3 qui joue, la fin, les patates (seulement dans un
 * groupe ou une soirée, si la base les a allumées), les points, le dévoilement ; 4 « C'est lancé ! ». Ouvert depuis un
 * groupe (?group=) ou un événement (?event=) : il est déjà choisi. Dans l'app iPhone, l'écran natif prend la main.
 */
export default function NewProno() {
  const params = useLocalSearchParams<{ group?: string; event?: string }>();
  const fixedGroup = typeof params.group === 'string' ? params.group : null;
  const fixedEvent = typeof params.event === 'string' ? params.event : null;
  const listPath = fixedGroup ? `/group/${fixedGroup}/pronos` : fixedEvent ? `/event/${fixedEvent}` : '/pronos';
  const native = nativePronos();
  useEffect(() => {
    if (native?.create) { native.create({ group: fixedGroup ?? undefined, event: fixedEvent ?? undefined }); goBack(fixedGroup ? `/group/${fixedGroup}` : fixedEvent ? `/event/${fixedEvent}` : '/'); }
  }, [native, fixedGroup, fixedEvent]);
  const terms = useTermsGate('Avant de lancer un prono');
  const { data, loading } = useQuery(async () => {
    const [groups, people, event, templates] = await Promise.all([
      fetchMyGroups(),
      rpc<Face[]>('prono_suggestions').catch((): Face[] => []),
      fixedEvent ? supabase.from('events').select('id, title').eq('id', fixedEvent).maybeSingle().then((r) => r.data as { id: string; title: string } | null)
        : Promise.resolve(null),
      // Base d'avant Pronos v2 : pas de modèles, il reste « Partir de zéro ».
      rpc<Template[] | null>('prono_templates').catch((): Template[] => []),
    ]);
    return { groups: groups.filter((g) => !g.system && g.member), people, event, templates: templates ?? [] };
  }, [fixedEvent]);

  const [step, setStep] = useState<1 | 2 | 3 | 4>(1);
  const [draft, setDraft] = useState<Draft>(() => draftFrom(null));
  const [who, setWho] = useState<Who>({ group: fixedGroup, event: fixedEvent, people: [], link: false });
  const [end, setEnd] = useState(() => endChoices()[1].local);
  const [patates, setPatates] = useState(true);
  const [points, setPoints] = useState(3);
  const [reveal, setReveal] = useState<'close' | 'result'>('close');
  const [bag, setBag] = useState<Bag | undefined>(undefined);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [created, setCreated] = useState<{ id: string; linkPath: string | null; closesAt: string; patates: boolean } | null>(null);

  // Le sac du terrain choisi dit si les patates sont allumées (null : éteintes, ou ni groupe ni soirée).
  useEffect(() => {
    if (!who.group && !who.event) return;
    let live = true;
    rpc<Bag>('prono_bag', { group_id: who.group, event_id: who.group ? null : who.event })
      .then((b) => { if (live) setBag(b ?? null); }).catch(() => { if (live) setBag(null); });
    return () => { live = false; };
  }, [who.group, who.event]);
  const terrainBag = who.group || who.event ? bag : null;

  const awards: Award[] = useMemo(() => data?.templates.find((t) => t.awards?.length)?.awards ?? AWARDS, [data]);
  const group = data?.groups.find((g) => g.id === who.group) ?? null;
  const event = data?.event ?? null;
  const place: Place = group
    ? { group: { id: group.id, name: groupName(group), emoji: group.emoji, color: group.color, photo: group.photo }, event: null,
      label: groupName(group), emoji: group.emoji, faces: group.faces, members: group.members }
    : event ? { group: null, event, label: event.title, emoji: '📅', faces: [], members: 0 }
      : { group: null, event: null, label: 'Invités', emoji: '👥', faces: [], members: 0 };

  async function launch(): Promise<void> {
    const iso = parseLocalDateTime(end);
    if (!iso) return;
    setBusy(true);
    setErr(null);
    try {
      const body = createBody(draft, { who, end, patates: patates && !!terrainBag && patatesPossible(draft.kind), points, reveal }, iso);
      const p = await rpc<{ id: string; link?: { path: string | null } | null }>('prono_create', { body });
      setCreated({ id: p.id, linkPath: p.link?.path ?? null, closesAt: iso, patates: body.patates === true });
      setStep(4);
    } catch (e) {
      if (isTerms(e) && (await terms.ensure())) return launch();
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  if (loading && !data) return <Loading />;
  const told = group ? `Tout le groupe « ${groupName(group)} » est prévenu.`
    : event ? 'Les participants sont prévenus.'
      : who.people.length ? `${plural(who.people.length, 'personne')} ${who.people.length > 1 ? 'sont prévenues' : 'est prévenue'}.`
        : 'Partage le lien : qui l’ouvre peut jouer.';
  return (
    <>
      <Stack.Screen options={{ headerShown: false, title: 'Nouveau prono' }} />
      {step === 1 ? (
        <StepTemplate templates={data?.templates ?? null} onClose={() => goBack(listPath)}
          onPick={(t) => { setDraft(draftFrom(t)); setStep(2); }} onScratch={(k) => { setDraft(draftFrom(null, k)); setStep(2); }} />
      ) : step === 2 ? (
        <StepQuestion d={draft} setD={setDraft} awards={awards} place={place} onBack={() => setStep(1)} onNext={() => setStep(3)} />
      ) : step === 3 || !created ? (
        <StepSettings d={draft} awards={awards} groups={data?.groups ?? []} event={event} people={data?.people ?? []}
          who={who} setWho={setWho} end={end} setEnd={setEnd} bag={terrainBag} patates={patates} setPatates={setPatates}
          points={points} setPoints={setPoints} reveal={reveal} setReveal={setReveal} busy={busy} err={err}
          onBack={() => setStep(2)} onLaunch={() => void launch()} />
      ) : (
        <StepLaunched id={created.id} linkPath={created.linkPath} d={draft} awards={awards} place={place} closesAt={created.closesAt}
          patates={created.patates} told={told} listPath={listPath}
          chat={who.group ? `/chats/${who.group}` : who.event ? `/event/${who.event}/chat` : null} />
      )}
      {terms.sheet}
    </>
  );
}
