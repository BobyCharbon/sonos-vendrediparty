// Abonné temps réel avec la vraie bibliothèque de l'app (lancé depuis web/events pour ses node_modules) : écrit READY,
// puis la liste des changements reçus sur member_group_members (filtrés sur le compte) au bout de 12 s.
import { createClient } from '@supabase/supabase-js';
const [url, key, token, uid] = process.argv.slice(2);
const sb = createClient(url, key, { global: { headers: { Authorization: `Bearer ${token}` } }, auth: { persistSession: false } });
sb.realtime.setAuth(token);
const got = [];
sb.channel('probe').on('postgres_changes', { event: '*', schema: 'public', table: 'member_group_members', filter: `user_id=eq.${uid}` },
  (p) => got.push(p.eventType)).subscribe((s) => { if (s === 'SUBSCRIBED') console.log('READY'); });
setTimeout(() => { console.log(JSON.stringify(got)); process.exit(0); }, 12000);
