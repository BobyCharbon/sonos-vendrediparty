-- Recherche d'une personne par son numéro (Inviter dans un groupe, avis de l'admin du 23.11) : tous les formats suisses
-- courants trouvent la personne. Déjà : 079…, +41 79…, 0041 79…. En plus : « +41 (0)79… », « +41 079… », « 0041 079… »
-- (le 0 après l'indicatif est retiré) et « 79 123 45 67 » (9 chiffres sans le 0 : numéro suisse).
-- Même règle dans les écrans : web phoneOf (GroupInvite.tsx), iPhone GroupText.phone (GroupsAPI.swift).
-- Purement additive et rejouable.

create or replace function private.search_phone(q text) returns text
language sql immutable set search_path = '' as $$
  select case
    when t !~ '^(\+|00)?[0-9][0-9 .()/-]{6,}$' then null
    when intl is not null then nullif(case when intl ~ '^410' and length(intl) = 12 then '41' || substr(intl, 4) else intl end, '')
    when d ~ '^0[1-9]' and length(d) = 10 then '41' || substr(d, 2)
    when d ~ '^[1-9]' and length(d) = 9 then '41' || d
    else d end
  from (select t, d, case when d ~ '^00' then substr(d, 3) when t ~ '^\+' then d end as intl
        from (select btrim(coalesce(q, '')) t, regexp_replace(coalesce(q, ''), '\D', '', 'g') d) x) y;
$$;

