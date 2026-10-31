-- Tricount (avis 8213efc66ee4) : dépenses partagées dans des groupes à part (« un groupe créé sur le pot commun »),
-- rejoints par un lien partageable ; membres avec ou sans compte (un prénom ajouté à la main, que la personne
-- peut ensuite reprendre en rejoignant) ; dépenses partagées à parts égales, par parts ou par montants ; remboursements ;
-- photo du ticket ; profil de paiement (IBAN, lien Revolut / Twint / PayPal…) visible des seuls co-membres.
-- Lecture : règles RLS (membres actifs du groupe). Écriture : uniquement par les fonctions ci-dessous, qui vérifient
-- tout (appartenance, sommes, membres du même groupe). Migration additive et rejouable.

create table if not exists public.tc_groups (
  id uuid primary key default gen_random_uuid(),
  name text not null check (char_length(btrim(name)) between 1 and 60),
  emoji text not null default '💸' check (char_length(emoji) <= 8),
  currency text not null default 'CHF' check (currency ~ '^[A-Z]{3}$'),
  join_token uuid not null default gen_random_uuid() unique,
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  archived boolean not null default false
);

create table if not exists public.tc_members (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.tc_groups(id) on delete cascade,
  user_id uuid references auth.users(id) on delete set null,
  name text not null check (char_length(btrim(name)) between 1 and 40),
  created_at timestamptz not null default now(),
  left_at timestamptz
);
create unique index if not exists tc_members_one_account on public.tc_members(group_id, user_id) where user_id is not null;
create index if not exists tc_members_user on public.tc_members(user_id);

create table if not exists public.tc_expenses (
  id uuid primary key default gen_random_uuid(),
  group_id uuid not null references public.tc_groups(id) on delete cascade,
  kind text not null default 'expense' check (kind in ('expense', 'transfer')),
  title text not null check (char_length(btrim(title)) between 1 and 80),
  amount_cents bigint not null check (amount_cents > 0 and amount_cents <= 100000000),
  currency text not null default 'CHF' check (currency ~ '^[A-Z]{3}$'),
  rate numeric not null default 1 check (rate > 0 and rate < 100000),  -- 1 unité de cette monnaie = rate × monnaie du groupe
  paid_by uuid not null references public.tc_members(id) on delete restrict,
  spent_on date not null default current_date,
  category text not null default 'other' check (char_length(category) <= 20),
  note text check (char_length(note) <= 500),
  receipt_path text check (char_length(receipt_path) <= 200),
  split_mode text not null default 'equal' check (split_mode in ('equal', 'shares', 'amounts')),
  created_by uuid references auth.users(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists tc_expenses_group on public.tc_expenses(group_id, spent_on desc, created_at desc);

create table if not exists public.tc_shares (
  expense_id uuid not null references public.tc_expenses(id) on delete cascade,
  member_id uuid not null references public.tc_members(id) on delete restrict,
  weight numeric not null default 1 check (weight >= 0 and weight <= 1000),
  amount_cents bigint check (amount_cents >= 0),
  primary key (expense_id, member_id)
);

create table if not exists public.tc_payment (
  user_id uuid primary key references auth.users(id) on delete cascade,
  iban text check (iban is null or iban ~ '^[A-Z]{2}[0-9]{2}[A-Z0-9]{11,30}$'),
  holder text check (char_length(holder) <= 80),
  links jsonb not null default '{}'::jsonb check (jsonb_typeof(links) = 'object'),
  note text check (char_length(note) <= 200),
  updated_at timestamptz not null default now()
);

-- Qui lit quoi ---------------------------------------------------------------------------------------------------

create or replace function private.tc_member_of(grp uuid, uid uuid) returns uuid
language sql stable security definer set search_path = '' as $$
  select id from public.tc_members where group_id = grp and user_id = uid and left_at is null limit 1;
$$;

create or replace function private.tc_reads(grp uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select auth.uid() is not null and private.tc_member_of(grp, auth.uid()) is not null;
$$;

alter table public.tc_groups enable row level security;
alter table public.tc_members enable row level security;
alter table public.tc_expenses enable row level security;
alter table public.tc_shares enable row level security;
alter table public.tc_payment enable row level security;

drop policy if exists "tricount : ses groupes" on public.tc_groups;
create policy "tricount : ses groupes" on public.tc_groups for select to authenticated using (private.tc_reads(id));
drop policy if exists "tricount : membres de ses groupes" on public.tc_members;
create policy "tricount : membres de ses groupes" on public.tc_members for select to authenticated using (private.tc_reads(group_id));
drop policy if exists "tricount : dépenses de ses groupes" on public.tc_expenses;
create policy "tricount : dépenses de ses groupes" on public.tc_expenses for select to authenticated using (private.tc_reads(group_id));
drop policy if exists "tricount : parts de ses groupes" on public.tc_shares;
create policy "tricount : parts de ses groupes" on public.tc_shares for select to authenticated
  using (exists (select 1 from public.tc_expenses e where e.id = expense_id and private.tc_reads(e.group_id)));
drop policy if exists "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment;
create policy "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment for select to authenticated
  using (user_id = (select auth.uid()) or exists (
    select 1 from public.tc_members mine join public.tc_members theirs on theirs.group_id = mine.group_id
    where mine.user_id = (select auth.uid()) and mine.left_at is null and theirs.user_id = tc_payment.user_id and theirs.left_at is null));

-- Fonctions (toute écriture passe par ici) -----------------------------------------------------------------------

create or replace function private.tc_need(grp uuid) returns uuid
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := private.tc_member_of(grp, auth.uid());
begin
  if auth.uid() is null or me is null then raise exception 'forbidden: tu ne fais pas partie de ce pot commun'; end if;
  return me;
end $$;

create or replace function public.tc_create(group_name text, group_emoji text, group_currency text, my_name text) returns uuid
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  if auth.uid() is null then raise exception 'forbidden: connecte-toi'; end if;
  insert into public.tc_groups (name, emoji, currency, created_by)
  values (btrim(group_name), coalesce(nullif(btrim(group_emoji), ''), '💸'), coalesce(nullif(upper(btrim(group_currency)), ''), 'CHF'), auth.uid())
  returning id into grp;
  insert into public.tc_members (group_id, user_id, name) values (grp, auth.uid(), btrim(my_name));
  return grp;
end $$;

create or replace function public.tc_update_group(grp uuid, group_name text, group_emoji text, group_currency text, is_archived boolean)
returns void language plpgsql security definer set search_path = '' as $$
begin
  perform private.tc_need(grp);
  update public.tc_groups set name = coalesce(nullif(btrim(group_name), ''), name), emoji = coalesce(nullif(btrim(group_emoji), ''), emoji),
         currency = coalesce(nullif(upper(btrim(group_currency)), ''), currency), archived = coalesce(is_archived, archived)
  where id = grp;
end $$;

create or replace function public.tc_renew_link(grp uuid) returns uuid
language plpgsql security definer set search_path = '' as $$
declare token uuid := gen_random_uuid();
begin
  perform private.tc_need(grp);
  update public.tc_groups set join_token = token where id = grp;
  return token;
end $$;

-- Avant de rejoindre : le nom du groupe et les prénoms ajoutés à la main (la personne peut reprendre le sien).
create or replace function public.tc_join_info(token uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', g.id, 'name', g.name, 'emoji', g.emoji, 'currency', g.currency,
    'already', exists (select 1 from public.tc_members m where m.group_id = g.id and m.user_id = auth.uid() and m.left_at is null),
    'members', coalesce((select jsonb_agg(jsonb_build_object('id', m.id, 'name', m.name, 'linked', m.user_id is not null) order by m.created_at)
                         from public.tc_members m where m.group_id = g.id and m.left_at is null), '[]'::jsonb))
  from public.tc_groups g where g.join_token = token and not g.archived and auth.uid() is not null;
$$;

create or replace function public.tc_join(token uuid, my_name text, claim uuid default null) returns uuid
language plpgsql security definer set search_path = '' as $$
declare grp uuid; existing uuid;
begin
  if auth.uid() is null then raise exception 'forbidden: connecte-toi'; end if;
  select id into grp from public.tc_groups where join_token = token and not archived;
  if grp is null then raise exception 'forbidden: lien invalide ou remplacé'; end if;
  select id into existing from public.tc_members where group_id = grp and user_id = auth.uid();
  if existing is not null then
    update public.tc_members set left_at = null where id = existing;
    return grp;
  end if;
  if claim is not null then  -- reprendre un prénom ajouté à la main (ses dépenses deviennent les siennes)
    update public.tc_members set user_id = auth.uid() where id = claim and group_id = grp and user_id is null and left_at is null;
    if found then return grp; end if;
  end if;
  insert into public.tc_members (group_id, user_id, name) values (grp, auth.uid(), btrim(my_name));
  return grp;
end $$;

create or replace function public.tc_add_member(grp uuid, member_name text) returns uuid
language plpgsql security definer set search_path = '' as $$
declare new_id uuid;
begin
  perform private.tc_need(grp);
  insert into public.tc_members (group_id, name) values (grp, btrim(member_name)) returning id into new_id;
  return new_id;
end $$;

create or replace function public.tc_rename_member(member uuid, member_name text) returns void
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  select group_id into grp from public.tc_members where id = member;
  perform private.tc_need(grp);
  update public.tc_members set name = btrim(member_name) where id = member;
end $$;

-- Retirer : un prénom jamais utilisé disparaît ; sinon il quitte le groupe mais ses dépenses restent.
create or replace function public.tc_remove_member(member uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  select group_id into grp from public.tc_members where id = member;
  perform private.tc_need(grp);
  if exists (select 1 from public.tc_expenses where paid_by = member) or exists (select 1 from public.tc_shares where member_id = member) then
    update public.tc_members set left_at = now() where id = member;
  else
    delete from public.tc_members where id = member;
  end if;
end $$;

create or replace function public.tc_leave(grp uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  update public.tc_members set left_at = now() where id = private.tc_need(grp);
end $$;

-- Dépense ou remboursement (nouveau ou modifié) : vérifie que tout le monde est du groupe et que les montants tombent juste.
create or replace function public.tc_save_expense(grp uuid, exp jsonb) returns uuid
language plpgsql security definer set search_path = '' as $$
declare
  eid uuid := nullif(exp->>'id', '')::uuid;
  mode text := coalesce(exp->>'split_mode', 'equal');
  total bigint := (exp->>'amount_cents')::bigint;
  payer uuid := (exp->>'paid_by')::uuid;
  share jsonb;
  sum_amounts bigint := 0;
begin
  perform private.tc_need(grp);
  if not exists (select 1 from public.tc_members where id = payer and group_id = grp) then
    raise exception 'forbidden: celui qui a payé n''est pas du groupe';
  end if;
  if jsonb_typeof(exp->'shares') <> 'array' or jsonb_array_length(exp->'shares') = 0 then
    raise exception 'forbidden: choisis au moins une personne';
  end if;
  for share in select * from jsonb_array_elements(exp->'shares') loop
    if not exists (select 1 from public.tc_members where id = (share->>'member_id')::uuid and group_id = grp) then
      raise exception 'forbidden: une personne n''est pas du groupe';
    end if;
    sum_amounts := sum_amounts + coalesce((share->>'amount_cents')::bigint, 0);
  end loop;
  if mode = 'amounts' and sum_amounts <> total then
    raise exception 'forbidden: les montants de chacun ne font pas le total';
  end if;
  if eid is null then
    insert into public.tc_expenses (group_id, kind, title, amount_cents, currency, rate, paid_by, spent_on, category, note, receipt_path, split_mode, created_by)
    values (grp, coalesce(exp->>'kind', 'expense'), btrim(exp->>'title'), total, coalesce(exp->>'currency', 'CHF'),
            coalesce((exp->>'rate')::numeric, 1), payer, coalesce((exp->>'spent_on')::date, current_date),
            coalesce(exp->>'category', 'other'), nullif(btrim(exp->>'note'), ''), nullif(exp->>'receipt_path', ''), mode, auth.uid())
    returning id into eid;
  else
    update public.tc_expenses set kind = coalesce(exp->>'kind', kind), title = btrim(exp->>'title'), amount_cents = total,
           currency = coalesce(exp->>'currency', currency), rate = coalesce((exp->>'rate')::numeric, rate), paid_by = payer,
           spent_on = coalesce((exp->>'spent_on')::date, spent_on), category = coalesce(exp->>'category', category),
           note = nullif(btrim(exp->>'note'), ''), receipt_path = nullif(exp->>'receipt_path', ''), split_mode = mode, updated_at = now()
    where id = eid and group_id = grp;
    if not found then raise exception 'forbidden: dépense introuvable'; end if;
    delete from public.tc_shares where expense_id = eid;
  end if;
  insert into public.tc_shares (expense_id, member_id, weight, amount_cents)
  select eid, (s->>'member_id')::uuid, coalesce((s->>'weight')::numeric, 1), (s->>'amount_cents')::bigint
  from jsonb_array_elements(exp->'shares') s;
  return eid;
end $$;

create or replace function public.tc_delete_expense(expense uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare grp uuid;
begin
  select group_id into grp from public.tc_expenses where id = expense;
  perform private.tc_need(grp);
  delete from public.tc_expenses where id = expense;
end $$;

create or replace function public.tc_set_payment(pay_iban text, pay_holder text, pay_links jsonb, pay_note text) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'forbidden: connecte-toi'; end if;
  insert into public.tc_payment (user_id, iban, holder, links, note, updated_at)
  values (auth.uid(), nullif(upper(replace(btrim(pay_iban), ' ', '')), ''), nullif(btrim(pay_holder), ''), coalesce(pay_links, '{}'::jsonb),
          nullif(btrim(pay_note), ''), now())
  on conflict (user_id) do update set iban = excluded.iban, holder = excluded.holder, links = excluded.links, note = excluded.note,
          updated_at = now();
end $$;

-- Tout un pot commun en un appel (le serveur calcule soldes et remboursements) ; liste de ses tricounts.
create or replace function private.tc_group_json(grp uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object(
    'id', g.id, 'name', g.name, 'emoji', g.emoji, 'currency', g.currency, 'join_token', g.join_token, 'archived', g.archived,
    'created_at', g.created_at, 'me', private.tc_member_of(g.id, auth.uid()),
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

create or replace function public.tc_state(grp uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform private.tc_need(grp);
  return private.tc_group_json(grp);
end $$;

create or replace function public.tc_list() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(private.tc_group_json(m.group_id) order by g.archived, g.created_at desc), '[]'::jsonb)
  from public.tc_members m join public.tc_groups g on g.id = m.group_id
  where m.user_id = auth.uid() and m.left_at is null;
$$;

create or replace function public.tc_my_payment() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce((select jsonb_build_object('iban', iban, 'holder', holder, 'links', links, 'note', note)
                   from public.tc_payment where user_id = auth.uid()), '{}'::jsonb);
$$;

revoke all on function public.tc_create(text, text, text, text), public.tc_update_group(uuid, text, text, text, boolean),
  public.tc_renew_link(uuid), public.tc_join_info(uuid), public.tc_join(uuid, text, uuid), public.tc_add_member(uuid, text),
  public.tc_rename_member(uuid, text), public.tc_remove_member(uuid), public.tc_leave(uuid), public.tc_save_expense(uuid, jsonb),
  public.tc_delete_expense(uuid), public.tc_set_payment(text, text, jsonb, text), public.tc_state(uuid), public.tc_list(),
  public.tc_my_payment() from public, anon;
grant execute on function public.tc_create(text, text, text, text), public.tc_update_group(uuid, text, text, text, boolean),
  public.tc_renew_link(uuid), public.tc_join_info(uuid), public.tc_join(uuid, text, uuid), public.tc_add_member(uuid, text),
  public.tc_rename_member(uuid, text), public.tc_remove_member(uuid), public.tc_leave(uuid), public.tc_save_expense(uuid, jsonb),
  public.tc_delete_expense(uuid), public.tc_set_payment(text, text, jsonb, text), public.tc_state(uuid), public.tc_list(),
  public.tc_my_payment() to authenticated;

-- Photos des tickets (bucket privé, dossier = tricount) : envoyées et vues par les membres.
insert into storage.buckets (id, name, public, file_size_limit, allowed_mime_types)
values ('tc-receipts', 'tc-receipts', false, 8 * 1024 * 1024, array['image/jpeg', 'image/png', 'image/heic', 'image/webp'])
on conflict (id) do update set file_size_limit = excluded.file_size_limit, allowed_mime_types = excluded.allowed_mime_types;

drop policy if exists "tricount : envoyer un ticket" on storage.objects;
create policy "tricount : envoyer un ticket" on storage.objects for insert to authenticated
  with check (bucket_id = 'tc-receipts' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
              and private.tc_reads(((storage.foldername(name))[1])::uuid));
drop policy if exists "tricount : voir les tickets" on storage.objects;
create policy "tricount : voir les tickets" on storage.objects for select to authenticated
  using (bucket_id = 'tc-receipts' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
         and private.tc_reads(((storage.foldername(name))[1])::uuid));
