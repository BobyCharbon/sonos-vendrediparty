-- PROD, lot 6 (27.11) : suppression du compte de nouveau possible pour qui a validé l'événement d'un autre, ajouté un objet
-- « qui amène quoi », demandé / validé un groupe pour un événement, mis la photo d'un groupe (cascade *_by -> null à travers
-- guard_event, guard_bring_item, guard_event_group_status, group_photo_guard) ; blocage respecté (co-organisateur,
-- set_rsvp_for, notifications coorganizer_added / rsvp_set) — migration 20261127110000.
-- Testé sur TEST le 27.11 : tests/supabase_live/test_suppression_compte_cascade_live.py (vraie suppression par colonne, toutes
-- les lignes de TEST), test_blocage_coorganisateur_live.py. Rejouable, ancres vérifiées contre la prod (lecture seule).
-- Indépendant des fichiers du « Plan de mise en prod du 27.11 » (aucune fonction commune) : n'importe quel ordre.
-- Retour arrière : 2026-11-27-suppression-blocage-rollback.sql.
begin;
-- Lot 6 (27.11), additive et rejouable.
-- 1. Suppression du compte (Apple 5.1.1(v)) : comme pour les présences sans compte (20261127090000), la cascade
--    `on delete set null` d'une colonne « qui a fait quoi » passait par des gardes BEFORE UPDATE qui la refusaient
--    (guard_event : « Seuls ses organisateurs… » pour qui a VALIDÉ l'événement d'un autre) ou remettaient l'identifiant
--    effacé (guard_bring_item : added_by / claimed_by, guard_event_group_status : requested_by / answered_by,
--    group_photo_guard : photo_by). Remis, l'identifiant d'un compte effacé reste dans la ligne (la base ne le revérifie
--    pas) ou fait échouer la suppression. Correctif : une mise à jour qui ne change QUE des colonnes « qui » de la table
--    (liste fermée par garde), vers null, et seulement quand le compte qu'elles nommaient n'existe plus (cascade de la
--    base, jamais l'écran), passe telle quelle. Chaque garde est étendue par ancre (insertion en tête du corps).
-- 2. Blocage (Apple 1.2) : ni co-organisateur (event_organizers), ni présence notée (set_rsvp_for) entre deux personnes
--    dont l'une a bloqué l'autre ; « coorganizer_added » et « rsvp_set » rejoignent les notifications jetées entre
--    personnes bloquées (drop_blocked_notification).

-- 1. Suppression du compte -----------------------------------------------------------------------------------------------
-- o / n : ancienne et nouvelle ligne ; cols : les colonnes « qui » de la table que la cascade peut vider.
create or replace function private.cleared_by_account_deletion(o jsonb, n jsonb, cols text[]) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from jsonb_each(o) e where e.value is distinct from n -> e.key)
     and not exists (
       select 1 from jsonb_each(o) e
       where e.value is distinct from n -> e.key
         and not (
           e.key = any (cols)
           and jsonb_typeof(n -> e.key) = 'null'
           and jsonb_typeof(e.value) = 'string'
           and (e.value #>> '{}') ~ '^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
           and (not exists (select 1 from public.profiles p where p.id = (e.value #>> '{}')::uuid)
                or not exists (select 1 from auth.users u where u.id = (e.value #>> '{}')::uuid))));
$$;
revoke all on function private.cleared_by_account_deletion(jsonb, jsonb, text[]) from public, anon, authenticated;

do $patch$
declare def text; f record;
begin
  for f in select * from (values
    ('public.guard_event()', 'approved_by', $a$declare s group_settings; privileged boolean;
begin
$a$),
    ('public.guard_bring_item()', 'added_by,claimed_by', $a$declare promised int;
begin
$a$),
    ('private.guard_event_group_status()', 'requested_by,answered_by', $a$AS $function$
begin
$a$),
    ('private.group_photo_guard()', 'photo_by,invite_token_by,created_by', $a$AS $function$
begin
$a$)) v(fn, cols, anchor)
  loop
    def := pg_get_functiondef(f.fn::regprocedure);
    continue when position('compte supprimé : la base efface seulement qui a fait quoi' in def) > 0;
    if position(f.anchor in def) = 0 then
      raise exception '% : ancre introuvable, rien n''est modifié', f.fn;
    end if;
    -- `public.guard_event` a search_path = public : la fonction private.* est toujours nommée en entier.
    execute replace(def, f.anchor, f.anchor || format($a$  if tg_op = 'UPDATE' and private.cleared_by_account_deletion(to_jsonb(old), to_jsonb(new), %L) then
    return new; -- compte supprimé : la base efface seulement qui a fait quoi (20261127110000)
  end if;
$a$, '{' || f.cols || '}'));
  end loop;
end $patch$;

-- 2. Blocage -------------------------------------------------------------------------------------------------------------
-- Co-organisateur : jamais quelqu'un qui m'a bloqué ou que j'ai bloqué (service / séries récurrentes : auth.uid() null).
create or replace function private.guard_coorganizer_block() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if private.blocked_either(auth.uid(), new.user_id) then
    raise exception 'blocked: tu ne peux pas ajouter cette personne comme co-organisateur' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.guard_coorganizer_block() from public, anon, authenticated;
drop trigger if exists event_organizers_block on public.event_organizers;
create trigger event_organizers_block before insert or update of user_id on public.event_organizers
  for each row execute function private.guard_coorganizer_block();

-- Présence notée par l'organisateur : même refus.
do $patch$
declare def text;
  anchor text := $a$  if not private.is_account_active(member) then raise exception 'Ce compte n''existe pas ou n''est plus actif'; end if;
$a$;
  added text := $a$  if private.blocked_either(auth.uid(), member) then
    raise exception 'blocked: tu ne peux pas noter la réponse de cette personne' using errcode = '42501';
  end if;
$a$;
begin
  def := pg_get_functiondef('public.set_rsvp_for(uuid, uuid, public.rsvp_status)'::regprocedure);
  if position('blocked: tu ne peux pas noter la réponse' in def) > 0 then return; end if;
  if position(anchor in def) = 0 then raise exception 'set_rsvp_for : ancre introuvable, rien n''est modifié'; end if;
  execute replace(def, anchor, anchor || added);
end $patch$;

-- Notifications jetées entre personnes bloquées : + coorganizer_added, rsvp_set. Insérés AVANT 'group_join' : les ancres
-- des migrations pas encore en prod (« 'group_added') » des Pronos, « 'group_added', » des Souvenirs, « 'prono_result') »)
-- restent intactes, dans n'importe quel ordre.
do $patch$
declare def text;
  anchor text := $a$'group_join',$a$;
begin
  def := pg_get_functiondef('private.drop_blocked_notification()'::regprocedure);
  if position('''coorganizer_added'', ''rsvp_set''' in def) > 0 then return; end if;
  if position(anchor in def) = 0 then raise exception 'drop_blocked_notification : ancre introuvable, rien n''est modifié'; end if;
  execute replace(def, anchor, $a$'coorganizer_added', 'rsvp_set', $a$ || anchor);
end $patch$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261127110000', 'suppression_compte_blocage') on conflict do nothing;
commit;
