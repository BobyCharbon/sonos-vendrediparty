-- Bar de la soirée : un compte qui a commandé ou servi au bar peut toujours être supprimé (Apple 5.1.1(v), RGPD).
-- Trouvé par le test réel du 10.11.2026 (suppression d'un Guest par l'admin) : le registre « en ajout seul » refusait la
-- mise à vide automatique de ses colonnes de personne (actor, user_id, item_id : « on delete set null »), donc la
-- suppression du compte échouait (« event_bar_log est un registre en ajout seul »).
-- Désormais permis : seulement en cascade (pg_trigger_depth() > 1) et seulement une colonne qui devient vide ; toute
-- autre modification reste refusée. Purement additif et rejouable.
create or replace function private.guard_bar_append_only() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  -- Compte ou article supprimé : la ligne perd la personne (ou l'article), le reste ne bouge pas.
  if tg_op = 'UPDATE' and pg_trigger_depth() > 1 and not exists (
       select 1 from jsonb_each(to_jsonb(new)) n join jsonb_each(to_jsonb(old)) o using (key)
       where n.value is distinct from o.value and n.value <> 'null'::jsonb) then
    return new;
  end if;
  -- Engagements et journal : jamais modifiés ; effacés seulement par la purge ou en cascade (bar, compte supprimés).
  if tg_op = 'UPDATE' or (tg_op = 'DELETE' and coalesce(current_setting('party.bar_purge', true), '') <> 'on'
                          and pg_trigger_depth() = 1) then
    raise exception 'forbidden: % est un registre en ajout seul', tg_table_name using errcode = '42501';
  end if;
  return case when tg_op = 'DELETE' then old else new end;
end $$;
revoke all on function private.guard_bar_append_only() from public, anon, authenticated;
