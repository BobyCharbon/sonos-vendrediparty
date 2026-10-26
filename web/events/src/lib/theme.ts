import { Platform, type TextStyle } from 'react-native';

// Même nuit violette que le reste de Party (app/static/style.css) : une seule app, un seul fond.
export const colors = {
  bg: '#15102A',
  surface: '#221A3D',
  surface2: '#2C2350',
  line: '#2F2752',
  lineStrong: '#3E3468',
  text: '#F5F0FF',
  textSoft: '#D9D2EE',
  muted: '#B1A8CF',
  accent: '#FF4F9A',
  accentDim: '#3A1730',
  coral: '#FFB347',
  coralSoft: '#FFD099',
  coralDim: '#3B2918',
  lavender: '#B9A7FF',
  lavenderDim: '#2A2440',
  onAccent: '#240A18',
  onCoral: '#2A1A06',
  // Réponses : vert « c'est bon », rouge « absent » (toujours modifiable).
  mint: '#5BE3A6',
  mintDim: '#123527',
  onMint: '#0B2A1D',
  red: '#FF6363',
  redSoft: '#FF8A8A',
  redDim: '#3A1519',
  onRed: '#2B0A0C',
};

// Police système (SF Pro sur iPhone, comme le reste de Party) ; Bricolage reste la voix des grands titres.
const SYSTEM = Platform.OS === 'web'
  ? '-apple-system, BlinkMacSystemFont, "SF Pro Text", system-ui, "Segoe UI", Roboto, sans-serif'
  : undefined;
export const font = {
  display: { fontFamily: 'BricolageGrotesque_800ExtraBold' },
  body: { fontFamily: SYSTEM, fontWeight: '400' },
  medium: { fontFamily: SYSTEM, fontWeight: '500' },
  semibold: { fontFamily: SYSTEM, fontWeight: '600' },
  bold: { fontFamily: SYSTEM, fontWeight: '700' },
} as const satisfies Record<string, TextStyle>;
export type FontWeight = keyof typeof font;

export const radius = { sm: 10, md: 14, lg: 20, pill: 999 };

export const rsvpColors = { yes: colors.mint, maybe: colors.coral, no: colors.red } as const;
