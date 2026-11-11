import { barChf, optionsOf, round2, type BarCategory, type Cart, type MyBar, type MyBarItem } from './bar';

/**
 * Options du bar (migration 20261110160000) : catégories de la carte, limites par personne pour la soirée, textes des
 * options. La base décide (elle refuse ce qui dépasse) ; ces fonctions servent à afficher et à éteindre le « + » à temps.
 */

export const CATEGORIES: { key: BarCategory; label: string }[] = [
  { key: 'softs', label: 'Softs' }, { key: 'bieres', label: 'Bières' }, { key: 'vins', label: 'Vins' },
  { key: 'cocktails', label: 'Cocktails' }, { key: 'shots', label: 'Shots' }, { key: 'autre', label: 'Autre' },
];
export const CATEGORY_LABEL = Object.fromEntries(CATEGORIES.map((c) => [c.key, c.label])) as Record<BarCategory, string>;

/** La carte regroupée par catégorie, dans l'ordre fixe ; une seule catégorie (ou aucune) : un seul groupe sans titre. */
export function groupByCategory<T extends { category?: BarCategory }>(items: T[]): { key: BarCategory; label: string | null; items: T[] }[] {
  const groups = CATEGORIES.map((c) => ({ key: c.key, label: c.label as string | null, items: items.filter((i) => (i.category ?? 'autre') === c.key) }))
    .filter((g) => g.items.length > 0);
  return groups.length > 1 ? groups : groups.map((g) => ({ ...g, label: null }));
}

/** Ce qu'il me reste pour la soirée (limites de l'organisateur), commande en cours comprise ; null : sans limite. */
export function eveningRoom(bar: Pick<MyBar, 'options' | 'mine' | 'items'>, cart: Cart): { glasses: number | null; chf: number | null } {
  const o = optionsOf(bar);
  const chosen = bar.items.reduce((acc, i) => {
    const q = cart[i.id] ?? 0;
    return { count: acc.count + q, chf: round2(acc.chf + q * i.price_chf) };
  }, { count: 0, chf: 0 });
  const mine = bar.mine ?? { glasses: 0, chf: 0 };
  return {
    glasses: o.limit_glasses == null ? null : Math.max(0, o.limit_glasses - mine.glasses - chosen.count),
    chf: o.limit_chf == null ? null : Math.max(0, round2(o.limit_chf - Number(mine.chf) - chosen.chf)),
  };
}

/** Le « + » d'un article dans les limites de la soirée ? */
export function roomFor(item: MyBarItem, room: { glasses: number | null; chf: number | null }): boolean {
  return (room.glasses == null || room.glasses >= 1) && (room.chf == null || room.chf >= item.price_chf);
}

/** « Limite de la soirée : 6 verres et 40 CHF par personne (tu en es à 2 verres, 9 CHF). » ; null : aucune limite. */
export function limitsLine(bar: Pick<MyBar, 'options' | 'mine'>): string | null {
  const o = optionsOf(bar);
  if (o.limit_glasses == null && o.limit_chf == null) return null;
  const mine = bar.mine ?? { glasses: 0, chf: 0 };
  const parts = [o.limit_glasses != null ? `${o.limit_glasses} verres` : null, o.limit_chf != null && !o.free_bar ? barChf(o.limit_chf) : null]
    .filter(Boolean);
  if (!parts.length) return null;
  const done = [`${mine.glasses} verre${mine.glasses > 1 ? 's' : ''}`, o.limit_chf != null && !o.free_bar ? barChf(Number(mine.chf)) : null]
    .filter(Boolean).join(', ');
  return `Limite de la soirée : ${parts.join(' et ')} par personne (tu en es à ${done}).`;
}

/** « Il en reste 3 » (stock montré par l'organisateur), « Épuisé », « Indisponible pour l'instant ». */
export function stockNote(item: MyBarItem): { text: string; tone: 'muted' | 'warn' | 'off' } | null {
  if (item.unavailable) return { text: 'Indisponible pour l’instant', tone: 'off' };
  if (item.sold_out || item.available === 0) return { text: 'Épuisé', tone: 'off' };
  if (item.available != null) return { text: `Il en reste ${item.available}`, tone: item.available <= 3 ? 'warn' : 'muted' };
  return null;
}
