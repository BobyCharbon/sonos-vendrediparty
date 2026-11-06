import { router, useLocalSearchParams } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { ChatsPause } from '@/components/NotificationPause';
import { PartyNotifications } from '@/components/PartyNotifications';
import { ZicouReactionsRow } from '@/components/ZicouReactionsRow';
import { compagnonOn, discussionsOn } from '@/lib/features';
import { SubscriptionPicker } from '@/components/SubscriptionPicker';
import { Button, Chip, ErrorText, Field, LinkRow, Screen, s, Section, Segmented, T, ToggleRow } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { check, must, supabase } from '@/lib/supabase';
import { enableWebPush, testWebPush, webPushState, type WebPushState } from '@/lib/push';
import type { ChatMode, NewEventScope, NotificationPrefs, Reminder } from '@/lib/types';

const reminderLabels: Record<Reminder, string> = { '7d': '7 jours avant', '1d': 'La veille', '2h': '2 heures avant', '0h': 'Au début' };
const newEventHints: Record<NewEventScope, string> = {
  all: 'Chaque nouvel événement visible pour toi. Choisis « Si abonné » pour n’être prévenu que des catégories et tags que tu suis.',
  subscribed: 'Seulement les événements qui ont au moins une catégorie OU un tag que tu suis ci-dessous.',
  none: 'Aucune alerte de nouvel événement. Les annonces admin restent actives.',
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
          hint="Éteins pour couper toutes les alertes choisies plus bas, sans perdre tes réglages. Les annonces des admins ont leur propre réglage."
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

      <Section title="Nouveaux événements et abonnements">
        <T muted size={13}>Quand un nouvel événement est publié, me prévenir :</T>
        <Segmented<NotificationPrefs['new_event']> value={prefs.new_event} disabled={saving}
          onChange={(new_event) => update({ new_event })}
          options={[{ key: 'all', label: 'Toujours' }, { key: 'subscribed', label: 'Si abonné' }, { key: 'none', label: 'Jamais' }]} />
        <T muted size={13}>{newEventHints[prefs.new_event]}</T>
        {prefs.new_event === 'subscribed' || fromFilter ? <SubscriptionPicker disabled={saving} /> : null}
      </Section>

      <Section title="Événements où je suis inscrit">
        <ToggleRow disabled={saving} label="Événement modifié ou annulé" hint="Changement de date, d’heure ou de lieu, ou annulation" value={prefs.event_changed} onChange={(v) => update({ event_changed: v })} />
        <ToggleRow disabled={saving} label="Nouveau sondage" hint="L’organisateur ajoute un sondage à l’événement" value={prefs.poll_new} onChange={(v) => update({ poll_new: v })} />
        <ToggleRow disabled={saving} label="Date choisie" hint="Le sondage de dates est terminé et la date est fixée" value={prefs.date_fixed} onChange={(v) => update({ date_fixed: v })} />
        <ToggleRow disabled={saving} label="Un organisateur répond pour moi" hint="Il te note présent, peut-être ou absent à sa place" value={prefs.rsvp_set !== false} onChange={(v) => update({ rsvp_set: v })} />
        <ToggleRow disabled={saving} label="Invitation à un événement privé" hint="On t’invite à un événement réservé aux invités" value={prefs.invites !== false} onChange={(v) => update({ invites: v })} />
        <ToggleRow disabled={saving} label="Rappel pour voter" hint="24 h avant la fin d’un sondage de dates, seulement si tu n’as pas encore voté" value={prefs.poll_nudge} onChange={(v) => update({ poll_nudge: v })} />
        <ToggleRow disabled={saving} label="Place libérée" hint="Tu es sur liste d’attente et une place se libère" value={prefs.waitlist} onChange={(v) => update({ waitlist: v })} />
        <ToggleRow disabled={saving} label="Paiement de ma place confirmé" hint="L’organisateur a reçu ton paiement (ou ne l’a pas reçu) après ton « J’ai payé »" value={prefs.ticket_pay_confirmed !== false} onChange={(v) => update({ ticket_pay_confirmed: v })} />
        <ToggleRow disabled={saving} label="Billet prêt" hint="L’organisateur t’a remis ton billet QR : il s’affiche sur l’événement" value={prefs.ticket_issued !== false} onChange={(v) => update({ ticket_issued: v })} />
      </Section>

      <Section title="Rappels avant l’événement">
        <T muted size={13}>Pour les événements où tu as répondu Présent ou Peut-être. C’est toi qui choisis, pour tous les événements ; tu peux en cocher plusieurs.</T>
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
        {/* Deux pauses distinctes (avis de l'admin) : discussions des événements ici, groupes plus bas. */}
        <ChatsPause scope="event_chats" />
      </Section>

      {/* Discussions éteintes (production) : seuls les réglages des groupes restent (invitation, nouveau membre). */}
      <Section title={discussionsOn ? 'Discussions des groupes' : 'Groupes'}>
        {discussionsOn ? <>
        <ToggleRow disabled={saving} label="Messages des groupes" hint="Les messages de tes groupes, selon le choix de chaque groupe (tous, si on me cite ou rien)" value={prefs.group_messages !== false} onChange={(v) => update({ group_messages: v })} />
        {/* Messages directs (conversation privée à deux) : leur propre interrupteur ; la pause des Discussions les couvre aussi. */}
        <ToggleRow disabled={saving} label="Messages directs" hint="« Nouveau message de … » quand quelqu’un t’écrit en privé (chaque conversation peut aussi être mise en sourdine)" value={prefs.direct_messages !== false} onChange={(v) => update({ direct_messages: v })} />
        <ChatsPause scope="chats" />
        {/* Groupes de Discussions : @tout et @annonce préviennent tout le groupe ; chacun peut le couper ici. */}
        <ToggleRow disabled={saving} label="Annonces et @tout des groupes"
          hint="Quand quelqu’un écrit @tout ou fait une annonce (@annonce) dans un de tes groupes. Les @surnom et les réponses restent notifiés selon le réglage de chaque groupe."
          value={prefs.group_broadcasts !== false} onChange={(v) => update({ group_broadcasts: v })} />
        </> : null}
        <ToggleRow disabled={saving} label="Invitation dans un groupe" hint="Quelqu’un t’ajoute à un groupe" value={prefs.group_invites !== false} onChange={(v) => update({ group_invites: v })} />
        <ToggleRow disabled={saving} label="Quelqu’un rejoint mon groupe" hint="Un membre entre dans un groupe que tu as créé" value={prefs.group_joins !== false} onChange={(v) => update({ group_joins: v })} />
      </Section>

      {/* Mes amis dans Party : chaque type a son interrupteur, aussi dans les Réglages de l'app iPhone. */}
      <Section title="Amis">
        <ToggleRow disabled={saving} label="Quelqu’un rejoint Party grâce à moi" hint="Une personne s’inscrit avec ton lien d’invitation" value={prefs.referral_joins !== false} onChange={(v) => update({ referral_joins: v })} />
        <ToggleRow disabled={saving} label="Un contact arrive sur Party" hint="Dans l’app iPhone : quelqu’un de tes contacts vient de s’inscrire" value={prefs.contact_joins !== false} onChange={(v) => update({ contact_joins: v })} />
      </Section>

      {/* Compagnon (jeu de l'onglet Jeux) : un interrupteur par type, aussi dans les Réglages de l'app iPhone. Au plus une
          notification par jour (hors alertes vitales), jamais la nuit ni pendant une soirée. En bêta : absent hors site de test. */}
      {compagnonOn ? <Section title="Zicou">
        <ToggleRow disabled={saving} label="Rappel du jour" hint="Une fois par jour au plus, vers l’heure où tu passes d’habitude, si tu n’es pas encore venu" value={prefs.pet_daily !== false} onChange={(v) => update({ pet_daily: v })} />
        <ToggleRow disabled={saving} label="Alertes vitales" hint="Deux alertes au plus avant qu’il ne s’envole, quand son ventre est vide depuis longtemps" value={prefs.pet_alerts !== false} onChange={(v) => update({ pet_alerts: v })} />
        <ToggleRow disabled={saving} label="Cadeau d’un ami" hint="Un ami lui a fait un câlin ou apporté un goûter" value={prefs.pet_gifts !== false} onChange={(v) => update({ pet_gifts: v })} />
        <ToggleRow disabled={saving} label="Paliers de série" hint="Le jour où ta série 🔥 atteint un palier (3, 7, 14, 30 jours…)" value={prefs.pet_streaks !== false} onChange={(v) => update({ pet_streaks: v })} />
        <ToggleRow disabled={saving} label="Barre pleine" hint="Ta barre 🎁 est pleine : deux fois par jour au plus, jamais la nuit (23 h – 8 h)" value={prefs.pet_bar !== false} onChange={(v) => update({ pet_bar: v })} />
        <ZicouReactionsRow disabled={saving} />
      </Section> : null}

      <Section title="Quand j’organise">
        <ToggleRow disabled={saving} label="Réponses à mes événements" hint="Quelqu’un répond Présent, Peut-être ou Absent à un événement que j’organise" value={prefs.rsvp_mine} onChange={(v) => update({ rsvp_mine: v })} />
        <ToggleRow disabled={saving} label="Quelqu’un rejoint par le lien" hint="Une personne s’inscrit à ton événement avec son lien d’invitation" value={prefs.link_join !== false} onChange={(v) => update({ link_join: v })} />
        <ToggleRow disabled={saving} label="Quelqu’un dit avoir payé" hint="Sur un événement payant que j’organise, une personne touche « J’ai payé » : à confirmer quand tu as reçu l’argent" value={prefs.ticket_pay_declared !== false} onChange={(v) => update({ ticket_pay_declared: v })} />
        <ToggleRow disabled={saving} label="Ma proposition validée ou refusée" hint="Un admin publie ou refuse l’événement que tu as proposé" value={prefs.proposal_result !== false} onChange={(v) => update({ proposal_result: v })} />
        <ToggleRow disabled={saving} label="Réponse du groupe à mes demandes" hint="Ton annonce au groupe est acceptée, refusée ou partie d’office après 48 h ; ton événement est accepté ou refusé par le groupe" value={prefs.announce_results !== false} onChange={(v) => update({ announce_results: v })} />
        <ToggleRow disabled={saving} label="Annonce à valider" hint="Un membre de ton groupe veut prévenir le groupe d’un événement (tu es créateur, admin ou organisateur du groupe)" value={prefs.announce_requests !== false} onChange={(v) => update({ announce_requests: v })} />
        <ToggleRow disabled={saving} label="Événement à valider pour mon groupe" hint="Un membre propose un événement à ton groupe, réglé « avec validation »" value={prefs.group_event_requests !== false} onChange={(v) => update({ group_event_requests: v })} />
        {isAdmin ? <ToggleRow disabled={saving} label="Proposition à valider" hint="Un membre propose un événement qui attend la validation d’un admin" value={prefs.proposals} onChange={(v) => update({ proposals: v })} /> : null}
      </Section>

      {/* Modération commune : chaque type a son interrupteur (règle permanente). */}
      <Section title="Modération">
        <ToggleRow disabled={saving} label="Message de la modération" hint="Un modérateur t’avertit qu’un de tes contenus ne respecte pas les conditions d’utilisation" value={prefs.moderation_notices !== false} onChange={(v) => update({ moderation_notices: v })} />
        {can('moderation.reports') ? <ToggleRow disabled={saving} label="Nouveau signalement" hint="Un message, un profil ou une photo vient d’être signalé (le contenu reste dans Administration › Signalements)" value={prefs.moderation_reports !== false} onChange={(v) => update({ moderation_reports: v })} /> : null}
      </Section>

      <Section title="Annonces des admins">
        <ToggleRow disabled={saving} label="Annonces des admins" hint="Les messages des admins à tout le groupe. Coupées, elles restent lisibles dans Activité." value={prefs.announcements !== false} onChange={(v) => update({ announcements: v })} />
        <LinkRow label="Lire les annonces admin" onPress={() => router.push('/announcements')} />
      </Section>

      <PartyNotifications />

      <T muted size={12}>Pour couper un seul événement, utilise « Sourdine » sur sa page.</T>
    </Screen>
  );
}
