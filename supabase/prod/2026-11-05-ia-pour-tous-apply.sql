-- PROD, ai_pour_tous (20261105110000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration. Rejouable.
-- Effet : le droit « Utiliser l'assistant IA » est donné une fois à tous les rôles (Guest → Admin). À appliquer en même
-- temps que le code (develop → main) qui demande l'accord exprès (403 « accord requis ») et pose le plafond global
-- (AI_GLOBAL_MONTHLY_BUDGET_USD, 30 $) ; jamais avant, sinon l'IA s'ouvre sans feuille d'accord.
-- Prérequis : 2026-11-02-droit-ia-apply.sql (20261031170000) et 2026-11-03-roles-apply.sql (20261103140000). Tout ou rien.
begin;
-- Assistant IA ouvert à tous les comptes (plan « bêta → main » du 04.11, audit A5) : le droit « Utiliser l'assistant
-- IA » (ai.use) est donné UNE fois à tous les rôles existants (Guest → Admin, rôles créés dans l'app compris).
-- Chaque rôle reste réglable ensuite dans Administration › Rôles et droits : un admin qui le retire à un rôle ne le voit
-- jamais revenir (la distribution ne repasse pas, private.one_time_changes).
-- Garde-fous côté serveur Party (app/assistant.py) : accord exprès avant le 1er envoi à Anthropic (403 « accord
-- requis » sinon), plafond mensuel par personne (AI_MONTHLY_BUDGET_USD) et pour toute l'app
-- (AI_GLOBAL_MONTHLY_BUDGET_USD, 30 $ par défaut). Purement additif et rejouable.

insert into public.permissions (key, grp, label, hint, sort) values
  ('ai.use', 'Assistant IA', 'Utiliser l''assistant IA',
   'Créer ou modifier un événement en le décrivant, lire un ticket (après accord ; chaque usage est compté et plafonné)', 70)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'ai_use_all_roles_2026_11_05') then
    return;
  end if;
  insert into public.role_permissions (role, perm) select key, 'ai.use' from public.roles on conflict do nothing;
  insert into private.one_time_changes (name) values ('ai_use_all_roles_2026_11_05');
end $$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261105110000', 'ai_pour_tous')
  on conflict (version) do nothing;
commit;
