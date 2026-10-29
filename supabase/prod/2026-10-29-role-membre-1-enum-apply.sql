-- PROD, role_membre_enum (20261028200000_role_membre_enum).
-- À appliquer SEULEMENT après l'accord explicite de l'admin (« Ok prod »), dans l'ordre : 1-enum puis 2.
-- Rejouable.
-- Nouveau rôle « Membre » (valeur basic), entre Guest et Membre VIP (retour de l'admin du 28 octobre 2026).
-- À part : une nouvelle valeur d'énumération doit être enregistrée avant d'être utilisée (20261028200100).
alter type public.member_role add value if not exists 'basic' before 'member';

insert into supabase_migrations.schema_migrations (version, name) values ('20261028200000', 'role_membre_enum')
  on conflict (version) do nothing;
