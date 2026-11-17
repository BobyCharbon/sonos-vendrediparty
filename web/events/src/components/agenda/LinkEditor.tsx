import { router, type Href } from 'expo-router';
import { useEffect, useRef, useState } from 'react';
import { Image, Modal, Pressable, StyleSheet, Text, View } from 'react-native';

import { CheckRow, Divider, FieldChoice, Group, Label, Note, StatusPill } from '@/components/agenda/Bits';
import { useTermsGate } from '@/components/TermsSheet';
import { Button, Chip, ConfirmButton, ErrorText, Input, Segmented, T, Toast, ToggleRow } from '@/components/ui';
import {
  addDays, agoText, calColor, dateShort, DEFAULT_FIELDS, durationText, errorText, FIELD_LABELS, iosKey, isProfile, isTerms, linkUrl, MODELS,
  nativeAgenda, rpc, rulesText, slugify, spanText, syncBusyNow, tinyDay, dayKey, WEEK_LETTERS, type BookingFields, type Calendar, type Link, type Model,
  type Links, type NativeCalendar, type Rule,
} from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { enter, pressTransition } from '@/lib/motion';
import { notifyState } from '@/lib/notifyBanner';
import { supabase } from '@/lib/supabase';
import { qrDataUri } from '@/lib/tickets';
import { colors, font, radius } from '@/lib/theme';

/** Demi-heures proposées ; « 24:00 » pour finir à minuit. */
const HALF = Array.from({ length: 49 }, (_, i) => `${String(Math.floor(i / 2)).padStart(2, '0')}:${i % 2 ? '30' : '00'}`);
const HORIZONS = [{ days: 14, label: '2 semaines' }, { days: 28, label: '4 semaines' }, { days: 60, label: '60 jours' }];
const DURATIONS = [30, 60, 90, 120];
const MARGINS = [0, 30, 60, 90]; // demi-heures : les plages « pris » sont arrondies à 30 min

function modelOf(rules: Rule[]): Model {
  const same = (a: Rule[], b: Rule[]) => JSON.stringify(a) === JSON.stringify(b);
  return MODELS.find((m) => m.key !== 'custom' && same(m.rules, rules))?.key ?? 'custom';
}

/** Copier un lien (presse-papiers), sinon le montrer. */
export async function copyText(text: string): Promise<boolean> {
  try { await navigator.clipboard.writeText(text); return true; } catch { return false; }
}

/** Partager : la feuille du système si elle existe (téléphone), sinon copier. */
export async function shareLink(link: Link): Promise<'shared' | 'copied' | 'failed'> {
  const url = linkUrl(link);
  const nav = navigator as Navigator & { share?: (d: { title?: string; url: string }) => Promise<void> };
  if (typeof nav.share === 'function') {
    try { await nav.share({ title: link.display_name ? `Prendre rendez-vous avec ${link.display_name}` : 'Mes disponibilités', url }); return 'shared'; }
    catch { return 'failed'; }
  }
  return (await copyText(url)) ? 'copied' : 'failed';
}

export function QrModal({ link, onClose }: { link: Link | null; onClose: () => void }) {
  return (
    <Modal visible={!!link} transparent animationType="fade" onRequestClose={onClose}>
      <View style={st.overlay}>
        <View style={[st.qrCard, enter('pop')]} accessibilityViewIsModal accessibilityLabel="Code QR du lien">
          <T weight="bold" size={20} style={{ textAlign: 'center' }}>Montre ce code</T>
          <T muted size={13} style={{ textAlign: 'center' }}>{link?.name}</T>
          {link ? <Image source={{ uri: qrDataUri(linkUrl(link)) }} style={st.qr} accessibilityLabel="Code QR du lien de dispo" /> : null}
          <T muted size={12} style={{ textAlign: 'center' }}>La personne vise le code avec l’appareil photo. Sans compte, sans voir tes rendez-vous.</T>
          <Button label="Fermer" variant="secondary" onPress={onClose} />
        </View>
      </View>
    </Modal>
  );
}

/** Feuille « Toute personne qui a ce lien voit quand tu es libre » (maquette 6B), avant chaque nouveau lien. */
export function LinkIntro({ onGo, onCancel }: { onGo: () => void; onCancel: () => void }) {
  const lines = [
    { icon: '👁️', title: 'Seulement Disponible ou Occupé', text: 'Dans les jours et heures que tu choisis. Jamais le titre, le lieu ni avec qui.' },
    { icon: '🕒', title: 'À partir de demain', text: 'Jamais aujourd’hui. 60 jours au plus.' },
    { icon: '↥', title: 'Il peut être transféré', text: 'Donne-le seulement à qui tu veux.' },
    { icon: '⏹', title: 'Tu l’arrêtes quand tu veux', text: 'Permanent, ou 90 jours si tu préfères : tu choisis.' },
  ];
  return (
    <View style={[st.intro, enter('rise')]} testID="link-intro">
      <View style={st.introIcon}><T size={30}>🔗</T></View>
      <T size={24} weight="bold" style={{ textAlign: 'center' }}>Toute personne qui a ce lien voit quand tu es libre</T>
      <Group>
        {lines.map((l, i) => (
          <View key={l.title}>
            {i ? <Divider /> : null}
            <View style={st.introRow}>
              <T size={18}>{l.icon}</T>
              <View style={{ flex: 1 }}>
                <T size={15} weight="bold">{l.title}</T>
                <T muted size={13}>{l.text}</T>
              </View>
            </View>
          </View>
        ))}
      </Group>
      <Button label="J’ai compris, continuer" onPress={onGo} />
      <Button label="Annuler" variant="ghost" onPress={onCancel} />
    </View>
  );
}

/**
 * Réglage d'un lien de dispo (maquettes 6C, 6D, et 6a de la page publique) : nom pour soi, modèle ou plages, nom que voit
 * la personne, jusqu'où elle voit, demandes de rendez-vous (éteintes au départ : durée, champs Non / Facultatif /
 * Obligatoire, « Me prévenir des demandes »), et l'aperçu « Voici ce que verra la personne ».
 */
export function LinkEditor({ link, model: startModel, onSaved }: { link: Link | null; model?: Model; onSaved: (l: Link) => void }) {
  const me = useMe();
  const terms = useTermsGate('Avant de créer un lien');
  const first = MODELS.find((m) => m.key === (startModel ?? 'week')) ?? MODELS[0];
  const [name, setName] = useState(link?.name ?? (first.key === 'custom' ? '' : first.name));
  const [emoji, setEmoji] = useState(link?.emoji ?? first.emoji);
  const [rules, setRules] = useState<Rule[]>(link?.rules ?? first.rules);
  const [model, setModel] = useState<Model>(link ? modelOf(link.rules) : first.key);
  const myFirst = (me.first_name || me.display_name || '').trim();
  const [pro, setPro] = useState(!!link?.display_name && link.display_name !== myFirst);
  const [display, setDisplay] = useState(link?.display_name && link.display_name !== myFirst ? link.display_name : '');
  const [horizon, setHorizon] = useState(link?.horizon_days ?? 28);
  const [booking, setBooking] = useState(link?.booking_enabled ?? false);
  const [durationMin, setDuration] = useState(link?.duration_min ?? 60);
  const [fields, setFields] = useState<BookingFields>(link?.booking_fields ?? DEFAULT_FIELDS);
  const [label, setLabel] = useState(link?.message_label ?? '');
  const [notify, setNotify] = useState(true);
  const [deviceOff, setDeviceOff] = useState(false);
  const [preview, setPreview] = useState<[string, string][] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [needProfile, setNeedProfile] = useState(false);
  const [permanent, setPermanent] = useState(link ? link.permanent : true);
  const [before, setBefore] = useState(link?.buffer_before_min ?? 0);
  const [after, setAfter] = useState(link?.buffer_after_min ?? 0);
  // Calendriers qui rendent occupé : ceux de Party et des agendas ajoutés avec un lien, et ceux de l'iPhone (app seulement,
  // noms lus sur l'iPhone). Nouveau lien : tout coché. null tant qu'ils ne sont pas lus (rien n'est alors envoyé : « tout »).
  const [cals, setCals] = useState<{ party: Calendar[]; phone: NativeCalendar[] | null } | null>(null);
  const [picked, setPicked] = useState<Set<string> | null>(link?.calendars ? new Set(link.calendars) : null);
  const native = nativeAgenda();
  // Adresse lisible (/agenda/<nom>/<lien>) : le nom est choisi une fois pour tous les liens, le nom du lien ici.
  const [readable, setReadable] = useState(link ? !!link.slug : true);
  const [handle, setHandle] = useState<string | null>(null);
  const [serverHandle, setServerHandle] = useState<string | null | undefined>(undefined);
  const [editHandle, setEditHandle] = useState(false);
  const [slug, setSlug] = useState(link?.slug ?? slugify(name));
  const [slugTouched, setSlugTouched] = useState(!!link?.slug);
  const [taken, setTaken] = useState<string[]>([]);
  const savedId = useRef<string | null>(link?.id ?? null);

  useEffect(() => {
    void rpc<Links>('agenda_links').then((l) => {
      setNotify(l.notify !== false);
      setServerHandle(l.handle ?? null);
      setHandle(l.handle ?? slugify(me.display_name || me.first_name || '', 30));
      setTaken(l.links.filter((x) => x.id !== link?.id && x.slug).map((x) => x.slug!));
    }).catch(() => setServerHandle(null));
    void notifyState().then((s) => setDeviceOff(s !== 'on')).catch(() => undefined);
    void (async () => {
      const party = await rpc<Calendar[]>('agenda_calendars_list').catch((): Calendar[] => []);
      let phone: NativeCalendar[] | null = null;
      if (native) {
        try {
          if ((await native.status()).access === 'full') phone = (await native.calendars()).filter((c) => !c.excluded);
        } catch { /* sans l'iPhone : les calendriers de Party seulement */ }
      }
      setCals({ party, phone });
      // Nouveau lien, ou lien d'avant (sans liste) : tout ce qui peut rendre occupé est coché.
      setPicked((p) => p ?? new Set([...party.map((c) => c.id), ...(phone ?? []).map((c) => iosKey(c.id))]));
    })();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- une seule lecture à l'ouverture
  }, []);

  // Aperçu : relu un instant après chaque changement (rien n'est enregistré).
  const ask = useRef(0);
  useEffect(() => {
    const n = ++ask.current;
    const t = setTimeout(() => {
      void rpc<{ slots: [string, string][] }>('agenda_link_preview', { link: { rules, horizon_days: horizon, duration_min: durationMin, booking_enabled: booking,
        calendars: picked ? [...picked] : null, buffer_before_min: before, buffer_after_min: after } })
        .then((r) => { if (n === ask.current) setPreview(r.slots ?? []); }).catch(() => { if (n === ask.current) setPreview([]); });
    }, 350);
    return () => clearTimeout(t);
  }, [rules, horizon, durationMin, booking, picked, before, after]);

  function pickModel(m: Model) {
    setModel(m);
    const def = MODELS.find((x) => x.key === m)!;
    if (m !== 'custom') setRules(def.rules);
    setEmoji(def.emoji);
    if (!name.trim() || MODELS.some((x) => x.name === name)) {
      setName(m === 'custom' ? name : def.name);
      if (!slugTouched) setSlug(slugify(m === 'custom' ? name : def.name));
    }
  }
  function setRule(i: number, patch: Partial<Rule>) {
    setRules((r) => r.map((x, j) => (j === i ? { ...x, ...patch } : x)));
  }
  async function setNotifyPref(v: boolean) {
    setNotify(v);
    await supabase.from('notification_prefs').update({ booking_requests: v }).eq('user_id', me.id);
  }

  async function save() {
    setError(null);
    setNeedProfile(false);
    if (!rules.length || rules.some((r) => !r.days.length || r.to <= r.from)) { setError('Choisis au moins un jour et des heures (la fin après le début).'); return; }
    if (pro && !display.trim()) { setError('Écris le nom que verra la personne.'); return; }
    const h = slugify(handle ?? '', 30), sl = slugify(slug);
    if (readable) {
      if (h.length < 3) { setError('Ton nom d’adresse : 3 lettres au moins (lettres, chiffres, tirets).'); return; }
      if (!sl) { setError('Donne un nom au lien, par exemple « semaine ».'); return; }
      if (taken.includes(sl)) { setError(`Tu as déjà un lien « ${sl} ». Choisis un autre nom.`); return; }
    }
    const body = { name: name.trim() || 'Mes dispos', emoji, display_name: pro ? display.trim() : myFirst || null, rules, horizon_days: horizon,
      duration_min: durationMin, booking_enabled: booking, booking_fields: { ...fields, first_name: 'required' }, message_label: label.trim() || null,
      permanent, buffer_before_min: before, buffer_after_min: after, ...(picked ? { calendars: [...picked] } : {}) };
    if (!link && !(await terms.ensure())) return;
    setBusy(true);
    try {
      // Le nom d'adresse d'abord (déjà pris : rien n'est créé), puis le lien, puis son nom.
      if (readable && h !== serverHandle) {
        await rpc('agenda_handle_set', { handle: h });
        setServerHandle(h);
      }
      const args = () => (savedId.current ? { link: body, id: savedId.current } : { link: body });
      let saved: Link;
      try { saved = await rpc<Link>('agenda_link_save', args()); }
      catch (e) {
        if (!isTerms(e) || !(await terms.ensure())) throw e;
        saved = await rpc<Link>('agenda_link_save', args());
      }
      savedId.current = saved.id;
      if ((readable ? sl : null) !== (saved.slug ?? null)) {
        saved = await rpc<Link>('agenda_link_set_slug', { id: saved.id, slug: readable ? sl : null });
      }
      // Les plages des calendriers choisis partent tout de suite (sinon : à la prochaine ouverture de Party).
      await syncBusyNow();
      onSaved(saved);
    } catch (e) {
      if (isProfile(e)) setNeedProfile(true);
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  // Aperçu en jours : « Mer. 18 · ✓ 20 h 30 – 23 h ».
  const tomorrow = addDays(dayKey(new Date()), 1);
  const byDay = new Map<string, [string, string][]>();
  for (const s of preview ?? []) {
    const k = dayKey(new Date(s[0]));
    byDay.set(k, [...(byDay.get(k) ?? []), s]);
  }
  const shownDays = [...byDay.keys()].sort().slice(0, 5);
  const shownName = pro ? display.trim() || 'Nom pro' : myFirst || 'Toi';
  const toggle = (key: string, on: boolean) => setPicked((p) => {
    const next = new Set(p ?? []);
    if (on) next.add(key); else next.delete(key);
    return next;
  });
  // Calendriers de l'iPhone choisis ailleurs (dans l'app) : gardés, comptés ici sans leur nom.
  const phoneElsewhere = picked && !cals?.phone ? [...picked].filter((k) => k.startsWith('ios:')).length : 0;
  const order = { party: 0, personal: 1, ics: 2 } as const;
  const partyCals = [...(cals?.party ?? [])].sort((a, b) => order[a.kind] - order[b.kind]);

  return (
    <View style={{ gap: 12 }}>
      <View style={st.nameBox}>
        <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>NOM DU LIEN (POUR TOI)</T>
        <Input accessibilityLabel="Nom du lien (pour toi)" placeholder="Pro – semaine" value={name} onChangeText={(v) => { setName(v); if (!slugTouched) setSlug(slugify(v)); }} maxLength={40} style={st.nameInput} />
      </View>

      <Label>Commence par un modèle</Label>
      <View style={st.models} accessibilityRole="radiogroup">
        {MODELS.map((m) => {
          const on = model === m.key;
          return (
            <Pressable key={m.key} accessibilityRole="radio" aria-checked={on} accessibilityState={{ checked: on }} accessibilityLabel={`${m.name}, ${m.hint}`}
              testID={`model-${m.key}`} onPress={() => pickModel(m.key)} style={({ pressed }) => [st.model, on && st.modelOn, pressTransition, pressed && { opacity: 0.85 }]}>
              <T size={22}>{m.emoji}</T>
              <T size={15} weight="bold">{m.name}</T>
              <T muted size={12}>{m.hint}</T>
            </Pressable>
          );
        })}
      </View>

      {model === 'custom' ? (
        <View style={{ gap: 10 }}>
          {rules.map((r, i) => (
            <View key={i} style={[st.rule, enter('drop')]}>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' }}>
                <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>PLAGE {i + 1}</T>
                {rules.length > 1 ? (
                  <Pressable accessibilityRole="button" accessibilityLabel={`Retirer la plage ${i + 1}`} onPress={() => setRules(rules.filter((_, j) => j !== i))} style={{ minHeight: 44, justifyContent: 'center' }}>
                    <T size={14} weight="bold" color={colors.redSoft}>Retirer</T>
                  </Pressable>
                ) : null}
              </View>
              <View style={{ flexDirection: 'row', justifyContent: 'space-between' }} accessibilityLabel={`Jours de la plage ${i + 1}`}>
                {WEEK_LETTERS.map((l, d) => {
                  const day = d + 1;
                  const on = r.days.includes(day);
                  return (
                    <Pressable key={d} accessibilityRole="checkbox" aria-checked={on} accessibilityState={{ checked: on }}
                      accessibilityLabel={`${['Lundi', 'Mardi', 'Mercredi', 'Jeudi', 'Vendredi', 'Samedi', 'Dimanche'][d]}${on ? ', choisi' : ''}`}
                      onPress={() => setRule(i, { days: on ? r.days.filter((x) => x !== day) : [...r.days, day].sort() })}
                      style={[st.dayCircle, on && st.dayOn]}>
                      <Text style={{ color: on ? '#fff' : colors.textSoft, fontSize: 15, ...font.bold }}>{l}</Text>
                    </Pressable>
                  );
                })}
              </View>
              <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
                <HalfBox label="De" value={r.from} options={HALF.slice(0, 48)} onChange={(v) => setRule(i, { from: v })} />
                <T muted>→</T>
                <HalfBox label="À" value={r.to} options={HALF.slice(1)} onChange={(v) => setRule(i, { to: v })} />
              </View>
            </View>
          ))}
          {rules.length < 7 ? (
            <Button variant="secondary" label="+ Ajouter une plage" onPress={() => setRules([...rules, { days: [6], from: '10:00', to: '14:00' }])} />
          ) : null}
        </View>
      ) : <Note icon="🕒">{rulesText(rules)}</Note>}

      <Label>Nom que voit la personne</Label>
      <Segmented<'first' | 'pro'> value={pro ? 'pro' : 'first'} onChange={(v) => setPro(v === 'pro')}
        options={[{ key: 'first', label: myFirst || 'Mon prénom' }, { key: 'pro', label: 'Un nom pro' }]} />
      {pro ? <Input accessibilityLabel="Nom que voit la personne" placeholder={`${myFirst || 'Sofia'} · Graphiste`} value={display} onChangeText={setDisplay} maxLength={40} /> : null}
      <Note>Jamais ton nom de famille ni ta photo. Le nom est filtré comme un surnom.</Note>

      <Label>Elle voit jusqu’à</Label>
      <View style={st.wrap}>{HORIZONS.map((h) => <Chip key={h.days} label={h.label} selected={horizon === h.days} onPress={() => setHorizon(h.days)} />)}</View>

      <Label>Prendre rendez-vous</Label>
      <View style={st.card}>
        <ToggleRow label="Demandes de rendez-vous" hint="Éteint au départ. La personne choisit un créneau, tu acceptes ou refuses." value={booking} onChange={setBooking} />
        {booking ? (
          <View style={[{ gap: 10 }, enter('drop')]}>
            <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>DURÉE D’UN RENDEZ-VOUS</T>
            <View style={st.wrap}>{DURATIONS.map((d) => <Chip key={d} label={durationText(d)} selected={durationMin === d} onPress={() => setDuration(d)} />)}</View>
            <Note>La page propose des créneaux de cette durée dans tes heures libres.</Note>
            <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>CE QUE LA PERSONNE REMPLIT</T>
            <Group>
              {FIELD_LABELS.map((f, i) => (
                <View key={f.key}>
                  {i ? <Divider /> : null}
                  <FieldChoice label={f.label} value={f.key === 'first_name' ? 'required' : fields[f.key]} locked={f.key === 'first_name'}
                    onChange={(v) => setFields((x) => ({ ...x, [f.key]: v }))} />
                </View>
              ))}
            </Group>
            <Note>« Non » : le champ n’apparaît pas. Le prénom est toujours demandé.</Note>
            {fields.message !== 'off' ? (
              <Input accessibilityLabel="Question posée à la personne (facultatif)" placeholder="Question posée (facultatif) : « Votre message »" value={label}
                onChangeText={setLabel} maxLength={60} />
            ) : null}
            <ToggleRow label="Me prévenir des demandes" hint="Aussi dans Réglages › Notifications" value={notify} onChange={(v) => void setNotifyPref(v)} />
            {deviceOff ? (
              <View style={st.warn}><T size={13} color={colors.coralSoft}>🔔 Les notifications de cet appareil sont coupées : pense à ouvrir Party, une demande expire après 48 h sans réponse.</T></View>
            ) : null}
          </View>
        ) : null}
      </View>

      <Label>Adresse du lien</Label>
      <Segmented<'nice' | 'secret'> value={readable ? 'nice' : 'secret'} onChange={(v) => setReadable(v === 'nice')}
        options={[{ key: 'nice', label: 'Lisible' }, { key: 'secret', label: 'En lettres' }]} />
      {readable ? (
        <View style={[st.card, enter('drop')]}>
          {serverHandle && !editHandle ? (
            <View style={{ flexDirection: 'row', alignItems: 'center', gap: 8 }}>
              <T muted size={14} style={{ flex: 1 }}>Ton nom : <Text style={{ color: colors.text, ...font.bold }}>{serverHandle}</Text></T>
              <Pressable accessibilityRole="button" onPress={() => setEditHandle(true)} style={{ minHeight: 44, justifyContent: 'center' }}>
                <T size={14} weight="bold" color={colors.accent}>Changer</T>
              </Pressable>
            </View>
          ) : (
            <View style={{ gap: 6 }}>
              <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>TON NOM (POUR TOUS TES LIENS)</T>
              <Input accessibilityLabel="Ton nom d’adresse" placeholder="ludovic" value={handle ?? ''} autoCapitalize="none" autoCorrect={false}
                onChangeText={(v) => setHandle(slugify(v, 30, true))} maxLength={30} />
              {serverHandle ? <Note>Changer ton nom change l’adresse de tous tes liens lisibles. Les anciennes ne marchent plus.</Note> : null}
            </View>
          )}
          <View style={{ gap: 6 }}>
            <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>NOM DU LIEN</T>
            <Input accessibilityLabel="Nom du lien dans l’adresse" placeholder="semaine" value={slug} autoCapitalize="none" autoCorrect={false}
              onChangeText={(v) => { setSlugTouched(true); setSlug(slugify(v, 40, true)); }} maxLength={40} />
          </View>
          <View style={st.address} testID="link-nice-address">
            <T size={14} weight="semibold" numberOfLines={2}>
              {(typeof location !== 'undefined' ? location.host : '')}/agenda/{slugify(handle ?? '', 30) || 'ton-nom'}/{slugify(slug) || 'lien'}
            </T>
          </View>
        </View>
      ) : null}
      <Note>{readable
        ? 'Facile à dire et à retenir, mais quelqu’un qui connaît ton nom peut la deviner. L’adresse en lettres marche aussi.'
        : 'Une suite de lettres au hasard : impossible à deviner. Pour un lien que tu veux garder discret.'}</Note>

      <Label>Ce qui te rend occupé</Label>
      <Group>
        {!cals ? <View style={{ padding: 14 }}><T muted size={14}>Lecture de tes calendriers…</T></View> : null}
        {partyCals.map((c, i) => (
          <View key={c.id}>
            {i ? <Divider /> : null}
            <CheckRow label={c.kind === 'party' ? '🎉 Mes soirées Party' : c.name} testID={`link-cal-${c.kind === 'ics' ? c.id : c.kind}`}
              hint={c.kind === 'party' ? 'Présent, Peut-être, j’organise' : c.kind === 'personal' ? 'Rendez-vous notés dans Party' : 'Agenda ajouté avec un lien'}
              checked={!!picked?.has(c.id)} onChange={(v) => toggle(c.id, v)} left={<View style={[st.calDot, { backgroundColor: calColor(c.color) }]} />} />
          </View>
        ))}
        {(cals?.phone ?? []).map((c) => (
          <View key={c.id}>
            <Divider />
            <CheckRow label={c.title} hint={`iPhone · ${c.source}`} checked={!!picked?.has(iosKey(c.id))} onChange={(v) => toggle(iosKey(c.id), v)}
              left={<View style={[st.calDot, { backgroundColor: c.color }]} />} />
          </View>
        ))}
      </Group>
      {native && cals && !cals.phone ? (
        <Button variant="secondary" label="📱 Ajouter les calendriers de mon iPhone" onPress={() => router.push('/agenda/calendars?iphone=1' as Href)} />
      ) : null}
      {phoneElsewhere ? <Note icon="📱">Et {phoneElsewhere} calendrier{phoneElsewhere > 1 ? 's' : ''} de ton iPhone, choisi{phoneElsewhere > 1 ? 's' : ''} dans l’app Party.</Note> : null}
      <Note>Un rendez-vous dans un calendrier coché te rend occupé sur ce lien. Seules les heures partent, jamais le titre. Les demandes de rendez-vous comptent toujours.</Note>

      <Label>Marges autour de tes rendez-vous</Label>
      <View style={st.card}>
        {([['Avant', before, setBefore], ['Après', after, setAfter]] as const).map(([word, value, set]) => (
          <View key={word} style={{ gap: 8 }} accessibilityRole="radiogroup" accessibilityLabel={`Marge ${word.toLowerCase()} chaque rendez-vous`}>
            <T size={12} weight="bold" color={colors.muted} style={{ letterSpacing: 0.8 }}>{word.toUpperCase()} CHAQUE RENDEZ-VOUS</T>
            <View style={st.wrap}>
              {MARGINS.map((m) => <Chip key={m} label={m ? durationText(m) : 'Aucune'} selected={value === m} onPress={() => set(m)} />)}
            </View>
          </View>
        ))}
      </View>
      <Note>{before || after
        ? `Pas disponible ${[before ? `${durationText(before)} avant` : '', after ? `${durationText(after)} après` : ''].filter(Boolean).join(' et ')} chaque rendez-vous : le temps d’arriver, de souffler.`
        : 'Aucune marge : un créneau peut commencer dès la fin d’un rendez-vous.'}</Note>

      <Label>Durée du lien</Label>
      <Segmented<'forever' | 'days'> value={permanent ? 'forever' : 'days'} onChange={(v) => setPermanent(v === 'forever')}
        options={[{ key: 'forever', label: 'Permanent' }, { key: 'days', label: '90 jours' }]} />
      <Note>{permanent ? 'Il marche jusqu’à ce que tu l’arrêtes.' : 'Il s’arrête seul après 90 jours. Tu pourras le prolonger.'}</Note>

      <Label>Voici ce que verra la personne</Label>
      <View style={st.preview} testID="link-preview">
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 10 }}>
          <View style={st.pvAvatar}><Text style={{ color: '#3A3550', fontSize: 13, ...font.bold }}>{shownName.slice(0, 2).toUpperCase()}</Text></View>
          <View style={{ flex: 1 }}>
            <Text style={st.pvTitle}>{booking ? `Prendre rendez-vous avec ${shownName}` : `Disponibilités de ${shownName}`}</Text>
            <Text style={st.pvSub}>À partir de demain · {HORIZONS.find((h) => h.days === horizon)?.label}</Text>
          </View>
        </View>
        <Text style={st.pvToday}>{tinyDay(dayKey(new Date()))} · Aujourd’hui n’est jamais montré</Text>
        {preview === null ? <Text style={st.pvSub}>Calcul…</Text> : null}
        {preview && !shownDays.length ? <Text style={st.pvSub}>Aucun moment libre dans ces heures pour l’instant.</Text> : null}
        {shownDays.map((k) => (
          <View key={k} style={st.pvDay}>
            <Text style={st.pvDayName}>{tinyDay(k)}</Text>
            <View style={{ flex: 1, flexDirection: 'row', flexWrap: 'wrap', gap: 4 }}>
              {byDay.get(k)!.slice(0, 4).map(([s, e]) => (
                <View key={s} style={st.pvSlot}><Text style={st.pvSlotText}>✓ {spanText(new Date(s), new Date(e))}</Text></View>
              ))}
              {byDay.get(k)!.length > 4 ? <Text style={st.pvSub}>+{byDay.get(k)!.length - 4}</Text> : null}
            </View>
          </View>
        ))}
        <Text style={st.pvFoot}>Jamais le titre, le lieu ni avec qui. Dès le {tinyDay(tomorrow)}.</Text>
      </View>

      <ErrorText error={error} />
      {needProfile ? <Button variant="secondary" label="Compléter mon profil" onPress={() => router.push('/settings/profile' as Href)} /> : null}
      <Button label={link ? 'Enregistrer' : 'Créer le lien'} loading={busy} onPress={() => void save()} />
      {terms.sheet}
    </View>
  );
}

function HalfBox({ label, value, options, onChange }: { label: string; value: string; options: string[]; onChange: (v: string) => void }) {
  return (
    <View style={st.halfBox}>
      <T size={12} weight="bold" color={colors.muted}>{label.toUpperCase()}</T>
      <select aria-label={label === 'De' ? 'Début de la plage' : 'Fin de la plage'} value={value} onChange={(e) => onChange(e.target.value)}
        style={{ background: 'transparent', border: 'none', color: colors.text, fontSize: 20, fontWeight: 700, appearance: 'none', colorScheme: 'dark',
          fontFamily: font.body.fontFamily, padding: 0, width: '100%', outlineColor: colors.accent }}>
        {options.map((x) => <option key={x} value={x}>{x}</option>)}
      </select>
    </View>
  );
}

/** Carte de gestion d'un lien (maquette 6A) : état, heures, nom affiché, vues, fin ; Copier, Partager, Code QR, Arrêter. */
export function LinkCard({ link, onChanged, index = 0 }: { link: Link; onChanged: () => unknown; index?: number }) {
  const [toast, setToast] = useState<string | null>(null);
  const [qr, setQr] = useState(false);
  const [error, setError] = useState<string | null>(null);
  async function act(action: 'stop' | 'restart' | 'extend' | 'delete') {
    setError(null);
    try {
      await rpc('agenda_link_set', { id: link.id, action });
      setToast(action === 'stop' ? 'Lien arrêté. Il n’affiche plus rien.' : action === 'restart' ? 'Lien rallumé, à la même adresse.' : action === 'extend' ? 'Prolongé de 90 jours.' : 'Lien supprimé.');
      await onChanged();
    } catch (e) { setError(errorText(e)); }
  }
  const live = link.status === 'active';
  return (
    <View style={[st.linkCard, !live && { opacity: 0.92 }, enter('rise', index)]} testID={`link-card-${link.id}`}>
      <Pressable accessibilityRole="link" accessibilityLabel={`Régler le lien ${link.name}`} onPress={() => router.push(`/agenda/links/${link.id}` as Href)}
        style={{ gap: 6 }}>
        <View style={{ flexDirection: 'row', alignItems: 'center', gap: 12 }}>
          <View style={st.linkEmoji}><T size={22}>{link.emoji || '🔗'}</T></View>
          <T size={19} weight="bold" style={{ flex: 1 }} numberOfLines={1}>{link.name}</T>
          <StatusPill status={link.status} />
        </View>
        {live ? (
          <>
            <T size={15} weight="semibold">{rulesText(link.rules)}</T>
            <T muted size={13}>Nom affiché : <Text style={{ color: colors.text, ...font.bold }}>{link.display_name}</Text></T>
            <T muted size={13}>{link.views ? `Vu ${link.views} fois${link.last_viewed_at ? ` · dernière fois ${agoText(link.last_viewed_at)}` : ''}` : 'Pas encore vu'}</T>
          </>
        ) : (
          <T muted size={13}>{link.status === 'stopped' ? `Arrêté le ${dateShort(link.stopped_at ?? link.created_at)}. Le lien n’affiche plus rien.` : `Expiré le ${dateShort(link.expires_at ?? link.created_at)}. Le lien n’affiche plus rien.`}</T>
        )}
      </Pressable>
      {live && link.permanent ? <T muted size={13}>♾️ Permanent · tu l’arrêtes quand tu veux</T> : null}
      {live && !link.permanent && link.expires_at ? (
        <View style={{ flexDirection: 'row', alignItems: 'center', flexWrap: 'wrap', gap: 4 }}>
          <T muted size={13}>S’arrête seul le {dateShort(link.expires_at)} ·</T>
          <Pressable accessibilityRole="button" accessibilityLabel={`Prolonger ${link.name} de 90 jours`} onPress={() => void act('extend')} style={{ minHeight: 32, justifyContent: 'center' }}>
            <T size={13} weight="bold" color={colors.accent}>Prolonger</T>
          </Pressable>
        </View>
      ) : null}
      {link.booking_enabled || link.pending ? (
        <Pressable accessibilityRole="link" testID={`link-requests-${link.id}`} onPress={() => router.push(`/agenda/requests?link=${link.id}` as Href)}
          style={({ pressed }) => [st.requests, !link.pending && { backgroundColor: colors.fill }, pressTransition, pressed && { opacity: 0.85 }]}>
          <T size={15} weight="bold" color={link.pending ? colors.coral : colors.textSoft} style={{ flex: 1 }}>
            {link.pending ? `📩 ${link.pending} demande${link.pending > 1 ? 's' : ''} de rendez-vous` : '📩 Demandes de rendez-vous · aucune en attente'}
          </T>
          <T size={18} color={colors.muted}>›</T>
        </Pressable>
      ) : null}
      {live ? (
        <View style={st.actions}>
          <Action icon="⧉" label="Copier" onPress={async () => setToast((await copyText(linkUrl(link))) ? 'Lien copié.' : linkUrl(link))} />
          <Action icon="↥" label="Partager" onPress={async () => { const r = await shareLink(link); if (r === 'copied') setToast('Lien copié.'); }} />
          <Action icon="▦" label="Code QR" onPress={() => setQr(true)} />
          <Action icon="◉" label="Arrêter" danger onPress={() => void act('stop')} />
        </View>
      ) : (
        <View style={{ flexDirection: 'row', gap: 8 }}>
          <Button small variant="secondary" label="Rallumer ce lien" style={{ flex: 1 }} onPress={() => void act('restart')} />
          <ConfirmButton small label="Supprimer" confirmLabel="Supprimer" style={{ flex: 1 }} onConfirm={() => act('delete')} />
        </View>
      )}
      <ErrorText error={error} />
      <QrModal link={qr ? link : null} onClose={() => setQr(false)} />
      {toast ? <Toast message={toast} onHide={() => setToast(null)} /> : null}
    </View>
  );
}

function Action({ icon, label, onPress, danger }: { icon: string; label: string; onPress: () => unknown; danger?: boolean }) {
  return (
    <Pressable accessibilityRole="button" accessibilityLabel={label} onPress={() => void onPress()}
      style={({ pressed }) => [st.action, pressTransition, pressed && { opacity: 0.8, transform: [{ scale: 0.96 }] }]}>
      <Text style={{ fontSize: 16, color: danger ? colors.redSoft : colors.text }}>{icon}</Text>
      <Text style={{ fontSize: 13, color: danger ? colors.redSoft : colors.text, ...font.semibold }}>{label}</Text>
    </Pressable>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(8,5,20,0.88)', alignItems: 'center', justifyContent: 'center', padding: 16 },
  qrCard: { width: '100%', maxWidth: 360, gap: 12, padding: 20, borderRadius: radius.lg, backgroundColor: colors.surface },
  qr: { width: 240, height: 240, alignSelf: 'center', borderRadius: 12 },
  intro: { gap: 14, padding: 18, borderRadius: 24, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  calDot: { width: 12, height: 12, borderRadius: 6 },
  address: { padding: 12, borderRadius: radius.md, backgroundColor: colors.fill },
  introIcon: { alignSelf: 'center', width: 64, height: 64, borderRadius: 18, backgroundColor: colors.action, alignItems: 'center', justifyContent: 'center',
    shadowColor: colors.accent, shadowOpacity: 0.5, shadowRadius: 18 },
  introRow: { flexDirection: 'row', gap: 12, padding: 12, alignItems: 'flex-start' },
  nameBox: { gap: 4, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  nameInput: { backgroundColor: 'transparent', paddingHorizontal: 0, fontSize: 19, height: 36, borderWidth: 0 },
  models: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  model: { flexBasis: '47%', flexGrow: 1, gap: 2, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface, borderWidth: 1.5, borderColor: 'transparent' },
  modelOn: { borderColor: colors.accent, backgroundColor: '#3A1C45' },
  rule: { gap: 10, padding: 12, borderRadius: radius.md, backgroundColor: colors.surface },
  dayCircle: { width: 44, height: 44, borderRadius: 22, borderWidth: 1.5, borderColor: colors.lineStrong, alignItems: 'center', justifyContent: 'center' },
  dayOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  halfBox: { flex: 1, gap: 2, padding: 10, borderRadius: radius.md, backgroundColor: colors.surface2 },
  wrap: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  card: { gap: 10, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  warn: { padding: 12, borderRadius: radius.md, backgroundColor: colors.coralDim },
  // Aperçu : la page publique est sobre et claire (vouvoiement, aucun look soirée).
  preview: { gap: 8, padding: 14, borderRadius: radius.lg, backgroundColor: '#F7F6FB' },
  pvAvatar: { width: 34, height: 34, borderRadius: 17, backgroundColor: '#E4E1EE', alignItems: 'center', justifyContent: 'center' },
  pvTitle: { color: '#1D1A2B', fontSize: 16, ...font.bold },
  pvSub: { color: '#6B6680', fontSize: 13, ...font.body },
  pvToday: { color: '#8A869C', fontSize: 13, fontStyle: 'italic', ...font.body, paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: '#E6E3EE' },
  pvDay: { flexDirection: 'row', gap: 10, alignItems: 'flex-start', paddingVertical: 4, borderBottomWidth: 1, borderBottomColor: '#EEEBF4' },
  pvDayName: { width: 64, color: '#1D1A2B', fontSize: 14, ...font.bold, paddingTop: 3 },
  pvSlot: { paddingHorizontal: 8, paddingVertical: 4, borderRadius: 8, backgroundColor: '#DDF5E8' },
  pvSlotText: { color: '#14653F', fontSize: 13, ...font.semibold },
  pvFoot: { color: '#8A869C', fontSize: 12, ...font.body },
  linkCard: { gap: 10, padding: 16, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  linkEmoji: { width: 44, height: 44, borderRadius: 12, backgroundColor: colors.surface2, alignItems: 'center', justifyContent: 'center' },
  requests: { flexDirection: 'row', alignItems: 'center', minHeight: 48, paddingHorizontal: 14, borderRadius: radius.md, backgroundColor: 'rgba(255,179,71,0.14)' },
  actions: { flexDirection: 'row', gap: 6 },
  action: { flex: 1, minHeight: 56, borderRadius: radius.md, backgroundColor: colors.fillStrong, alignItems: 'center', justifyContent: 'center', gap: 2 },
});
