-- Retour arrière de 2026-11-27-blocage-suite-apply.sql (20261127120000) : retire exactement les 4 ajouts (garde des
-- co-organisateurs, set_direct_block, join_group_by_link, join_event_by_link). Rejouable (rien si déjà retiré).
-- Ne remet PAS « et photo » dans les messages (la photo n'est jamais exigée) et ne recrée pas les co-organisateurs retirés
-- par un blocage. 2026-11-23-reglages-groupe-admin-rollback.sql redéfinit aussi join_group_by_link (sans ce contrôle).
begin;
do $patch$
declare p record; def text;
begin
  for p in select * from (values
    ('private.guard_coorganizer_block()',
     'créateur de l''événement (20261127120000)',
     $a$  if private.blocked_either(auth.uid(), new.user_id) then
$a$,
     $a$  if private.blocked_either(auth.uid(), new.user_id)
     or (auth.uid() is not null and private.blocked_either(
           (select e.created_by from public.events e where e.id = new.event_id), new.user_id)) then -- créateur de l'événement (20261127120000)
$a$),
    ('public.set_direct_block(uuid,boolean)',
     'plus co-organisateurs l''un de l''autre (20261127120000)',
     $a$    insert into public.direct_blocks (user_id, blocked_id) values (auth.uid(), target) on conflict do nothing;
$a$,
     $a$    insert into public.direct_blocks (user_id, blocked_id) values (auth.uid(), target) on conflict do nothing;
    -- plus co-organisateurs l'un de l'autre (20261127120000) : le créateur reste, les autres événements aussi.
    delete from public.event_organizers o using public.events e
      where e.id = o.event_id and o.user_id <> e.created_by
        and ((e.created_by = auth.uid() and o.user_id = target) or (e.created_by = target and o.user_id = auth.uid()));
$a$),
    ('public.join_group_by_link(uuid)',
     'Tu ne peux pas rejoindre ce groupe.',
     $a$  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
$a$,
     $a$  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  -- En blocage avec le créateur du groupe ou l'auteur du lien : n'entre pas, sans dire qui a bloqué (20261127120000).
  if private.blocked_either(auth.uid(), (select g.created_by from public.member_groups g where g.id = grp))
     or exists (select 1 from public.member_groups g where g.id = grp and g.invite_token = join_group_by_link.token
                  and private.blocked_either(auth.uid(), g.invite_token_by))
     or exists (select 1 from private.invite_links l where l.token = join_group_by_link.token
                  and private.blocked_either(auth.uid(), l.created_by)) then
    raise exception 'Tu ne peux pas rejoindre ce groupe.' using errcode = '42501';
  end if;
$a$),
    ('public.join_event_by_link(uuid)',
     'sans dire qui a bloqué, comme accept_invite (20261127120000)',
     $a$  if ev.id is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
$a$,
     $a$  if ev.id is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  -- En blocage avec l'organisateur ou l'auteur du lien : n'entre pas, sans dire qui a bloqué, comme accept_invite (20261127120000).
  if private.blocked_either(ev.created_by, auth.uid())
     or exists (select 1 from private.invite_links l where l.token = join_event_by_link.token
                  and private.blocked_either(l.created_by, auth.uid())) then
    raise exception 'Tu ne peux pas répondre à cette invitation.' using errcode = '42501';
  end if;
$a$)) v(fn, marker, anchor, repl)
  loop
    continue when to_regprocedure(p.fn) is null;
    def := pg_get_functiondef(p.fn::regprocedure);
    if position(p.repl in def) > 0 then execute replace(def, p.repl, p.anchor); end if;
  end loop;
end $patch$;
delete from supabase_migrations.schema_migrations where version = '20261127120000';
commit;
