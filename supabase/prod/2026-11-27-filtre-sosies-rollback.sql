-- Retour arrière de 2026-11-27-filtre-sosies-apply.sql : mod_normalize et mod_hit telles que 20261104200000_moderation.sql.
begin;
create or replace function private.mod_normalize(t text) returns text
language sql immutable set search_path = '' as $$
  select translate(lower(coalesce(t, '')),
    'àáâãäåāăąæçćčďèéêëēėęěìíîïīįłñńňòóôõöøōőœŕřśšşßťùúûüūůűÿýžźż0134578@$€',
    'aaaaaaaaaacccdeeeeeeeeiiiiiilnnnooooooooorrsssstuuuuuuuyyzzzoieastbase');
$$;

create or replace function private.mod_hit(t text, kind text) returns text
language plpgsql stable security definer set search_path = '' as $$
declare words text := private.mod_merged(private.mod_normalize(t)); cat text; low text := lower(t);
begin
  foreach cat in array array['haine', 'sexuel', 'insulte'] loop
    if words ~ private.mod_regex(cat) then return cat; end if;
  end loop;
  if kind in ('name', 'word', 'offer', 'showcase') then
    if low ~ '(https?://|www\.|(^|[^a-z0-9])[a-z0-9-]+\.(com|ch|fr|de|it|net|org|io|ly|me|gg|app|xyz|info|co|tv|be|eu|uk|us|link|site|shop|ru|to|li)($|[^a-z0-9]))' then
      return 'lien';
    end if;
    if length(regexp_replace(low, '[^0-9]', '', 'g')) >= 8 then return 'numero'; end if;
  end if;
  return null;
end $$;

revoke all on function private.mod_normalize(text), private.mod_hit(text, text) from public, anon, authenticated;
delete from supabase_migrations.schema_migrations where version = '20261127130000';
commit;
