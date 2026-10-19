import { router } from 'expo-router';
import { useRef, useState } from 'react';
import { View } from 'react-native';

import { Button, Chip, ErrorText, Field, LinkRow, Screen, s, Section, Segmented, T, ToggleRow } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { check, must, supabase } from '@/lib/supabase';
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
  const hhmm = (t: string | null) => (t ?? '').slice(0, 5);
  const setTime = (key: 'quiet_start' | 'quiet_end', v: string) => {
    if (!/^([01]\d|2[0-3]):[0-5]\d$/.test(v)) return setError('Saisis une heure entre 00:00 et 23:59.');
    const other = key === 'quiet_start' ? prefs!.quiet_end : prefs!.quiet_start;
    if (v === other?.slice(0, 5)) return setError('Le début et la fin du mode silencieux doivent être différents.');
    void update({ [key]: v });
  };

  return (
    <Screen edges={[]}>
      <ErrorText error={error ?? loadError} />
      {saving ? <T muted size={13}>Enregistrement…</T> : null}
      <Section title="Dans Party">
        <T muted>Retrouve les notifications des événements dans Activité. Les notifications de musique se règlent séparément dans l’onglet Musique.</T>
      </Section>
      <Section title="Général">
        <ToggleRow disabled={saving} label="Notifications push" hint="Sinon, tout reste visible dans l’onglet Activité" value={prefs.push_enabled} onChange={(v) => update({ push_enabled: v })} />
        <ToggleRow
          disabled={saving}
          label="Mode silencieux"
          hint="Les notifications sont gardées et envoyées à la fin"
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
        <LinkRow
          label={{ all: 'Tous les événements', subscribed: 'Mes abonnements seulement', none: 'Jamais' }[prefs.new_event]}
          hint="Choisir mes catégories et mes tags"
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

      <T muted size={12}>Tu peux aussi couper un seul événement depuis sa page (Sourdine).</T>
    </Screen>
  );
}
