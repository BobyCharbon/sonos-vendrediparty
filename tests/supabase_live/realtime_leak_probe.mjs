// Abonné temps réel SANS filtre (test de sécurité) : écrit READY, puis au bout de 12 s la liste de ce qui est arrivé
// (type de changement + lignes reçues), pour vérifier qu'un compte ne reçoit rien d'un événement qu'il ne voit pas.
import { createClient } from '@supabase/supabase-js';
const [url, key, token, table] = process.argv.slice(2);
const sb = createClient(url, key, { global: { headers: { Authorization: `Bearer ${token}` } }, auth: { persistSession: false } });
sb.realtime.setAuth(token);
const got = [];
sb.channel('leak').on('postgres_changes', { event: '*', schema: 'public', table },
  (p) => got.push({ type: p.eventType, new: p.new, old: p.old })).subscribe((s) => { if (s === 'SUBSCRIBED') console.log('READY'); });
setTimeout(() => { console.log(JSON.stringify(got)); process.exit(0); }, 12000);
