-- Explicit API permissions. RLS remains the row-level authorization boundary.
revoke all on all tables in schema public from anon;
revoke execute on all functions in schema public from public, anon, authenticated;
grant usage on schema public to authenticated;
grant select, insert, update, delete on all tables in schema public to authenticated;
grant execute on function is_active(), is_admin(), is_organizer(uuid), can_see_event(uuid), can_participate(uuid), approve_event(uuid), reject_event(uuid,text), fix_event_date(uuid,uuid) to authenticated;

-- Internal trigger functions and notification jobs are not RPC endpoints.
revoke all on notifications from authenticated;
grant select on notifications to authenticated;
grant update (read_at) on notifications to authenticated;
revoke update on rsvps from authenticated;
grant update (status, plus_ones, note) on rsvps to authenticated;
revoke update on profiles from authenticated;
grant update (display_name, avatar_url, role, status) on profiles to authenticated;

-- No first-arrival administrator takeover; promote the verified owner explicitly.
create or replace function handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into profiles (id, phone, role, status) values (new.id, new.phone, 'member', 'pending');
  insert into notification_prefs (user_id) values (new.id);
  return new;
end $$;

create or replace function is_organizer(e uuid) returns boolean
language sql stable security definer set search_path = public as $$
  select is_active() and (
    exists (select 1 from events where id = e and created_by = auth.uid())
    or exists (select 1 from event_organizers where event_id = e and user_id = auth.uid())
  );
$$;

-- Anonymous aggregate totals: explicit authorization inside a non-exposed schema.
create schema if not exists private;
revoke all on schema private from public, anon;
grant usage on schema private to authenticated;
create or replace function private.poll_result_rows()
returns table (poll_id uuid, option_id uuid, votes integer)
language sql stable security definer set search_path = public as $$
  select o.poll_id, o.id, count(v.user_id)::int
  from poll_options o left join poll_votes v on v.option_id = o.id
  where auth.uid() is not null and is_active() and exists (
    select 1 from polls p where p.id = o.poll_id
    and (p.event_id is null or can_see_event(p.event_id))
    and (not p.results_after_vote or is_admin() or p.created_by = auth.uid()
      or exists (select 1 from poll_votes mv where mv.poll_id = p.id and mv.user_id = auth.uid()))
  ) group by o.poll_id, o.id;
$$;
revoke all on function private.poll_result_rows() from public, anon;
grant execute on function private.poll_result_rows() to authenticated;
create or replace view poll_results with (security_invoker = true) as
select * from private.poll_result_rows();
