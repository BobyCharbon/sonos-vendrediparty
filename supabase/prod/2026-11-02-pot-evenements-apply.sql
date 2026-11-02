-- PROD, pot_commun_events (20261031150000). À appliquer SEULEMENT après « Ok prod ». Rejouable.
-- Pot commun relié à un événement (events.pot_enabled, tc_groups.event_id, synchronisation des membres).
begin;
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

-- Gardes (audit du 2 novembre 2026) : un simple membre ne peut plus exclure les autres, changer le lien, la monnaie ni
-- archiver le pot, ni supprimer la dépense d'un autre. Ces gestes reviennent à qui gère le pot : son créateur, les
-- organisateurs de l'événement relié, ou un admin. Un prénom ajouté à la main (sans compte) peut être retiré par tous.
create or replace function private.tc_manages(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and (
    public.is_admin()
    or exists (select 1 from public.tc_groups g where g.id = grp and (g.created_by = auth.uid()
               or (g.event_id is not null and public.is_organizer(g.event_id)))));
$$;

create or replace function public.tc_update_group(grp uuid, group_name text, group_emoji text, group_currency text, is_archived boolean)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform private.tc_need(grp);
  if not private.tc_manages(grp) then raise exception 'forbidden: seul qui gère ce pot commun peut le modifier'; end if;
  update public.tc_groups set name = coalesce(nullif(btrim(group_name), ''), name), emoji = coalesce(nullif(btrim(group_emoji), ''), emoji),
         currency = coalesce(nullif(upper(btrim(group_currency)), ''), currency), archived = coalesce(is_archived, archived)
  where id = grp;
end $$;

create or replace function public.tc_renew_link(grp uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare token uuid := gen_random_uuid();
begin
  perform private.tc_need(grp);
  if not private.tc_manages(grp) then raise exception 'forbidden: seul qui gère ce pot commun peut changer le lien'; end if;
  update public.tc_groups set join_token = token where id = grp;
  return token;
end $$;

create or replace function public.tc_remove_member(member uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare grp uuid; account uuid;
begin
  select group_id, user_id into grp, account from public.tc_members where id = member;
  perform private.tc_need(grp);
  if account is not null and account <> auth.uid() and not private.tc_manages(grp) then
    raise exception 'forbidden: seul qui gère ce pot commun peut retirer quelqu''un';
  end if;
  if account is not null and account <> auth.uid() and not public.is_admin()
     and exists (select 1 from public.tc_groups where id = grp and created_by = account) then
    raise exception 'forbidden: le créateur du pot commun ne peut pas être retiré';
  end if;
  if exists (select 1 from public.tc_expenses where paid_by = member) or exists (select 1 from public.tc_shares where member_id = member) then
    update public.tc_members set left_at = now() where id = member;
  else
    delete from public.tc_members where id = member;
  end if;
end $$;

create or replace function public.tc_delete_expense(expense uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare grp uuid; author uuid;
begin
  select group_id, created_by into grp, author from public.tc_expenses where id = expense;
  perform private.tc_need(grp);
  if author is distinct from auth.uid() and not private.tc_manages(grp) then
    raise exception 'forbidden: seule la personne qui l''a ajoutée (ou qui gère le pot) peut supprimer cette dépense';
  end if;
  delete from public.tc_expenses where id = expense;
end $$;

-- Fonctions internes : appelées par les politiques (authenticated), jamais par les anonymes.
revoke all on function private.tc_member_of(uuid, uuid), private.tc_reads(uuid), private.tc_need(uuid),
  private.tc_manages(uuid) from public, anon;
grant execute on function private.tc_member_of(uuid, uuid), private.tc_reads(uuid), private.tc_need(uuid),
  private.tc_manages(uuid) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261031150000', 'pot_commun_events')
  on conflict (version) do nothing;
commit;
