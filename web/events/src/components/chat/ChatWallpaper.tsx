import { StyleSheet, View, type ViewStyle } from 'react-native';

/** Motif discret derrière les bulles, façon WhatsApp : petits dessins de fête (étoiles, notes, verres, confettis) en
 * filigrane, répétés. Une image SVG en ligne (aucune ressource externe), presque invisible sur la nuit violette. */
const TILE = `<svg xmlns="http://www.w3.org/2000/svg" width="180" height="180" viewBox="0 0 180 180" fill="none"
 stroke="#FFFFFF" stroke-opacity="0.06" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
<path d="M22 30l6 12 13 2-9 9 2 13-12-6-12 6 2-13-9-9 13-2z"/>
<path d="M120 22v26a7 7 0 1 1-4-6V26l18-4v20a7 7 0 1 1-4-6V22"/>
<path d="M70 92h22l-11 16zM81 108v16M74 124h14"/>
<circle cx="150" cy="96" r="5"/><circle cx="34" cy="138" r="3"/><circle cx="100" cy="160" r="4"/>
<path d="M140 140l14 14M154 140l-14 14"/>
<path d="M60 40c6-6 12 6 18 0s12 6 18 0"/>
<path d="M14 92c8-4 10 6 18 2"/>
<path d="M160 50l4 4M168 46l-2 6"/>
</svg>`;

// Propriétés CSS passées telles quelles par react-native-web (absentes des types de React Native).
const pattern = {
  backgroundImage: `url("data:image/svg+xml,${encodeURIComponent(TILE)}")`,
  backgroundRepeat: 'repeat',
  backgroundSize: '180px 180px',
} as unknown as ViewStyle;

export function ChatWallpaper() {
  return <View pointerEvents="none" accessible={false} style={[StyleSheet.absoluteFill, pattern]} />;
}
