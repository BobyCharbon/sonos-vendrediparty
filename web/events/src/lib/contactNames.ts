import { useSyncExternalStore } from 'react';

/**
 * Noms des contacts (avis f780431defe7) : dans l'app iPhone, un membre Party qui est dans le répertoire s'affiche
 * « Nom du contact · pseudo ». L'app donne la table { identifiant de compte : nom } par son pont
 * (window.PartyNative.contacts.names(), noms lus sur l'iPhone, jamais envoyés au serveur). Hors de l'app
 * (Safari, Android, ordinateur) : rien ne change, le pseudo reste.
 */
type Names = Record<string, string>;
type Bridge = { contacts?: { names?: () => Promise<unknown> } };

const REFRESH_MS = 30_000;
let names: Names = {};
let started = false;
const listeners = new Set<() => void>();

function bridge(): Bridge['contacts'] | undefined {
  return (globalThis as { PartyNative?: Bridge }).PartyNative?.contacts;
}

/** Garde seulement des paires texte → texte non vides (la table vient de l'app, mais on ne fait confiance à rien). */
export function cleanNames(raw: unknown): Names {
  if (!raw || typeof raw !== 'object' || Array.isArray(raw)) return {};
  const out: Names = {};
  for (const [id, name] of Object.entries(raw as Record<string, unknown>)) {
    if (typeof name === 'string' && name.trim() && /^[0-9a-f-]{36}$/i.test(id)) out[id.toLowerCase()] = name.trim();
  }
  return out;
}

function publish(next: Names) {
  const same = Object.keys(next).length === Object.keys(names).length && Object.entries(next).every(([k, v]) => names[k] === v);
  if (same) return;
  names = next;
  listeners.forEach((l) => l());
}

async function load() {
  const contacts = bridge();
  if (!contacts?.names) return;
  try {
    publish(cleanNames(await contacts.names()));
  } catch {
    // Pont indisponible : les pseudos restent.
  }
}

/** Relit la table au démarrage, au retour dans l'app et toutes les 30 s (un contact ajouté sur la fiche). */
function start() {
  if (started || !bridge()?.names) return;
  started = true;
  void load();
  if (typeof document !== 'undefined') {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'visible') void load();
    });
  }
  setInterval(() => {
    if (typeof document === 'undefined' || document.visibilityState === 'visible') void load();
  }, REFRESH_MS);
}

function subscribe(listener: () => void) {
  start();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

/** Table actuelle (vide hors de l'app iPhone). */
export function useContactNames(): Names {
  return useSyncExternalStore(subscribe, () => names, () => names);
}

export type PersonLabel = { primary: string; secondary: string | null };

const fold = (s: string) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

/** « Nom du contact » en principal, le pseudo en plus (sauf s'il est identique) ; sans contact : le pseudo seul. */
export function personLabel(table: Names, userId: string | null | undefined, pseudo: string): PersonLabel {
  const contact = userId ? table[userId.toLowerCase()]?.trim() : '';
  const nick = (pseudo ?? '').trim();
  if (!contact) return { primary: nick, secondary: null };
  return { primary: contact, secondary: nick && fold(nick) !== fold(contact) ? nick : null };
}

/** Texte sur une ligne : « Marie Dupont · Mimi », ou le pseudo. */
export function labelText(l: PersonLabel): string {
  return l.secondary ? `${l.primary} · ${l.secondary}` : l.primary;
}

/** Nom à afficher hors composant (sans abonnement) : celui du contact s'il existe, sinon le pseudo. */
export function displayName(userId: string | null | undefined, pseudo: string): string {
  return personLabel(names, userId, pseudo).primary;
}

/** Table id → nom (pseudos) réécrite avec les noms des contacts : « Marie Dupont · Mimi ». Même table sans contacts. */
export function withContactNames(pseudos: Map<string, string>, table: Names): Map<string, string> {
  if (!Object.keys(table).length) return pseudos;
  return new Map([...pseudos].map(([id, pseudo]) => [id, labelText(personLabel(table, id, pseudo))]));
}
