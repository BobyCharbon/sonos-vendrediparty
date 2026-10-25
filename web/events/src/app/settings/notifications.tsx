import { router, useLocalSearchParams } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { SubscriptionPicker } from '@/components/SubscriptionPicker';
import { Button, Chip, ErrorText, Field, LinkRow, Screen, s, Section, Segmented, T, ToggleRow } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { check, must, supabase } from '@/lib/supabase';
import { enableWebPush, testWebPush, webPushState, type WebPushState } from '@/lib/push';
import type { ChatMode, NewEventScope, NotificationPrefs, Reminder } from '@/lib/types';

const reminderLabels: Record<Reminder, string> = { '7d': '7 jours avant', '1d': 'La veille', '2h': '2 heures avant', '0h': 'Au début' };
const newEventHints: Record<NewEventScope, string> = {
  all: 'Chaque nouvelle sortie visible pour toi. Choisis « Si abonné » pour n’être prévenu que des catégories et tags que tu suis.',
  subscribed: 'Seulement les sorties qui ont au moins une catégorie OU un tag que tu suis ci-dessous.',
  none: 'Aucune alerte de nouvelle sortie. Les annonces admin restent actives.',
};
const chatHints: Record<ChatMode, string> = {
  all: 'Chaque message des discussions des événements auxquels tu participes.',
  mentions: 'Seulement quand quelqu’un écrit @ton prénom ou répond à ton message.',
  none: 'Aucune notification. Les messages restent lisibles dans l’app.',
};

export default function NotificationSettings() {
  const me = useMe();
  // Arrivée depuis le filtre « Mes abonnements » de la liste : la liste à cocher reste visible quel que soit le choix.
  const fromFilter = useLocalSearchParams<{ topics?: string }>().topics === '1';
  const { can } = useAuth();
  const isAdmin = can('events.approve');  // reçoit les propositions à valider
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
        <T weight="semibold">{!device ? 'Vérification de l’appareil…' : device.subscribed ? 'Notifications activées' : device.needsInstall ? 'Ajouter Party à l’écran d’accueil' : !device.supported ? 'Notifications indisponibles ici' : device.permission === 'denied' ? 'Notifications bloquées par le navigateur' : 'Notifications à activer'}</T>
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
      <Section title="Pause et heures de silence">
        <ToggleRow
          disabled={saving}
          label="Recevoir mes alertes"
          hint="Éteins pour mettre en pause toutes les alertes choisies plus bas, sans perdre tes réglages. Les annonces admin continuent d’arriver."
          value={prefs.push_enabled}
          onChange={(v) => update({ push_enabled: v })}
        />
        <ToggleRow
          disabled={saving}
          label="Heures de silence"
          hint="Pendant cette plage, rien ne sonne, pas même les annonces admin : tout arrive à la fin de la plage (heure du groupe)."
          value={quiet}
          onChange={(v) => update(v ? { quiet_start: '23:00', quiet_end: '08:00' } : { quiet_start: null, quiet_end: null })}
        />
        {quiet ? (
          <View style={s.row}>
            <View style={{ flex: 1 }}>
              <Field label="Début (HH:MM)" key={prefs.quiet_start} editable={!saving} defaultValue={hhmm(prefs.quiet_start)} onEndEditing={(e) => setTime('quiet_start', e.nativeEvent.text)} placeholder="23:00" />
            </View>
            <View style={{ flex: 1 }}>
              <Field label="Fin (HH:MM)" key={prefs.quiet_end} editable={!saving} defaultValue={hhmm(prefs.quiet_end)} onEndEditing={(e) => setTime('quiet_end', e.nativeEvent.text)} placeholder="08:00" />
            </View>
          </View>
        ) : null}
      </Section>

      <Section title="Nouvelles sorties et abonnements">
        <T muted size={13}>Quand une nouvelle sortie est publiée, me prévenir :</T>
        <Segmented<NotificationPrefs['new_event']> value={prefs.new_event} disabled={saving}
          onChange={(new_event) => update({ new_event })}
          options={[{ key: 'all', label: 'Toujours' }, { key: 'subscribed', label: 'Si abonné' }, { key: 'none', label: 'Jamais' }]} />
        <T muted size={13}>{newEventHints[prefs.new_event]}</T>
        {prefs.new_event === 'subscribed' || fromFilter ? <SubscriptionPicker disabled={saving} /> : null}
      </Section>

      <Section title="Sorties où je suis inscrit">
        <ToggleRow disabled={saving} label="Sortie modifiée ou annulée" hint="Changement de date, d’heure ou de lieu, ou annulation" value={prefs.event_changed} onChange={(v) => update({ event_changed: v })} />
        <ToggleRow disabled={saving} label="Nouveau sondage" hint="L’organisateur ajoute un sondage à la sortie" value={prefs.poll_new} onChange={(v) => update({ poll_new: v })} />
        <ToggleRow disabled={saving} label="Date choisie" hint="Le sondage de dates est terminé et la date est fixée" value={prefs.date_fixed} onChange={(v) => update({ date_fixed: v })} />
        <ToggleRow disabled={saving} label="Rappel pour voter" hint="24 h avant la fin d’un sondage de dates, seulement si tu n’as pas encore voté" value={prefs.poll_nudge} onChange={(v) => update({ poll_nudge: v })} />
        <ToggleRow disabled={saving} label="Place libérée" hint="Tu es sur liste d’attente et une place se libère" value={prefs.waitlist} onChange={(v) => update({ waitlist: v })} />
      </Section>

      <Section title="Rappels avant la sortie">
        <T muted size={13}>Pour les sorties où tu as répondu Présent ou Peut-être, si l’organisateur a activé les rappels. Tu peux en choisir plusieurs.</T>
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

      <Section title="Messages des discussions">
        <Segmented<ChatMode>
          disabled={saving}
          value={prefs.chat}
          onChange={(chat) => update({ chat })}
          options={[{ key: 'all', label: 'Tous' }, { key: 'mentions', label: 'Si on me cite' }, { key: 'none', label: 'Aucun' }]}
        />
        <T muted size={13}>{chatHints[prefs.chat]}</T>
      </Section>

      <Section title="Quand j’organise">
        <ToggleRow disabled={saving} label="Réponses à mes sorties" hint="Quelqu’un répond Présent, Peut-être ou Absent à une sortie que j’organise" value={prefs.rsvp_mine} onChange={(v) => update({ rsvp_mine: v })} />
        {isAdmin ? <ToggleRow disabled={saving} label="Proposition à valider" hint="Un membre propose une sortie qui attend la validation d’un admin" value={prefs.proposals} onChange={(v) => update({ proposals: v })} /> : null}
      </Section>

      <Section title="Annonces admin · toujours reçues">
        <T muted size={13}>Les messages des admins à tout le groupe ne se désactivent pas, même avec la pause, une sourdine ou sans abonnement. Ils restent lisibles dans Activité.</T>
        <LinkRow label="Lire les annonces admin" onPress={() => router.push('/announcements')} />
      </Section>

      <T muted size={12}>Pour couper une seule sortie, utilise « Sourdine » sur sa page. La musique et les jeux ont leurs propres réglages.</T>
    </Screen>
  );
}
