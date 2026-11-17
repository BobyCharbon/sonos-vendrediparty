import { supabase } from './supabase';
import { friendlyError } from './errors';
import { dbMessage, isTermsError } from './moderation';

/**
 * « Réunir les invités dans un groupe » (décision de l'admin du 17.11, migration 20261117110000). L'organisateur choisit un
 * groupe qu'il gère ; chaque invité COCHE lui-même « Rejoindre aussi le groupe » (décochée par défaut, avis de conformité du
 * 17.11) ; l'écran envoie join_group true/false avec la réponse, la base ne décide jamais seule.
 */
export type GuestGroupCard = { id: string; name: string; emoji?: string | null; members: number; owner?: string | null };
export type ManagedGroup = { id: string; name: string; emoji?: string | null; members: number };
export type Band = { present: number; all: number; names: string[] };
export type EventGuestGroup = {
  group: GuestGroupCard | null; in_group: boolean; offer: boolean; answered: boolean; choice: boolean | null;
  manage: boolean; groups: ManagedGroup[] | null; band: Band | null;
};
export type JoinNote = { event_id: string; event_title: string; group_name: string; owner: string | null; creator: boolean };
/** Réglage de l'organisateur : éteint, un groupe existant, ou « Nouveau groupe » (nom pré-rempli avec le titre). */
export type GuestGroupSetting = { on: boolean; group: string | 'new' | null; name: string };

export const groupLabel = (g: Pick<GuestGroupCard, 'name' | 'emoji'>) => `${g.emoji ? `${g.emoji} ` : ''}${g.name}`;

/** Texte de la case (avis de conformité du 17.11) : clair, rien de caché, aucune récompense. */
export const joinTitle = (g: GuestGroupCard) => `Rejoindre aussi le groupe « ${groupLabel(g)} »${g.owner ? ` de ${g.owner}` : ''}`;
export const JOIN_DETAIL = 'Les membres verront ton surnom, ton nom et ta photo, pourront t’écrire dans la discussion du groupe, '
  + 'et tu seras invité à ses prochains événements. Ton numéro reste caché. Tu quittes le groupe quand tu veux.';
export const membersLine = (n: number) => (n > 1 ? `${n} membres` : n === 1 ? '1 membre' : 'Aucun membre pour l’instant');

async function rpc<T>(name: string, args: Record<string, unknown>, fallback: string): Promise<T> {
  const { data, error } = await supabase.rpc(name, args);
  // CGU (« Nouveau groupe ») : le code reste pour que l'écran ouvre la feuille puis réessaie.
  if (error) throw new Error(isTermsError(error.message) ? error.message : friendlyError(dbMessage(error.message, fallback)));
  return data as T;
}

export const fetchEventGuestGroup = (e: string) =>
  rpc<EventGuestGroup>('event_guest_group', { e }, 'Le groupe de l’événement n’a pas pu être lu.');

export const setGuestGroupChoice = (e: string, join: boolean) =>
  rpc<{ status: string }>('set_guest_group_choice', { e, join_group: join }, 'Ton choix pour le groupe n’a pas été enregistré. Réessaie.');

export function saveGuestGroupSetting(e: string, s: GuestGroupSetting) {
  const newName = s.on && s.group === 'new' ? s.name.trim() : null;
  const grp = s.on && s.group && s.group !== 'new' ? s.group : null;
  if (s.on && s.group === 'new' && !newName) return Promise.reject(new Error('Donne un nom au groupe.'));
  return rpc<EventGuestGroup>('set_event_guest_group', { e, grp, new_name: newName }, 'Le groupe n’a pas été enregistré. Réessaie.');
}

export const keepBand = (e: string, who: 'present' | 'all' | 'none', grp: string | null, newName: string | null) =>
  rpc<{ invited: number; group_id?: string }>('keep_band', { e, who, grp, new_name: newName }, 'Les invitations n’ont pas pu partir. Réessaie.');

/** Bandeau de la discussion du groupe : rendu une seule fois (première ouverture) ; null sinon ou base plus ancienne. */
export async function takeGroupJoinNote(grp: string): Promise<JoinNote | null> {
  const { data, error } = await supabase.rpc('take_group_join_note', { grp });
  return error ? null : (data as JoinNote | null);
}
