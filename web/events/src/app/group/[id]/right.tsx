import { router, Stack, useLocalSearchParams } from 'expo-router';
import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { Button, ErrorText, HeaderBack, Loading, Screen, Segmented, T, Title, ToggleRow } from '@/components/ui';
import { useAuth, useMe } from '@/lib/auth';
import { useQuery } from '@/lib/data';
import { setGroupRules } from '@/lib/groupAnnounce';
import { LEVEL_TITLE, LEVELS, levelDetail, loadGroupPanel, RIGHT_KEYS, RIGHTS, type Level, type RightKey } from '@/lib/groupRights';
import { dbMessage } from '@/lib/moderation';
import { roleRank } from '@/lib/roles';
import { supabase } from '@/lib/supabase';
import { colors } from '@/lib/theme';

/**
 * « Qui peut… » un droit du groupe (maquette du 23.11) : Admins seulement / Organisateurs et admins / Tous les membres ;
 * créer un événement : « À valider par un admin » (les organisateurs publient directement) ; prévenir le groupe : les
 * notifications des événements. Enregistrer → set_group_right (la base vérifie le droit de régler le groupe).
 */
export default function GroupRight() {
  const { id, k } = useLocalSearchParams<{ id: string; k: string }>();
  const key = (RIGHT_KEYS as string[]).includes(k) ? (k as RightKey) : 'invite';
  const me = useMe();
  const { rank } = useAuth();
  const [level, setLevel] = useState<Level | null>(null);
  const [approval, setApproval] = useState<boolean | null>(null);
  const [mode, setMode] = useState<'request' | 'free' | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data: panel, loading } = useQuery(() => loadGroupPanel(id, me.id, rank >= roleRank('admin')), [id]);

  if (loading && !panel) return <Loading />;
  if (!panel || !panel.me.rules || panel.group.system) {
    return <Screen edges={[]}><ErrorText error="Seuls l’admin et les co-admins du groupe changent ses droits." /></Screen>;
  }
  const chosen = level ?? panel.rights[key];
  const needApproval = approval ?? panel.events_need_approval;
  const announceMode = mode ?? panel.announce_mode;

  async function save() {
    if (!panel) return;
    setBusy(true);
    setError(null);
    try {
      if (chosen !== panel.rights[key]) {
        const { error: failed } = await supabase.rpc('set_group_right', { grp: id, k: key, level: chosen });
        if (failed) throw failed;
      }
      if ((key === 'events' && needApproval !== panel.events_need_approval) || (key === 'announce' && announceMode !== panel.announce_mode)) {
        await setGroupRules(id, needApproval, announceMode);
      }
      router.back();
    } catch (e) {
      setError(dbMessage((e as { message?: string }).message ?? '', 'Le réglage n’a pas été enregistré. Réessaie.'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Screen edges={[]}>
      <Stack.Screen options={{ title: 'Qui peut…', headerLeft: () => <HeaderBack label="Retour" onPress={() => router.back()} /> }} />
      <View style={{ gap: 6 }}>
        <Title size={26}>{RIGHTS[key].label}</Title>
        <T muted size={15}>{RIGHTS[key].about}</T>
      </View>
      <View style={{ gap: 10 }} accessibilityRole="radiogroup">
        {LEVELS.map((l) => {
          const on = chosen === l;
          return (
            <Pressable key={l} accessibilityRole="radio" accessibilityState={{ checked: on }} aria-checked={on} accessibilityLabel={LEVEL_TITLE[l]}
              onPress={() => setLevel(l)} style={[st.choice, on && st.choiceOn]}>
              <View style={[st.ring, on && { borderColor: colors.accentSoft }]}>{on ? <View style={st.dot} /> : null}</View>
              <View style={{ flex: 1, gap: 3 }}>
                <T weight="bold">{LEVEL_TITLE[l]}</T>
                <T muted size={13}>{levelDetail(key, l)}</T>
              </View>
            </Pressable>
          );
        })}
      </View>
      {key === 'events' && chosen === 'members' ? (
        <View style={st.box}>
          <ToggleRow label="À valider par un admin" value={needApproval} onChange={setApproval}
            hint="Celui d’un membre attend ton accord (ou celui d’un co-admin) avant d’être visible. Les organisateurs publient directement." />
        </View>
      ) : null}
      {key === 'events' ? (
        <T muted size={13}>Un événement PUBLIC passe toujours par l’équipe de Vendredi Party, quel que soit ce réglage.</T>
      ) : null}
      {key === 'announce' ? (
        <View style={[st.box, { gap: 8 }]}>
          <T weight="semibold">Notifications des événements</T>
          <Segmented<'request' | 'free'> options={[{ key: 'request', label: 'Sur demande' }, { key: 'free', label: 'Libres' }]}
            value={announceMode} onChange={setMode} />
          <T muted size={13}>{announceMode === 'request'
            ? '« Prévenir le groupe » d’un membre devient une demande : toi, les admins et les organisateurs du groupe l’acceptez ou la refusez. Sans réponse sous 48 h, l’annonce part automatiquement.'
            : 'Chaque membre décide lui-même de prévenir le groupe quand il publie un événement.'}</T>
        </View>
      ) : null}
      <ErrorText error={error} />
      <Button label="Enregistrer" loading={busy} onPress={() => void save()} />
    </Screen>
  );
}

const st = StyleSheet.create({
  choice: { flexDirection: 'row', alignItems: 'center', gap: 14, padding: 14, minHeight: 72, borderRadius: 18, borderWidth: 2, borderColor: colors.line, backgroundColor: colors.surface },
  choiceOn: { borderColor: colors.accentSoft, backgroundColor: '#2A1A3D' },
  ring: { width: 24, height: 24, borderRadius: 12, borderWidth: 2, borderColor: '#7E74A6', alignItems: 'center', justifyContent: 'center' },
  dot: { width: 12, height: 12, borderRadius: 6, backgroundColor: colors.accentSoft },
  box: { backgroundColor: colors.surface, borderColor: colors.line, borderWidth: 1, borderRadius: 20, padding: 14 },
});
