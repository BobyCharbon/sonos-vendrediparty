import { useState } from 'react';
import { View } from 'react-native';

import { barSaveSettings, barSetCurrency, barUnit, errorText, optionsOf, type BarCurrency, type BarOptions, type BarOverview, type BarSettings } from '@/lib/bar';
import { colors } from '@/lib/theme';

import { Button, Chip, ErrorText, Field, s, Section, T, ToggleRow } from '../ui';

type Flag = Exclude<keyof BarOptions, 'limit_glasses' | 'limit_chf' | 'currency'>;
type Row = { key: Flag; label: string; hint: string };

const ORDERS: Row[] = [
  { key: 'guest_orders', label: 'Les invités commandent dans l’app',
    hint: 'Éteint : la carte se consulte dans l’app, on commande au comptoir en montrant son QR.' },
  { key: 'counter_serve', label: 'Service au comptoir sans commande',
    hint: 'Le barman scanne le QR et sert directement ce qu’on lui demande, sans commande préalable.' },
  { key: 'show_stock', label: 'Montrer aux invités combien il en reste',
    hint: 'Allumé : « Il en reste 3 » sur la carte. Éteint : seul « Épuisé » s’affiche.' },
];
const STAFF: Row[] = [
  { key: 'staff_adjust_stock', label: 'Ajuster les quantités', hint: '« Il en reste… » et « + Réassort » depuis l’écran de service.' },
  { key: 'staff_unavailable', label: 'Marquer un article indisponible', hint: 'L’article reste visible, grisé ; plus de nouvelle commande.' },
  { key: 'staff_correct', label: 'Annuler un service ou un verre en attente', hint: 'Annuler son service pendant 10 s, annuler un verre commandé.' },
  { key: 'staff_prices', label: 'Changer les prix', hint: 'Les verres déjà commandés gardent leur prix.' },
  { key: 'staff_items', label: 'Ajouter ou modifier des articles', hint: 'Nom, emoji, catégorie, stock, limites : comme l’organisateur.' },
];

const CURRENCIES: [BarCurrency, string][] = [['CHF', 'Francs (CHF)'], ['EUR', 'Euros (€)']];

const limitText = (n: number | null) => (n == null ? '' : String(n));

/** Limites par personne pour la soirée (servis + en attente) : verres et/ou CHF, vide = sans limite. */
function Limits({ options, busy, onSave }: { options: BarOptions; busy: boolean; onSave: (s: BarSettings) => void }) {
  const [glasses, setGlasses] = useState(limitText(options.limit_glasses));
  const [chf, setChf] = useState(limitText(options.limit_chf));
  const [error, setError] = useState<string | null>(null);
  const dirty = glasses !== limitText(options.limit_glasses) || chf !== limitText(options.limit_chf);

  function save() {
    const g = glasses.trim();
    const c = chf.trim().replace(',', '.');
    if (g && (!/^\d+$/.test(g) || Number(g) < 1 || Number(g) > 200)) return setError('Verres : de 1 à 200, ou vide pour sans limite.');
    if (c && (!/^\d+(\.\d{1,2})?$/.test(c) || Number(c) < 1 || Number(c) > 5000)) return setError(`${barUnit()} : de 1 à 5000, ou vide pour sans limite.`);
    setError(null);
    onSave({ limit_glasses: g ? Number(g) : null, limit_chf: c ? Number(c) : null });
  }

  return (
    <Section title="Limites par personne">
      <T muted size={13}>Pour toute la soirée : verres servis et en attente. Au-delà, la commande est refusée avec un message clair.</T>
      <View style={[s.row, { alignItems: 'flex-start' }]}>
        <View style={{ flex: 1 }}>
          <Field label="Verres au plus" value={glasses} onChangeText={setGlasses} inputMode="numeric" keyboardType="number-pad" placeholder="Sans limite" />
        </View>
        {options.free_bar ? null : (
          <View style={{ flex: 1 }}>
            <Field label={`${barUnit()} au plus`} value={chf} onChangeText={setChf} inputMode="decimal" keyboardType="decimal-pad" placeholder="Sans limite" />
          </View>
        )}
      </View>
      <ErrorText error={error} />
      {dirty ? <Button small variant="secondary" label="Enregistrer les limites" loading={busy} onPress={save} /> : null}
    </Section>
  );
}

/**
 * Onglet « Options » : comment le bar marche ce soir (commandes, comptoir, stock montré, bar offert), limites par
 * personne, ce que peuvent faire les barmans. Chaque interrupteur est enregistré tout de suite ; la base vérifie tout.
 */
export function OptionsTab({ eventId, overview, onOverview }: { eventId: string; overview: BarOverview; onOverview: (o: BarOverview) => void }) {
  const options = optionsOf(overview);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function save(key: string, settings: BarSettings, currency?: BarCurrency) {
    setBusy(key);
    setError(null);
    try {
      onOverview(await (currency ? barSetCurrency(eventId, currency) : barSaveSettings(eventId, settings)));
    } catch (e) {
      setError(errorText(e, 'L’option n’a pas pu être enregistrée. Réessaie.'));
    } finally {
      setBusy(null);
    }
  }

  function toggle(key: Flag, value: boolean) {
    // Sans commande dans l'app, le comptoir est la seule façon d'être servi : on l'allume avec.
    const extra: BarSettings = key === 'guest_orders' && !value ? { counter_serve: true } : {};
    void save(key, { [key]: value, ...extra });
  }

  const row = (r: Row, disabled = false, hint = r.hint) => (
    <ToggleRow key={r.key} label={r.label} hint={hint} value={options[r.key]} disabled={!!busy || disabled}
      onChange={(v) => toggle(r.key, v)} />
  );

  return (
    <>
      <Section title="Devise">
        <View style={[s.row, { flexWrap: 'wrap' }]}>
          {CURRENCIES.map(([c, label]) => (
            <Chip key={c} label={label} selected={options.currency === c} disabled={!!busy}
              onPress={() => (options.currency === c ? undefined : void save('currency', {}, c))} />
          ))}
        </View>
        <T muted size={13}>Prix, soldes et remboursements du bar. Se choisit avant les premières commandes payantes.</T>
      </Section>
      <Section title="Options du bar">
        {row(ORDERS[0])}
        {row(ORDERS[1], !options.guest_orders,
          options.guest_orders ? ORDERS[1].hint : 'Toujours allumé quand les invités ne commandent pas dans l’app.')}
        {row(ORDERS[2])}
      </Section>
      <Section title="Bar offert">
        <ToggleRow label="Bar offert" value={options.free_bar} disabled={!!busy}
          hint="Rien à rembourser : prix cachés aux invités, pas d’engagement à cocher, pas de solde. Tu gardes le compte des verres servis. Sur un événement public, le bar est toujours offert."
          onChange={(v) => toggle('free_bar', v)} />
        {options.free_bar ? <T size={13} color={colors.mint}>Les verres sont à 0 {barUnit()}. Le nombre servi reste dans « Direct ».</T> : null}
      </Section>
      <Limits key={`${options.limit_glasses}|${options.limit_chf}`} options={options} busy={busy === 'limits'}
        onSave={(l) => void save('limits', l)} />
      <Section title="Ce que peuvent faire les barmans">
        <T muted size={13}>Toi et les co-organisateurs pouvez toujours tout faire.</T>
        {STAFF.map((r) => row(r))}
      </Section>
      <ErrorText error={error} />
    </>
  );
}
