import { readFileSync, writeFileSync } from 'node:fs';

const path = new URL('../dist/index.html', import.meta.url);
// Comportement d’app : pas de rebond qui entraîne la page, pas de zoom au double tap,
// pas de surbrillance grise au toucher, plein écran jusqu’aux bords arrondis de l’iPhone.
const appStyle = `<style id="app-shell">
html,body,#root{height:100%;margin:0;background:#0E0B16;overflow:hidden}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;touch-action:manipulation;overscroll-behavior:none}
*{-webkit-tap-highlight-color:transparent;overscroll-behavior:contain}
*{touch-action:pan-x pan-y}
</style>`;
let html = readFileSync(path, 'utf8')
  .replace('<html lang="en">', '<html lang="fr">')
  .replace('You need to enable JavaScript to run this app.', 'Active JavaScript pour consulter les événements de Party.')
  .replace(/<meta name="viewport"[^>]*>/, '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="#0E0B16">');
if (!html.includes('id="app-shell"')) html = html.replace('</head>', `${appStyle}</head>`);
writeFileSync(path, html);
