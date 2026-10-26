import { readFileSync, writeFileSync } from 'node:fs';

const path = new URL('../dist/index.html', import.meta.url);
// Comportement d’app : pas de rebond qui entraîne la page, pas de zoom au double tap,
// pas de surbrillance grise au toucher, plein écran jusqu’aux bords arrondis de l’iPhone.
// Jamais d’overscroll-behavior ni de touch-action sur « * » (retour #10) : sous Android, Chrome traite chaque
// carte en overflow: hidden comme un conteneur de défilement ; avec overscroll-behavior: contain, le geste
// commencé sur une carte n’atteignait plus la liste (seul le bord droit, sans carte, défilait). Le rebond est
// déjà bloqué par html { overscroll-behavior: none }. Test : test_android_finger_on_an_event_card_scrolls_the_list.
const appStyle = `<style id="app-shell">
html,body,#root{height:100%;margin:0;background:#0B0817;overflow:hidden}
#root{background:#15102A}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%;touch-action:manipulation;overscroll-behavior:none}
*{-webkit-tap-highlight-color:transparent}
</style>`;
let html = readFileSync(path, 'utf8')
  .replace('<html lang="en">', '<html lang="fr">')
  .replace('You need to enable JavaScript to run this app.', 'Active JavaScript pour consulter les événements de Party.')
  .replace(/<meta name="viewport"[^>]*>/, '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover"><meta name="theme-color" content="#15102A">');
if (!html.includes('id="app-shell"')) html = html.replace('</head>', `${appStyle}</head>`);
writeFileSync(path, html);
