import { useState } from 'react';
import { Pressable, StyleSheet, View } from 'react-native';

import { useTermsGate } from './TermsSheet';
import { Avatar, Button, Card, ErrorText, Field, T } from './ui';
import {
  CarpoolError, MAX_SEATS, carpoolSummary, drive, drop, fetchCarpool, freeSeats, leave, pick, seek, takeSeat,
  type Carpool, type CarpoolDriver, type CarpoolMe, type CarpoolPerson,
} from '@/lib/carpool';
import { useQuery } from '@/lib/data';
import { pressTransition } from '@/lib/motion';
import { colors, radius } from '@/lib/theme';

type Mode = 'drive' | 'seek' | null;
const DEFAULT_SEATS = 3;

/**
 * Covoiturage (avis 34d5c07f2e56 de l'admin, 11.11) : qui conduit (places, ville de départ facultative), qui cherche une
 * place, qui monte avec qui. Option de l'événement ; seuls les participants (Présent / Peut-être) y prennent part.
 * answer : la réponse de la personne (la carte se recharge quand elle change).
 */
export function CarpoolCard({ eventId, answer }: { eventId: string; answer: string }) {
  const { data } = useQuery(() => fetchCarpool(eventId), [eventId, answer]);
  const [fresh, setFresh] = useState<Carpool | null>(null);
  const [mode, setMode] = useState<Mode>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const terms = useTermsGate();

  const shown = fresh ?? data;
  if (!shown || !shown.enabled) return null;
  if (!shown.member) {
    return (
      <Card>
        <T weight="bold" size={17}>🚗 Covoiturage</T>
        <T muted size={13}>Réponds Présent ou Peut-être pour proposer tes places ou en trouver une.</T>
      </Card>
    );
  }

  async function run(job: () => Promise<Carpool>, withCity = false): Promise<void> {
    if (busy) return;
    if (withCity && !terms.accepted && !(await terms.ensure())) return;
    setBusy(true);
    setError(null);
    try {
      setFresh(await job());
      setMode(null);
    } catch (e) {
      // CGU pas encore acceptées (ville saisie) : la feuille s'ouvre, puis un nouvel essai.
      if (e instanceof CarpoolError && e.terms && (await terms.ensure())) {
        setBusy(false);
        return run(job);
      }
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const me = shown.me;
  const myCar = me?.role === 'driver' ? shown.drivers.find((d) => d.id === me.id) : undefined;
  const riding = me?.role === 'passenger' && me.driver_id ? shown.drivers.find((d) => d.id === me.driver_id) : undefined;
  const others = shown.drivers.filter((d) => d.id !== me?.id);
  const seekers = shown.seekers.filter((p) => p.id !== me?.id);

  return (
    <Card>
      <View style={{ gap: 2 }}>
        <T weight="bold" size={17}>🚗 Covoiturage</T>
        <T muted size={13}>{carpoolSummary(shown.drivers, shown.seekers)}</T>
      </View>

      {me && !mode ? (
        <MyStatus me={me} myCar={myCar} riding={riding} busy={busy} onLeave={() => run(() => leave(eventId))}
          onChange={() => setMode(me.role === 'driver' ? 'drive' : 'seek')} onDrop={(id) => run(() => drop(eventId, id))} />
      ) : null}
      {!me && !mode ? (
        <View style={st.row}>
          <Button label="🚗 Je conduis" variant="secondary" small onPress={() => setMode('drive')} style={st.grow} />
          <Button label="🙋 Je cherche une place" variant="secondary" small onPress={() => setMode('seek')} style={st.grow} />
        </View>
      ) : null}
      {mode ? (
        <OfferForm mode={mode} busy={busy} initialSeats={me?.seats ?? DEFAULT_SEATS} initialCity={me?.from_city ?? ''}
          onCancel={() => setMode(null)}
          onSubmit={(seats, city) => run(() => (mode === 'drive' ? drive(eventId, seats, city) : seek(eventId, city)), !!city.trim())} />
      ) : null}

      {others.map((d) => (
        <DriverRow key={d.id} d={d} meId={me?.id} busy={busy} canBoard={me?.role !== 'driver' && riding?.id !== d.id && freeSeats(d) > 0}
          onBoard={() => run(() => takeSeat(eventId, d.id))} />
      ))}
      {seekers.length ? (
        <View style={{ gap: 8 }}>
          <T size={12} weight="bold" color={colors.textSoft}>CHERCHENT UNE PLACE</T>
          {seekers.map((p) => (
            <SeekerRow key={p.id} p={p} busy={busy} canPick={!!myCar && freeSeats(myCar) > 0} onPick={() => run(() => pick(eventId, p.id))} />
          ))}
        </View>
      ) : null}
      <ErrorText error={error} />
      {terms.sheet}
    </Card>
  );
}

function plural(n: number, word: string): string {
  return `${n} ${word}${n > 1 ? 's' : ''}`;
}

function statusLine(me: CarpoolMe, myCar?: CarpoolDriver, riding?: CarpoolDriver): string {
  const from = (city?: string | null) => (city ? ` depuis ${city}` : '');
  if (me.role === 'driver') {
    const riders = myCar?.passengers.length ?? 0;
    const free = myCar ? freeSeats(myCar) : me.seats ?? 0;
    const seats = free ? `${plural(free, 'place')} libre${free > 1 ? 's' : ''}` : 'complet';
    return `Tu conduis${from(me.from_city)} · ${riders ? `${plural(riders, 'passager')} · ` : ''}${seats}`;
  }
  if (riding) return `Tu montes avec ${riding.name}${riding.from_city ? ` (départ de ${riding.from_city})` : ''}`;
  return `Tu cherches une place${from(me.from_city)}`;
}

function MyStatus({ me, myCar, riding, busy, onLeave, onChange, onDrop }: {
  me: CarpoolMe; myCar?: CarpoolDriver; riding?: CarpoolDriver; busy: boolean;
  onLeave: () => void; onChange: () => void; onDrop: (id: string) => void;
}) {
  const leaveLabel = me.role === 'driver' ? 'Je ne conduis plus' : riding ? 'Descendre' : 'Je n’en cherche plus';
  return (
    <View style={st.mine}>
      <T weight="semibold" size={14}>{statusLine(me, myCar, riding)}</T>
      {myCar?.passengers.map((p) => (
        <View key={p.id} style={st.person}>
          <Avatar id={p.id} name={p.name} size={26} />
          <T size={14} style={st.grow}>{p.name}</T>
          <Button label="Retirer" variant="ghost" small disabled={busy} accessibilityLabel={`Retirer ${p.name} de ta voiture`} onPress={() => onDrop(p.id)} />
        </View>
      ))}
      <View style={st.row}>
        {!riding ? <Button label="Modifier" variant="secondary" small disabled={busy} onPress={onChange} /> : null}
        <Button label={leaveLabel} variant="ghost" small disabled={busy} onPress={onLeave} />
      </View>
    </View>
  );
}

function OfferForm({ mode, busy, initialSeats, initialCity, onCancel, onSubmit }: {
  mode: 'drive' | 'seek'; busy: boolean; initialSeats: number; initialCity: string;
  onCancel: () => void; onSubmit: (seats: number, city: string) => void;
}) {
  const [seats, setSeats] = useState(initialSeats);
  const [city, setCity] = useState(initialCity);
  return (
    <View style={st.mine}>
      {mode === 'drive' ? (
        <View style={st.person}>
          <T size={14} style={st.grow}>Places libres dans ta voiture</T>
          <Pressable accessibilityRole="button" accessibilityLabel="Une place de moins" disabled={seats <= 1}
            onPress={() => setSeats((n) => Math.max(1, n - 1))} style={({ pressed }) => [st.step, pressTransition, pressed && st.pressed]}>
            <T size={18} weight="bold">−</T>
          </Pressable>
          <T size={17} weight="bold" style={st.count}>{seats}</T>
          <Pressable accessibilityRole="button" accessibilityLabel="Une place de plus" disabled={seats >= MAX_SEATS}
            onPress={() => setSeats((n) => Math.min(MAX_SEATS, n + 1))} style={({ pressed }) => [st.step, pressTransition, pressed && st.pressed]}>
            <T size={18} weight="bold">+</T>
          </Pressable>
        </View>
      ) : null}
      <Field label="Ville de départ (facultatif)" placeholder="Ex. Sion" value={city} onChangeText={setCity} maxLength={60} />
      <View style={st.row}>
        <Button label={mode === 'drive' ? 'Proposer mes places' : 'Chercher une place'} small loading={busy} disabled={busy}
          onPress={() => onSubmit(seats, city)} style={st.grow} />
        <Button label="Annuler" variant="ghost" small disabled={busy} onPress={onCancel} />
      </View>
    </View>
  );
}

function DriverRow({ d, meId, canBoard, busy, onBoard }: {
  d: CarpoolDriver; meId?: string; canBoard: boolean; busy: boolean; onBoard: () => void;
}) {
  const free = freeSeats(d);
  return (
    <View style={st.person}>
      <Avatar id={d.id} name={d.name} size={32} photo={d.avatar_url} />
      <View style={st.grow}>
        <T weight="semibold" size={15}>{d.name}{d.from_city ? <T muted size={13}> · depuis {d.from_city}</T> : null}</T>
        <T size={13} color={free ? colors.mint : colors.muted}>
          {free ? `${plural(free, 'place')} libre${free > 1 ? 's' : ''}` : 'Complet'}
          {d.passengers.length ? <T muted size={13}> · avec {d.passengers.map((p) => (p.id === meId ? 'toi' : p.name)).join(', ')}</T> : null}
        </T>
      </View>
      {canBoard ? <Button label="Monter" small disabled={busy} accessibilityLabel={`Monter avec ${d.name}`} onPress={onBoard} /> : null}
    </View>
  );
}

function SeekerRow({ p, canPick, busy, onPick }: { p: CarpoolPerson; canPick: boolean; busy: boolean; onPick: () => void }) {
  return (
    <View style={st.person}>
      <Avatar id={p.id} name={p.name} size={28} photo={p.avatar_url} />
      <T size={14} style={st.grow}>{p.name}{p.from_city ? <T muted size={13}> · depuis {p.from_city}</T> : null}</T>
      {canPick ? <Button label="Prendre" variant="secondary" small disabled={busy} accessibilityLabel={`Prendre ${p.name} dans ta voiture`} onPress={onPick} /> : null}
    </View>
  );
}

const st = StyleSheet.create({
  row: { flexDirection: 'row', gap: 8, flexWrap: 'wrap' },
  grow: { flex: 1 },
  mine: { gap: 10, padding: 12, borderRadius: radius.md, backgroundColor: colors.fill },
  person: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  step: { width: 44, height: 44, borderRadius: 22, alignItems: 'center', justifyContent: 'center', backgroundColor: colors.fillStrong },
  count: { minWidth: 22, textAlign: 'center' },
  pressed: { opacity: 0.8, transform: [{ scale: 0.94 }] },
});
