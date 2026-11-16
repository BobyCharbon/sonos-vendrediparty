-- Temps réel de l'événement (demande de l'admin du 16.11.2026 : « que les gens n'aient pas besoin de recharger la page » ;
-- le verre servi par le barman n'apparaissait chez l'invité qu'à la relecture suivante). Le bar, les billets et le
-- covoiturage passent par des fonctions (tables sans accès direct) : le temps réel Supabase ne les voit pas. Chaque
-- changement écrit ici un signal « recharge cet événement » pour chaque personne concernée ; la page de la personne
-- l'écoute (temps réel, filtré sur elle-même, RLS : on ne lit que SES signaux) et se relit aussitôt.
-- Aucun contenu (ni montant, ni nom) : juste qui, quel événement, quand. Un signal par personne et par transaction
-- (clé primaire avec now()) ; purgés toutes les heures. Purement additif et rejouable ; tables absentes (bar pas encore
-- en production) : leurs déclencheurs sont simplement ignorés.

create table if not exists public.live_pings (
  user_id uuid not null references public.profiles (id) on delete cascade,
  event_id uuid not null references public.events (id) on delete cascade,
  at timestamptz not null default now(),
  primary key (user_id, event_id, at)
);
alter table public.live_pings enable row level security;
drop policy if exists live_pings_mine on public.live_pings;
create policy live_pings_mine on public.live_pings for select to authenticated using (user_id = auth.uid());
revoke all on public.live_pings from anon;
revoke insert, update, delete, truncate on public.live_pings from authenticated;
grant select on public.live_pings to authenticated;

do $$ begin
  if not exists (select 1 from pg_publication_tables where pubname = 'supabase_realtime' and schemaname = 'public' and tablename = 'live_pings') then
    alter publication supabase_realtime add table public.live_pings;
  end if;
end $$;

-- Signal à ces personnes ; ne fait JAMAIS échouer le geste qui l'a déclenché.
create or replace function private.live_ping(e uuid, people uuid[]) returns void
language plpgsql security definer set search_path = '' as $$
begin
  insert into public.live_pings (user_id, event_id)
    select distinct x, e from unnest(people) x where x is not null and exists (select 1 from public.profiles p where p.id = x)
    on conflict do nothing;
exception when others then null;
end $$;

-- Organisateurs et co-organisateurs (+ barmans, si le bar existe).
create or replace function private.live_managers(e uuid) returns uuid[]
language plpgsql stable security definer set search_path = '' as $$
declare out uuid[];
begin
  select array_agg(m) into out from private.event_managers(e) m;
  if to_regclass('public.event_bar_staff') is not null then
    execute 'select coalesce($1, ''{}'') || coalesce(array_agg(user_id), ''{}'') from public.event_bar_staff where event_id = $2' into out using out, e;
  end if;
  return coalesce(out, '{}');
end $$;

-- Ligne d'une personne (verre, remboursement, billet) : elle-même + organisateurs + barmans.
create or replace function private.live_ping_member() returns trigger
language plpgsql security definer set search_path = '' as $$
declare r record;
begin
  r := case when tg_op = 'DELETE' then old else new end;
  perform private.live_ping(r.event_id, array[r.user_id] || private.live_managers(r.event_id));
  return null;
end $$;

-- Ce qui touche tout le bar (carte, réglages, barmans, engagements) : tous ceux qui y ont pris part + organisateurs.
create or replace function private.live_ping_bar() returns trigger
language plpgsql security definer set search_path = '' as $$
declare e uuid := case when tg_op = 'DELETE' then old.event_id else new.event_id end; people uuid[];
begin
  execute 'select array_agg(distinct user_id) from (select user_id from public.event_bar_units where event_id = $1
           union select user_id from public.event_bar_pledges where event_id = $1) s' into people using e;
  perform private.live_ping(e, coalesce(people, '{}') || private.live_managers(e));
  return null;
end $$;

-- Covoiturage : tout ce que voient les participants (Présent / Peut-être) et les organisateurs.
create or replace function private.live_ping_event() returns trigger
language plpgsql security definer set search_path = '' as $$
declare e uuid := case when tg_op = 'DELETE' then old.event_id else new.event_id end;
begin
  perform private.live_ping(e, (select coalesce(array_agg(user_id), '{}') from public.rsvps where event_id = e and status in ('yes', 'maybe'))
                               || private.live_managers(e));
  return null;
end $$;

revoke all on function private.live_ping(uuid, uuid[]), private.live_managers(uuid), private.live_ping_member(),
  private.live_ping_bar(), private.live_ping_event() from public, anon, authenticated;

do $$
declare t text;
begin
  foreach t in array array['event_bar_units', 'event_bar_refunds', 'event_tickets'] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop trigger if exists live_ping on public.%I', t);
      execute format('create trigger live_ping after insert or update or delete on public.%I for each row execute function private.live_ping_member()', t);
    end if;
  end loop;
  foreach t in array array['event_bars', 'event_bar_items', 'event_bar_staff', 'event_bar_pledges'] loop
    if to_regclass('public.' || t) is not null then
      execute format('drop trigger if exists live_ping on public.%I', t);
      execute format('create trigger live_ping after insert or update or delete on public.%I for each row execute function private.live_ping_bar()', t);
    end if;
  end loop;
  if to_regclass('public.event_carpool') is not null then
    drop trigger if exists live_ping on public.event_carpool;
    create trigger live_ping after insert or update or delete on public.event_carpool for each row execute function private.live_ping_event();
  end if;
end $$;

select cron.schedule('live-pings-purge', '23 * * * *', $cron$ delete from public.live_pings where at < now() - interval '10 minutes'; $cron$);

notify pgrst, 'reload schema';
