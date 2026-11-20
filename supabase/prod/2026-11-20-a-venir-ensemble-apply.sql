begin;
-- Profil d'une personne, « À venir ensemble » (retour de l'admin, 20.11.2026, capture du profil de Hono) : la liste montrait
-- les événements où la personne avait répondu « Pas présent ». Ensemble = les deux y vont : l'autre ET moi sommes Présent,
-- Peut-être ou organisateurs. (« Invité » sans réponse ou « Pas présent » : pas ensemble.) Le compte suit la même règle.
-- Modifie member_mini par repère (texte en place relu, jamais réécrit en entier). Rejouable.
do $$
declare src text := pg_get_functiondef('public.member_mini(uuid)'::regprocedure);
  old_text text := 'and public.can_see_event(ev.id) and private.chat_role(ev, p.id, me) is not null) y;';
  new_text text := 'and public.can_see_event(ev.id) and private.chat_role(ev, p.id, me) in (''organizer'', ''yes'', ''maybe'')
            and private.chat_role(ev, me, me) in (''organizer'', ''yes'', ''maybe'')) y;';
begin
  if position('private.chat_role(ev, me, me) in (''organizer'', ''yes'', ''maybe'')' in src) > 0 then return; end if;  -- déjà fait
  if position(old_text in src) = 0 then raise exception 'member_mini : repère introuvable, rien changé'; end if;
  execute replace(src, old_text, new_text);
end $$;
insert into supabase_migrations.schema_migrations (version, name) values ('20261120150000', 'a_venir_ensemble') on conflict do nothing;
commit;
