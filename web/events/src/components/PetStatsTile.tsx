import { View } from 'react-native';

import { Card, ErrorText, s, Section, T } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { must, supabase } from '@/lib/supabase';

/** Compagnon (lot 1 « revenir tous les jours ») : la mesure, lue dans private.pet_engagement par pet_admin_stats()
 *  (migration 20261104150000, réservée aux admins). */
type Cohort = { eligible: number; retained: number; pct: number | null };
type PetStats = {
  pets: number;
  alive: number;
  players: number;
  active_7d: number;
  active_today: number;
  active_days_per_7: number | null;
  opens_per_day: number | null;
  cohorts: Record<string, Cohort>;
  sources_7d: Record<string, number>;
  switches_off: Record<string, number>;
};

const SOURCES: Record<string, string> = { tab: 'onglet Jeux', notification: 'notification', widget: 'widget', link: 'lien' };
const SWITCHES: Record<string, string> = { pet_daily: 'rappel du jour', pet_alerts: 'alertes vitales', pet_gifts: 'cadeau d’un ami', pet_streaks: 'paliers de série', pet_bar: 'barre pleine' };

function cohortText(c: Cohort | undefined): string {
  if (!c || !c.eligible) return '—';
  return `${c.pct ?? 0} % (${c.retained}/${c.eligible})`;
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <View style={{ flex: 1, minWidth: 90 }}>
      <T weight="bold" size={20}>{value}</T>
      <T muted size={12}>{label}</T>
    </View>
  );
}

export function PetStatsTile() {
  const { data, error } = useQuery(async () => must(await supabase.rpc('pet_admin_stats')) as unknown as PetStats, []);
  const sources = Object.entries(data?.sources_7d ?? {}).map(([k, n]) => `${SOURCES[k] ?? k} ${n}`).join(' · ');
  const off = Object.entries(data?.switches_off ?? {}).filter(([, n]) => n > 0).map(([k, n]) => `${SWITCHES[k] ?? k} ${n}`).join(' · ');
  return (
    <Section title="Zicou">
      <ErrorText error={error} />
      {data ? (
        <Card style={{ gap: 12 }}>
          <View style={[s.row, { flexWrap: 'wrap' }]}>
            <Stat label="aujourd’hui" value={String(data.active_today)} />
            <Stat label="actifs sur 7 j" value={String(data.active_7d)} />
            <Stat label="jours actifs / 7" value={data.active_days_per_7 != null ? String(data.active_days_per_7) : '—'} />
            <Stat label="ouvertures / jour" value={data.opens_per_day != null ? String(data.opens_per_day) : '—'} />
          </View>
          <T size={14}>Retour J1 {cohortText(data.cohorts['1'])} · J7 {cohortText(data.cohorts['7'])} · J30 {cohortText(data.cohorts['30'])}</T>
          <T muted size={13}>{data.alive} Zicou en vie sur {data.pets} · {data.players} joueur(s) mesuré(s)</T>
          <T muted size={13}>Ouvertures sur 7 j : {sources || 'aucune'}</T>
          <T muted size={13}>Interrupteurs coupés : {off || 'aucun'}</T>
        </Card>
      ) : null}
    </Section>
  );
}
