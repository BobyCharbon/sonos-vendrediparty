import { Stack, useLocalSearchParams } from 'expo-router';
import { useEffect, useState } from 'react';
import { Platform, Share, Text, View } from 'react-native';

import { goBack, TopBar } from '@/components/agenda/Bits';
import { Header } from '@/components/pronos/play/Header';
import { Organizer, ResultPicker } from '@/components/pronos/play/Organizer';
import { Answers, Finished, Play, Waiting } from '@/components/pronos/play/Play';
import { Reactions } from '@/components/pronos/play/Reactions';
import { PronoReportSheet, type ReportWhat } from '@/components/pronos/play/Report';
import { C, withPatates, type PronoV2 } from '@/components/pronos/play/model';
import { useTermsGate } from '@/components/TermsSheet';
import { Button, ErrorText, Loading, Screen, T } from '@/components/ui';
import { useQuery, useSignal } from '@/lib/data';
import { formatShort } from '@/lib/format';
import { errorText, isTerms, nativePronos, rpc, type Prono } from '@/lib/pronos';

/**
 * Un prono, Pronos v2 (maquettes 3-* du 18.11) : en-tête avec couverture, réponse par type, patates à planter (si le
 * prono en a et que la base les allume), « Sceller ma réponse », état scellé, réactions, organisation repliée,
 * contestation ; une fois le résultat donné, le dévoilement (une fois par personne) puis le résultat.
 * La base garde les réponses cachées (organisateur compris) et décide de tout. Dans l'app iPhone, l'écran natif prend le relais.
 */
export default function PronoScreen() {
  const { id, pick } = useLocalSearchParams<{ id: string; pick?: string }>();
  const native = nativePronos();
  useEffect(() => {
    if (native && id) { native.open(id); goBack('/'); }
  }, [native, id]);
  const { data, error, loading, reload } = useQuery(() => rpc<Prono>('prono_get', { id }), [id]);
  useSignal(id ? [`prono:${id}`] : [], reload);
  // La réponse d'une action remplace l'affichage jusqu'à la relecture suivante (temps réel, retour) : la plus récente gagne.
  const [acted, setP] = useState<{ prono: Prono; base: Prono | null | undefined } | null>(null);
  const raw = acted && acted.base === data ? acted.prono : (data ?? acted?.prono ?? null);
  const terms = useTermsGate('Avant de jouer');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [report, setReport] = useState<ReportWhat | null>(null);

  /** Appelle la base ; renvoie l'erreur en français (null si c'est passé). CGU d'abord quand la base les exige. */
  async function call(fn: string, args: Record<string, unknown>): Promise<string | null> {
    setBusy(true);
    try {
      setP({ prono: await rpc<Prono>(fn, args), base: data });
      return null;
    } catch (e) {
      if (isTerms(e) && (await terms.ensure())) return call(fn, args);
      return errorText(e);
    } finally {
      setBusy(false);
    }
  }
  async function act(fn: string, args: Record<string, unknown>): Promise<boolean> {
    setErr(null);
    const e = await call(fn, args);
    setErr(e);
    return !e;
  }

  if (loading && !raw) return <Loading />;
  if (!raw) {
    return (
      <Screen contentStyle={{ gap: 12 }}>
        <Stack.Screen options={{ headerShown: false }} />
        <TopBar back="Pronos" fallback="/pronos" title="Prono introuvable" />
        <T muted>Ce prono n’existe plus, ou il ne t’est pas ouvert.</T>
        <ErrorText error={error ?? null} />
      </Screen>
    );
  }
  const p = raw as unknown as PronoV2;
  const url = p.link?.path && typeof location !== 'undefined' ? `${location.origin}${p.link.path}` : null;
  async function share() {
    if (!url) return;
    if (Platform.OS === 'web' && typeof navigator !== 'undefined' && 'share' in navigator) {
      await (navigator as Navigator).share({ title: 'Un prono pour toi', text: p.question, url }).catch(() => undefined);
    } else await Share.share({ message: `${p.question} ${url}` }).catch(() => undefined);
  }
  const back = () => goBack(p.group ? `/group/${p.group.id}/pronos` : '/pronos');

  return (
    <Screen contentStyle={{ gap: 24, paddingBottom: 48 }}>
      <Stack.Screen options={{ headerShown: false, title: p.question }} />
      <Header p={p} compact={!!p.my_answer || p.state !== 'open'} onBack={back} onShare={url ? () => void share() : undefined}
        onMore={p.mine ? undefined : () => setReport({ label: 'ce prono' })} />
      {p.state === 'open' ? <Play key={p.id} p={p} pick={pick} busy={busy} act={act} /> : null}
      {p.state === 'closed' && p.mine && p.can_result ? <ResultPicker p={p} busy={busy} onResult={(body) => act('prono_result', { id: p.id, body })} /> : null}
      {p.state === 'closed' && !(p.mine && p.can_result && p.kind !== 'majority' && p.kind !== 'award' && p.kind !== 'when') ? <Waiting p={p} /> : null}
      {p.state === 'done' ? <Finished p={p} busy={busy} act={act} call={call} /> : null}
      {p.state === 'cancelled' ? (
        <T muted>Ce prono a été annulé : {withPatates(p) ? 'toutes les patates sont rendues, ' : ''}aucun point n’est compté.</T>
      ) : null}
      <ErrorText error={err} />
      {p.revealed && p.state === 'closed' && p.answers ? <Answers p={p} onReport={(author) => setReport({ label: 'cette réponse', author })} /> : null}
      {p.state !== 'cancelled' ? (
        <Reactions list={p.reactions} busy={busy} waiting={p.state === 'open'} patates={withPatates(p)}
          onReact={(emoji) => void act('prono_react', { id: p.id, emoji })} />
      ) : null}
      {p.mine ? <Organizer p={p} busy={busy} act={act} /> : (
        <Button small variant="ghost" label="Signaler ce prono" onPress={() => setReport({ label: 'ce prono' })} />
      )}
      <View style={{ alignItems: 'center' }}>
        <Text style={{ color: C.t3, fontSize: 12 }}>Proposé par {p.creator.me ? 'toi' : p.creator.name} · {formatShort(p.created_at)}</Text>
      </View>
      <PronoReportSheet prono={p.id} what={report} patates={withPatates(p)} onClose={() => setReport(null)} />
      {terms.sheet}
    </Screen>
  );
}
