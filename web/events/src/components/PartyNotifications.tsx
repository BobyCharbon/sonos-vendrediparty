import { useState } from 'react';

import { useQuery } from '@/lib/data';
import { ErrorText, Section, T, ToggleRow } from './ui';

/** Types de notifications de la soirée (GUEST_NOTIFY_DEFAULTS dans app/party.py), même ordre que l'app iOS. */
const KINDS = [
  { kind: 'track', label: 'Mon titre passe', hint: 'Quand le titre que tu as ajouté démarre' },
  { kind: 'games', label: 'Nouvelle partie lancée', hint: 'Quelqu’un lance un jeu : rejoins-le d’un toucher' },
  { kind: 'feedback', label: 'Réponse à mes avis', hint: 'Ton idée ou ton bug est terminé, ou l’organisateur te répond' },
] as const;

type GuestNotify = { prefs: Record<string, boolean>; subscribed: boolean };

/** Identifiant d'invité de la page Party (même origine que le module) : ses choix sont gardés par le serveur Party. */
function guestId(): string | null {
  try { return localStorage.getItem('vp_guest'); } catch { return null; }
}

async function call(path: string, init?: RequestInit): Promise<GuestNotify | 'code'> {
  const r = await fetch(path, { credentials: 'same-origin', ...init, headers: { 'Content-Type': 'application/json', ...init?.headers } });
  if (r.status === 401) return 'code';
  if (!r.ok) throw new Error('Les notifications de la soirée n’ont pas pu être lues.');
  return (await r.json()) as GuestNotify;
}

/** Réglages › Notifications › Soirée : musique, jeux et réponses aux avis (serveur Party, pas Supabase). */
export function PartyNotifications() {
  const id = guestId();
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const { data, setData } = useQuery(async () => (id ? call(`/api/notify?guest_id=${encodeURIComponent(id)}`) : null), [id]);
  if (!id || data === null) return null;

  async function toggle(kind: string, on: boolean) {
    if (busy || !id) return;
    setBusy(kind); setError(null);
    try {
      const next = await call('/api/notify', { method: 'POST', body: JSON.stringify({ guest_id: id, kind, on }) });
      setData(next);
    } catch {
      setError('Ton choix n’a pas été enregistré. Réessaie dans un instant.');
    } finally { setBusy(null); }
  }

  return (
    <Section title="Soirée : musique, jeux et avis">
      {data === 'code' ? (
        <T muted size={13}>Entre le code de la soirée (onglet Musique) pour choisir ces notifications.</T>
      ) : (
        <>
          {KINDS.map(({ kind, label, hint }) => (
            <ToggleRow key={kind} disabled={busy !== null} label={label} hint={hint}
              value={data.prefs[kind] === true} onChange={(on) => toggle(kind, on)} />
          ))}
          {!data.subscribed ? (
            <T muted size={13}>Cet appareil ne reçoit pas encore les notifications de la soirée : active « Me prévenir quand mon titre passe » dans Musique.</T>
          ) : null}
        </>
      )}
      <ErrorText error={error} />
    </Section>
  );
}
