import { readFileSync, writeFileSync } from 'node:fs';
const path = new URL('../dist/index.html', import.meta.url);
const html = readFileSync(path, 'utf8').replace('<html lang="en">', '<html lang="fr">').replace('You need to enable JavaScript to run this app.', 'Active JavaScript pour consulter les événements de Party.');
writeFileSync(path, html);
