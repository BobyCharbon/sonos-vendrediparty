-- Retour arrière : le compte de démo repasse en attente (il peut aussi être supprimé depuis l'admin).
begin;
update public.profiles set status = 'pending' where id = '49d9777e-82a5-49d2-b9c3-6f07f0d91fdd';
delete from supabase_migrations.schema_migrations where version = '20261105100000';
commit;
