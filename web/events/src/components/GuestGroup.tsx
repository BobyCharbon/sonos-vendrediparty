import { router, type Href } from 'expo-router';
import { useState, type ReactNode } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { useTermsGate } from './TermsSheet';
import { Button, ErrorText, Input, T, ToggleRow } from './ui';
import { useQuery } from '@/lib/data';
import {
  JOIN_DETAIL, fetchEventGuestGroup, groupLabel, joinTitle, keepBand, membersLine, saveGuestGroupSetting, setGuestGroupChoice,
  takeGroupJoinNote, type EventGuestGroup, type GuestGroupCard, type GuestGroupSetting, type ManagedGroup,
} from '@/lib/guestGroup';
import { isTermsError } from '@/lib/moderation';
import { enter, pressTransition } from '@/lib/motion';
import { supabase } from '@/lib/supabase';
import { colors, radius } from '@/lib/theme';

/**
 * La case « Rejoindre aussi le groupe » (avis de conformité du 17.11) : DÉCOCHÉE par défaut, grande, juste sous les
 * boutons de réponse ; elle vaut pour les trois réponses et ne bloque jamais la réponse. Tout est dit : ce que voient les
 * membres, le numéro caché, quitter quand on veut, le nombre de membres.
 */
export function GuestGroupCheck({ card, value, onChange, disabled = false }: {
  card: GuestGroupCard; value: boolean; onChange: (v: boolean) => void; disabled?: boolean;
}) {
  return (
    <Pressable accessibilityRole="checkbox" accessibilityState={{ checked: value, disabled }} aria-checked={value}
      accessibilityLabel={joinTitle(card)} accessibilityHint={JOIN_DETAIL} disabled={disabled} onPress={() => onChange(!value)}
      testID="guest-group-check"
      style={({ pressed }) => [st.check, value && st.checkOn, pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
      <View style={[st.box, value && st.boxOn]}>
        {value ? <T size={16} weight="bold" color={colors.onMint} style={enter('pop')}>✓</T> : null}
      </View>
      <View style={{ flex: 1, gap: 4 }}>
        <T size={16} weight="bold">{joinTitle(card)}</T>
        <T size={13} weight="semibold" color={colors.lavender}>👥 {membersLine(card.members)}</T>
        <T size={13} color={colors.textSoft}>{JOIN_DETAIL}</T>
      </View>
    </Pressable>
  );
}

/** Personne déjà répondue sans cocher (ou avant que l'option existe) : un bouton, sans relance ni notification. */
export function GuestGroupJoin({ eventId, data, onJoined }: { eventId: string; data: EventGuestGroup; onJoined: () => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);
  const card = data.group;
  if (!card) return null;
  if (done || data.in_group) {
    return (
      <View style={[st.joined, enter('fade')]}>
        <T size={14} weight="semibold" color={colors.mint}>👥 Tu es dans le groupe « {groupLabel(card)} »</T>
        <Button small variant="ghost" label="Voir" onPress={() => router.push(`/chats/${card.id}` as Href)} />
      </View>
    );
  }
  if (!data.offer || !data.answered) return null;
  async function join() {
    setBusy(true);
    setError(null);
    try {
      const r = await setGuestGroupChoice(eventId, true);
      if (r.status === 'joined' || r.status === 'already') { setDone(r.status); onJoined(); }
      else setError('Tu ne peux pas rejoindre ce groupe.');
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <View style={st.offer}>
      <T size={15} weight="bold">👥 {card.owner ? `${card.owner} réunit ses invités` : 'Les invités se retrouvent'} dans « {groupLabel(card)} »</T>
      <T size={13} color={colors.textSoft}>{membersLine(card.members)}. {JOIN_DETAIL}</T>
      <Button small label="Rejoindre le groupe" loading={busy} onPress={() => void join()} />
      <ErrorText error={error} />
    </View>
  );
}

/** Réglage de l'organisateur : interrupteur (éteint par défaut), « Nouveau groupe » au nom du titre, ou un groupe qu'il gère. */
export function GuestGroupSettingCard({ value, onChange, groups, disabled = false }: {
  value: GuestGroupSetting; onChange: (v: GuestGroupSetting) => void; groups: ManagedGroup[]; disabled?: boolean;
}) {
  const choose = (group: string) => onChange({ ...value, group });
  return (
    <View style={{ gap: 10 }}>
      <ToggleRow label="👥 Réunir tes invités dans un groupe" disabled={disabled}
        hint="Chaque invité choisit lui-même : une case, décochée, sous ses réponses. Pour les réinviter d’un toucher."
        value={value.on} onChange={(on) => onChange({ ...value, on, group: value.group ?? 'new' })} />
      {value.on ? (
        <View style={[{ gap: 8 }, enter('drop')]}>
          <Radio selected={value.group === 'new'} title="Nouveau groupe" onPress={() => choose('new')} disabled={disabled}>
            {value.group === 'new' ? (
              <Input value={value.name} onChangeText={(name) => onChange({ ...value, name })} maxLength={60} editable={!disabled}
                accessibilityLabel="Nom du nouveau groupe" placeholder="Nom du groupe" />
            ) : null}
          </Radio>
          {groups.map((g) => (
            <Radio key={g.id} selected={value.group === g.id} title={groupLabel(g)} hint={`Ton groupe · ${membersLine(g.members)}`}
              onPress={() => choose(g.id)} disabled={disabled} />
          ))}
          <T muted size={12}>
            Entre seulement qui coche la case en répondant (Je viens, Peut-être ou Pas présent), prévenu, « Quitter » d’un toucher.
            Jamais quelqu’un qui t’a bloqué ni quelqu’un qui a quitté le groupe. Le groupe n’est pas prévenu.
          </T>
        </View>
      ) : null}
    </View>
  );
}

function Radio({ selected, title, hint, onPress, disabled, children }: {
  selected: boolean; title: string; hint?: string; onPress: () => void; disabled?: boolean; children?: ReactNode;
}) {
  return (
    <Pressable accessibilityRole="radio" accessibilityState={{ selected, disabled }} aria-checked={selected} accessibilityLabel={title}
      onPress={onPress} disabled={disabled}
      style={({ pressed }) => [st.radio, selected && st.radioOn, pressTransition, pressed && { transform: [{ scale: 0.98 }] }]}>
      <View style={[st.dot, selected && st.dotOn]} />
      <View style={{ flex: 1, gap: 6 }}>
        <T weight="bold">{title}</T>
        {hint ? <T muted size={12}>{hint}</T> : null}
        {children}
      </View>
    </Pressable>
  );
}

/** Enregistre le réglage ; « Nouveau groupe » crée le groupe (CGU d'abord si besoin, puis un seul nouvel essai). */
export function useSaveGuestGroup() {
  const terms = useTermsGate('Avant de créer le groupe');
  async function save(eventId: string, value: GuestGroupSetting) {
    try {
      return await saveGuestGroupSetting(eventId, value);
    } catch (e) {
      if (!(e instanceof Error && isTermsError(e.message) && (await terms.ensure()))) throw e;
      return saveGuestGroupSetting(eventId, value);
    }
  }
  return { save, sheet: terms.sheet };
}

/** Fiche de l'organisateur : « Régler » le groupe des invités, puis « Garder cette bande ? » le lendemain de la soirée. */
export function GuestGroupManager({ eventId, title, refreshKey, onChanged, editing, onClose }: {
  eventId: string; title: string; refreshKey?: unknown; onChanged: () => void; editing: boolean; onClose: () => void;
}) {
  const { data, reload } = useQuery(() => fetchEventGuestGroup(eventId).catch(() => null), [eventId, refreshKey]);
  const [edited, setValue] = useState<GuestGroupSetting | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const saver = useSaveGuestGroup();
  // Fermé : le prochain « Régler » repart du réglage enregistré.
  if (!editing && edited) setValue(null);
  const value = editing && data ? edited ?? { on: !!data.group, group: data.group?.id ?? 'new', name: title } : null;
  if (!data?.manage) return null;
  async function save() {
    if (!value) return;
    setBusy(true);
    setError(null);
    try {
      await saver.save(eventId, value);
      reload();
      onChanged();
      onClose();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      {saver.sheet}
      {editing && value ? (
        <View style={[st.settings, enter('drop')]}>
          <GuestGroupSettingCard value={value} onChange={setValue} groups={data.groups ?? []} disabled={busy} />
          <View style={{ flexDirection: 'row', gap: 8 }}>
            <Button small label="Enregistrer" loading={busy} style={{ flex: 1 }} onPress={() => void save()} />
            <Button small variant="secondary" label="Annuler" style={{ flex: 1 }} onPress={onClose} />
          </View>
          <ErrorText error={error} />
        </View>
      ) : null}
      {data.band ? <KeepBand eventId={eventId} band={data.band} groups={data.groups ?? []} title={title} onDone={() => { reload(); onChanged(); }} /> : null}
    </>
  );
}

/**
 * « 🎉 Garder cette bande ? » (variante B, 17.11) : le lendemain, sur la fiche de l'organisateur, de la fin de la soirée à
 * 7 jours après, une seule fois. Chacun reçoit une INVITATION au groupe et entre seulement s'il accepte.
 */
function KeepBand({ eventId, band, groups, title, onDone }: {
  eventId: string; band: NonNullable<EventGuestGroup['band']>; groups: ManagedGroup[]; title: string; onDone: () => void;
}) {
  const [who, setWho] = useState<'present' | 'all'>(band.present ? 'present' : 'all');
  const [target, setTarget] = useState<string>('new');
  const [name, setName] = useState(title);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sent, setSent] = useState<number | null>(null);
  const terms = useTermsGate('Avant de créer le groupe');
  if (!band.all) return null;
  async function send(choice: 'present' | 'all' | 'none') {
    setBusy(true);
    setError(null);
    const args = [eventId, choice, target === 'new' ? null : target, target === 'new' ? name.trim() || title : null] as const;
    try {
      let r;
      try { r = await keepBand(...args); } catch (e) {
        if (!(e instanceof Error && isTermsError(e.message) && (await terms.ensure()))) throw e;
        r = await keepBand(...args);
      }
      if (choice === 'none') onDone(); else setSent(r.invited);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  if (sent !== null) {
    return (
      <View style={[st.band, enter('fade')]}>
        <T size={17} weight="bold">🎉 C’est parti</T>
        <T color={colors.textSoft}>{sent > 1 ? `${sent} invitations envoyées` : sent === 1 ? '1 invitation envoyée' : 'Personne de plus à inviter'} : chacun entre s’il accepte.</T>
        <Button small variant="secondary" label="Fermer" onPress={onDone} />
      </View>
    );
  }
  const label = target === 'new' ? name.trim() || title : groupLabel(groups.find((g) => g.id === target) ?? { name: '…' });
  return (
    <View style={[st.band, enter('rise')]} accessibilityLabel="Garder cette bande ?">
      {terms.sheet}
      <T size={18} weight="bold">🎉 Garder cette bande ?</T>
      <T size={14} color={colors.textSoft}>
        {band.present ? `Vous étiez ${band.present + 1}.` : 'La soirée est passée.'} Fais-en un groupe : la prochaine soirée s’organise en un toucher.
      </T>
      {band.names.length ? <T size={13} color={colors.lavender} numberOfLines={2}>{band.names.join(', ')}{band.present > band.names.length ? '…' : ''}</T> : null}
      {band.present ? (
        <Radio selected={who === 'present'} title={`Les ${band.present} présents`} hint="Je viens, ou passés à l’entrée" onPress={() => setWho('present')} />
      ) : null}
      <Radio selected={who === 'all'} title={`Tous les invités (${band.all})`} hint="Même ceux qui n’ont pas pu venir" onPress={() => setWho('all')} />
      <Radio selected={target === 'new'} title="Nouveau groupe" onPress={() => setTarget('new')}>
        {target === 'new' ? <Input value={name} onChangeText={setName} maxLength={60} accessibilityLabel="Nom du groupe" /> : null}
      </Radio>
      {groups.map((g) => (
        <Radio key={g.id} selected={target === g.id} title={`Ajouter à « ${groupLabel(g)} »`} hint={membersLine(g.members)} onPress={() => setTarget(g.id)} />
      ))}
      <Button label={target === 'new' ? `Créer « ${label} » et inviter` : `Inviter dans « ${label} »`} loading={busy} onPress={() => void send(who)} />
      <Button small variant="ghost" label="Non merci" disabled={busy} onPress={() => void send('none')} />
      <T muted size={12}>Chacun reçoit une invitation. Personne n’entre sans accepter. Jamais ceux qui ont refusé le groupe ou l’ont quitté.</T>
      <ErrorText error={error} />
    </View>
  );
}

/**
 * Bandeau de la discussion du groupe, à la première ouverture après une entrée par une réponse : d'où l'on vient, et
 * « Quitter » d'un toucher (la base garde la date du départ : on n'y est plus jamais remis sans son propre geste).
 */
export function GroupJoinNote({ groupId, me, onLeft }: { groupId: string; me: string; onLeft: () => void }) {
  const { data: note } = useQuery(() => takeGroupJoinNote(groupId), [groupId]);
  const [hidden, setHidden] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (!note || hidden) return null;
  async function leave() {
    const { error: failed } = await supabase.from('member_group_members').delete().eq('group_id', groupId).eq('user_id', me);
    if (failed) return setError('Tu n’as pas pu quitter le groupe. Réessaie.');
    setHidden(true);
    onLeft();
  }
  return (
    <View style={[st.note, enter('drop')]} accessibilityRole="summary" testID="group-join-note">
      <T size={20}>👥</T>
      <View style={{ flex: 1, gap: 2 }}>
        <T size={14} weight="bold">Tu es dans le groupe « {note.group_name} »</T>
        <T size={12} color={colors.textSoft}>Ajouté avec ta réponse à « {note.event_title} »{note.owner ? ` de ${note.owner}` : ''}</T>
        <ErrorText error={error} />
      </View>
      {note.creator ? null : (
        <Pressable accessibilityRole="button" accessibilityLabel={confirm ? 'Confirmer : quitter le groupe' : 'Quitter le groupe'}
          onPress={() => (confirm ? void leave() : setConfirm(true))}
          style={({ pressed }) => [st.leave, pressed && { opacity: 0.7 }]}>
          <T size={13} weight="bold" color={colors.redSoft}>{confirm ? 'Confirmer' : 'Quitter'}</T>
        </Pressable>
      )}
      <Pressable accessibilityRole="button" accessibilityLabel="Fermer" hitSlop={8} onPress={() => setHidden(true)}>
        <T size={14} color={colors.muted}>✕</T>
      </Pressable>
    </View>
  );
}

const st = StyleSheet.create({
  check: { flexDirection: 'row', alignItems: 'flex-start', gap: 12, padding: 14, borderRadius: radius.md, borderWidth: 1.5,
    borderColor: colors.lineStrong, backgroundColor: colors.lavenderDim },
  checkOn: { borderColor: colors.mint, backgroundColor: colors.mintDim },
  box: { width: 28, height: 28, borderRadius: 8, borderWidth: 2, borderColor: colors.lavender, alignItems: 'center', justifyContent: 'center', marginTop: 1 },
  boxOn: { backgroundColor: colors.mint, borderColor: colors.mint },
  offer: { gap: 8, padding: 14, borderRadius: radius.md, backgroundColor: colors.lavenderDim, borderWidth: 1, borderColor: colors.lineStrong },
  joined: { flexDirection: 'row', alignItems: 'center', justifyContent: 'space-between', gap: 8, paddingVertical: 4 },
  settings: { gap: 12, padding: 14, borderRadius: radius.md, backgroundColor: colors.surface2 },
  radio: { flexDirection: 'row', alignItems: 'flex-start', gap: 10, padding: 12, borderRadius: radius.md, backgroundColor: colors.fill,
    borderWidth: 1, borderColor: 'transparent' },
  radioOn: { backgroundColor: 'rgba(185,167,255,0.12)', borderColor: colors.lavender },
  dot: { width: 22, height: 22, borderRadius: 11, borderWidth: 2, borderColor: colors.lineStrong, marginTop: 1 },
  dotOn: { borderWidth: 7, borderColor: colors.lavender },
  band: { gap: 10, padding: 16, borderRadius: radius.lg, backgroundColor: colors.accentDim, borderWidth: 1, borderColor: '#5A2346' },
  note: { flexDirection: 'row', alignItems: 'center', gap: 10, marginHorizontal: 12, marginTop: 8, padding: 12, borderRadius: radius.md,
    backgroundColor: colors.lavenderDim, borderWidth: 1, borderColor: colors.lineStrong },
  leave: { borderRadius: 999, paddingHorizontal: 12, paddingVertical: 7, backgroundColor: colors.redDim },
});
