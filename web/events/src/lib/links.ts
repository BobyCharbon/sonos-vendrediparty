/**
 * Liens cliquables dans les textes des événements (avis 2c221fd8effc) : description, infos de paiement,
 * messages de la discussion, notes… Le texte est découpé en morceaux (texte brut / lien) : on ne produit
 * jamais de HTML, React échappe chaque morceau. Seuls http(s), mailto: et tel: deviennent des liens,
 * jamais javascript:, data:, file:…
 *
 * Fichier sans dépendance : testé directement par Node (tests/test_event_links.py).
 */

export type LinkKind = 'url' | 'email' | 'phone';
export type Segment = { text: string; href?: string; kind?: LinkKind };

const SAFE_PROTOCOLS = new Set(['http:', 'https:', 'mailto:', 'tel:']);
const MAX_TEXT = 20000; // au-delà, on ne cherche pas de liens (texte affiché tel quel)

// Ordre des branches : adresse web, puis e-mail, puis numéro (suisse ou international).
//   1. https://… ou www.… jusqu’au prochain espace ou chevron ;
//   2. e-mail classique ;
//   3. +41 79 123 45 67 ou 079 123 45 67 (10 chiffres), sans toucher un IBAN, une date ni un prix.
const PATTERN = new RegExp(
  [
    String.raw`(?<url>\b(?:https?:\/\/|www\.)[^\s<>"'«»]+)`,
    String.raw`(?<email>\b[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,})`,
    String.raw`(?<phone>(?<![\w+])\+\d{2,3}(?:[ .]?\d){7,11}(?![\d])|(?<![\w+.,])0\d{2}[ .]?\d{3}[ .]?\d{2}[ .]?\d{2}(?![\d]))`,
  ].join('|'),
  'gi',
);

/** Retire la ponctuation de fin de phrase et la parenthèse fermante qui n’appartient pas au lien. */
function trimUrl(raw: string): string {
  let url = raw;
  for (;;) {
    const last = url.slice(-1);
    if ('.,;:!?…'.includes(last) && last) {
      url = url.slice(0, -1);
      continue;
    }
    if (last === ')' && (url.match(/\(/g)?.length ?? 0) < (url.match(/\)/g)?.length ?? 0)) {
      url = url.slice(0, -1);
      continue;
    }
    if (last === ']' && !url.includes('[')) {
      url = url.slice(0, -1);
      continue;
    }
    return url;
  }
}

/**
 * Adresse sûre à ouvrir, ou null. Accepte seulement http(s), mailto: et tel: ; « www.x.ch » devient https://www.x.ch.
 * Sert aussi au lien du lieu (location_url), saisi librement par l’organisateur.
 */
export function safeHref(raw: string | null | undefined): string | null {
  const value = (raw ?? '').trim();
  if (!value || value.length > 2048) return null;
  // Pas de caractères de contrôle ni d’espaces cachés (« java\tscript: »…).
  if (/[\u0000-\u001F\u007F\s]/.test(value)) return null;
  const withScheme = /^www\./i.test(value) ? `https://${value}` : value;
  let parsed: URL;
  try {
    parsed = new URL(withScheme);
  } catch {
    return null;
  }
  if (!SAFE_PROTOCOLS.has(parsed.protocol)) return null;
  if ((parsed.protocol === 'http:' || parsed.protocol === 'https:') && !parsed.hostname) return null;
  if (parsed.username || parsed.password) return null; // https://banque.ch@piege.com : trompeur
  return parsed.protocol === 'http:' || parsed.protocol === 'https:' ? parsed.href : withScheme;
}

function hrefFor(kind: LinkKind, text: string): string | null {
  if (kind === 'email') return safeHref(`mailto:${text}`);
  if (kind === 'phone') {
    const digits = text.replace(/[ .]/g, '');
    return safeHref(`tel:${digits}`);
  }
  return safeHref(text);
}

/** Découpe un texte en morceaux de texte brut et de liens (adresses web, e-mails, numéros de téléphone). */
export function linkify(text: string | null | undefined): Segment[] {
  const source = text ?? '';
  if (!source) return [];
  if (source.length > MAX_TEXT) return [{ text: source }];
  const out: Segment[] = [];
  let cursor = 0;
  const push = (plain: string) => {
    if (!plain) return;
    const prev = out[out.length - 1];
    if (prev && !prev.href) prev.text += plain;
    else out.push({ text: plain });
  };
  for (const match of source.matchAll(PATTERN)) {
    const groups = match.groups ?? {};
    const kind: LinkKind = groups.url ? 'url' : groups.email ? 'email' : 'phone';
    const found = kind === 'url' ? trimUrl(match[0]) : match[0];
    const start = match.index ?? 0;
    const href = found ? hrefFor(kind, found) : null;
    push(source.slice(cursor, start));
    if (href) out.push({ text: found, href, kind });
    else push(found);
    cursor = start + found.length;
  }
  push(source.slice(cursor));
  return out;
}

/** Vrai si le texte contient au moins un lien (évite un découpage inutile à l’affichage). */
export function hasLink(text: string | null | undefined): boolean {
  return linkify(text).some((s) => s.href);
}
