-- Pot commun relié à un événement : l'organisateur active « Pot commun » dans l'événement ; un pot commun est créé
-- (nom et date de l'événement) et chaque personne présente (réponse « oui », hors liste d'attente) y entre
-- automatiquement, avec son compte : il apparaît dans Réglages › Pot commun. Désactiver l'option archive le pot
-- (les dépenses restent) ; la réactiver le rouvre. Une personne qui a quitté le pot n'y est pas remise.
-- Migration additive et rejouable.

alter table public.events add column if not exists pot_enabled boolean not null default false;
alter table public.tc_groups add column if not exists event_id uuid references public.events(id) on delete set null;
create unique index if not exists tc_groups_one_per_event on public.tc_groups(event_id) where event_id is not null;

-- Crée (ou rouvre / archive) le pot de l'événement et y fait entrer les présents qui n'y sont pas encore.
create or replace function private.tc_event_sync(e uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare ev public.events; grp uuid;
begin
  select * into ev from public.events where id = e;
  if not found then return; end if;
  select id into grp from public.tc_groups where event_id = e;
  if not ev.pot_enabled then
    update public.tc_groups set archived = true where id = grp and not archived;
    return;
  end if;
  if grp is null then
    insert into public.tc_groups (name, emoji, currency, created_by, event_id)
    values (left(btrim(ev.title), 60), '🎉', 'CHF', ev.created_by, e)
    returning id into grp;
  else
    update public.tc_groups set archived = false where id = grp and archived;
  end if;
  insert into public.tc_members (group_id, user_id, name)
  select grp, r.user_id, left(coalesce(nullif(btrim(p.display_name), ''), 'Invité'), 40)
  from public.rsvps r join public.profiles p on p.id = r.user_id
  where r.event_id = e and r.status = 'yes' and not r.waitlisted
    and not exists (select 1 from public.tc_members m where m.group_id = grp and m.user_id = r.user_id)
  order by r.updated_at;
end $$;
revoke all on function private.tc_event_sync(uuid) from public, anon, authenticated;

create or replace function private.tc_event_changed() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' and not new.pot_enabled then return null; end if;
  perform private.tc_event_sync(new.id);
  return null;
end $$;

drop trigger if exists tc_event_pot on public.events;
create trigger tc_event_pot after insert or update of pot_enabled on public.events
  for each row execute function private.tc_event_changed();

create or replace function private.tc_rsvp_changed() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.status = 'yes' and not new.waitlisted
     and exists (select 1 from public.events where id = new.event_id and pot_enabled) then
    perform private.tc_event_sync(new.event_id);
  end if;
  return null;
end $$;

drop trigger if exists tc_rsvp_pot on public.rsvps;
create trigger tc_rsvp_pot after insert or update of status, waitlisted on public.rsvps
  for each row execute function private.tc_rsvp_changed();

-- Le pot commun dit à quel événement il est relié.
create or replace function private.tc_group_json(grp uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', g.id, 'name', g.name, 'emoji', g.emoji, 'currency', g.currency, 'join_token', g.join_token, 'archived', g.archived,
    'created_at', g.created_at, 'me', private.tc_member_of(g.id, auth.uid()),
    'event', (select jsonb_build_object('id', ev.id, 'title', ev.title, 'starts_at', ev.starts_at) from public.events ev where ev.id = g.event_id),
    'members', coalesce((select jsonb_agg(jsonb_build_object('id', m.id, 'name', m.name, 'linked', m.user_id is not null,
                 'left', m.left_at is not null,
                 'payment', case when m.user_id is not null and m.left_at is null then
                   (select jsonb_build_object('iban', p.iban, 'holder', p.holder, 'links', p.links, 'note', p.note)
                    from public.tc_payment p where p.user_id = m.user_id) end) order by m.created_at)
               from public.tc_members m where m.group_id = g.id), '[]'::jsonb),
    'expenses', coalesce((select jsonb_agg(jsonb_build_object('id', e.id, 'kind', e.kind, 'title', e.title, 'amount_cents', e.amount_cents,
                 'currency', e.currency, 'rate', e.rate, 'paid_by', e.paid_by, 'spent_on', e.spent_on, 'category', e.category,
                 'note', e.note, 'receipt_path', e.receipt_path, 'split_mode', e.split_mode, 'created_at', e.created_at,
                 'shares', coalesce((select jsonb_agg(jsonb_build_object('member_id', s.member_id, 'weight', s.weight, 'amount_cents', s.amount_cents))
                                     from public.tc_shares s where s.expense_id = e.id), '[]'::jsonb))
                 order by e.spent_on desc, e.created_at desc)
               from public.tc_expenses e where e.group_id = g.id), '[]'::jsonb))
  from public.tc_groups g where g.id = grp;
$$;

