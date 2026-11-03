/**
 * « Ajouter aux contacts » (fiche d'un membre) : une vCard 3.0 (FN, N, NICKNAME, TEL), que Safari et Android
 * proposent d'ajouter au répertoire. Générée ici, seulement avec un numéro que la base nous laisse voir
 * (member_card applique la règle « numéro montré aux membres de ses groupes »).
 */
export type VCardPerson = { phone: string; firstName?: string | null; lastName?: string | null; nickname?: string | null };

/** Échappement vCard 3.0 (RFC 2426) : \ ; , et retours à la ligne. */
export function vcardEscape(value: string): string {
  return value.replace(/\\/g, '\\\\').replace(/;/g, '\\;').replace(/,/g, '\\,').replace(/\r\n|\r|\n/g, '\\n');
}

/** Numéro international « +41… », ou null si ce n'est pas un numéro. */
export function dialable(phone: string | null | undefined): string | null {
  const digits = (phone ?? '').replace(/[^0-9]/g, '');
  return digits.length >= 6 && digits.length <= 15 ? `+${digits}` : null;
}

export function buildVCard(p: VCardPerson): string | null {
  const tel = dialable(p.phone);
  if (!tel) return null;
  const first = (p.firstName ?? '').trim();
  const last = (p.lastName ?? '').trim();
  const nick = (p.nickname ?? '').trim();
  const given = first || last ? first : nick;  // sans nom public : le pseudo, à renommer dans Contacts
  const full = [given, last].filter(Boolean).join(' ') || tel;
  const lines = [
    'BEGIN:VCARD',
    'VERSION:3.0',
    `N:${vcardEscape(last)};${vcardEscape(given)};;;`,
    `FN:${vcardEscape(full)}`,
    ...(nick && (first || last) ? [`NICKNAME:${vcardEscape(nick)}`] : []),
    `TEL;TYPE=CELL:${tel}`,
    'END:VCARD',
  ];
  return lines.join('\r\n') + '\r\n';
}

/** Nom du fichier : lettres, chiffres et tirets seulement. */
export function vcardFileName(p: VCardPerson): string {
  const base = [p.firstName, p.lastName].filter(Boolean).join(' ') || p.nickname || 'contact';
  const safe = base.normalize('NFD').replace(/[\u0300-\u036f]/g, '').replace(/[^A-Za-z0-9]+/g, '-').replace(/^-|-$/g, '');
  return `${safe || 'contact'}.vcf`;
}

type NativeAdd = { contacts?: { add?: (p: VCardPerson) => Promise<unknown> } };

/** App iPhone : fiche Contacts d'Apple préremplie (pont natif). Ailleurs : téléchargement de la vCard. */
export async function addToContacts(p: VCardPerson): Promise<boolean> {
  const native = (globalThis as { PartyNative?: NativeAdd }).PartyNative?.contacts;
  if (native?.add) {
    await native.add({ phone: dialable(p.phone) ?? '', firstName: p.firstName ?? null, lastName: p.lastName ?? null, nickname: p.nickname ?? null });
    return true;
  }
  const card = buildVCard(p);
  if (!card || typeof document === 'undefined') return false;
  const url = URL.createObjectURL(new Blob([card], { type: 'text/vcard;charset=utf-8' }));
  const a = document.createElement('a');
  a.href = url;
  a.download = vcardFileName(p);
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
  return true;
}
