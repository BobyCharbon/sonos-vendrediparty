-- PROD, contact_names (20261103170000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration. Rejouable.
-- Indépendante des autres migrations du 3 novembre. Tout ou rien (begin/commit).
begin;
-- Noms des contacts (avis de l'admin du 3 novembre 2026, f780431defe7) : dans l'app iPhone, un membre Party qui est
-- dans les contacts du téléphone s'affiche sous le nom que l'utilisateur lui a donné (« Nom du contact · pseudo »),
-- comme WhatsApp. Reconnaissance parmi tous les comptes actifs ; aucune option pour s'y soustraire (choix de l'admin).
--
-- Vie privée :
-- - le téléphone n'envoie JAMAIS un numéro ni un nom : seulement HMAC-SHA256(clé, numéro E.164 « +41… »), en hexadécimal ;
-- - la clé (contacts_key) n'est donnée qu'aux comptes actifs ;
-- - contacts_match ne renvoie que {user_id, hash} des correspondances (jamais un numéro) et ne garde AUCUNE empreinte :
--   seulement l'heure et le nombre d'empreintes de chaque appel, pour la limite (effacés après 24 h) ;
-- - les noms des contacts restent sur l'iPhone (correspondance user_id → nom gardée sur l'appareil).
-- Limites contre l'énumération des numéros : 20 000 empreintes par appel, 12 appels par heure, 60 000 empreintes par
-- 24 h et par compte.
-- Purement additif et rejouable.

create table if not exists private.contact_key (
  id smallint primary key default 1 check (id = 1),
  key text not null check (key ~ '^[0-9a-f]{64}$'),
  created_at timestamptz not null default now()
);
insert into private.contact_key (id, key) values (1, encode(extensions.gen_random_bytes(32), 'hex'))
on conflict (id) do nothing;
revoke all on private.contact_key from public, anon, authenticated;

-- Appels récents (limite de débit) : ni empreinte ni numéro, seulement l'instant et le nombre d'empreintes.
create table if not exists private.contact_match_calls (
  user_id uuid not null references public.profiles (id) on delete cascade,
  at timestamptz not null default now(),
  hashes integer not null check (hashes >= 0)
);
create index if not exists contact_match_calls_user on private.contact_match_calls (user_id, at);
revoke all on private.contact_match_calls from public, anon, authenticated;

-- Clé des empreintes : comptes actifs seulement.
create or replace function public.contacts_key() returns text
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  return (select k.key from private.contact_key k where k.id = 1);
end $$;

-- Empreintes du répertoire → comptes actifs dont le numéro correspond (sauf soi-même) : [{user_id, hash}].
create or replace function public.contacts_match(hashes text[]) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare
  me uuid := auth.uid();
  n integer := coalesce(cardinality(hashes), 0);
  k text;
  result jsonb;
begin
  if me is null or not private.is_account_active(me) then
    raise exception 'Connexion requise' using errcode = '42501';
  end if;
  if n > 20000 then
    raise exception 'Trop de numéros d''un coup' using errcode = '22023';
  end if;
  if exists (select 1 from unnest(hashes) h where h is null or h !~ '^[0-9a-f]{64}$') then
    raise exception 'Empreinte invalide' using errcode = '22023';
  end if;
  delete from private.contact_match_calls where at < now() - interval '24 hours';
  if (select count(*) from private.contact_match_calls c where c.user_id = me and c.at > now() - interval '1 hour') >= 12
     or (select coalesce(sum(c.hashes), 0) from private.contact_match_calls c where c.user_id = me) + n > 60000 then
    raise exception 'rate_limited: Trop de demandes, réessaie plus tard' using errcode = '54000';
  end if;
  insert into private.contact_match_calls (user_id, hashes) values (me, n);
  if n = 0 then return '[]'::jsonb; end if;
  select c.key into k from private.contact_key c where c.id = 1;
  select coalesce(jsonb_agg(jsonb_build_object('user_id', m.id, 'hash', m.hash) order by m.id), '[]'::jsonb) into result
  from (
    select p.id, encode(extensions.hmac('+' || p.phone, k, 'sha256'), 'hex') as hash
    from public.profiles p
    where p.status = 'active' and p.id <> me and p.phone ~ '^[1-9][0-9]{7,14}$'
  ) m
  where m.hash in (select distinct h from unnest(hashes) h);
  return result;
end $$;

revoke all on function public.contacts_key(), public.contacts_match(text[]) from public, anon;
grant execute on function public.contacts_key(), public.contacts_match(text[]) to authenticated;

insert into supabase_migrations.schema_migrations (version, name) values ('20261103170000', 'contact_names') on conflict do nothing;
commit;

notify pgrst, 'reload schema';
