import { useEffect, useRef, useState } from 'react';
import { Modal, StyleSheet, View } from 'react-native';

import { SheetBackdrop, SheetTop, useSheetDrag, useSheetSignal, useSheetTop } from './SheetGesture';
import { Button, T } from './ui';
import { addPollDates, agendaLink, datesToAdd, nativeCalendar, type AddDatesResult, type AgendaLink } from '@/lib/calendar';
import { formatShort } from '@/lib/format';
import { colors, radius } from '@/lib/theme';
import type { DateVote, EventRow } from '@/lib/types';

type PollEvent = Pick<EventRow, 'id' | 'title' | 'description' | 'location_name' | 'location_address'>;
type ProposedDate = { id: string; starts_at: string; ends_at?: string | null };

type Props = {
  event: PollEvent;
  dates: ProposedDate[];
  votes: Record<string, DateVote | null | undefined>;
};

/**
 * « Valider mes dates » (retour de l'admin du 11.11.2026) : les votes partent à chaque toucher, mais sans bouton final
 * les nouveaux invités croyaient que rien n'était enregistré. Le bouton confirme, puis propose en un toucher de mettre
 * les dates votées dans l'agenda, qui se met ensuite à jour tout seul quand la date est fixée.
 */
export function ValidateDates({ event, dates, votes }: Props) {
  const [open, setOpen] = useState(false);
  const answered = dates.filter((d) => votes[d.id]).length;
  const missing = dates.length - answered;
  const hint = !answered ? 'Réponds Oui, Si besoin ou Non pour chaque date, puis valide.'
    : missing ? `Encore ${missing} date${missing > 1 ? 's' : ''} sans réponse : tu peux valider quand même.` : null;
  return (
    <View style={{ gap: 6 }}>
      <Button label="Valider mes dates" disabled={!answered} onPress={() => setOpen(true)} />
      {hint ? <T muted size={12} style={st.center}>{hint}</T> : null}
      {open ? <ValidatedSheet visible onClose={() => setOpen(false)} event={event} dates={datesToAdd(dates, votes)} /> : null}
    </View>
  );
}

export const AGENDA_DONE: Record<AddDatesResult, string> = {
  added: '✓ Ajouté à ton calendrier « Vendredi Party » : il y apparaît d’ici peu (au plus une heure) et suivra chaque changement.',
  native: '✓ C’est dans ton agenda. Quand la date sera fixée, Party gardera la bonne et retirera les autres.',
  subscribed: '✓ Confirme l’abonnement « Vendredi Party » dans ton agenda : tes événements s’y mettront ensuite à jour tout seuls.',
  file: 'Ajoute-les dans la fenêtre qui s’ouvre.',
  denied: 'Party n’a pas accès à ton calendrier : autorise-le dans Réglages › Party › Calendriers.',
};

function ValidatedSheet({ visible, onClose, event, dates }: {
  visible: boolean; onClose: () => void; event: PollEvent; dates: ProposedDate[];
}) {
  const card = useRef<View>(null);
  const overlay = useRef<View>(null);
  const sheetTop = useSheetTop();
  const [already, setAlready] = useState(false);
  const [link, setLink] = useState<AgendaLink | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<AddDatesResult | null>(null);
  useSheetDrag(visible, onClose, card, overlay);
  useSheetSignal(visible);
  const n = dates.length;

  useEffect(() => {
    if (!visible) return;
    let alive = true;  // feuille montée à chaque ouverture : résultat remis à zéro
    // Demandé dès l'ouverture : le toucher sur « Ajouter » ouvre l'agenda tout de suite (sinon Safari peut le bloquer).
    void agendaLink(event.id).then(async (l) => {
      if (!alive) return;
      setLink(l);
      if (l) return setAlready(l.added && l.subscribed);
      const native = nativeCalendar();  // sans agenda abonné : les dates déjà mises par l'app iPhone
      const r = native ? await native.status(event.id).catch(() => ({ added: 0 })) : { added: 0 };
      if (alive) setAlready(n > 0 && (r.added ?? 0) >= n);
    });
    return () => { alive = false; };
  }, [visible, event.id, n]);

  async function add() {
    setBusy(true);
    try {
      setResult(await addPollDates(event, dates, link));
    } finally {
      setBusy(false);
    }
  }

  const addLabel = n > 1 ? `Ajouter les ${n} dates à mon agenda` : 'Ajouter la date à mon agenda';
  return (
    <Modal visible={visible} transparent animationType="fade" onRequestClose={onClose}>
      <View ref={overlay} style={[st.overlay, { paddingTop: sheetTop }]}>
        <SheetBackdrop onPress={onClose} />
        <View ref={card} style={st.sheet} accessibilityViewIsModal accessibilityLabel="Dates validées">
          <SheetTop onClose={onClose} />
          <View style={st.check}><T size={28} weight="bold" color={colors.onMint}>✓</T></View>
          <T weight="bold" size={22} style={st.center}>C’est validé !</T>
          <T size={15} color={colors.textSoft} style={st.center}>
            Tes réponses sont enregistrées. L’organisateur fixera la date qui arrange le plus de monde : tu seras prévenu.
          </T>
          {n ? (
            <View style={st.agenda}>
              <T weight="bold" size={16}>📆 Garde {n > 1 ? 'ces dates' : 'cette date'} dans ton agenda</T>
              <T size={14} color={colors.textSoft}>{dates.map((d) => formatShort(d.starts_at)).join(' · ')}</T>
              <T muted size={13}>Quand la date sera fixée, ton agenda se mettra à jour tout seul : la bonne reste, les autres disparaissent.</T>
            </View>
          ) : null}
          {result ? (
            <>
              <T size={14} weight="bold" color={result === 'denied' ? colors.coralSoft : colors.mint} style={st.center}>{AGENDA_DONE[result]}</T>
              <Button label="Terminé" onPress={onClose} />
            </>
          ) : already || !n ? (
            <>
              {already ? <T size={14} weight="bold" color={colors.mint} style={st.center}>✓ Tes dates sont déjà dans ton agenda.</T> : null}
              <Button label="Terminé" onPress={onClose} />
            </>
          ) : (
            <View style={{ gap: 8 }}>
              <Button label={busy ? 'Ajout…' : addLabel} loading={busy} onPress={() => void add()} />
              <Button label="Plus tard" variant="secondary" onPress={onClose} />
            </View>
          )}
        </View>
      </View>
    </Modal>
  );
}

const st = StyleSheet.create({
  overlay: { flex: 1, backgroundColor: 'rgba(10,6,22,0.94)', alignItems: 'center', padding: 16, overflowY: 'auto' } as object,
  sheet: { width: '100%', maxWidth: 420, marginVertical: 'auto', gap: 12, padding: 20, borderRadius: radius.lg, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.lineStrong },
  check: { alignSelf: 'center', width: 56, height: 56, borderRadius: 28, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.mint },
  center: { textAlign: 'center' },
  agenda: { gap: 6, padding: 14, borderRadius: radius.md, backgroundColor: colors.fill },
});
