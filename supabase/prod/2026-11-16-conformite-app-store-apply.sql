-- PROD, conformité App Store (20261116150000) : CGU 2026-11-16, blocage signalé, bar sans tabac ni drogue, bar payant
-- réservé aux soirées privées. À appliquer APRÈS 2026-11-16-demo-apple-bar-discussions-apply.sql. Rejouable. Tout ou rien.
begin;
-- Conformité App Store (contrôle du 16.11.2026, bar et Discussions allumés en production). Purement additive et rejouable.
--  1. Conditions d'utilisation version 2026-11-16 (« Réservé aux adultes », « Paiements, billets et bar ») : chaque compte
--     les accepte à nouveau avant son prochain contenu (web lib/terms.ts, iPhone TermsView.swift).
--  2. Bloquer quelqu'un prévient aussi la modération (Apple 1.2 : « blocking should also notify the developer ») :
--     un signalement « Autre raison » du profil, une fois (la file de modération et sa notification habituelles).
--  3. Bar : pas de tabac ni de drogue parmi les articles (Apple 1.4.3 : « facilitating the sale of … tobacco »).
--  4. Bar PAYANT réservé aux événements non publics (soirée privée entre amis ; vendre de l'alcool au public demande
--     une autorisation) : sur un événement public, le bar est offert ; un événement ne devient pas public avec un bar payant.

-- 1. ----------------------------------------------------------------------------------------------------------------
update private.moderation_settings set terms_version = '2026-11-16' where terms_version < '2026-11-16';
alter table private.moderation_settings alter column terms_version set default '2026-11-16';

-- 2. ----------------------------------------------------------------------------------------------------------------
create or replace function public.set_direct_block(target uuid, blocked boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if target is null or target = auth.uid() then raise exception 'Choisis une autre personne' using errcode = '22023'; end if;
  if blocked then
    insert into public.direct_blocks (user_id, blocked_id) values (auth.uid(), target) on conflict do nothing;
    -- Signalement automatique aux modérateurs (une fois par personne bloquée ; jamais un échec du blocage lui-même).
    begin
      perform public.report_content('profile', target::text, 'other', 'Bloqué par un membre (signalement automatique)');
    exception when others then
      null;
    end;
  else
    delete from public.direct_blocks where user_id = auth.uid() and blocked_id = target;
  end if;
end $$;

-- 3. ----------------------------------------------------------------------------------------------------------------
create or replace function private.bar_item_allowed() returns trigger
language plpgsql set search_path = '' as $$
declare txt text := lower(coalesce(new.name, '') || ' ' || coalesce(new.detail, ''));
begin
  if txt ~ '\m(cigarettes?|clopes?|tabacs?|snus|puffs?|vapes?|vapoteuses?|e-?cig[a-z]*|cigares?|cigarillos?|chichas?|shishas?|narguil[eé]s?|iqos|juul|nicotine|cannabis|cbd|thc|joints?|beuh|weed|marijuana|haschich|hasch|shit|coca[iï]ne|ecstasy|mdma|drogues?)\M' then
    raise exception 'Le bar ne sert ni tabac ni drogue : seulement des boissons et de quoi grignoter.' using errcode = '22023';
  end if;
  return new;
end $$;

do $$
begin
  if to_regclass('public.event_bar_items') is not null then
    drop trigger if exists bar_item_allowed on public.event_bar_items;
    create trigger bar_item_allowed before insert or update of name, detail on public.event_bar_items
      for each row execute function private.bar_item_allowed();
  end if;
end $$;

-- 4. ----------------------------------------------------------------------------------------------------------------
create or replace function private.event_is_public(e uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select ev.visibility = 'all' and ev.public_link from public.events ev where ev.id = e), false);
$$;
revoke all on function private.event_is_public(uuid) from public, anon, authenticated;

create or replace function private.bar_private_only() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if not private.event_is_public(new.event_id) or new.free_bar then return new; end if;
  if tg_op = 'INSERT' then
    new.free_bar := true;  -- bar créé sur un événement public : offert
    return new;
  end if;
  raise exception 'Un bar payant est réservé aux soirées privées (sur invitation, groupe, membres). Sur un événement public, le bar est offert.'
    using errcode = '22023';
end $$;

create or replace function private.event_public_bar_guard() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.visibility = 'all' and new.public_link
     and not (old.visibility = 'all' and old.public_link)
     and to_regclass('public.event_bars') is not null then
    if exists (select 1 from public.event_bars b where b.event_id = new.id and not b.free_bar) then
      raise exception 'Cet événement a un bar payant, réservé aux soirées privées : passe le bar en « offert » (Gérer le bar › Options) avant de le rendre public.'
        using errcode = '22023';
    end if;
  end if;
  return new;
end $$;

do $$
begin
  if to_regclass('public.event_bars') is not null then
    drop trigger if exists bar_private_only on public.event_bars;
    create trigger bar_private_only before insert or update of free_bar on public.event_bars
      for each row execute function private.bar_private_only();
  end if;
end $$;
drop trigger if exists event_public_bar_guard on public.events;
create trigger event_public_bar_guard before update of visibility, public_link on public.events
  for each row execute function private.event_public_bar_guard();


insert into supabase_migrations.schema_migrations (version, name) values ('20261116150000', 'conformite_app_store') on conflict do nothing;
commit;

notify pgrst, 'reload schema';
