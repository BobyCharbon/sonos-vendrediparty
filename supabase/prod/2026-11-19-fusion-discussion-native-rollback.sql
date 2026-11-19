-- PROD, retour arrière de fusion_discussion_native (20261119100000) : les fonctions remplacées retrouvent leur texte de prod du 19.11 (lu
-- avant la mise en prod), les nouveaux déclencheurs sont retirés. Tables, colonnes et fonctions nouvelles restent
-- (sans effet). Tout ou rien.
begin;
drop trigger if exists chat_list_state_to_event_prefs on public.chat_list_state;

drop trigger if exists event_chat_prefs_to_list on public.event_chat_prefs;

delete from supabase_migrations.schema_migrations where version = '20261119100000';
commit;
