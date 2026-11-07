-- Ménage (accord de l'admin, 07.11.2026) : compte vide créé par erreur en PRODUCTION à 03:04 UTC par le banc des bots
-- (module construit avec un cache Metro périmé qui visait la prod). Numéro de test de Bot Oscar, aucun prénom, aucun contenu.
-- Pas de retour arrière : le compte n'avait rien.
begin;
delete from auth.users
  where phone = '41790000104'
    and created_at between '2026-11-07 03:00:00+00' and '2026-11-07 03:10:00+00'
    and not exists (select 1 from public.profiles p where p.id = auth.users.id and coalesce(p.display_name, '') <> '');
insert into supabase_migrations.schema_migrations (version, name) values ('20261107130000', 'supprimer_compte_bot');
commit;
