-- PROD, retour arrière de contact_names (20261103170000) : l'app iPhone ne reconnaît plus les contacts (elle garde
-- les pseudos ; les noms déjà reconnus restent sur l'appareil jusqu'à la prochaine actualisation). La clé des
-- empreintes est supprimée : une nouvelle sera tirée si la migration est réappliquée. Tout ou rien.
begin;

drop function if exists public.contacts_match(text[]);
drop function if exists public.contacts_key();
drop table if exists private.contact_match_calls;
drop table if exists private.contact_key;

delete from supabase_migrations.schema_migrations where version = '20261103170000';
commit;

notify pgrst, 'reload schema';
