import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { Button, Chip, ErrorText, Field, LinkRow, Screen, s, Section, Segmented, T, ToggleRow } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { check, must, supabase } from '@/lib/supabase';
import { enableWebPush, testWebPush, webPushState, type WebPushState } from '@/lib/push';
import type { ChatMode, NotificationPrefs, Reminder } from '@/lib/types';

const reminderLabels: Record<Reminder, string> = { '7d': 'J-7', '1d': 'J-1', '2h': 'H-2', '0h': 'Au début' };
const chatHints: Record<ChatMode, string> = {
  all: 'Chaque message des discussions des événements auxquels tu participes.',
  mentions: 'Seulement quand on écrit @ton prénom ou qu’on répond à ton message.',
  none: 'Aucune notification. Les messages restent lisibles dans l’app.',
};

export default function NotificationSettings() {
  const me = useMe();
  const { isAdmin } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const saveLock = useRef(false);
  const [device, setDevice] = useState<WebPushState | null>(null);
  const [deviceBusy, setDeviceBusy] = useState(false);
  const [deviceMessage, setDeviceMessage] = useState<string | null>(null);
  const { error: deviceError, reload: reloadDevice } = useQuery(async () => {
    const state = await webPushState();
    setDevice(state);
    return state;
  }, [me.id]);
  const { data: prefs, error: loadError, setData, reload } = useQuery(
    async () => must(await supabase.from('notification_prefs').select('*').eq('user_id', me.id).single()) as NotificationPrefs,
    [me.id],
  );

  if (!prefs) return <Screen edges={[]}><ErrorText error={loadError} />{loadError ? <Button label="Réessayer" onPress={reload} /> : <T muted>Chargement des préférences…</T>}</Screen>;

  async function update(patch: Partial<NotificationPrefs>) {
    if (!prefs || saveLock.current) return;
    saveLock.current = true;
    setSaving(true);
    setError(null);
    try {
      check(await supabase.from('notification_prefs').update(patch).eq('user_id', me.id));
      setData({ ...prefs, ...patch });
    } catch {
      setError('Tes préférences n’ont pas été enregistrées. Vérifie ta connexion et réessaie.');
    } finally {
      saveLock.current = false;
      setSaving(false);
    }
  }

  const quiet = prefs.quiet_start !== null && prefs.quiet_end !== null;
  async function deviceAction(test = false) {
    if (deviceBusy) return;
    setDeviceBusy(true); setError(null); setDeviceMessage(null);
    try {
      if (test) {
        await testWebPush();
        setDeviceMessage('Notification d’essai mise en attente pour cet appareil. Elle devrait partir dans la minute.');
      } else {
        setDevice(await enableWebPush());
        setDeviceMessage('Cet appareil est prêt à recevoir les annonces admin et les alertes que tu choisis.');
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Impossible d’activer les notifications. Réessaie dans un instant.');
    } finally { setDeviceBusy(false); }
  }
  const hhmm = (t: string | null) => (t ?? '').slice(0, 5);
  const setTime = (key: 'quiet_start' | 'quiet_end', v: string) => {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(v)) return setError('Saisis une heure entre 00:00 et 23:59.');
    const other = key === 'quiet_start' ? prefs!.quiet_end : prefs!.quiet_start;
    if (v === other?.slice(0, 5)) return setError('Le début et la fin du mode silencieux doivent être différents.');
    void update({ [key]: v });
  };

  return (
    <Screen edges={[]}>
      <ErrorText error={error ?? loadError ?? deviceError} />
      {saving ? <T muted size={13}>Enregistrement…</T> : null}
      <Section title="Sur cet appareil">
        <T weight="semibold">{device?.subscribed ? 'Notifications activées' : device?.permission === 'denied' ? 'Notifications bloquées par le navigateur' : 'Notifications à activer'}</T>
        <T muted size={13}>{device?.needsInstall
          ? 'Sur iPhone ou iPad : dans Safari, Partager → Ajouter à l’écran d’accueil. Ouvre ensuite l’icône Party pour activer les notifications.'
          : device && !device.supported
            ? 'Ce navigateur ne propose pas les notifications web. Les annonces et l’activité restent accessibles ici.'
            : device?.permission === 'denied'
              ? 'Autorise les notifications dans les réglages du navigateur, puis reviens ici.'
              : 'L’activation concerne ce navigateur. Active aussi les notifications sur tes autres appareils si tu souhaites les y recevoir.'}</T>
        {device?.subscribed ? (
          <Button label="Envoyer une notification d’essai" variant="secondary" loading={deviceBusy} onPress={() => deviceAction(true)} />
        ) : device?.supported && !device.needsInstall && device.permission !== 'denied' ? (
          <Button label="Activer sur cet appareil" loading={deviceBusy} onPress={() => deviceAction()} />
        ) : null}
        <Button label="Vérifier l’activation" small variant="ghost" disabled={deviceBusy} onPress={reloadDevice} />
        {deviceMessage ? <View role="status"><T size={13}>{deviceMessage}</T></View> : null}
      </Section>
      <Section title="Annonces admin · obligatoires">
        <T>Les annonces concernent tout le groupe. Elles restent toujours visibles dans Activité, même après lecture.</T>
        <T muted size={13}>Elles ne se désactivent pas ici et ne dépendent ni des catégories, ni des tags, ni de la sourdine d’un événement. Leur envoi sur l’appareil nécessite l’autorisation du navigateur.</T>
        <LinkRow label="Lire les annonces admin" onPress={() => router.push('/announcements')} />
      </Section>
      <Section title="Général">
        <ToggleRow disabled={saving} label="Alertes facultatives" hint="Couper les alertes choisies ci-dessous. Les annonces admin restent activées." value={prefs.push_enabled} onChange={(v) => update({ push_enabled: v })} />
        <ToggleRow
          disabled={saving}
          label="Mode silencieux"
          hint="Toutes les notifications, y compris les annonces admin, attendent la fin de cette plage (heure du groupe)."
          value={quiet}
          onChange={(v) => update(v ? { quiet_start: '23:00', quiet_end: '08:00' } : { quiet_start: null, quiet_end: null })}
        />
        {quiet ? (
          <View style={s.row}>
            <View style={{ flex: 1 }}>
              <Field label="De" key={prefs.quiet_start} editable={!saving} defaultValue={hhmm(prefs.quiet_start)} onEndEditing={(e) => setTime('quiet_start', e.nativeEvent.text)} placeholder="23:00" />
            </View>
            <View style={{ flex: 1 }}>
              <Field label="À" key={prefs.quiet_end} editable={!saving} defaultValue={hhmm(prefs.quiet_end)} onEndEditing={(e) => setTime('quiet_end', e.nativeEvent.text)} placeholder="08:00" />
            </View>
          </View>
        ) : null}
      </Section>

      <Section title="Nouveaux événements">
        <Segmented<NotificationPrefs['new_event']> value={prefs.new_event} disabled={saving}
          onChange={(new_event) => update({ new_event })}
          options={[{ key: 'all', label: 'Tous' }, { key: 'subscribed', label: 'Mes abonnements' }, { key: 'none', label: 'Aucun' }]} />
        <T muted size={13}>{prefs.new_event === 'subscribed'
          ? 'Une catégorie OU un tag auquel tu es abonné suffit pour recevoir l’alerte.'
          : prefs.new_event === 'all' ? 'Tous les nouveaux événements visibles pour toi.' : 'Aucune alerte de nouvel événement. Les annonces admin restent actives.'}</T>
        <LinkRow
          label="Choisir mes catégories et mes tags"
          hint="Soirée, bar, cinéma…"
          onPress={() => router.push('/settings/subscriptions')}
        />
      </Section>

      <Section title="Événements auxquels je participe">
        <ToggleRow disabled={saving} label="Modifié ou annulé" hint="Date, heure, lieu, annulation" value={prefs.event_changed} onChange={(v) => update({ event_changed: v })} />
        <ToggleRow disabled={saving} label="Nouveau sondage" value={prefs.poll_new} onChange={(v) => update({ poll_new: v })} />
        <ToggleRow disabled={saving} label="Date fixée" hint="Quand un sondage de dates est clos" value={prefs.date_fixed} onChange={(v) => update({ date_fixed: v })} />
        <ToggleRow disabled={saving} label="Relance si je n’ai pas voté" hint="24 h avant la fin d’un sondage de dates" value={prefs.poll_nudge} onChange={(v) => update({ poll_nudge: v })} />
        <ToggleRow disabled={saving} label="Place libérée" hint="Si je suis sur liste d’attente" value={prefs.waitlist} onChange={(v) => update({ waitlist: v })} />
      </Section>

      <Section title="Rappels">
        <T muted size={13}>Pour les événements où tu es Présent ou Peut-être (si l’organisateur les a activés)</T>
        <View style={s.wrap}>
          {(Object.keys(reminderLabels) as Reminder[]).map((r) => (
            <Chip
              key={r}
              disabled={saving}
              label={reminderLabels[r]}
              selected={prefs.reminders.includes(r)}
              onPress={() => update({ reminders: prefs.reminders.includes(r) ? prefs.reminders.filter((x) => x !== r) : [...prefs.reminders, r] })}
            />
          ))}
        </View>
      </Section>

      <Section title="Discussions">
        <Segmented<ChatMode>
          disabled={saving}
          value={prefs.chat}
          onChange={(chat) => update({ chat })}
          options={[{ key: 'all', label: 'Tous' }, { key: 'mentions', label: 'Mentions' }, { key: 'none', label: 'Aucun' }]}
        />
        <T muted size={13}>{chatHints[prefs.chat]}</T>
      </Section>

      <Section title="Organisateur et admin">
        <ToggleRow disabled={saving} label="Réponses à mes événements" hint="Quand quelqu’un répond Présent, Peut-être ou Absent" value={prefs.rsvp_mine} onChange={(v) => update({ rsvp_mine: v })} />
        {isAdmin ? <ToggleRow disabled={saving} label="Nouvelle proposition à valider" value={prefs.proposals} onChange={(v) => update({ proposals: v })} /> : null}
      </Section>

      <T muted size={12}>Tu peux aussi couper les alertes d’un événement depuis sa page (Sourdine). Les annonces admin restent actives. La musique et les jeux gardent leurs propres réglages.</T>
    </Screen>
  );
}
