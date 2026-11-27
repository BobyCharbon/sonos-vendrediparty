-- Retour arrière de 2026-11-27-suppression-blocage-apply.sql (20261127110000) : retire le passage « compte supprimé » des 4
-- gardes, le refus du blocage de set_rsvp_for, les 2 notifications ajoutées à drop_blocked_notification, la garde des
-- co-organisateurs et la fonction d'aide. Rejouable (rien à faire si déjà retiré).
begin;
do $patch$
declare def text; f record; added text;
begin
  for f in select * from (values
    ('public.guard_event()', 'approved_by'),
    ('public.guard_bring_item()', 'added_by,claimed_by'),
    ('private.guard_event_group_status()', 'requested_by,answered_by'),
    ('private.group_photo_guard()', 'photo_by,invite_token_by,created_by')) v(fn, cols)
  loop
    def := pg_get_functiondef(f.fn::regprocedure);
    added := format($a$  if tg_op = 'UPDATE' and private.cleared_by_account_deletion(to_jsonb(old), to_jsonb(new), %L) then
    return new; -- compte supprimé : la base efface seulement qui a fait quoi (20261127110000)
  end if;
$a$, '{' || f.cols || '}');
    if position(added in def) > 0 then execute replace(def, added, ''); end if;
  end loop;

  def := pg_get_functiondef('public.set_rsvp_for(uuid, uuid, public.rsvp_status)'::regprocedure);
  added := $a$  if private.blocked_either(auth.uid(), member) then
    raise exception 'blocked: tu ne peux pas noter la réponse de cette personne' using errcode = '42501';
  end if;
$a$;
  if position(added in def) > 0 then execute replace(def, added, ''); end if;

  def := pg_get_functiondef('private.drop_blocked_notification()'::regprocedure);
  if position($a$'coorganizer_added', 'rsvp_set', $a$ in def) > 0 then
    execute replace(def, $a$'coorganizer_added', 'rsvp_set', $a$, '');
  elsif position($a$, 'coorganizer_added', 'rsvp_set'$a$ in def) > 0 then  -- première version, sur TEST seulement
    execute replace(def, $a$, 'coorganizer_added', 'rsvp_set'$a$, '');
  end if;
end $patch$;
drop trigger if exists event_organizers_block on public.event_organizers;
drop function if exists private.guard_coorganizer_block();
drop function if exists private.cleared_by_account_deletion(jsonb, jsonb, text[]);
delete from supabase_migrations.schema_migrations where version = '20261127110000';
commit;
