/**
 * Petit PDF A4 écrit à la main (texte, filets, rectangles ; Helvetica et Helvetica-Bold, accents et « € » compris), pour
 * exporter un récapitulatif sans bibliothèque ni serveur. Les emojis n'existent pas dans ces polices : ils sont retirés.
 */
export const PAGE = { w: 595.28, h: 841.89, margin: 42 };

// Largeurs Helvetica / Helvetica-Bold (AFM, millièmes de point) des caractères 32 à 126.
const REGULAR = [278, 278, 355, 556, 556, 889, 667, 191, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556,
  556, 556, 556, 278, 278, 584, 584, 584, 556, 1015, 667, 667, 722, 722, 667, 611, 778, 722, 278, 500, 667, 556, 833, 722, 778, 667,
  778, 722, 667, 611, 722, 667, 944, 667, 667, 611, 278, 278, 278, 469, 556, 333, 556, 556, 500, 556, 556, 278, 556, 556, 222, 222,
  500, 222, 833, 556, 556, 556, 556, 333, 500, 278, 556, 500, 722, 500, 500, 500, 334, 260, 334, 584];
const BOLD = [278, 333, 474, 556, 556, 889, 722, 238, 333, 333, 389, 584, 278, 333, 278, 278, 556, 556, 556, 556, 556, 556, 556, 556,
  556, 556, 333, 333, 584, 584, 584, 611, 975, 722, 722, 722, 722, 667, 611, 778, 722, 278, 556, 722, 611, 833, 722, 778, 667, 778,
  722, 667, 611, 722, 667, 944, 667, 667, 611, 333, 278, 333, 584, 556, 333, 556, 611, 556, 611, 556, 333, 611, 611, 278, 278, 556,
  278, 889, 611, 611, 611, 611, 389, 556, 333, 611, 556, 778, 556, 556, 500, 389, 280, 389, 584];
// Caractères hors ASCII de WinAnsiEncoding (le reste de Latin-1, 0xA0 à 0xFF, garde son code).
const WIN: Record<string, number> = { '€': 0x80, '‚': 0x82, '„': 0x84, '…': 0x85, 'Œ': 0x8c, '‘': 0x91, '’': 0x92, '“': 0x93,
  '”': 0x94, '•': 0x95, '–': 0x96, '—': 0x97, 'œ': 0x9c, ' ': 0xa0 };
const WIDE: Record<number, number> = { 0x80: 556, 0x85: 1000, 0x91: 222, 0x92: 222, 0x93: 333, 0x94: 333, 0x95: 350, 0x96: 556,
  0x97: 1000, 0x8c: 1000, 0x9c: 944, 0xa0: 278, 0xab: 556, 0xbb: 556, 0xb7: 278, 0xd7: 584 };

/** Texte → codes WinAnsi (emojis et caractères inconnus retirés). */
function codes(text: string): number[] {
  const out: number[] = [];
  for (const ch of text) {
    const c = ch.codePointAt(0) ?? 0;
    if (c >= 32 && c <= 126) out.push(c);
    else if (WIN[ch] != null) out.push(WIN[ch]);
    else if (c >= 0xa0 && c <= 0xff) out.push(c);
  }
  return out;
}

function charWidth(c: number, bold: boolean): number {
  if (c >= 32 && c <= 126) return (bold ? BOLD : REGULAR)[c - 32];
  if (WIDE[c] != null) return WIDE[c];
  const base = String.fromCharCode(c).normalize('NFD').charCodeAt(0);  // « é » ≈ « e »
  return base >= 32 && base <= 126 ? (bold ? BOLD : REGULAR)[base - 32] : 556;
}

export function textWidth(text: string, size: number, bold = false): number {
  return codes(text).reduce((sum, c) => sum + charWidth(c, bold), 0) * size / 1000;
}

/** Coupe le texte à la largeur donnée, avec « … ». */
export function fit(text: string, width: number, size: number, bold = false): string {
  if (textWidth(text, size, bold) <= width) return text;
  let t = text;
  while (t.length > 1 && textWidth(`${t}…`, size, bold) > width) t = t.slice(0, -1);
  return `${t.trimEnd()}…`;
}

type Rgb = [number, number, number];
const rgb = (c: Rgb) => c.map((v) => (v / 255).toFixed(3)).join(' ');
const num = (n: number) => n.toFixed(2);

export class PdfDoc {
  private pages: string[][] = [];
  private ops: string[] = [];
  /** Position verticale du curseur, depuis le HAUT de la page (plus simple à lire que le repère PDF). */
  y = PAGE.margin;

  constructor() { this.newPage(); }

  newPage() {
    this.ops = [];
    this.pages.push(this.ops);
    this.y = PAGE.margin;
  }

  /** Pas la place pour `height` points : page suivante. */
  ensure(height: number) {
    if (this.y + height > PAGE.h - PAGE.margin - 24) this.newPage();
  }

  text(x: number, top: number, text: string, opts: { size?: number; bold?: boolean; color?: Rgb; align?: 'left' | 'right' } = {}) {
    const size = opts.size ?? 10;
    const bold = !!opts.bold;
    const bytes = codes(text);
    if (!bytes.length) return;
    const left = opts.align === 'right' ? x - textWidth(text, size, bold) : x;
    const escaped = bytes.map((c) => (c === 40 || c === 41 || c === 92 ? `\\${String.fromCharCode(c)}`
      : c < 128 ? String.fromCharCode(c) : `\\${c.toString(8).padStart(3, '0')}`)).join('');
    this.ops.push(`${rgb(opts.color ?? [20, 20, 28])} rg BT /${bold ? 'F2' : 'F1'} ${size} Tf 1 0 0 1 ${num(left)} ${num(PAGE.h - top - size)} Tm (${escaped}) Tj ET`);
  }

  rect(x: number, top: number, w: number, h: number, color: Rgb) {
    this.ops.push(`${rgb(color)} rg ${num(x)} ${num(PAGE.h - top - h)} ${num(w)} ${num(h)} re f`);
  }

  line(x1: number, top: number, x2: number, color: Rgb = [220, 220, 228]) {
    this.ops.push(`${rgb(color)} RG 0.6 w ${num(x1)} ${num(PAGE.h - top)} m ${num(x2)} ${num(PAGE.h - top)} l S`);
  }

  /** Octets du fichier ; `footer(page, total)` est écrit en bas de chaque page. */
  bytes(footer?: (page: number, total: number) => string): Uint8Array<ArrayBuffer> {
    const total = this.pages.length;
    const chunks: string[] = [];
    const offsets: number[] = [];
    let length = 0;
    const add = (s: string) => { chunks.push(s); length += s.length; };  // un caractère = un octet (latin-1)
    const obj = (id: number, body: string) => { offsets[id] = length; add(`${id} 0 obj\n${body}\nendobj\n`); };
    add('%PDF-1.4\n%\xe2\xe3\xcf\xd3\n');
    const pageIds = this.pages.map((_, i) => 5 + i * 2);
    obj(1, '<< /Type /Catalog /Pages 2 0 R >>');
    obj(2, `<< /Type /Pages /Kids [${pageIds.map((id) => `${id} 0 R`).join(' ')}] /Count ${total} >>`);
    obj(3, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>');
    obj(4, '<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>');
    this.pages.forEach((ops, i) => {
      if (footer) {
        this.ops = ops;
        this.text(PAGE.w / 2 - textWidth(footer(i + 1, total), 8) / 2, PAGE.h - PAGE.margin + 6, footer(i + 1, total), { size: 8, color: [130, 130, 140] });
      }
      const stream = ops.join('\n');
      obj(pageIds[i], `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${PAGE.w} ${PAGE.h}] /Resources << /Font << /F1 3 0 R /F2 4 0 R >> >> /Contents ${pageIds[i] + 1} 0 R >>`);
      obj(pageIds[i] + 1, `<< /Length ${stream.length} >>\nstream\n${stream}\nendstream`);
    });
    const xref = length;
    const count = pageIds.length * 2 + 5;
    add(`xref\n0 ${count}\n0000000000 65535 f \n`);
    for (let id = 1; id < count; id++) add(`${String(offsets[id]).padStart(10, '0')} 00000 n \n`);
    add(`trailer\n<< /Size ${count} /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
    const text = chunks.join('');
    const out = new Uint8Array(text.length);
    for (let i = 0; i < text.length; i++) out[i] = text.charCodeAt(i) & 0xff;
    return out;
  }
}

/** Partager le PDF (iPhone, Android : Fichiers, Mail, AirDrop, imprimer…) ou, sinon, le télécharger. */
export async function savePdf(bytes: Uint8Array<ArrayBuffer>, filename: string, title: string): Promise<'shared' | 'downloaded' | 'cancelled'> {
  const blob = new Blob([bytes], { type: 'application/pdf' });
  const file = typeof File === 'function' ? new File([blob], filename, { type: 'application/pdf' }) : null;
  const touch = typeof navigator !== 'undefined' && (navigator.maxTouchPoints ?? 0) > 0;
  if (file && touch && navigator.canShare?.({ files: [file] })) {
    try {
      await navigator.share({ files: [file], title });
      return 'shared';
    } catch (e) {
      if ((e as { name?: string }).name === 'AbortError') return 'cancelled';
    }
  }
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 60_000);
  return 'downloaded';
}
