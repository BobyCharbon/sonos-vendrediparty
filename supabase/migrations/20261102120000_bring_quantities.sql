-- Qui amène quoi, en quantités partagées (demande de l'admin, 2 novembre 2026) : « 15 bouteilles » ne doit plus être
-- pris en entier par une seule personne. L'organisateur fixe une quantité (bring_items.quantity) ; chaque participant
-- dit combien il en amène (bring_claims, une ligne par personne). Sans quantité, rien ne change (claimed_by).
-- Purement additif et rejouable : le code qui ignore la quantité continue de marcher.

alter table public.bring_items add column if not exists quantity int;
alter table public.bring_items drop constraint if exists bring_items_quantity_check;
alter table public.bring_items add constraint bring_items_quantity_check check (quantity is null or quantity between 2 and 999);

create table if not exists public.bring_claims (
  item_id uuid not null references public.bring_items (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  quantity int not null check (quantity between 1 and 999),
  created_at timestamptz not null default now(),
  primary key (item_id, user_id)
);
create index if not exists bring_claims_user on public.bring_claims (user_id);
alter table public.bring_claims enable row level security;

-- L'événement d'un objet (lu par les politiques, sans dépendre des droits de lecture sur bring_items).
create or replace function private.bring_item_event(i uuid) returns uuid
language sql stable security definer set search_path = '' as $$
  select event_id from public.bring_items where id = i;
$$;
revoke all on function private.bring_item_event(uuid) from public, anon;
grant execute on function private.bring_item_event(uuid) to authenticated;

drop policy if exists "voir qui amène combien" on public.bring_claims;
create policy "voir qui amène combien" on public.bring_claims for select using (
  public.can_see_event(private.bring_item_event(item_id)) or public.is_organizer(private.bring_item_event(item_id)));

drop policy if exists "dire combien j'amène" on public.bring_claims;
create policy "dire combien j'amène" on public.bring_claims for insert with check (
  user_id = auth.uid() and public.can_participate(private.bring_item_event(item_id)));

drop policy if exists "changer combien j'amène" on public.bring_claims;
create policy "changer combien j'amène" on public.bring_claims for update
  using (user_id = auth.uid() and public.can_participate(private.bring_item_event(item_id)))
  with check (user_id = auth.uid());

drop policy if exists "ne plus rien amener" on public.bring_claims;
create policy "ne plus rien amener" on public.bring_claims for delete using (
  user_id = auth.uid() or public.is_admin() or public.is_organizer(private.bring_item_event(item_id)));

-- Jamais plus que demandé, même si deux personnes répondent en même temps : l'objet est verrouillé le temps du calcul.
create or replace function public.guard_bring_claim() returns trigger
language plpgsql security definer set search_path = '' as $$
declare
  wanted int;
  taken int;
begin
  if tg_op = 'UPDATE' then
    new.item_id := old.item_id;
    new.user_id := old.user_id;
  end if;
  select quantity into wanted from public.bring_items where id = new.item_id for update;
  if wanted is null then
    raise exception 'Cet objet n''a pas de quantité : prends-le en entier.';
  end if;
  select coalesce(sum(quantity), 0) into taken from public.bring_claims
    where item_id = new.item_id and user_id <> new.user_id;
  if taken + new.quantity > wanted then
    raise exception 'Il n''en reste que %.', greatest(wanted - taken, 0);
  end if;
  return new;
end $$;

drop trigger if exists bring_claims_guard on public.bring_claims;
create trigger bring_claims_guard before insert or update on public.bring_claims
  for each row execute function public.guard_bring_claim();

-- La garde des objets protège aussi la quantité : seul l'organisateur (ou un admin) la change.
create or replace function public.guard_bring_item() returns trigger
language plpgsql security definer set search_path = '' as $$
declare promised int;
begin
  if auth.uid() is not null and not (public.is_admin() or public.is_organizer(old.event_id)) then
    new.event_id := old.event_id;
    new.label := old.label;
    new.sort := old.sort;
    new.added_by := old.added_by;
    new.quantity := old.quantity;
    -- Un objet à partager se prend par quantités (bring_claims), jamais en entier par un seul participant.
    if new.quantity is not null then
      new.claimed_by := old.claimed_by;
    end if;
  end if;
  -- Personne (organisateur compris) ne descend sous ce qui est déjà promis, ni n'enlève la quantité d'un objet promis.
  if new.quantity is distinct from old.quantity then
    select sum(quantity) into promised from public.bring_claims where item_id = new.id;
    if promised is not null and (new.quantity is null or new.quantity < promised) then
      raise exception 'Déjà % promis : la quantité ne peut pas descendre plus bas.', promised;
    end if;
  end if;
  return new;
end $$;

grant select, insert, update, delete on public.bring_claims to authenticated;

-- Un participant ajoute ce que lui amène (en entier) : la quantité à partager reste à l'organisateur.
drop policy if exists "ajouter ce que j'amène" on public.bring_items;
create policy "ajouter ce que j'amène" on public.bring_items for insert with check (
  public.can_participate(event_id) and added_by = auth.uid() and claimed_by = auth.uid() and quantity is null
  and length(label) between 1 and 100);
