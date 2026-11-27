-- PROD, filtre commun : sosies cyrillique / grec et formes NFKC (20261127130000, contrôle Apple, tour 5).
-- Testé sur TEST le 27.11 (« Cоnnard », « CОNNARD », « Ｃｏｎｎａｒｄ », « 𝐒𝐚𝐥𝐨𝐩𝐞 » refusés ; Léa, Paris, Anaïs, Νίκος acceptés). Rejouable.
-- Retour arrière : 2026-11-27-filtre-sosies-rollback.sql. NE PAS appliquer sans le « Ok prod » de l'admin.
begin;
-- Filtre commun : sosies cyrillique / grec → latin et formes NFKC (contrôle Apple, tour 5, 27.11).
-- « Cоnnard » (o cyrillique), « Hіtler » (i ukrainien), « Ｃｏｎｎａｒｄ » (pleine chasse) passaient le filtre des surnoms,
-- noms de groupe et messages. Même algorithme que app/moderation.py (normalize, nfkc, _hit), vérifié par
-- tests/test_moderation.py. Additif et rejouable : deux fonctions redéfinies (create or replace), rien d'autre.
-- - mod_normalize reste lettre pour lettre (même longueur : le masquage des insultes s'y repère) : sosies (majuscules
--   d'abord, Η grec → h), minuscules, accents, chiffres ;
-- - mod_hit détecte sur la forme NFKC (la longueur peut changer : détection seulement ; une insulte en pleine chasse
--   qu'on ne sait pas masquer est donc refusée).

create or replace function private.mod_normalize(t text) returns text
language sql immutable set search_path = '' as $$
  select translate(lower(translate(coalesce(t, ''),
    'АВЕЁКМНОРСТУХЅІЇЈҺԀԚԜаеёкмнорстухѕіїјһԁԛԝвьгпΑΒΕΖΗΙΚΜΝΟΡΤΥΧΆΈΉΊΌΎαβγδεζηικνορτυχωςάέήίόύώμ',
    'abeekmhopctyxsiijhdqwaeekmhopctyxsiijhdqwbbrnabezhikmnoptyxaehioyabydeznikvoptuxwsaeniouwu')),
    'àáâãäåāăąæçćčďèéêëēėęěìíîïīįłñńňòóôõöøōőœŕřśšşßťùúûüūůűÿýžźż0134578@$€АВЕЁКМНОРСТУХЅІЇЈҺԀԚԜаеёкмнорстухѕіїјһԁԛԝвьгпΑΒΕΖΗΙΚΜΝΟΡΤΥΧΆΈΉΊΌΎαβγδεζηικνορτυχωςάέήίόύώμ',
    'aaaaaaaaaacccdeeeeeeeeiiiiiilnnnooooooooorrsssstuuuuuuuyyzzzoieastbaseabeekmhopctyxsiijhdqwaeekmhopctyxsiijhdqwbbrnabezhikmnoptyxaehioyabydeznikvoptuxwsaeniouwu');
$$;

create or replace function private.mod_hit(t text, kind text) returns text
language plpgsql stable security definer set search_path = '' as $$
declare nf text := normalize(coalesce(t, ''), NFKC);
  words text := private.mod_merged(private.mod_normalize(nf)); cat text; low text := lower(nf);
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
insert into supabase_migrations.schema_migrations (version, name) values ('20261127130000', 'filtre_sosies') on conflict do nothing;
commit;
