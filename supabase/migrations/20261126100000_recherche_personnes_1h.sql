-- Recherches de personnes (« Ajouter quelqu'un » d'un groupe, private.group_search_log) : gardées 1 heure au plus, et
-- seulement une EMPREINTE de la recherche (sha256), jamais le numéro ni le nom tapé (contrôle Apple / RGPD du 26.11).
-- La limite anti-annuaire (30 recherches différentes par heure) est inchangée. Purge : à chaque recherche (toutes les
-- personnes) et chaque heure par pg_cron. Additive et rejouable.

-- 1. Ce qui est déjà gardé : plus d'une heure → effacé ; le reste → empreinte.
delete from private.group_search_log where at < now() - interval '1 hour';
update private.group_search_log set q = encode(sha256(convert_to(q, 'UTF8')), 'hex') where q !~ '^[0-9a-f]{64}$';

-- 2. La recherche : empreinte seulement, purge d'une heure pour tous.
create or replace function public.group_people_search(grp uuid, q text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare
  me uuid := auth.uid(); g public.member_groups; number text := private.search_phone(q);
  qq text := private.fold(btrim(regexp_replace(coalesce(q, ''), '^\s*@', '')));
  key text; out jsonb;
begin
  if me is null or not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.may_invite_group(grp) then
    raise exception 'forbidden: seuls ceux qui gèrent le groupe invitent' using errcode = '42501';
  end if;
  if number is not null and length(number) < 8 then return '[]'::jsonb; end if;
  if number is null and char_length(qq) < 3 then return '[]'::jsonb; end if;
  -- Anti-annuaire : 30 recherches différentes par heure (la même recherche répétée ne compte qu'une fois).
  -- Seule une empreinte est gardée, une heure au plus.
  key := encode(sha256(convert_to(coalesce('tel:' || number, qq), 'UTF8')), 'hex');
  delete from private.group_search_log l where l.at < now() - interval '1 hour';
  if not exists (select 1 from private.group_search_log l where l.user_id = me and l.q = key and l.at > now() - interval '1 hour') then
    if (select count(*) from private.group_search_log l where l.user_id = me and l.at > now() - interval '1 hour') >= 30 then
      raise exception 'limit: tu as fait beaucoup de recherches, réessaie dans une heure' using errcode = '54000';
    end if;
    insert into private.group_search_log (user_id, q) values (me, key);
  end if;
  select * into g from public.member_groups where id = grp;
  with cand as (
    select p.id, p.display_name, p.avatar_url, p.last_name,
           starts_with(private.fold(p.display_name), qq) as prefix
    from public.profiles p
    where p.status = 'active' and p.id <> me
      and private.identity_complete(p.id)
      and case when number is not null then private.digits(p.phone) = number
               else position(qq in private.fold(p.display_name)) > 0
                 or starts_with(private.fold(p.first_name), qq) or starts_with(private.fold(p.last_name), qq)
                 or position(qq in private.fold(concat_ws(' ', p.first_name, p.last_name))) > 0 end
      and not exists (select 1 from public.member_group_members m where m.group_id = grp and m.user_id = p.id)
      and not private.blocked_either(me, p.id)
      and (g.created_by is null or not private.blocked_either(p.id, g.created_by))
    order by prefix desc, p.display_name
    limit 50
  )
  select coalesce(jsonb_agg(jsonb_build_object(
           'id', x.id, 'display_name', x.display_name, 'avatar_url', x.avatar_url,
           'initial', nullif(upper(left(btrim(coalesce(x.last_name, '')), 1)), ''),
           'invited', exists (select 1 from private.group_invitations i where i.group_id = grp and i.user_id = x.id and i.status = 'pending'))
         order by x.prefix desc, x.display_name), '[]'::jsonb) into out
  from (select * from cand
        where private.dm_check_core(me, cand.id, number is not null, false) ->> 'link' <> 'none'
        order by cand.prefix desc, cand.display_name limit 5) x;
  return out;
end $$;
revoke all on function public.group_people_search(uuid, text) from public, anon;
grant execute on function public.group_people_search(uuid, text) to authenticated;

-- 3. Purge chaque heure, même quand personne ne cherche.
select cron.unschedule('group-search-log-purge') where exists (select 1 from cron.job where jobname = 'group-search-log-purge');
select cron.schedule('group-search-log-purge', '23 * * * *',
  $$delete from private.group_search_log where at < now() - interval '1 hour'$$);
