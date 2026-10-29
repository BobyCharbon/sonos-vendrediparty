-- PROD, role_guest_plus_enum (20261029120000). À appliquer SEULEMENT après « Ok prod », AVANT le fichier 2.
-- Nouveau rôle « Guest+ » (valeur guestplus), entre Guest et Membre (demande de l'admin du 29 octobre 2026).
-- À part : une nouvelle valeur d'énumération doit être enregistrée avant d'être utilisée (20261029120100).
alter type public.member_role add value if not exists 'guestplus' after 'guest';

insert into supabase_migrations.schema_migrations (version, name) values ('20261029120000', 'role_guest_plus_enum')
  on conflict (version) do nothing;
