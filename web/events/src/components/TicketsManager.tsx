import { useCallback, useEffect, useState } from 'react';
import { StyleSheet, View } from 'react-native';

import { colors, radius } from '@/lib/theme';
import { fetchCheckins, issueAllTickets, issueTicket, setTicketsEnabled, type TicketPerson } from '@/lib/tickets';

import { PersonName } from './PersonName';
import { Avatar, Button, ErrorText, Section, T, ToggleRow } from './ui';

type Props = {
  eventId: string;
  enabled: boolean;
  /** Organisateur, co-organisateur, admin : allume ou éteint l'option (les droits de l'entrée seuls remettent). */
  canToggle: boolean;
  /** Après un changement de l'option : la page relit l'événement. */
  onToggled: () => void;
  /** Change quand les réponses changent (temps réel de la page) : la liste est relue. */
  refreshKey?: string;
  /** false : seulement l'option et « Remettre à tous » (l'écran d'entrée a déjà sa liste). */
  list?: boolean;
  /** Prévenu après chaque remise (l'écran d'entrée relit sa liste). */
  onIssued?: () => void;
};

/**
 * « Billets QR » d'un événement, côté organisateur (demande de l'admin, 4.11) : l'option (éteinte par défaut), puis
 * la remise des billets aux présents, un à un ou à tous. Seul un billet remis montre son QR au participant ; une
 * place payée confirmée remet aussi le billet.
 */
export function TicketsManager({ eventId, enabled, canToggle, onToggled, refreshKey, list = true, onIssued }: Props) {
  const [people, setPeople] = useState<TicketPerson[] | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const load = useCallback(() => fetchCheckins(eventId).then(
    (rows) => { setPeople(rows); setError(null); },
    (e: unknown) => setError(e instanceof Error ? e.message : 'La liste ne se charge pas. Réessaie.'),
  ), [eventId]);
  useEffect(() => { if (enabled) void load(); }, [load, enabled, refreshKey]);

  async function run(key: string, action: () => Promise<unknown>) {
    setBusy(key);
    setDone(null);
    try {
      await action();
      setError(null);
      if (enabled) await load();
      onIssued?.();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'La connexion a échoué. Réessaie.');
    } finally {
      setBusy(null);
    }
  }

  const present = (people ?? []).filter((p) => !p.waitlisted && p.status === 'yes');
  const waiting = present.filter((p) => !p.issued);

  return (
    <Section
      title="Billets QR"
      right={enabled && people ? <T size={13} weight="bold" color={colors.mint}>{present.length - waiting.length} / {present.length} remis</T> : undefined}
    >
      {canToggle ? (
        <ToggleRow
          disabled={busy === 'toggle'}
          label="Billets QR"
          hint={enabled ? 'Remets son billet à chaque présent : il voit alors son QR (et peut l’ajouter à Apple Wallet).'
            : 'Éteint : personne n’a de QR. Allume-le pour remettre des billets à scanner à l’entrée.'}
          value={enabled}
          onChange={(v) => { void run('toggle', async () => { await setTicketsEnabled(eventId, v); onToggled(); }); }}
        />
      ) : (
        <T muted size={13}>{enabled ? 'Billets QR activés par l’organisateur.' : 'Billets QR désactivés : l’organisateur les active dans l’événement.'}</T>
      )}
      {enabled ? (
        <>
          <Button
            small
            label={waiting.length ? `Remettre à tous les présents (${waiting.length})` : 'Tous les présents ont leur billet ✓'}
            disabled={!waiting.length}
            loading={busy === 'all'}
            onPress={() => run('all', async () => {
              const n = await issueAllTickets(eventId);
              setDone(n ? `${n} billet${n > 1 ? 's' : ''} remis : chacun est prévenu.` : 'Tous les présents ont déjà leur billet.');
            })}
          />
          {done ? <T size={13} color={colors.mint}>{done}</T> : null}
          {list ? present.map((p) => (
            <View key={p.user_id} style={st.row}>
              <Avatar id={p.user_id} name={p.display_name} photo={p.avatar_url} size={34} />
              <View style={{ flex: 1, minWidth: 0 }}>
                <PersonName id={p.user_id} pseudo={p.display_name} weight="semibold" />
                <T size={12} color={p.issued ? colors.mint : colors.muted}>{p.issued ? '✓ Billet remis' : p.paid ? 'Payé · billet à remettre' : 'Billet pas encore remis'}</T>
              </View>
              <IssueButton person={p} busy={busy === p.user_id} onPress={(issued) => run(p.user_id, () => issueTicket(eventId, p.user_id, issued))} />
            </View>
          )) : null}
          {list && people && !present.length ? <T muted size={13}>Personne n’est encore noté présent.</T> : null}
        </>
      ) : null}
      <ErrorText error={error} />
    </Section>
  );
}

/** « Remettre le billet » / « Retirer » pour un présent (liste des présents, écran d'entrée). */
export function IssueButton({ person, busy, onPress }: { person: TicketPerson; busy?: boolean; onPress: (issued: boolean) => void }) {
  return person.issued ? (
    <Button small variant="ghost" label="Retirer" loading={busy} onPress={() => onPress(false)} />
  ) : (
    <Button small label="Remettre le billet" loading={busy} onPress={() => onPress(true)} />
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', alignItems: 'center', gap: 10, paddingVertical: 6, paddingHorizontal: 4, borderRadius: radius.md, flexWrap: 'wrap' },
});
