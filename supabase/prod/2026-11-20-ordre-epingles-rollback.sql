-- Retour arrière de 20261120200100 : la fonction d'ordre disparaît (les épingles gardent leur dernier ordre).
begin;
drop function if exists public.reorder_chat_pins(jsonb);
delete from supabase_migrations.schema_migrations where version = '20261120200100';
commit;
