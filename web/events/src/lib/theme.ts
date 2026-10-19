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
};

export const fonts = {
  display: 'BricolageGrotesque_800ExtraBold',
  body: 'Figtree_400Regular',
  medium: 'Figtree_500Medium',
  semibold: 'Figtree_600SemiBold',
  bold: 'Figtree_700Bold',
};

export const radius = { sm: 10, md: 14, lg: 20, pill: 999 };

export const rsvpColors = { yes: colors.accent, maybe: colors.lavender, no: colors.coral } as const;
