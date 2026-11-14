// Abonné temps réel avec la vraie bibliothèque de l'app (lancé depuis web/events pour ses node_modules) : écrit READY,
// puis la liste des changements reçus au bout de 12 s : sur member_group_members (filtrés sur le compte) par défaut,
// ou sur la table et le filtre donnés en 5e et 6e arguments (avis ead4902642da : rsvps, bring_claims…).
import { createClient } from '@supabase/supabase-js';
const [url, key, token, uid, table = 'member_group_members', filter = `user_id=eq.${uid}`] = process.argv.slice(2);
const sb = createClient(url, key, { global: { headers: { Authorization: `Bearer ${token}` } }, auth: { persistSession: false } });
sb.realtime.setAuth(token);
const got = [];
sb.channel('probe').on('postgres_changes', { event: '*', schema: 'public', table, filter },
  (p) => got.push(p.eventType)).subscribe((s) => { if (s === 'SUBSCRIBED') console.log('READY'); });
setTimeout(() => { console.log(JSON.stringify(got)); process.exit(0); }, 12000);
