import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Image, View } from 'react-native';

import { Avatar, Badge, Button, Card, Chip, Empty, ErrorText, Field, Input, Loading, Screen, Section, Segmented, T, ToggleRow } from '@/components/ui';
import { useAuth } from '@/lib/auth';
import { signedPhotos } from '@/lib/chats';
import { useQuery } from '@/lib/data';
import { dbMessage, moderationInfo, REPORT_REASONS, type PublicInfo } from '@/lib/moderation';
import { roleRank } from '@/lib/roles';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

type Status = 'open' | 'actioned' | 'dismissed' | 'all';
type Action = 'hide' | 'warn' | 'suspend' | 'ban' | 'dismiss';
type Report = {
  id: string; kind: string; target_id: string; reason: string; comment: string | null; status: Exclude<Status, 'all'>;
  resolution: string | null; note: string | null; created_at: string; handled_at: string | null; handled_by: string | null;
  snapshot: { text?: string; photo_path?: string | null; place?: string; at?: string };
  reporter: { id: string | null; name: string | null };
  target_user: { id: string; name: string; avatar_url: string | null; status: string } | null;
  same_target: number; user_reports: number;
  sanctions: { kind: string; ends_at: string | null; lifted_at: string | null; at: string }[];
};

const KIND_LABELS: Record<string, string> = {
  group_message: 'Message de groupe', direct_message: 'Message direct', event_message: 'Discussion d’événement',
  profile: 'Profil', profile_photo: 'Photo de profil', pet_name: 'Nom du Zicou', pet_item: 'Objet de Zicou',
  pet_offer: 'Offre d’échange', pet_showcase: 'Vitrine', pet_word: 'Mot de Zicou',
};
const RESOLUTIONS: Record<string, string> = {
  hide: 'Contenu masqué', warn: 'Averti', suspend: 'Suspendu', ban: 'Banni', dismiss: 'Classé sans suite',
};
const DAYS = [1, 7, 30];
const reasonLabel = (key: string) => REPORT_REASONS.find((r) => r.key === key)?.label ?? key;
const when = (iso: string) => new Date(iso).toLocaleString('fr-CH', { dateStyle: 'short', timeStyle: 'short' });

/** Réglages › Administration › Signalements (droit « Modérer les signalements ») : la file, le contenu signalé (copie
 * prise au moment du signalement), et les actions ; chaque action est notée dans le Journal. Suspendre et bannir
 * visent le COMPTE (jamais une adresse IP) et demandent aussi le droit « Bannir ou réintégrer un compte ». */
export default function ReportsScreen() {
  const { can, rank } = useAuth();
  const [status, setStatus] = useState<Status>('open');
  const { data, loading, error, reload } = useQuery(async () => {
    const { data, error } = await supabase.rpc('moderation_queue', { p_status: status, p_limit: 150 });
    if (error) throw new Error(dbMessage(error.message, 'Les signalements n’ont pas pu être lus.'));
    return (data as Report[] | null) ?? [];
  }, [status]);
  const [photos, setPhotos] = useState<Map<string, string>>(new Map());
  useEffect(() => {
    const paths = (data ?? []).filter((r) => r.kind !== 'profile_photo').map((r) => r.snapshot.photo_path).filter((p): p is string => !!p);
    void signedPhotos(paths).then(setPhotos).catch(() => {});
  }, [data]);

  if (!can('moderation.reports')) {
    return <Screen><Empty>Réservé aux modérateurs (droit « Modérer les signalements »).</Empty></Screen>;
  }
  return (
    <Screen edges={[]}>
      <Segmented<Status> value={status} onChange={setStatus} options={[
        { key: 'open', label: 'À traiter' }, { key: 'actioned', label: 'Traités' }, { key: 'dismissed', label: 'Classés' }, { key: 'all', label: 'Tous' },
      ]} />
      {loading && !data ? <Loading /> : null}
      <ErrorText error={error} />
      {data && !data.length ? <Empty>{status === 'open' ? 'Aucun signalement à traiter. 🎉' : 'Rien ici.'}</Empty> : null}
      {(data ?? []).map((r) => (
        <ReportCard key={r.id} report={r} photo={r.snapshot.photo_path ? photos.get(r.snapshot.photo_path) ?? null : null}
          canBan={can('members.ban')} onDone={reload} />
      ))}
      <Button variant="ghost" label="Journal des actions" onPress={() => router.push('/admin/journal')} />
      {rank >= roleRank('admin') ? <ModerationSettings /> : null}
    </Screen>
  );
}

function ReportCard({ report: r, photo, canBan, onDone }: { report: Report; photo: string | null; canBan: boolean; onDone: () => void }) {
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [days, setDays] = useState(DAYS[1]);
  const user = r.target_user;
  const banned = user?.status === 'banned';

  async function act(action: Action) {
    setBusy(action);
    setError(null);
    const { data, error } = await supabase.rpc('moderation_act', {
      p_report: r.id, p_action: action, p_note: note.trim() || null, p_days: action === 'suspend' ? days : null,
    });
    if (!error && (data as { remove_photo?: string } | null)?.remove_photo) {
      const removed = await supabase.storage.from('profile-photos').remove([(data as { remove_photo: string }).remove_photo]);
      if (removed.error) setError('La photo n’a pas pu être retirée. Réessaie.');
    }
    setBusy(null);
    if (error) return setError(dbMessage(error.message, 'L’action n’a pas été enregistrée.'));
    onDone();
  }

  async function lift() {
    if (!user) return;
    setBusy('lift');
    const { error } = await supabase.rpc('moderation_lift', { p_user: user.id });
    setBusy(null);
    if (error) return setError(dbMessage(error.message, 'Le compte n’a pas pu être réintégré.'));
    onDone();
  }

  return (
    <Card style={{ gap: 10 }}>
      <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
        <Badge label={reasonLabel(r.reason)} fg={colors.text} bg={colors.coralDim} />
        <T muted size={12}>{KIND_LABELS[r.kind] ?? r.kind}{r.snapshot.place ? ` · ${r.snapshot.place}` : ''} · {when(r.created_at)}</T>
      </View>
      {user ? (
        <View style={{ flexDirection: 'row', gap: 10, alignItems: 'center' }}>
          <Avatar id={user.id} name={user.name} photo={user.avatar_url} size={36} />
          <View style={{ flex: 1 }}>
            <T weight="semibold">{user.name}{banned ? ' · accès retiré' : ''}</T>
            <T muted size={12}>{r.user_reports} signalement(s) sur ce compte{r.same_target > 1 ? ` · ${r.same_target} sur ce contenu` : ''}</T>
          </View>
        </View>
      ) : <T muted size={12}>Compte supprimé</T>}
      <View style={{ padding: 10, borderRadius: 12, backgroundColor: colors.fill, gap: 6 }}>
        {r.kind === 'profile_photo' && r.snapshot.photo_path && user ? (
          <Avatar id={user.id} name={user.name} photo={r.snapshot.photo_path} size={120} profile={false} />
        ) : null}
        {photo ? <Image source={{ uri: photo }} style={{ width: 160, height: 160, borderRadius: 10 }} accessibilityLabel="Photo signalée" /> : null}
        <T>{r.snapshot.text || (r.kind === 'profile_photo' ? '' : '(sans texte)')}</T>
      </View>
      <T muted size={13}>Signalé par {r.reporter.name ?? 'un compte supprimé'}{r.comment ? ` : « ${r.comment} »` : ''}</T>
      {r.sanctions.length ? (
        <T muted size={12}>Sanctions : {r.sanctions.map((s) => `${RESOLUTIONS[s.kind] ?? s.kind} le ${when(s.at)}${s.ends_at && !s.lifted_at ? ` (jusqu’au ${when(s.ends_at)})` : ''}`).join(' · ')}</T>
      ) : null}
      {r.status !== 'open' ? (
        <T size={13} weight="semibold">{RESOLUTIONS[r.resolution ?? ''] ?? r.status}{r.handled_by ? ` par ${r.handled_by}` : ''}{r.handled_at ? ` · ${when(r.handled_at)}` : ''}{r.note ? ` · « ${r.note} »` : ''}</T>
      ) : (
        <>
          <Input accessibilityLabel="Note (envoyée avec l’avertissement)" placeholder="Note (envoyée avec l’avertissement, notée au journal)"
            value={note} onChangeText={setNote} maxLength={500} />
          <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8 }}>
            <Button small label="Masquer le contenu" loading={busy === 'hide'} onPress={() => void act('hide')} />
            <Button small variant="secondary" label="Avertir" loading={busy === 'warn'} disabled={!user} onPress={() => void act('warn')} />
            <Button small variant="ghost" label="Classer sans suite" loading={busy === 'dismiss'} onPress={() => void act('dismiss')} />
          </View>
          {canBan && user ? (
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 8, alignItems: 'center' }}>
              {DAYS.map((d) => <Chip key={d} label={`${d} j`} selected={days === d} onPress={() => setDays(d)} />)}
              <Button small variant="secondary" label={`Suspendre ${days} jour${days > 1 ? 's' : ''}`} loading={busy === 'suspend'} onPress={() => void act('suspend')} />
              <Button small variant="danger" label="Bannir le compte" loading={busy === 'ban'} onPress={() => void act('ban')} />
            </View>
          ) : null}
        </>
      )}
      {banned && canBan ? <Button small variant="secondary" label={`Réintégrer ${user?.name}`} loading={busy === 'lift'} onPress={() => void lift()} /> : null}
      <ErrorText error={error} />
    </Card>
  );
}

/** Admin : adresse de contact publiée (CGU, fiche de l'app) et exigence des CGU par la base. */
function ModerationSettings() {
  const [info, setInfo] = useState<PublicInfo | null>(null);
  const [email, setEmail] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  useEffect(() => {
    void moderationInfo().then((i) => { setInfo(i); setEmail(i?.contact_email ?? ''); });
  }, []);

  async function save(next: { contact_email?: string; terms_enforced?: boolean }) {
    setError(null);
    setSaved(false);
    const { data, error } = await supabase.rpc('set_moderation_settings', {
      p_contact_email: next.contact_email ?? null, p_terms_enforced: next.terms_enforced ?? null,
    });
    if (error) return setError(dbMessage(error.message, 'Le réglage n’a pas été enregistré (adresse e-mail valable ?).'));
    setInfo(data as PublicInfo);
    setSaved(true);
  }

  if (!info) return null;
  return (
    <Section title="Réglages de la modération">
      <Field label="Adresse de contact publiée" hint="Affichée dans les conditions d’utilisation (exigée par Apple et Google)"
        value={email} onChangeText={setEmail} keyboardType="email-address" autoCapitalize="none" />
      <Button small variant="secondary" label="Enregistrer l’adresse" onPress={() => void save({ contact_email: email.trim() || '' })} />
      <ToggleRow label="Exiger les conditions d’utilisation" value={info.terms_enforced}
        hint="La base refuse tout message ou nom tant que le compte ne les a pas acceptées. À activer une fois l’app iPhone à jour."
        onChange={(v) => void save({ terms_enforced: v })} />
      {saved ? <T muted size={12}>Enregistré.</T> : null}
      <ErrorText error={error} />
    </Section>
  );
}
