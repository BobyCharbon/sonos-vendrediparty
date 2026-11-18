import { createElement } from 'react';

/** Icônes au trait des maquettes Néon (24 × 24, trait arrondi), en SVG dans la page : le module ne tourne que sur le web. */
const PATHS = {
  search: ['M11 4a7 7 0 1 0 0 14a7 7 0 1 0 0-14', 'm20 20-3.6-3.6'],
  compose: ['M12 4H6.5A2.5 2.5 0 0 0 4 6.5v11A2.5 2.5 0 0 0 6.5 20h11a2.5 2.5 0 0 0 2.5-2.5V12', 'M17.6 3.4a2 2 0 0 1 2.9 2.9L12.2 14.6 8.5 15.5l.9-3.7z'],
  bellslash: ['M18 8.5A6 6 0 0 0 8.4 3.7M6 8.5C6 15 3 17 3 17h14', 'M13.7 21a2 2 0 0 1-3.4 0', 'm3 3 18 18'],
  bell: ['M6 8a6 6 0 1 1 12 0c0 7 3 8 3 8H3s3-1 3-8', 'M10 20a2 2 0 0 0 4 0'],
  moon: ['M20 14.5A8 8 0 1 1 9.5 4a6.5 6.5 0 0 0 10.5 10.5z'],
  more: ['M5 11.1a.9.9 0 1 0 0 1.8a.9.9 0 1 0 0-1.8', 'M12 11.1a.9.9 0 1 0 0 1.8a.9.9 0 1 0 0-1.8', 'M19 11.1a.9.9 0 1 0 0 1.8a.9.9 0 1 0 0-1.8'],
  mic: ['M12 3a3 3 0 0 1 3 3v5.5a3 3 0 0 1-6 0V6a3 3 0 0 1 3-3z', 'M5.5 11a6.5 6.5 0 0 0 13 0M12 17.5V21'],
  check: ['m5 12.5 4.5 4.5L19 7.5'],
  check2: ['m2.5 12.5 4.5 4.5L15.5 7.5', 'm11.5 16 1 1L21.5 7.5'],
  pin: ['M12 16.5V22M8.5 3h7l-1 6 3.5 4.5h-12L9.5 9z'],
  archive: ['M4.5 4h15A1.5 1.5 0 0 1 21 5.5v2A1.5 1.5 0 0 1 19.5 9h-15A1.5 1.5 0 0 1 3 7.5v-2A1.5 1.5 0 0 1 4.5 4z', 'M5 9v9a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9M10 13h4'],
  inbox: ['M3 13h4.5l1.5 3h6l1.5-3H21', 'M5.6 5h12.8L21 13v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5z'],
  chat: ['M21 11.5a8.5 8.5 0 0 1-12.4 7.6L3 20.5l1.5-5A8.5 8.5 0 1 1 21 11.5z'],
  users: ['M9 4.5a3.5 3.5 0 1 0 0 7a3.5 3.5 0 1 0 0-7', 'M2.5 20a6.5 6.5 0 0 1 13 0', 'M16 4.6a3.5 3.5 0 0 1 0 6.8M18 14.5a6.5 6.5 0 0 1 3.5 5.5'],
  sparkle: ['M12 3c.6 4.6 2.4 6.4 7 7-4.6.6-6.4 2.4-7 7-.6-4.6-2.4-6.4-7-7 4.6-.6 6.4-2.4 7-7z'],
  person: ['M12 4a4 4 0 1 0 0 8a4 4 0 1 0 0-8', 'M4 21a8 8 0 0 1 16 0'],
  block: ['M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18', 'm5.6 5.6 12.8 12.8'],
  flag: ['M5 21V4M5 4h11.5l-2 4.5 2 4.5H5'],
  x: ['M6 6l12 12M18 6 6 18'],
  chevl: ['m15 18-6-6 6-6'],
  chevr: ['m9 18 6-6-6-6'],
  camera: ['M3 8.5A2.5 2.5 0 0 1 5.5 6h2l1.6-2.2h5.8L16.5 6h2A2.5 2.5 0 0 1 21 8.5v9a2.5 2.5 0 0 1-2.5 2.5h-13A2.5 2.5 0 0 1 3 17.5z', 'M12 9.2a3.6 3.6 0 1 0 0 7.2a3.6 3.6 0 1 0 0-7.2'],
  cal: ['M6.5 4.5h11A3.5 3.5 0 0 1 21 8v9.5a3.5 3.5 0 0 1-3.5 3.5h-11A3.5 3.5 0 0 1 3 17.5V8a3.5 3.5 0 0 1 3.5-3.5z', 'M3 9.5h18M8 2.5v4M16 2.5v4'],
} as const;
export type IconName = keyof typeof PATHS;

export function Icon({ name, size = 22, color = 'currentColor', stroke }: { name: IconName; size?: number; color?: string; stroke?: number }) {
  const width = stroke ?? (size <= 13 ? 2.4 : size <= 16 ? 2.1 : 1.9);
  return createElement('svg', {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: color, strokeWidth: width,
    strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': true, style: { flexShrink: 0, display: 'block' },
  }, PATHS[name].map((d) => createElement('path', { key: d, d })));
}
