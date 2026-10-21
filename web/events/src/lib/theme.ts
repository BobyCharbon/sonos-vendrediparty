export const colors = {
  bg: '#0E0B16',
  surface: '#1A1526',
  surface2: '#241D35',
  line: '#2E2A3D',
  lineStrong: '#3A3550',
  text: '#F4F1FA',
  textSoft: '#D6D1E2',
  muted: '#B5ADC7',
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

export const fonts = {
  display: 'BricolageGrotesque_800ExtraBold',
  body: 'Figtree_400Regular',
  medium: 'Figtree_500Medium',
  semibold: 'Figtree_600SemiBold',
  bold: 'Figtree_700Bold',
};

export const radius = { sm: 10, md: 14, lg: 20, pill: 999 };

export const rsvpColors = { yes: colors.mint, maybe: colors.coral, no: colors.red } as const;
