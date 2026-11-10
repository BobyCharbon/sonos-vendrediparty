import { router } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { barCreate, barOverview, errorText, fetchEventPeople, phaseLine, PHASE_LABEL, useBarRefresh, type BarOverview } from '@/lib/bar';
import { useQuery } from '@/lib/data';
import { colors } from '@/lib/theme';

import { Badge, Button, Empty, ErrorText, Loading, Screen, Segmented, T, Toast } from '../ui';
import { BarHeader } from './BarHeader';
import { ItemsTab } from './ItemsTab';
import { LiveTab } from './LiveTab';
import { RefundTab } from './RefundTab';
import { StaffTab } from './StaffTab';

type Tab = 'items' | 'refund' | 'staff' | 'live';
const TABS: { key: Tab; label: string }[] = [
  { key: 'items', label: 'Articles' }, { key: 'refund', label: 'Rembourser' }, { key: 'staff', label: 'Barmans' }, { key: 'live', label: 'Direct' },
];

const back = (eventId: string) => (router.canGoBack() ? router.back() : router.replace(`/event/${eventId}`));

/** Pas encore de bar (lien direct) : le créer ici. */
function NoBar({ eventId, onCreated }: { eventId: string; onCreated: (o: BarOverview) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <>
      <Empty>Pas encore de bar pour cet événement.</Empty>
      <Button label="🍹 Créer le bar de la soirée" loading={busy} onPress={async () => {
        setBusy(true);
        setError(null);
        try { onCreated(await barCreate(eventId)); } catch (e) { setError(errorText(e, 'Le bar n’a pas pu être créé. Réessaie.')); } finally { setBusy(false); }
      }} />
      <ErrorText error={error} />
    </>
  );
}

/**
 * Gérer le bar (organisateur, co-organisateurs, admin) : 4 onglets — Articles · Rembourser · Barmans · Direct.
 * Relu toutes les 10 s et après chaque geste ; la base refuse tout le reste (« réservé aux organisateurs »).
 */
export function BarManage({ eventId }: { eventId: string }) {
  const { data: overview, error, loading, reload, setData } = useQuery(() => barOverview(eventId), [eventId]);
  useBarRefresh(reload, !!overview);
  const { data: people } = useQuery(() => fetchEventPeople(eventId), [eventId]);
  const [tab, setTab] = useState<Tab>('items');
  const [toast, setToast] = useState<string | null>(null);

  if (loading) return <Loading />;
  const header = <BarHeader title="Bar de la soirée" eventId={eventId} />;
  if (!overview) {  // une relecture ratée garde l'écran (et le brouillon d'article) déjà affiché
    return (
      <Screen edges={[]}>
        {header}
        {error ? <ErrorText error={error} /> : <NoBar eventId={eventId} onCreated={setData} />}
        <Button variant="ghost" label="Retour à l’événement" onPress={() => back(eventId)} />
      </Screen>
    );
  }

  const props = { eventId, overview, onOverview: setData };
  return (
    <>
    <Screen edges={[]}>
      {header}
      <View style={st.top}>
        <Badge label={PHASE_LABEL[overview.phase]} fg={overview.phase === 'open' ? colors.onMint : colors.textSoft}
          bg={overview.phase === 'open' ? colors.mint : colors.surface2} />
        <T muted size={13} style={{ flex: 1 }}>{phaseLine(overview)}</T>
      </View>
      <Segmented options={TABS} value={tab} onChange={setTab} />
      {tab === 'items' ? <ItemsTab {...props} reload={() => void reload()} /> : null}
      {tab === 'refund' ? <RefundTab key={`${overview.pay_method}|${overview.payee_id}|${overview.repay_by}`} {...props} people={people}
        onSaved={() => setToast('Conditions enregistrées : les invités qui ont commandé sont prévenus.')} /> : null}
      {tab === 'staff' ? <StaffTab {...props} people={people} /> : null}
      {tab === 'live' ? <LiveTab {...props} /> : null}
    </Screen>
    {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
    </>
  );
}

const st = StyleSheet.create({
  top: { flexDirection: 'row', alignItems: 'center', gap: 10, flexWrap: 'wrap' },
});
