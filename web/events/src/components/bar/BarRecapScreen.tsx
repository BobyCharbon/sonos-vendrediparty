import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { amount, barRecap, errorText, type BarRecap, type RecapLine } from '@/lib/bar';
import { money, recapFilename, recapPdf } from '@/lib/barRecapPdf';
import { useQuery } from '@/lib/data';
import { formatShort, plural } from '@/lib/format';
import { savePdf } from '@/lib/pdf';
import { colors, font, radius } from '@/lib/theme';

import { Button, Empty, ErrorText, Loading, Screen, Section, T, Toast } from '../ui';
import { BarHeader } from './BarHeader';

const label = (i: RecapLine) => `${i.emoji ? `${i.emoji} ` : ''}${i.name}${i.detail ? ` (${i.detail})` : ''}`;

function Stat({ value, label: text, color = colors.text }: { value: string; label: string; color?: string }) {
  return (
    <View style={st.stat}>
      <Text style={[st.big, { color }]}>{value}</Text>
      <T muted size={12} style={st.center}>{text}</T>
    </View>
  );
}

function Recap({ r }: { r: BarRecap }) {
  const cur = (n: number) => money(n, r.currency);
  const unit = r.currency === 'EUR' ? '€' : 'CHF';
  const free = r.free_bar;
  return (
    <>
      <View style={st.stats}>
        <Stat value={String(r.totals.served)} label={free ? 'servis (offerts)' : 'servis'} />
        {free ? <Stat value={String(r.totals.people)} label="personnes" /> : (
          <>
            <Stat value={amount(r.totals.amount)} label={`${unit} au total`} />
            <Stat value={amount(r.totals.due)} label={`${unit} à recevoir`} color={colors.coral} />
          </>
        )}
      </View>
      {!free && r.totals.refunded > 0 ? <T size={13} color={colors.mint}>Déjà remboursé : {cur(r.totals.refunded)}</T> : null}
      {r.totals.pending > 0 ? (
        <T size={13} color={colors.coral}>{plural(r.totals.pending, 'article')} encore en attente : pas servis, pas comptés.</T>
      ) : null}

      <Section title={`Par personne (${r.people.length})`}>
        {r.people.length === 0 ? <T muted size={14}>Personne n’a rien pris.</T> : null}
        {r.people.map((p) => (
          <View key={p.id} style={st.person} accessibilityLabel={`${p.name} : ${plural(p.served, 'article')}${free ? '' : `, ${cur(p.amount)}`}`}>
            <View style={st.rowBetween}>
              <T size={16} weight="bold" style={{ flex: 1 }}>{p.name}</T>
              <T size={16} weight="bold">{free ? plural(p.served, 'article') : cur(p.amount)}</T>
            </View>
            {p.items.map((i) => (
              <View key={i.name} style={st.rowBetween}>
                <T size={14} style={{ flex: 1 }}><Text style={st.qty}>{i.qty} × </Text>{label(i)}</T>
                {free ? null : <T muted size={14}>{cur(i.amount)}</T>}
              </View>
            ))}
            {free ? null : (
              <T size={12} color={p.balance > 0 ? colors.coral : colors.mint}>
                {[p.refunded > 0 ? `Remboursé ${cur(p.refunded)}` : null,
                  p.balance > 0 ? `reste dû ${cur(p.balance)}` : p.balance < 0 ? `à lui rendre ${cur(-p.balance)}` : 'tout est réglé',
                  p.pending ? `${p.pending} en attente` : null].filter(Boolean).join(' · ')}
              </T>
            )}
          </View>
        ))}
      </Section>

      <Section title="Par article">
        {r.items.length === 0 ? <T muted size={14}>Aucun article servi.</T> : null}
        {r.items.map((i) => (
          <View key={i.name} style={st.rowBetween}>
            <T size={14} style={{ flex: 1 }}>{label(i)}</T>
            <T size={14} weight="semibold" style={st.num}>{i.qty}</T>
            {free ? null : <T muted size={14} style={st.amount}>{cur(i.amount)}</T>}
          </View>
        ))}
      </Section>

      {r.staff.length ? (
        <Section title="Barmans">
          {r.staff.map((s) => (
            <View key={s.name} style={st.rowBetween}>
              <T size={14} style={{ flex: 1 }}>{s.name}</T>
              <T muted size={14}>{s.served} servi{s.served > 1 ? 's' : ''}</T>
            </View>
          ))}
        </Section>
      ) : null}
    </>
  );
}

/**
 * Récapitulatif de la soirée (organisateurs ; demande de l'admin du 16.11) : qui a pris quoi, combien, remboursé, reste dû ;
 * par article ; par barman. « Exporter en PDF » : le même récapitulatif en A4 (partagé sur téléphone, téléchargé sinon).
 */
export function BarRecapScreen({ eventId }: { eventId: string }) {
  const { data: recap, error, loading } = useQuery(() => barRecap(eventId), [eventId]);
  const [busy, setBusy] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  async function exportPdf(r: BarRecap) {
    setBusy(true);
    setExportError(null);
    try {
      const done = await savePdf(recapPdf(r), recapFilename(r), `Récapitulatif du bar · ${r.title}`);
      if (done === 'downloaded') setToast('PDF téléchargé.');
    } catch (e) {
      setExportError(errorText(e, 'Le PDF n’a pas pu être créé. Réessaie.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <Screen edges={[]}>
        <BarHeader title="Récapitulatif du bar" eventId={eventId} />
        {loading ? <Loading /> : null}
        {!loading && error ? <ErrorText error={error} /> : null}
        {!loading && !error && !recap ? <Empty>Pas de bar pour cet événement.</Empty> : null}
        {recap ? (
          <>
            <View style={{ gap: 2 }}>
              <T size={18} weight="bold">{recap.title}</T>
              <T muted size={13}>
                {recap.starts_at ? formatShort(recap.starts_at) : 'Date à définir'} · {recap.closed_at ? 'bar fermé' : 'bar encore ouvert : les chiffres peuvent encore bouger'}
              </T>
            </View>
            <Button label="📄 Exporter en PDF" loading={busy} onPress={() => void exportPdf(recap)} />
            <ErrorText error={exportError} />
            <Recap r={recap} />
          </>
        ) : null}
      </Screen>
      {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
    </>
  );
}

const st = StyleSheet.create({
  stats: { flexDirection: 'row', gap: 8 },
  stat: { flex: 1, alignItems: 'center', gap: 2, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  big: { ...font.display, fontSize: 22, lineHeight: 26, fontVariant: ['tabular-nums'] },
  center: { textAlign: 'center' },
  person: { gap: 4, paddingVertical: 10, borderTopWidth: 1, borderTopColor: colors.line },
  rowBetween: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  qty: { color: colors.muted, fontVariant: ['tabular-nums'] },
  num: { width: 36, textAlign: 'right', fontVariant: ['tabular-nums'] },
  amount: { width: 84, textAlign: 'right', fontVariant: ['tabular-nums'] },
});
