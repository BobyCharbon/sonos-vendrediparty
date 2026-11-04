import { router } from 'expo-router';
import { useEffect, useMemo, useState } from 'react';
import { View } from 'react-native';

import { Badge, Button, Card, Chip, ConfirmButton, Empty, ErrorText, Field, LinkRow, Loading, Screen, Section, T, ToggleRow } from '@/components/ui';
import { useQuery } from '@/lib/data';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

/** Cadeaux Zicou d'un événement (Compagnon, lot A) : l'admin — ou l'organisateur, dans les bornes fixées par l'admin —
 * choisit EN AMONT les objets à gagner et leur chance ; une fois publiées, chances et exemplaires sont figés. Tirage par
 * le serveur à la fin de l'événement pour TOUS les présents, jamais selon un paiement. Règlement visible de tous
 * (Apple 5.3 : « Apple et Google ne sont ni organisateurs ni sponsors »). Base : migration 20261104210000. */

type Rarity = 'common' | 'rare' | 'epic' | 'legendary' | 'mythic';
type Prize = { item: string | null; label: string; rarity: Rarity; pct: number; copies: number | null; given: number };
type CatalogItem = { id: string; label: string; rarity: Rarity; series: string; slot: string; edition: number | null; left: number | null };
type Bounds = { organizers: boolean; max_pct: Record<Rarity, number>; max_prizes: number; max_copies: number };
type DropData = {
  event: { id: string; title: string; starts_at: string | null; ends_at: string | null; status: string; started: boolean };
  role: 'admin' | 'organizer' | null;
  drop: { status: 'draft' | 'published' | 'drawn'; seed_hash: string | null; seed: string | null; published_at: string | null;
    drawn_at: string | null; eligible_count: number | null; draw_at: string | null; prizes: Prize[] } | null;
  eligible_now: number | null;
  bounds: Bounds | null;
  catalog: CatalogItem[] | null;
  mine: { item: string; label: string; rarity: Rarity; roll: number; prize: number }[];
};
type Row = { item: string; pct: string; copies: string };

export const RARITY: Record<Rarity, { label: string; fg: string; bg: string }> = {
  common: { label: 'Commun', fg: '#120a26', bg: '#9aa3b5' },
  rare: { label: 'Rare', fg: '#fff', bg: '#2f6fd6' },
  epic: { label: 'Épique', fg: '#fff', bg: '#7e3fd9' },
  legendary: { label: 'Légendaire', fg: '#2a1a06', bg: '#ffbf3c' },
  mythic: { label: 'Mythique', fg: '#240a18', bg: '#ff9be0' },
};
const RARITIES: Rarity[] = ['common', 'rare', 'epic', 'legendary', 'mythic'];
// Même texte que app/pet_events.py RULES (le règlement dans l'app).
export const RULES = [
  'Qui participe : toutes les personnes présentes à l’événement (billet scanné ou arrivée notée, ou notées « Présent » par l’organisateur). Jamais selon un paiement : payer ou non sa part ne change rien.',
  'Quoi : des accessoires du Compagnon Zicou uniquement, sans aucune valeur en argent. Aucun lot réel (boisson, bon, place, objet physique), rien à acheter, rien à miser.',
  'Chances et nombre d’exemplaires : publiés avant le début de l’événement, puis figés (personne ne peut plus les changer, pas même l’admin).',
  'Tirage : fait par le serveur de Party à la fin de l’événement, un jet par personne et par objet. L’empreinte de la graine est publiée avant ; la graine est révélée après, pour que chacun puisse vérifier son jet.',
  'Apple et Google ne sont ni organisateurs ni sponsors de ces cadeaux, et n’y participent d’aucune manière.',
];

const pct = (v: number) => `${String(v).replace('.', ',')} %`;
const when = (iso: string | null) => (iso ? new Date(iso).toLocaleString('fr-CH', { dateStyle: 'medium', timeStyle: 'short' }) : '—');
/** « invalid: … », « frozen: … » : la partie lisible du refus de la base. */
const readable = (message: string | undefined, fallback: string) => {
  const m = (message ?? '').trim();
  return /^[a-z_]+: /.test(m) ? m.replace(/^[a-z_]+: /, '') : fallback;
};

async function load(eventId: string): Promise<DropData> {
  const { data, error } = await supabase.rpc('pet_event_drop_get', { p_event: eventId });
  if (error) throw new Error(readable(error.message, 'Les cadeaux n’ont pas pu être lus.'));
  return data as DropData;
}

/** Lien depuis la fiche d'un événement : visible des organisateurs / admins, et de tous dès que les cadeaux sont publiés. */
export function EventGiftsLink({ eventId, canManage }: { eventId: string; canManage: boolean }) {
  const [state, setState] = useState<DropData | null>(null);
  useEffect(() => {
    let on = true;
    load(eventId).then((d) => on && setState(d)).catch(() => {});
    return () => { on = false; };
  }, [eventId]);
  const published = state?.drop && state.drop.status !== 'draft';
  if (!(published || (canManage && state?.role))) return null;
  const hint = published ? (state?.drop?.status === 'drawn' ? 'Tirage fait : voir les gagnants et vérifier' : 'Chances publiées, tirage à la fin pour tous les présents')
    : 'Préparer les objets à gagner (avant le début)';
  return <LinkRow label="🎁 Cadeaux Zicou de l’événement" hint={hint} onPress={() => router.push(`/event/${eventId}/gifts`)} />;
}

export function EventGifts({ eventId }: { eventId: string }) {
  const { data, loading, error, reload, setData } = useQuery(() => load(eventId), [eventId]);
  if (loading && !data) return <Screen edges={[]}><Loading /></Screen>;
  if (!data) return <Screen edges={[]}><ErrorText error={error} /></Screen>;
  const editable = !!data.role && (!data.drop || data.drop.status === 'draft') && !data.event.started;
  return (
    <Screen edges={[]}>
      <T size={13} muted>{data.event.title}</T>
      {data.drop && data.drop.status !== 'draft' ? <Published data={data} /> : null}
      {editable ? <Editor data={data} onSaved={(d) => setData(d)} /> : null}
      {!data.drop && !editable ? <Empty>Pas de cadeaux Zicou pour cet événement.</Empty> : null}
      {data.role && data.drop?.status === 'draft' && data.event.started ? (
        <Empty>L’événement a commencé : un brouillon non publié n’est jamais tiré.</Empty>
      ) : null}
      <Section title="Règlement">
        <Card style={{ gap: 8 }}>
          {RULES.map((r) => <T key={r} size={13}>• {r}</T>)}
        </Card>
      </Section>
      {data.role === 'admin' && data.bounds ? <BoundsEditor bounds={data.bounds} onSaved={reload} /> : null}
    </Screen>
  );
}

function PrizeLine({ p, eligible }: { p: Prize; eligible: number | null }) {
  const r = RARITY[p.rarity];
  const expected = eligible != null ? Math.min(p.copies ?? Infinity, Math.round((eligible * p.pct) / 100 * 10) / 10) : null;
  return (
    <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6 }}>
      <View style={{ flex: 1, gap: 4 }}>
        <T weight="semibold">{p.label}</T>
        <View style={{ flexDirection: 'row', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
          <Badge label={r.label} fg={r.fg} bg={r.bg} />
          <T size={12} muted>{p.copies ? `${p.copies} exemplaire${p.copies > 1 ? 's' : ''} au plus` : 'sans limite'}{p.given ? ` · ${p.given} gagné${p.given > 1 ? 's' : ''}` : ''}</T>
        </View>
        {expected != null ? <T size={12} muted>Aperçu : ≈ {String(expected).replace('.', ',')} gagnant(s) sur {eligible} présent(s) aujourd’hui</T> : null}
      </View>
      <T size={20} weight="bold" color={colors.coral}>{pct(p.pct)}</T>
    </View>
  );
}

function Published({ data }: { data: DropData }) {
  const d = data.drop!;
  return (
    <Section title={d.status === 'drawn' ? 'Tirage fait' : 'Chances publiées (figées)'}>
      <Card style={{ gap: 4 }}>
        {d.prizes.map((p, i) => <PrizeLine key={`${p.item}-${i}`} p={p} eligible={null} />)}
        <T size={12} muted>Publié le {when(d.published_at)}. Tirage : {d.status === 'drawn' ? `fait le ${when(d.drawn_at)}, ${d.eligible_count ?? 0} présent(s)` : `à la fin de l’événement (${when(d.draw_at)})`}.</T>
        <T size={11} muted>Empreinte de la graine (sha256) : {d.seed_hash}</T>
        {d.seed ? <T size={11} muted>Graine révélée : {d.seed}</T> : null}
      </Card>
      {data.mine.length ? (
        <Card style={{ gap: 6, marginTop: 10 }}>
          <T weight="bold">🎁 Tes cadeaux</T>
          {data.mine.map((m) => <T key={m.prize}>{m.label} · ton jet : {String(m.roll).replace('.', ',')} (gagnant sous {pct(d.prizes[m.prize]?.pct ?? 0)})</T>)}
          <T size={12} muted>Ouvre ton Compagnon (onglet Jeux) pour le découvrir.</T>
        </Card>
      ) : d.status === 'drawn' ? <T muted size={13}>Pas de cadeau pour toi cette fois.</T> : null}
    </Section>
  );
}

function Editor({ data, onSaved }: { data: DropData; onSaved: (d: DropData) => void }) {
  const initial: Row[] = (data.drop?.prizes ?? []).map((p) => ({ item: p.item ?? '', pct: String(p.pct), copies: p.copies ? String(p.copies) : '' }));
  const [rows, setRows] = useState<Row[]>(initial.length ? initial : []);
  const [filter, setFilter] = useState('');
  const [rarity, setRarity] = useState<Rarity>('common');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const catalog = useMemo(() => data.catalog ?? [], [data.catalog]);
  const byId = useMemo(() => new Map(catalog.map((c) => [c.id, c])), [catalog]);
  const bounds = data.bounds!;
  const choices = catalog.filter((c) => c.rarity === rarity && !rows.some((r) => r.item === c.id)
    && (!filter || c.label.toLowerCase().includes(filter.toLowerCase())));
  const preview: Prize[] = rows.filter((r) => byId.has(r.item)).map((r) => ({
    item: r.item, label: byId.get(r.item)!.label, rarity: byId.get(r.item)!.rarity, pct: Number(r.pct.replace(',', '.')) || 0,
    copies: r.copies ? Number(r.copies) : null, given: 0,
  }));
  const payload = () => rows.map((r) => ({ item: r.item, pct: Number(r.pct.replace(',', '.')), copies: r.copies ? Number(r.copies) : null }));
  const run = async (what: string, fn: () => PromiseLike<{ data: unknown; error: { message: string } | null }>) => {
    setBusy(what);
    setError(null);
    const { data: d, error: e } = await fn();
    setBusy(null);
    if (e) return setError(readable(e.message, 'Ça n’a pas marché, réessaie.'));
    onSaved(d as DropData);
  };
  const set = (i: number, patch: Partial<Row>) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const limit = data.role === 'admin' ? 10 : bounds.max_prizes;
  return (
    <Section title="Cadeaux de l’événement">
      <Card style={{ gap: 12 }}>
        <T size={13} muted>
          {data.role === 'admin' ? 'Admin : tous les objets, Mythiques compris (exemplaires restants).'
            : `Organisateur : dans les bornes de l’admin (Commun ≤ ${pct(bounds.max_pct.common)}, Rare ≤ ${pct(bounds.max_pct.rare)}, Épique ≤ ${pct(bounds.max_pct.epic)}, Légendaire ≤ ${pct(bounds.max_pct.legendary)}, ${bounds.max_copies} exemplaires au plus).`}
          {' '}Jusqu’à {limit} objets. Publie avant le début : ensuite, plus rien ne change.
        </T>
        {rows.map((r, i) => {
          const c = byId.get(r.item);
          return (
            <View key={r.item} style={{ gap: 6, borderTopWidth: i ? 1 : 0, borderColor: colors.line, paddingTop: i ? 10 : 0 }}>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                {c ? <Badge label={RARITY[c.rarity].label} fg={RARITY[c.rarity].fg} bg={RARITY[c.rarity].bg} /> : null}
                <T weight="semibold" style={{ flex: 1 }}>{c?.label ?? r.item}</T>
                <Button small variant="danger" label="Retirer" onPress={() => setRows(rows.filter((_, j) => j !== i))} />
              </View>
              <View style={{ flexDirection: 'row', gap: 10 }}>
                <View style={{ flex: 1 }}><Field label="Chance (%)" value={r.pct} onChangeText={(v) => set(i, { pct: v })} keyboardType="decimal-pad" placeholder="ex. 20" /></View>
                <View style={{ flex: 1 }}><Field label="Exemplaires" value={r.copies} onChangeText={(v) => set(i, { copies: v.replace(/\D/g, '') })}
                  keyboardType="number-pad" placeholder={c && ['legendary', 'mythic'].includes(c.rarity) ? 'obligatoire' : 'sans limite'}
                  hint={c?.left != null ? `${c.left} restant(s) sur ${c.edition}` : undefined} /></View>
              </View>
            </View>
          );
        })}
        {rows.length < limit ? (
          <View style={{ gap: 8 }}>
            <T weight="bold">Ajouter un objet</T>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
              {RARITIES.filter((k) => catalog.some((c) => c.rarity === k)).map((k) => (
                <Chip key={k} label={RARITY[k].label} selected={rarity === k} onPress={() => setRarity(k)} />
              ))}
            </View>
            <Field label="Chercher" value={filter} onChangeText={setFilter} placeholder="Bonnet, couronne…" />
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }}>
              {choices.slice(0, 24).map((c) => (
                <Chip key={c.id} label={`${c.label}${c.left != null ? ` (${c.left})` : ''}`} disabled={c.left === 0}
                  onPress={() => setRows([...rows, { item: c.id, pct: rarity === 'common' ? '100' : '10', copies: ['legendary', 'mythic'].includes(rarity) ? '1' : '' }])} />
              ))}
            </View>
          </View>
        ) : null}
      </Card>
      {preview.length ? (
        <Card style={{ marginTop: 10 }}>
          <T weight="bold">Aperçu des chances</T>
          {preview.map((p, i) => <PrizeLine key={`${p.item}-${i}`} p={p} eligible={data.eligible_now} />)}
          <T size={12} muted>Chaque présent a un jet pour chaque objet : on peut en gagner plusieurs.</T>
        </Card>
      ) : null}
      <ErrorText error={error} />
      <View style={{ gap: 8, marginTop: 10 }}>
        <Button label="Enregistrer le brouillon" variant="secondary" loading={busy === 'save'} disabled={!rows.length}
          onPress={() => run('save', () => supabase.rpc('pet_event_drop_save', { p_event: data.event.id, p_prizes: payload() }))} />
        {data.drop?.status === 'draft' ? (
          <ConfirmButton label="Publier les chances" confirmLabel="Publier : elles ne changeront plus"
            onConfirm={() => run('publish', () => supabase.rpc('pet_event_drop_publish', { p_event: data.event.id }))} />
        ) : null}
        {data.drop?.status === 'draft' ? (
          <Button small variant="danger" label="Supprimer le brouillon" loading={busy === 'delete'}
            onPress={() => run('delete', () => supabase.rpc('pet_event_drop_delete', { p_event: data.event.id }))} />
        ) : null}
      </View>
    </Section>
  );
}

function BoundsEditor({ bounds, onSaved }: { bounds: Bounds; onSaved: () => void }) {
  const [organizers, setOrganizers] = useState(bounds.organizers);
  const [maxPct, setMaxPct] = useState<Record<Rarity, string>>(Object.fromEntries(RARITIES.map((k) => [k, String(bounds.max_pct[k] ?? 0)])) as Record<Rarity, string>);
  const [prizes, setPrizes] = useState(String(bounds.max_prizes));
  const [copies, setCopies] = useState(String(bounds.max_copies));
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const save = async () => {
    setBusy(true);
    setError(null);
    const { error: e } = await supabase.rpc('pet_drop_bounds_set', {
      p_organizers: organizers, p_max_pct: Object.fromEntries(RARITIES.map((k) => [k, Number(maxPct[k].replace(',', '.')) || 0])),
      p_max_prizes: Number(prizes) || 5, p_max_copies: Number(copies) || 10,
    });
    setBusy(false);
    if (e) return setError(readable(e.message, 'Les bornes n’ont pas pu être enregistrées.'));
    onSaved();
  };
  return (
    <Section title="Bornes des organisateurs (admin)">
      <Card style={{ gap: 10 }}>
        <ToggleRow label="Les organisateurs peuvent préparer des cadeaux" value={organizers} onChange={setOrganizers} />
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 10 }}>
          {RARITIES.map((k) => (
            <View key={k} style={{ width: 120 }}>
              <Field label={`${RARITY[k].label} ≤ %`} value={maxPct[k]} keyboardType="decimal-pad" onChangeText={(v) => setMaxPct({ ...maxPct, [k]: v })} />
            </View>
          ))}
        </View>
        <View style={{ flexDirection: 'row', gap: 10 }}>
          <View style={{ flex: 1 }}><Field label="Objets au plus" value={prizes} keyboardType="number-pad" onChangeText={setPrizes} /></View>
          <View style={{ flex: 1 }}><Field label="Exemplaires au plus (Légendaire, Mythique)" value={copies} keyboardType="number-pad" onChangeText={setCopies} /></View>
        </View>
        <T size={12} muted>Mythique à 0 % : seul l’admin peut en mettre en jeu.</T>
        <ErrorText error={error} />
        <Button label="Enregistrer les bornes" variant="secondary" loading={busy} onPress={save} />
      </Card>
    </Section>
  );
}
