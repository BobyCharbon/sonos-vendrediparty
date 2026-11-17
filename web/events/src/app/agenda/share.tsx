import { router, useLocalSearchParams, type Href } from 'expo-router';
import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { CheckRow, Divider, goBack, Group, Label, Note, hatched, TopBar } from '@/components/agenda/Bits';
import { GroupTile } from '@/components/GroupBits';
import { Avatar, Button, ErrorText, Screen, T } from '@/components/ui';
import {
  errorText, nativeAgenda, rpc, syncWebBusy, type Calendar, type NativeCalendar, type Sharing,
} from '@/lib/agenda';
import { useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { groupName } from '@/lib/groups';
import { colors, font, radius } from '@/lib/theme';

/**
 * « Partager mes dispos » (maquettes 4A, 4B ; clarté §2.4) : tout est décoché au départ, groupe par groupe (jamais Membres
 * Vendredi Party d'office), et l'écran dit ce qui part (des heures « occupé » arrondies, 60 jours), d'où ça vient et
 * comment arrêter. Le bouton compte les groupes (« Partager avec 1 groupe ») ; sans groupe coché, il reste grisé.
 */
export default function ShareScreen() {
  const me = useMe();
  const p = useLocalSearchParams<{ group?: string }>();
  const first = typeof p.group === 'string' ? p.group : null;
  const native = nativeAgenda();
  const { data, error } = useQuery(async () => {
    const [sharing, calendars, access] = await Promise.all([
      rpc<Sharing>('agenda_sharing'),
      rpc<Calendar[]>('agenda_calendars_list'),
      native ? native.status().then((s) => s.access).catch(() => null) : Promise.resolve(null),
    ]);
    const phone: NativeCalendar[] = native && access === 'full' ? await native.calendars().catch((): NativeCalendar[] => []) : [];
    return { sharing, calendars, phone, access };
  }, []);
  // Ce qui est déjà partagé reste coché ; un premier partage part de zéro (ce que l'on touche ensuite prend le dessus).
  const [picked, setGroups] = useState<Set<string> | null>(null);
  const groups = picked ?? new Set(data?.sharing.groups.filter((g) => g.shared).map((g) => g.id) ?? []);
  const [partyPick, setParty] = useState<boolean | null>(null);
  const party = partyPick ?? !!data?.sharing.share_party;
  const [manualPick, setManual] = useState<boolean | null>(null);
  const manual = manualPick ?? !!data?.sharing.share_manual;
  const [icsPick, setIcsOn] = useState<Record<string, boolean>>({});
  const [phonePick, setPhoneOn] = useState<Record<string, boolean>>({});
  const icsOn = (c: Calendar) => icsPick[c.id] ?? c.counts_busy;
  const phoneOn = (c: NativeCalendar) => phonePick[c.id] ?? c.countsBusy;
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const list = data ? [...data.sharing.groups].sort((a, b) => Number(b.id === first) - Number(a.id === first)) : [];
  const n = groups.size;
  const wasSharing = !!data?.sharing.groups.some((g) => g.shared);
  const ics = data?.calendars.filter((c) => c.kind === 'ics') ?? [];

  async function save() {
    if (!data) return;
    setBusy(true);
    setErr(null);
    try {
      if (!n) {
        await rpc('agenda_stop_sharing');
        router.replace('/agenda/calendars?tab=share' as Href);
        return;
      }
      // Agendas comptés : un réglage de chaque calendrier (iPhone : gardé sur l'iPhone, jamais envoyé).
      const cals: Calendar[] = [];
      for (const c of ics) {
        if (c.counts_busy !== icsOn(c)) cals.push(await rpc<Calendar>('agenda_calendar_save', { id: c.id, cal: { counts_busy: icsOn(c) } }));
        else cals.push(c);
      }
      for (const c of data.phone) if (c.countsBusy !== phoneOn(c)) await native?.setCalendar(c.id, { countsBusy: phoneOn(c) });
      await rpc('agenda_set_sharing', { groups: [...groups], share_party: party, share_manual: manual });
      if (native) await native.syncBusy().catch(() => undefined);
      else if (cals.some((c) => c.counts_busy)) await syncWebBusy(cals);
      router.replace('/agenda/calendars?tab=share&done=1' as Href);
    } catch (e) {
      setErr(errorText(e));
    } finally {
      setBusy(false);
    }
  }

  const label = !n ? (wasSharing ? 'Arrêter de partager' : 'Partager mes dispos') : `Partager avec ${n} groupe${n > 1 ? 's' : ''}`;
  return (
    <Screen>
      <TopBar back="Calendriers" fallback="/agenda/calendars" title="Partager mes dispos"
        subtitle={<T size={15} color={colors.textSoft}>Tes groupes voient tes heures occupées. <Text style={{ ...font.bold }}>Jamais pourquoi.</Text></T>} />
      <ErrorText error={error} />

      <View style={st.example}>
        <T size={14} weight="bold">Ce que voit le groupe, par exemple :</T>
        <View style={st.exampleIn}>
          <Avatar id={me.id} name={me.display_name || 'Moi'} photo={me.avatar_url} size={34} profile={false} />
          <View style={{ flex: 1, gap: 6 }}>
            <T size={15} weight="semibold">{me.display_name || 'Toi'} · sam. 21</T>
            <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6, alignItems: 'center' }}>
              <View style={[st.busyPill, hatched]}><Text style={st.busyText}>Occupé</Text></View>
              <T size={14}>14 h – 16 h 30</T>
              <View style={st.freePill}><Text style={{ color: colors.mint, fontSize: 13, ...font.bold }}>✓ Disponible</Text></View>
              <T size={14}>ensuite</T>
            </View>
          </View>
        </View>
        <View style={{ flexDirection: 'row', flexWrap: 'wrap', gap: 6 }} accessibilityLabel="Ne part jamais : le titre, le lieu, avec qui, les notes">
          {['le titre', 'le lieu', 'avec qui', 'les notes'].map((w) => (
            <View key={w} style={st.never}><Text style={st.neverText}>✕ {w}</Text></View>
          ))}
        </View>
      </View>

      <Label>Qui le voit · coche les groupes</Label>
      {data && !list.length ? <T muted>Tu ne fais partie d’aucun groupe pour l’instant.</T> : null}
      <Group>
        {list.map((g, i) => (
          <View key={g.id}>
            {i ? <Divider /> : null}
            <CheckRow testID={`share-group-${g.id}`} label={groupName(g)}
              hint={g.system ? 'Tout Party · jamais coché d’office' : `${g.members} membre${g.members > 1 ? 's' : ''}`}
              checked={groups.has(g.id)} left={<GroupTile group={g} size={40} />}
              onChange={(v) => { const x = new Set(groups); if (v) x.add(g.id); else x.delete(g.id); setGroups(x); }} />
          </View>
        ))}
      </Group>
      <Note icon="👥" color={colors.mint}>Vaut aussi pour les personnes qui <Text style={{ ...font.bold }}>rejoindront ce groupe plus tard</Text>. Si tu quittes un groupe, le partage avec lui s’arrête. Les personnes bloquées ne voient jamais rien.</Note>

      <Label>D’où viennent tes heures occupées</Label>
      <Group>
        <CheckRow label="Mes soirées Party" hint="Présent et Peut-être" checked={party} onChange={setParty} testID="share-party" />
        <Divider />
        <CheckRow label="Ce que je note « Occupé » ici" hint="Tes rendez-vous de l’agenda Party" checked={manual} onChange={setManual} testID="share-manual" />
        {data?.phone.filter((c) => !/^vendredi party$/i.test(c.title)).map((c) => (
          <View key={c.id}>
            <Divider />
            <CheckRow label={c.title} hint="Calendrier de ton iPhone" checked={phoneOn(c)} onChange={(v) => setPhoneOn((s) => ({ ...s, [c.id]: v }))} />
          </View>
        ))}
        {ics.map((c) => (
          <View key={c.id}>
            <Divider />
            <CheckRow label={c.name} hint="Agenda ajouté avec un lien" checked={icsOn(c)} onChange={(v) => setIcsOn((s) => ({ ...s, [c.id]: v }))} />
          </View>
        ))}
      </Group>
      {!data?.phone.length && !ics.length ? <Note>Sans autre calendrier coché, seules tes soirées Party et ce que tu notes ici comptent.</Note> : null}
      <Note icon="🕒">Seules les heures partent, arrondies à la demi-heure, sur les 60 prochains jours.</Note>

      <Label>Pour arrêter</Label>
      <T size={14} color={colors.textSoft} style={{ paddingHorizontal: 4 }}>Quand tu veux : Calendriers › Partager › « Arrêter de partager ». Tout ce qui est parti est effacé aussitôt.</T>

      <View style={st.bottom}>
        {!n && !wasSharing ? <T muted size={13} style={{ textAlign: 'center' }}>Coche au moins un groupe</T> : null}
        <ErrorText error={err} />
        <Button label={label} variant={!n && wasSharing ? 'dangerSolid' : 'primary'} disabled={!data || (!n && !wasSharing)} loading={busy} onPress={() => void save()} />
        <Button label="Pas maintenant" variant="ghost" onPress={() => goBack('/agenda/calendars')} />
      </View>
    </Screen>
  );
}

const st = StyleSheet.create({
  example: { gap: 10, padding: 14, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.line },
  exampleIn: { flexDirection: 'row', gap: 12, padding: 12, borderRadius: radius.md, backgroundColor: colors.bg },
  busyPill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, borderWidth: 1, borderColor: 'rgba(185,167,255,0.6)' },
  busyText: { color: '#fff', fontSize: 13, ...font.bold },
  freePill: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8, backgroundColor: 'rgba(91,227,166,0.14)' },
  never: { paddingHorizontal: 10, paddingVertical: 5, borderRadius: radius.pill, backgroundColor: colors.redDim },
  neverText: { color: colors.redSoft, fontSize: 13, textDecorationLine: 'line-through', ...font.semibold },
  bottom: { gap: 6, paddingTop: 8 },
});
