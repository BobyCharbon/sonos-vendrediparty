-- Prod : 20261120200100_ordre_epingles (avis e75a1d5af3ee) : réorganiser les discussions épinglées.
begin;
create or replace function public.reorder_chat_pins(chats jsonb) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); item jsonb; i int := 0; base timestamptz := now();
begin
  if me is null then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if jsonb_typeof(chats) is distinct from 'array' or jsonb_array_length(chats) > 10 then
    raise exception 'invalid: Liste des épingles invalide' using errcode = '22023';
  end if;
  for item in select value from jsonb_array_elements(chats) loop
    if item ->> 'kind' not in ('direct', 'group', 'event') or (item ->> 'id') !~ '^[0-9a-fA-F-]{36}$' then
      raise exception 'invalid: Liste des épingles invalide' using errcode = '22023';
    end if;
    -- Seulement mes lignes déjà épinglées : rien à épingler ni à voir ici.
    update public.chat_list_state s set pinned_at = base - make_interval(secs => i)
    where s.user_id = me and s.kind = item ->> 'kind' and s.chat_id = (item ->> 'id')::uuid and s.pinned_at is not null;
    i := i + 1;
  end loop;
end $$;

revoke all on function public.reorder_chat_pins(jsonb) from public, anon;
grant execute on function public.reorder_chat_pins(jsonb) to authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261120200100', 'ordre_epingles') on conflict do nothing;
commit;
