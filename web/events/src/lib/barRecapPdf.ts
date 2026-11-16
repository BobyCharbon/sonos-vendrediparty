import type { BarRecap, RecapLine } from './bar';
import { fit, PAGE, PdfDoc } from './pdf';

const TZ = 'Europe/Zurich';
const dayFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, weekday: 'long', day: 'numeric', month: 'long', year: 'numeric' });
const stampFmt = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' });

const INK: [number, number, number] = [20, 20, 28];
const MUTED: [number, number, number] = [110, 110, 122];
const ACCENT: [number, number, number] = [214, 46, 112];
const SOFT: [number, number, number] = [246, 241, 245];
const CORAL: [number, number, number] = [196, 72, 52];
const MINT: [number, number, number] = [32, 140, 96];

/** « 4.50 CHF », « 3 € ». */
export function money(n: number, currency: string): string {
  const r = Math.round(Number(n) * 100) / 100;
  return `${Number.isInteger(r) ? r : r.toFixed(2)} ${currency === 'EUR' ? '€' : 'CHF'}`;
}

/** Nom de fichier : « bar-paintball-21-11-2026.pdf ». */
export function recapFilename(r: BarRecap): string {
  const slug = r.title.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '').slice(0, 40);
  const d = new Date(r.starts_at ?? r.generated_at);
  const day = new Intl.DateTimeFormat('fr-CH', { timeZone: TZ, day: '2-digit', month: '2-digit', year: 'numeric' }).format(d).replace(/\./g, '-');
  return `bar-${slug || 'soiree'}-${day}.pdf`;
}

/** Le récapitulatif de la soirée en PDF (A4) : chiffres clés, qui a pris quoi, par article, barmans. */
export function recapPdf(r: BarRecap): Uint8Array<ArrayBuffer> {
  const doc = new PdfDoc();
  const L = PAGE.margin;
  const R = PAGE.w - PAGE.margin;
  const cur = (n: number) => money(n, r.currency);
  const free = r.free_bar;

  // En-tête
  doc.rect(L, doc.y, 4, 46, ACCENT);
  doc.text(L + 14, doc.y, 'Récapitulatif du bar', { size: 20, bold: true });
  doc.text(L + 14, doc.y + 26, fit(r.title, R - L - 14, 13), { size: 13, color: MUTED });
  doc.y += 58;
  const when = [r.starts_at ? `Soirée du ${dayFmt.format(new Date(r.starts_at))}` : null,
    r.closed_at ? `bar fermé le ${stampFmt.format(new Date(r.closed_at))}` : 'bar encore ouvert'].filter(Boolean).join(' · ');
  doc.text(L, doc.y, when, { size: 9, color: MUTED });
  doc.text(L, doc.y + 12, `Édité le ${stampFmt.format(new Date(r.generated_at))}`, { size: 9, color: MUTED });
  doc.y += 34;

  // Chiffres clés
  const stats: [string, string, [number, number, number]][] = free
    ? [[String(r.totals.served), 'articles servis (bar offert)', INK], [String(r.totals.people), 'personnes', INK]]
    : [[String(r.totals.served), 'articles servis', INK], [cur(r.totals.amount), 'total consommé', INK],
       [cur(r.totals.refunded), 'remboursé', MINT], [cur(r.totals.due), 'reste à recevoir', CORAL]];
  const boxW = (R - L - (stats.length - 1) * 8) / stats.length;
  stats.forEach(([value, label, color], i) => {
    const x = L + i * (boxW + 8);
    doc.rect(x, doc.y, boxW, 50, SOFT);
    doc.text(x + 10, doc.y + 9, fit(value, boxW - 20, 16, true), { size: 16, bold: true, color });
    doc.text(x + 10, doc.y + 32, fit(label, boxW - 20, 8.5), { size: 8.5, color: MUTED });
  });
  doc.y += 62;
  if (r.totals.pending > 0) {
    doc.text(L, doc.y, `${r.totals.pending} article${r.totals.pending > 1 ? 's' : ''} encore en attente (pas servis, pas comptés).`, { size: 9, color: CORAL });
    doc.y += 16;
  }

  const heading = (title: string) => {
    doc.ensure(40);
    doc.y += 8;
    doc.text(L, doc.y, title, { size: 13, bold: true });
    doc.y += 20;
    doc.line(L, doc.y, R, [200, 200, 210]);
    doc.y += 8;
  };
  const label = (i: RecapLine) => (i.detail ? `${i.name} (${i.detail})` : i.name);

  // Par personne
  heading(`Par personne (${r.people.length})`);
  if (!r.people.length) { doc.text(L, doc.y, 'Personne n’a rien pris.', { size: 10, color: MUTED }); doc.y += 16; }
  for (const p of r.people) {
    const height = 22 + p.items.length * 14 + (free ? 0 : 16);
    doc.ensure(height);
    doc.text(L, doc.y, fit(p.name, R - L - 150, 11, true), { size: 11, bold: true });
    doc.text(R, doc.y, free ? `${p.served} article${p.served > 1 ? 's' : ''}` : cur(p.amount), { size: 11, bold: true, align: 'right' });
    doc.y += 17;
    for (const i of p.items) {
      doc.text(L + 12, doc.y, `${i.qty} ×`, { size: 10, color: MUTED });
      doc.text(L + 40, doc.y, fit(label(i), R - L - 130, 10), { size: 10 });
      if (!free) doc.text(R, doc.y, cur(i.amount), { size: 10, color: MUTED, align: 'right' });
      doc.y += 14;
    }
    if (!free) {
      const rest = p.balance > 0 ? `reste dû ${cur(p.balance)}` : p.balance < 0 ? `à lui rendre ${cur(-p.balance)}` : 'tout est réglé';
      const line = [p.refunded > 0 ? `Remboursé ${cur(p.refunded)}` : null, rest, p.pending ? `${p.pending} en attente` : null].filter(Boolean).join(' · ');
      doc.text(L + 12, doc.y, line, { size: 9, color: p.balance > 0 ? CORAL : MINT });
      doc.y += 14;
    }
    doc.y += 2;
    doc.line(L, doc.y, R);
    doc.y += 8;
  }

  // Par article
  heading('Par article');
  doc.text(L, doc.y, 'Article', { size: 9, bold: true, color: MUTED });
  doc.text(R - (free ? 0 : 110), doc.y, 'Quantité', { size: 9, bold: true, color: MUTED, align: 'right' });
  if (!free) doc.text(R, doc.y, 'Montant', { size: 9, bold: true, color: MUTED, align: 'right' });
  doc.y += 16;
  for (const i of r.items) {
    doc.ensure(16);
    doc.text(L, doc.y, fit(label(i), R - L - 200, 10), { size: 10 });
    doc.text(R - (free ? 0 : 110), doc.y, String(i.qty), { size: 10, align: 'right' });
    if (!free) doc.text(R, doc.y, cur(i.amount), { size: 10, align: 'right' });
    doc.y += 15;
  }
  doc.line(L, doc.y, R, [200, 200, 210]);
  doc.y += 6;
  doc.text(L, doc.y, 'Total', { size: 10, bold: true });
  doc.text(R - (free ? 0 : 110), doc.y, String(r.totals.served), { size: 10, bold: true, align: 'right' });
  if (!free) doc.text(R, doc.y, cur(r.totals.amount), { size: 10, bold: true, align: 'right' });
  doc.y += 20;

  // Barmans
  if (r.staff.length) {
    heading('Barmans');
    for (const s of r.staff) {
      doc.ensure(16);
      doc.text(L, doc.y, fit(s.name, R - L - 120, 10), { size: 10 });
      doc.text(R, doc.y, `${s.served} servi${s.served > 1 ? 's' : ''}`, { size: 10, align: 'right' });
      doc.y += 15;
    }
  }

  return doc.bytes((page, total) => `Vendredi Party · ${r.title} · page ${page} / ${total}`.slice(0, 120));
}

