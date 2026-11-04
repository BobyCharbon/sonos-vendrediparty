import { useState } from 'react';

import { useQuery } from '@/lib/data';
import { ErrorText, ToggleRow } from './ui';

type ReactionsPrefs = { enabled: boolean };

/** Identifiant de la page Party (même origine) : acct-… quand le compte est relié aux jeux. */
function memberId(): string | null {
  try {
    const id = localStorage.getItem('vp_guest');
    return id && /^acct-[0-9a-f]{40}$/.test(id) ? id : null;
  } catch { return null; }
}

async function prefs(guestId: string, on?: boolean): Promise<ReactionsPrefs> {
  const r = await fetch('/api/pet/reactions/prefs', {
    method: 'POST', credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(on === undefined ? { guest_id: guestId } : { guest_id: guestId, on }),
  });
  if (!r.ok) throw new Error('Ton choix n’a pas pu être lu.');
  return (await r.json()) as ReactionsPrefs;
}

/** Réglages › Compagnon : petits bandeaux « +5 🪙 pour Zicou » dans l'app (serveur Party ; jamais une notification).
 *  Aussi dans les Réglages de l'app iPhone. */
export function ZicouReactionsRow({ disabled }: { disabled?: boolean }) {
  const id = memberId();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { data, setData } = useQuery(async () => (id ? prefs(id) : null), [id]);
  if (!id || !data) return null;

  async function toggle(on: boolean) {
    if (!id || busy) return;
    setBusy(true); setError(null);
    try { setData(await prefs(id, on)); }
    catch { setError('Ton choix n’a pas été enregistré. Réessaie dans un instant.'); }
    finally { setBusy(false); }
  }

  return (
    <>
      <ToggleRow disabled={disabled || busy} label="Réactions de Zicou"
        hint="Un petit bandeau dans l’app quand ton Zicou gagne des pièces (titre ajouté, partie terminée). Jamais de notification."
        value={data.enabled} onChange={toggle} />
      <ErrorText error={error} />
    </>
  );
}
