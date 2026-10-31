-- Droit « Assistant IA » (demande de l'admin du 31 octobre 2026) : utiliser l'IA de Party (Claude), d'abord pour lire
-- un ticket dans le pot commun. Chaque usage coûte : donné au seul rôle Admin au départ, puis réglable dans
-- Administration › Rôles et droits. Rejouable : la distribution initiale ne repasse jamais.

insert into public.permissions (key, grp, label, hint, sort) values
  ('ai.use', 'Assistant IA', 'Utiliser l''assistant IA', 'Scanner un ticket dans le pot commun (chaque usage est payant et compté)', 70)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'ai_use_2026_10_31') then
    return;
  end if;
  insert into public.role_permissions (role, perm) values ('admin', 'ai.use') on conflict do nothing;
  insert into private.one_time_changes (name) values ('ai_use_2026_10_31');
end $$;
