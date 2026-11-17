import { router, useLocalSearchParams, type Href } from 'expo-router';
import { useState } from 'react';
import { Modal, Pressable, StyleSheet, Switch, Text, View } from 'react-native';

import { ast, Badge, Divider, Group, Label, Note, TopBar } from '@/components/agenda/Bits';
import { GroupTile } from '@/components/GroupBits';
import { Button, ErrorText, Field, Screen, Segmented, T, Toast } from '@/components/ui';
import {
  agoText, CAL_COLOR_NAMES, CAL_COLORS, calColor, dateDots, errorText, fetchIcs, nativeAgenda, rpc, savePrefs, useAgendaBadge,
  type Calendar, type Links, type NativeAccess, type NativeCalendar, type Prefs, type Sharing,
} from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery, useSignal } from '@/lib/data';
import { groupName } from '@/lib/groups';
import { enter, pressTransition } from '@/lib/motion';
import { colors, font, radius } from '@/lib/theme';

type Tab = 'see' | 'share';

/**
 * Calendriers (maquettes 3A, 3B, 3C, 7B) : deux gestes séparés, deux mots. « Voir ici » : ce qui s'affiche dans mon agenda,
 * visible par moi seul, rien ne part (Party, iPhone, agendas ajoutés avec un lien). « Partager » : mes dispos aux groupes
 * (Disponible / Occupé, jamais pourquoi) et mes liens de dispo hors de Party.
 */
export default function CalendarsScreen() {
  const me = useMe();
  const p = useLocalSearchParams<{ tab?: string; iphone?: string; add?: string; done?: string }>();
  const [tab, setTab] = useState<Tab>(p.tab === 'share' || p.done ? 'share' : 'see');
  const pending = useAgendaBadge(me.id);
  const { data, error, reload } = useQuery(async () => {
    const [calendars, prefs, sharing, links, access] = await Promise.all([
      rpc<Calendar[]>('agenda_calendars_list'),
      rpc<Prefs>('agenda_prefs_get').catch((): Prefs => ({})),
      rpc<Sharing>('agenda_sharing'),
      rpc<Links>('agenda_links'),
      nativeAgenda()?.status().then((s) => s.access).catch(() => null) ?? Promise.resolve(null),
    ]);
    const n = nativeAgenda();
    const phone: NativeCalendar[] = n && access === 'full' ? await n.calendars().catch((): NativeCalendar[] => []) : [];
    return { calendars, prefs, sharing, links, access: access as NativeAccess | null, phone };
  }, []);
  useSignal([`user:${me.id}`], reload);

  return (
    <Screen>
      <TopBar back="Agenda" fallback="/agenda" title="Calendriers"
        right={<Pressable accessibilityRole="button" onPress={() => router.navigate('/agenda')} style={st.ok}><Text style={st.okText}>OK</Text></Pressable>} />
      <Segmented<Tab> value={tab} onChange={setTab} options={[{ key: 'see', label: '👁️ Voir ici' }, { key: 'share', label: '📤 Partager' }]} />
      <ErrorText error={error} />
      {data && tab === 'see' ? <SeeHere data={data} reload={reload} openIphone={p.iphone === '1'} openAdd={p.add === '1'} /> : null}
      {data && tab === 'share' ? <ShareTab sharing={data.sharing} links={data.links} pending={pending} reload={reload} justDone={p.done === '1'} /> : null}
    </Screen>
  );
}

type Data = { calendars: Calendar[]; prefs: Prefs; sharing: Sharing; links: Links; access: NativeAccess | null; phone: NativeCalendar[] };

function SwitchRow({ dot, hollow, label, hint, value, onChange, testID }: {
  dot: string; hollow?: boolean; label: string; hint?: string; value: boolean; onChange: (v: boolean) => void; testID?: string;
}) {
  return (
    <Pressable accessibilityRole="switch" aria-checked={value} accessibilityState={{ checked: value }} accessibilityLabel={`Afficher ${label}`} testID={testID}
      onPress={() => onChange(!value)} style={st.row}>
      <View style={[st.dot, hollow ? { borderWidth: 2, borderColor: dot } : { backgroundColor: dot }]} />
      <View style={{ flex: 1, minWidth: 0 }}>
        <T size={16} weight="semibold" numberOfLines={1}>{label}</T>
        {hint ? <T muted size={13} numberOfLines={2}>{hint}</T> : null}
      </View>
      <Switch value={value} onValueChange={onChange} accessibilityElementsHidden importantForAccessibility="no"
        trackColor={{ false: colors.fillStrong, true: colors.mint }} thumbColor="#FFFFFF" {...{ activeThumbColor: '#FFFFFF' }} />
    </Pressable>
  );
}

function SeeHere({ data, reload, openIphone, openAdd }: { data: Data; reload: () => unknown; openIphone: boolean; openAdd: boolean }) {
  const party = data.calendars.find((c) => c.kind === 'party');
  const personal = data.calendars.find((c) => c.kind === 'personal');
  const ics = data.calendars.filter((c) => c.kind === 'ics');
  const native = nativeAgenda();
  const [explain, setExplain] = useState(openIphone && !!native && data.access !== 'full');
  const [denied, setDenied] = useState(false);
  const [adding, setAdding] = useState(openAdd);
  const [editing, setEditing] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [prefs, setPrefs] = useState<Prefs>(data.prefs);
  const [shownPick, setShown] = useState<Record<string, boolean>>({});
  const phone = data.phone.map((c) => ({ ...c, shown: shownPick[c.id] ?? c.shown }));

  async function setVisible(c: Calendar | undefined, visible: boolean) {
    if (!c) return;
    try { await rpc('agenda_calendar_save', { id: c.id, cal: { visible } }); await reload(); } catch (e) { setError(errorText(e)); }
  }
  function pref(patch: Prefs) {
    setPrefs((x) => ({ ...x, ...patch }));
    void savePrefs(patch);
  }
  async function link() {
    if (!native) return;
    const r = await native.requestAccess().catch(() => ({ access: 'denied' as NativeAccess }));
    setExplain(false);
    if (r.access !== 'full') { if (!prefs.native_denied_seen) { setDenied(true); pref({ native_denied_seen: true }); } }
    await reload();
  }

  return (
    <View style={{ gap: 12 }}>
      <Note icon="👁️">Ce qui s’affiche dans ton agenda, visible par toi seulement. <Text style={{ ...font.bold }}>Rien ne part.</Text></Note>
      <Label>Dans Party</Label>
      <Group>
        <SwitchRow dot={CAL_COLORS.pink} label="🎉 Mes soirées" hint="Présent, Peut-être, j’organise" value={party?.visible !== false} onChange={(v) => void setVisible(party, v)} />
        <Divider />
        <SwitchRow dot={CAL_COLORS.pink} hollow label="🗳️ Sondages à voter" value={prefs.show_polls !== false} onChange={(v) => pref({ show_polls: v })} />
        <Divider />
        <SwitchRow dot={calColor(personal?.color ?? 'mint')} label="Juste pour moi" hint="Ajoutés ici" value={personal?.visible !== false} onChange={(v) => void setVisible(personal, v)} />
      </Group>

      {native ? (
        <>
          <Label>{data.access === 'full' ? 'Sur ton iPhone · relié' : 'Sur ton iPhone'}</Label>
          <Group>
            {data.access === 'full' ? phone.map((c, i) => (
              <View key={c.id}>
                {i ? <Divider /> : null}
                <SwitchRow dot={c.color} label={c.title} hint={`iPhone · ${c.source}${c.shown ? '' : ' · masqué'}`} value={c.shown}
                  onChange={(v) => { setShown((m) => ({ ...m, [c.id]: v })); void native.setCalendar(c.id, { shown: v }); }} />
              </View>
            )) : (
              <Pressable accessibilityRole="button" onPress={() => setExplain(true)} style={st.row}>
                <View style={[st.dot, { borderWidth: 2, borderColor: colors.muted }]} />
                <View style={{ flex: 1 }}><T size={16} weight="semibold" color={colors.muted}>Pas relié</T></View>
                <T size={15} weight="bold" color={colors.accent}>Relier</T>
              </Pressable>
            )}
          </Group>
        </>
      ) : null}

      <Label>Ajoutés avec un lien</Label>
      <Group>
        {ics.map((c, i) => (
          <View key={c.id}>
            {i ? <Divider /> : null}
            <SwitchRow dot={calColor(c.color)} label={c.name}
              hint={c.fetch_error ? `⚠️ ${c.fetch_error}` : c.fetched_at ? `Mis à jour ${agoText(c.fetched_at)}` : 'Lu par Party dans un instant'}
              value={c.visible} onChange={(v) => void setVisible(c, v)} />
            <Pressable accessibilityRole="button" accessibilityLabel={`Modifier ${c.name}`} onPress={() => setEditing(editing === c.id ? null : c.id)} style={st.editLink}>
              <T size={13} weight="semibold" color={colors.accent}>{editing === c.id ? 'Fermer' : 'Couleur, nom, supprimer'}</T>
            </Pressable>
            {editing === c.id ? <IcsEditor cal={c} onDone={() => { setEditing(null); void reload(); }} /> : null}
          </View>
        ))}
        {ics.length ? <Divider /> : null}
        <Pressable accessibilityRole="button" testID="ics-add" onPress={() => setAdding(!adding)} style={st.row}>
          <T size={16} weight="semibold" color={colors.accent}>+ Ajouter un agenda avec un lien</T>
        </Pressable>
        {adding ? <IcsAdd count={ics.length} onDone={() => { setAdding(false); void reload(); }} /> : null}
      </Group>
      <Note>Masquer un calendrier le cache ici seulement. Ce que tu partages se règle dans Partager.</Note>

      <Label>Réglages de l’agenda</Label>
      <Group>
        <SwitchRow dot={colors.lavender} label="Numéros de semaine" value={!!prefs.week_numbers} onChange={(v) => pref({ week_numbers: v })} />
        <Divider />
        <SwitchRow dot={colors.muted} label="Soirées où j’ai dit Pas présent" value={!!prefs.show_declined} onChange={(v) => pref({ show_declined: v })} />
      </Group>
      <ErrorText error={error} />

      <Modal visible={explain} transparent animationType="fade" onRequestClose={() => setExplain(false)}>
        <View style={st.overlay}>
          <View style={[st.sheet, enter('rise')]} accessibilityViewIsModal accessibilityLabel="Voir ton iPhone ici">
            <View style={st.phoneBox}><T size={13} weight="bold" color={colors.mint}>🔒 TON IPHONE</T><T size={36}>📅 → 🎉</T></View>
            <T size={26} weight="bold" style={{ textAlign: 'center' }}>Voir ton iPhone ici</T>
            <T size={15} color={colors.textSoft} style={{ textAlign: 'center' }}>Tes rendez-vous de l’iPhone (iCloud, Google, Outlook…) s’affichent dans ton agenda Party.</T>
            <View style={ast.okCard}>
              <T size={15} weight="bold">🛡️ Rien n’est envoyé.</T>
              <T size={13} color={colors.textSoft}>Ils restent sur ton iPhone. Tes groupes ne voient rien de plus.</T>
            </View>
            <Note>Ton iPhone va te demander l’accès : choisis « Autoriser l’accès complet ».</Note>
            <Button label="Continuer" onPress={() => void link()} />
            <Button label="Plus tard" variant="ghost" onPress={() => setExplain(false)} />
          </View>
        </View>
      </Modal>
      <Modal visible={denied} transparent animationType="fade" onRequestClose={() => setDenied(false)}>
        <View style={[st.overlay, { justifyContent: 'flex-end' }]}>
          <View style={[st.sheet, enter('rise')]} accessibilityViewIsModal>
            <T size={40} style={{ textAlign: 'center' }}>🙂</T>
            <T size={22} weight="bold" style={{ textAlign: 'center' }}>Pas d’accès à ton iPhone ? Pas grave.</T>
            <T size={15} color={colors.textSoft} style={{ textAlign: 'center' }}>Tes soirées Party et ce que tu ajoutes ici marchent sans. Qui est libre ? et tes liens aussi.</T>
            <Note>Tu pourras relier ton iPhone plus tard dans Calendriers.</Note>
            <Button label="OK" onPress={() => setDenied(false)} />
          </View>
        </View>
      </Modal>
    </View>
  );
}

function ColorChips({ value, onChange }: { value: string; onChange: (c: string) => void }) {
  return (
    <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} accessibilityRole="radiogroup" accessibilityLabel="Couleur">
      {Object.keys(CAL_COLORS).map((k) => (
        <Pressable key={k} accessibilityRole="radio" aria-checked={value === k} accessibilityState={{ checked: value === k }} accessibilityLabel={CAL_COLOR_NAMES[k]}
          onPress={() => onChange(k)} style={[st.swatchHit, value === k && { borderColor: colors.text }]}>
          <View style={[st.swatch, { backgroundColor: CAL_COLORS[k] }]} />
        </Pressable>
      ))}
    </View>
  );
}

function IcsAdd({ count, onDone }: { count: number; onDone: () => void }) {
  const [name, setName] = useState('');
  const [url, setUrl] = useState('');
  const [color, setColor] = useState('sky');
  const [help, setHelp] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function add() {
    setBusy(true);
    setError(null);
    try {
      const cal = await rpc<Calendar>('agenda_calendar_save', { cal: { name: name.trim() || 'Mon agenda', color, ics_url: url.trim(), visible: true, counts_busy: false } });
      const now = new Date();
      await fetchIcs(cal.id, now, new Date(now.getTime() + 7 * 86400_000)).catch(() => []);
      onDone();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <View style={[st.inner, enter('drop')]}>
      {count >= 10 ? <T muted>Tu as déjà 10 agendas ajoutés avec un lien.</T> : null}
      <Field label="Nom" placeholder="Sorties Lausanne" value={name} onChangeText={setName} maxLength={40} />
      <Field label="Lien de l’agenda" placeholder="https://… ou webcal://…" value={url} onChangeText={setUrl} autoCapitalize="none" autoCorrect={false} keyboardType="url" />
      <ColorChips value={color} onChange={setColor} />
      <Pressable accessibilityRole="button" accessibilityState={{ expanded: help }} onPress={() => setHelp(!help)} style={{ minHeight: 40, justifyContent: 'center' }}>
        <T size={14} weight="semibold" color={colors.accent}>Où trouver ce lien ? {help ? '⌃' : '⌄'}</T>
      </Pressable>
      {help ? (
        <View style={{ gap: 8 }}>
          <T size={13} color={colors.textSoft}><Text style={{ ...font.bold }}>Google</Text> : Agenda Google sur un ordinateur › ⚙️ › ton agenda › « Adresse secrète au format iCal ».</T>
          <T size={13} color={colors.textSoft}><Text style={{ ...font.bold }}>iCloud</Text> : Calendrier › ⓘ à côté de l’agenda › « Calendrier public » › copier le lien.</T>
          <T size={13} color={colors.textSoft}><Text style={{ ...font.bold }}>Outlook</Text> : Paramètres › Calendrier › « Calendriers partagés » › Publier › lien ICS.</T>
          <Note icon="🔒">Le lien est lu par Party pour toi seul ; personne d’autre ne voit ce qu’il contient.</Note>
        </View>
      ) : null}
      <ErrorText error={error} />
      <Button label="Ajouter" loading={busy} disabled={!url.trim() || count >= 10} onPress={() => void add()} />
    </View>
  );
}

function IcsEditor({ cal, onDone }: { cal: Calendar; onDone: () => void }) {
  const [name, setName] = useState(cal.name);
  const [color, setColor] = useState(cal.color);
  const [error, setError] = useState<string | null>(null);
  async function save() {
    try { await rpc('agenda_calendar_save', { id: cal.id, cal: { name: name.trim() || cal.name, color } }); onDone(); } catch (e) { setError(errorText(e)); }
  }
  async function remove() {
    try { await rpc('agenda_calendar_delete', { id: cal.id }); onDone(); } catch (e) { setError(errorText(e)); }
  }
  return (
    <View style={[st.inner, enter('drop')]}>
      <Field label="Nom" value={name} onChangeText={setName} maxLength={40} />
      <ColorChips value={color} onChange={setColor} />
      <ErrorText error={error} />
      <View style={{ flexDirection: 'row', gap: 8 }}>
        <Button small variant="danger" label="Supprimer" style={{ flex: 1 }} onPress={() => void remove()} />
        <Button small label="Enregistrer" style={{ flex: 1 }} onPress={() => void save()} />
      </View>
    </View>
  );
}

function ShareTab({ sharing, links, pending, reload, justDone }: { sharing: Sharing; links: Links; pending: number; reload: () => unknown; justDone: boolean }) {
  const shared = sharing.groups.filter((g) => g.shared);
  const others = sharing.groups.length - shared.length;
  const [confirm, setConfirm] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const active = links.links.filter((l) => l.status === 'active').length;
  const stopped = links.links.length - active;
  async function stop() {
    await rpc('agenda_stop_sharing');
    setConfirm(false);
    setToast('C’est arrêté. Tes dispos sont effacées.');
    await reload();
  }
  return (
    <View style={{ gap: 12 }} testID="share-tab">
      <Note icon="↥" color={colors.accentSoft}>Ce que d’autres voient : seulement <Text style={{ ...font.bold }}>Disponible</Text> ou <Text style={{ ...font.bold }}>Occupé</Text>. Jamais le titre, le lieu ni avec qui.</Note>
      {justDone && shared.length ? (
        <View style={[ast.okCard, enter('pop')]} testID="share-done">
          <T size={16} weight="bold">✓ C’est fait.</T>
          <T size={14} color={colors.textSoft}>{shared.map((g) => groupName(g)).join(', ')} {shared.length > 1 ? 'voient' : 'voit'} tes heures occupées, jamais pourquoi. Accord du {dateDots(shared[0].consented_at ?? new Date().toISOString())}.</T>
        </View>
      ) : null}
      <Label>Avec mes groupes</Label>
      {shared.length ? (
        <View style={ast.card}>
          {shared.map((g) => (
            <View key={g.id} style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
              <GroupTile group={{ ...g, system: g.system }} size={44} />
              <View style={{ flex: 1 }}>
                <T size={16} weight="bold">{groupName(g)}</T>
                <T muted size={13}>{sharing.busy_updated_at ? `Mis à jour ${agoText(sharing.busy_updated_at)}` : `Accord du ${dateDots(g.consented_at ?? new Date().toISOString())}`}</T>
              </View>
              <View style={st.sharedPill}><T size={13} weight="bold" color={colors.mint}>● Partagé</T></View>
            </View>
          ))}
          {others ? <T muted size={13}>{others > 1 ? `Les ${others} autres groupes` : 'L’autre groupe'} : rien n’est partagé.</T> : null}
          {confirm ? (
            <View style={[{ gap: 8 }, enter('fade')]}>
              <T size={14} weight="semibold">Arrêter de partager ? Tes dispos seront effacées tout de suite pour tous tes groupes.</T>
              <View style={{ flexDirection: 'row', gap: 8 }}>
                <Button small variant="secondary" label="Annuler" style={{ flex: 1 }} onPress={() => setConfirm(false)} />
                <Button small variant="dangerSolid" label="Arrêter" style={{ flex: 1 }} onPress={() => void stop()} />
              </View>
            </View>
          ) : (
            <View style={{ flexDirection: 'row', gap: 8 }}>
              <Button small variant="secondary" label="Modifier" style={{ flex: 1 }} onPress={() => router.push('/agenda/share')} />
              <Button small variant="danger" label="Arrêter de partager" style={{ flex: 2 }} onPress={() => setConfirm(true)} />
            </View>
          )}
        </View>
      ) : (
        <View style={ast.card}>
          <T size={16} weight="bold">Personne ne voit tes dispos.</T>
          <T muted size={14}>Tu choisis groupe par groupe. Ils voient quand tu es occupé, jamais pourquoi.</T>
          <Button label="Partager mes dispos" onPress={() => router.push('/agenda/share')} />
        </View>
      )}
      <Label>Avec un lien, hors de Party</Label>
      <Pressable accessibilityRole="link" testID="links-row" accessibilityLabel={`Mes liens de dispo${pending ? `, ${pending} demande${pending > 1 ? 's' : ''} de rendez-vous` : ''}`}
        onPress={() => router.push('/agenda/links' as Href)} style={({ pressed }) => [ast.card, st.linkRow, pressTransition, pressed && { opacity: 0.85 }]}>
        <View style={st.linkIcon}><T size={20}>🔗</T></View>
        <View style={{ flex: 1 }}>
          <T size={16} weight="bold">Mes liens de dispo</T>
          <T muted size={13}>{links.links.length ? `${active} actif${active > 1 ? 's' : ''}${stopped ? ` · ${stopped} arrêté${stopped > 1 ? 's' : ''}` : ''} · ${links.links.length} sur ${links.max}` : 'Pour quelqu’un hors de Party (un client, ton coach…)'}</T>
        </View>
        <Badge count={pending} />
        <T muted size={20}>›</T>
      </Pressable>
      {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  ok: { minHeight: 44, minWidth: 44, justifyContent: 'center', alignItems: 'flex-end' },
  okText: { color: colors.accent, fontSize: 17, ...font.bold },
  row: { flexDirection: 'row', alignItems: 'center', gap: 12, minHeight: 56, paddingHorizontal: 14, paddingVertical: 8 },
  dot: { width: 12, height: 12, borderRadius: 6 },
  editLink: { paddingLeft: 38, paddingBottom: 8, marginTop: -6, minHeight: 32, justifyContent: 'center' },
  inner: { gap: 10, padding: 14, borderTopWidth: 1, borderTopColor: colors.line },
  swatchHit: { width: 44, height: 44, borderRadius: 22, borderWidth: 2, borderColor: 'transparent', alignItems: 'center', justifyContent: 'center' },
  swatch: { width: 28, height: 28, borderRadius: 14 },
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  sheet: { width: '100%', maxWidth: 420, gap: 12, padding: 20, borderRadius: 24, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  phoneBox: { alignSelf: 'center', alignItems: 'center', gap: 6, paddingHorizontal: 28, paddingVertical: 14, borderRadius: 22, borderWidth: 1.5,
    borderStyle: 'dashed', borderColor: 'rgba(91,227,166,0.5)' },
  sharedPill: { paddingHorizontal: 10, paddingVertical: 4, borderRadius: radius.pill, backgroundColor: 'rgba(91,227,166,0.14)' },
  linkRow: { flexDirection: 'row', alignItems: 'center', gap: 12 },
  linkIcon: { width: 40, height: 40, borderRadius: 12, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center' },
});
