-- PROD, moderation (20261104200000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration. Rejouable.
-- Prérequis en prod : 2026-11-04-messages-directs-apply.sql (public.direct_blocks, private.in_direct, set_direct_block).
-- Sans effet de bord pour les anciennes applis : « Exiger les CGU » reste DÉSACTIVÉ (l'admin l'active dans
-- Administration › Signalements une fois l'app iPhone à jour). Le filtre s'applique dès l'application (messages,
-- surnoms, noms de groupe). Fonctions send-push / send-web-push inchangées. Tout ou rien.
begin;
-- Modération commune à toute l'app (décision de l'admin du 4 novembre 2026, contrôle de conformité App Store / Play
-- Store : Apple 1.2, Google Play « User Generated Content ») : construite AVANT la collection du Compagnon, qui s'y branche.
--
-- 1. FILTRE de contenu (private.moderation_verdict, même algorithme que app/moderation.py ; liste : app/moderation_terms.py) :
--    · messages (Discussions de groupe, messages directs, discussions d'événement) : une insulte d'un mot est MASQUÉE
--      (••••) et le message part ; propos haineux ou sexuels, insultes en plusieurs mots ou déguisées : REFUS ;
--    · noms (surnom, nom de groupe ; nom du Zicou, mots, offres et vitrine plus tard) : REFUS de tout mot interdit,
--      de tout lien et de tout numéro de téléphone ;
--    · contournements simples : majuscules, accents, s@l0pe, saloooope, s.a.l.o.p.e, caractères invisibles.
-- 2. SIGNALER : public.content_reports (raison + commentaire, copie du contenu au moment du signalement), par
--    public.report_content ; l'auteur du signalement voit les siens (RLS), les modérateurs tout via fonctions ; au plus
--    10 signalements par heure et 30 par jour. Point d'accroche du Compagnon : private.report_snapshot_pet et
--    private.moderation_hide_pet (vides ici, remplacés par la migration du Compagnon).
-- 3. BLOCAGE COMMUN : la table public.direct_blocks (messages directs, 4.11) devient LE blocage de toute l'app
--    (pas de seconde table : une seule source, déjà lue par les messages directs). Un joueur bloqué (dans les deux sens)
--    ne peut plus : écrire en message direct (déjà), mentionner (citation retirée, aucune notification), inviter dans
--    un groupe ou à un événement, voir la fiche détaillée (public.member_card réduite) ; les notifications causées par
--    l'autre (message de groupe, réponse, @tout, invitation) ne partent plus. Pour le Compagnon : public.blocked_with.
-- 4. MODÉRATION : droit « Modérer les signalements » (moderation.reports, donné au rôle Admin) ; file
--    (public.moderation_queue), actions (public.moderation_act : masquer, avertir, suspendre, bannir, classer sans
--    suite) ; suspendre et bannir = statut du COMPTE (identifiant), jamais une adresse IP, et demandent aussi le droit
--    « Bannir ou réintégrer un compte » ; fin de suspension automatique (cron) ; journal = public.member_audit
--    (actions « moderation.* », écran Journal) ; notification « Nouveau signalement » (interrupteur
--    notification_prefs.moderation_reports) et « Message de la modération » (interrupteur moderation_notices).
-- 5. CONDITIONS D'UTILISATION : acceptation par compte avec la version (public.terms_acceptances) ; les applis la
--    demandent avant le premier contenu ; la base l'exige aussi quand l'admin coche « Exiger les CGU »
--    (private.moderation_settings.terms_enforced, NON par défaut : les anciennes versions de l'app iPhone, sans écran
--    d'acceptation, n'écriraient plus) ; adresse de contact publiée, réglable par l'admin (vide tant qu'il ne l'a pas
--    donnée).
-- Purement additif et rejouable. Les fonctions partagées réécrites par d'autres migrations (web_push_allowed,
-- may_receive_push, member_card) sont COMPLÉTÉES en place, une seule fois, jamais recopiées.

-- --------------------------------------------------------------------------------------------------------------
-- 1. Filtre
-- --------------------------------------------------------------------------------------------------------------
create table if not exists private.moderation_patterns (
  category text not null check (category in ('haine', 'sexuel', 'insulte')),
  pattern text not null,
  phrase boolean not null default false,
  primary key (category, pattern)
);
revoke all on private.moderation_patterns from public, anon, authenticated;

-- Généré par `python -m app.moderation --sql` (vérifié par tests/test_moderation.py).
-- Toute la liste est réécrite (rejouable : une entrée retirée de la liste quitte la base).
delete from private.moderation_patterns;
insert into private.moderation_patterns (category, pattern, phrase) values
  ('haine', 'n+e+g+r+e+(s|x|e|es|en|n)?', false),
  ('haine', 'b+o+u+g+n+o+u+l+[a-z]*', false),
  ('haine', 'b+i+c+o+t+(s|x|e|es|en|n)?', false),
  ('haine', 'y+o+u+p+i+n+(s|x|e|es|en|n)?', false),
  ('haine', 'y+o+u+t+r+e+(s|x|e|es|en|n)?', false),
  ('haine', 'b+a+m+b+o+u+l+a+(s|x|e|es|en|n)?', false),
  ('haine', 'c+h+i+n+e+t+o+q+u+e+(s|x|e|es|en|n)?', false),
  ('haine', 'n+i+a+k+o+u+e+(s|x|e|es|en|n)?', false),
  ('haine', 'p+e+d+e+(s|x|e|es|en|n)?', false),
  ('haine', 'p+d+(s|x|e|es|en|n)?', false),
  ('haine', 'g+o+u+i+n+e+(s|x|e|es|en|n)?', false),
  ('haine', 't+a+r+l+o+u+z+e+(s|x|e|es|en|n)?', false),
  ('haine', 's+a+l+e+[^a-z]+a+r+a+b+e+(s|x|e|es|en|n)?', true),
  ('haine', 's+a+l+e+[^a-z]+j+u+i+f+(s|x|e|es|en|n)?', true),
  ('haine', 's+a+l+e+[^a-z]+n+o+i+r+(s|x|e|es|en|n)?', true),
  ('haine', 's+a+l+e+[^a-z]+n+e+g+r+e+(s|x|e|es|en|n)?', true),
  ('haine', 'n+e+g+e+r+(s|x|e|es|en|n)?', false),
  ('haine', 'k+a+n+a+k+e+(s|x|e|es|en|n)?', false),
  ('haine', 'k+a+n+a+c+k+e+(s|x|e|es|en|n)?', false),
  ('haine', 's+c+h+w+u+c+h+t+e+l+(s|x|e|es|en|n)?', false),
  ('haine', 'j+u+d+e+n+s+a+u+(s|x|e|es|en|n)?', false),
  ('haine', 'h+e+i+l+[^a-z]+h+i+t+l+e+r+(s|x|e|es|en|n)?', true),
  ('haine', 's+i+e+g+[^a-z]+h+e+i+l+(s|x|e|es|en|n)?', true),
  ('haine', 'n+e+g+r+o+(s|x|e|es|en|n)?', false),
  ('haine', 'f+r+o+c+i+o+(s|x|e|es|en|n)?', false),
  ('haine', 'r+i+c+h+i+o+n+e+(s|x|e|es|en|n)?', false),
  ('haine', 'n+i+g{2,}(a|e+r)[a-z]*(s|x|e|es|en|n)?', false),
  ('haine', 'f+a+g+o+t+[a-z]*', false),
  ('haine', 'f+a+g+(s|x|e|es|en|n)?', false),
  ('haine', 'k+i+k+e+(s|x|e|es|en|n)?', false),
  ('haine', 'spic', false),
  ('haine', 'c+h+i+n+k+(s|x|e|es|en|n)?', false),
  ('haine', 't+r+a+n+y+(s|x|e|es|en|n)?', false),
  ('haine', 'w+h+i+t+e+[^a-z]+p+o+w+e+r+(s|x|e|es|en|n)?', true),
  ('sexuel', 'bite', false),
  ('sexuel', 't+e+u+b+(s|x|e|es|en|n)?', false),
  ('sexuel', 'z+g+e+g+(s|x|e|es|en|n)?', false),
  ('sexuel', 'p+o+r+n+o+[a-z]*', false),
  ('sexuel', 's+o+d+o+m+i+[a-z]*', false),
  ('sexuel', 'f+e+l+a+t+i+o+n+(s|x|e|es|en|n)?', false),
  ('sexuel', 'c+u+n+i+l+i+n+g+u+s+(s|x|e|es|en|n)?', false),
  ('sexuel', 'e+j+a+c+u+l+[a-z]*', false),
  ('sexuel', 'm+a+s+t+u+r+b+[a-z]*', false),
  ('sexuel', 'p+a+r+t+o+u+z+e+(s|x|e|es|en|n)?', false),
  ('sexuel', 'p+e+d+o+p+h+i+l+[a-z]*', false),
  ('sexuel', 'z+o+p+h+i+l+[a-z]*', false),
  ('sexuel', 'b+a+i+s+e+u+[a-z]*', false),
  ('sexuel', 'b+a+i+s+e+[^a-z]+m+o+i+(s|x|e|es|en|n)?', true),
  ('sexuel', 's+u+c+e+[^a-z]+m+o+i+(s|x|e|es|en|n)?', true),
  ('sexuel', 's+u+c+e+u+[a-z]*', false),
  ('sexuel', 'g+o+d+e+(s|x|e|es|en|n)?', false),
  ('sexuel', 'f+o+t+z+e+(s|x|e|es|en|n)?', false),
  ('sexuel', 'f+i+c+k+e+n+(s|x|e|es|en|n)?', false),
  ('sexuel', 'b+u+m+s+e+n+(s|x|e|es|en|n)?', false),
  ('sexuel', 'p+o+m+p+i+n+o+(s|x|e|es|en|n)?', false),
  ('sexuel', 's+c+o+p+a+r+e+(s|x|e|es|en|n)?', false),
  ('sexuel', 'f+i+g+a+(s|x|e|es|en|n)?', false),
  ('sexuel', 'p+o+r+n+[a-z]*', false),
  ('sexuel', 'b+l+o+w+j+o+b+[a-z]*', false),
  ('sexuel', 'c+u+m+s+h+o+t+[a-z]*', false),
  ('sexuel', 'h+a+n+d+j+o+b+[a-z]*', false),
  ('sexuel', 'd+i+l+d+o+[a-z]*', false),
  ('sexuel', 'p+u+s+y+(s|x|e|es|en|n)?', false),
  ('sexuel', 'c+o+c+k+(s|x|e|es|en|n)?', false),
  ('sexuel', 'h+o+r+n+y+(s|x|e|es|en|n)?', false),
  ('sexuel', 'n+u+d+e+s+(s|x|e|es|en|n)?', false),
  ('sexuel', 's+e+x+t+i+n+g+(s|x|e|es|en|n)?', false),
  ('sexuel', 'a+n+a+l+(s|x|e|es|en|n)?', false),
  ('sexuel', 'b+u+k+a+k+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'c+o+n+a+r+d+[a-z]*', false),
  ('insulte', 'c+o+n+a+s+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'con{2,}e(s|x|e|es|en|n)?', false),
  ('insulte', 'g+r+o+s+[^a-z]+c+o+n+(s|x|e|es|en|n)?', true),
  ('insulte', 's+a+l+e+[^a-z]+c+o+n+(s|x|e|es|en|n)?', true),
  ('insulte', 'p+a+u+v+r+e+[^a-z]+c+o+n+(s|x|e|es|en|n)?', true),
  ('insulte', 'e+n+c+u+l+[a-z]*', false),
  ('insulte', 's+a+l+o+p+e+(s|x|e|es|en|n)?', false),
  ('insulte', 's+a+l+a+u+d+(s|x|e|es|en|n)?', false),
  ('insulte', 'b+a+t+a+r+d+[a-z]*', false),
  ('insulte', 'p+u+t+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'f+i+l+s+[^a-z]+d+e+[^a-z]+p+u+t+e+(s|x|e|es|en|n)?', true),
  ('insulte', 'n+i+q+u+e+[^a-z]+t+a+[^a-z]+m+e+r+e+(s|x|e|es|en|n)?', true),
  ('insulte', 'n+t+m+(s|x|e|es|en|n)?', false),
  ('insulte', 'f+d+p+(s|x|e|es|en|n)?', false),
  ('insulte', 'p+o+u+f+i+a+s+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'p+e+t+a+s+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'b+r+a+n+l+e+u+r+[a-z]*', false),
  ('insulte', 'e+n+f+o+i+r+e+[a-z]*', false),
  ('insulte', 'g+r+o+g+n+a+s+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'a+r+s+c+h+l+o+c+h+[a-z]*', false),
  ('insulte', 'w+i+c+h+s+e+r+(s|x|e|es|en|n)?', false),
  ('insulte', 'h+u+r+e+n+s+o+h+n+[a-z]*', false),
  ('insulte', 'm+i+s+g+e+b+u+r+t+(s|x|e|es|en|n)?', false),
  ('insulte', 's+p+a+s+t+(s|x|e|es|en|n)?', false),
  ('insulte', 's+p+a+s+t+i+(s|x|e|es|en|n)?', false),
  ('insulte', 'f+i+c+k+[^a-z]+d+i+c+h+(s|x|e|es|en|n)?', true),
  ('insulte', 's+c+h+l+a+m+p+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'h+u+r+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'd+r+e+c+k+s+a+u+(s|x|e|es|en|n)?', false),
  ('insulte', 's+t+r+o+n+z+o+(s|x|e|es|en|n)?', false),
  ('insulte', 's+t+r+o+n+z+a+(s|x|e|es|en|n)?', false),
  ('insulte', 'v+a+f+a+n+c+u+l+o+(s|x|e|es|en|n)?', false),
  ('insulte', 'f+a+n+c+u+l+o+(s|x|e|es|en|n)?', false),
  ('insulte', 'c+o+g+l+i+o+n+e+(s|x|e|es|en|n)?', false),
  ('insulte', 'p+u+t+a+n+a+(s|x|e|es|en|n)?', false),
  ('insulte', 't+r+o+i+a+(s|x|e|es|en|n)?', false),
  ('insulte', 'b+a+s+t+a+r+d+o+(s|x|e|es|en|n)?', false),
  ('insulte', 'f+i+g+l+i+o+[^a-z]+d+i+[^a-z]+p+u+t+a+n+a+(s|x|e|es|en|n)?', true),
  ('insulte', 't+e+s+t+a+[^a-z]+d+i+[^a-z]+c+a+z+o+(s|x|e|es|en|n)?', true),
  ('insulte', 'f+u+c+k+[a-z]*', false),
  ('insulte', 'm+o+t+h+e+r+f+u+c+k+[a-z]*', false),
  ('insulte', 'a+s+h+o+l+e+[a-z]*', false),
  ('insulte', 'b+i+t+c+h+[a-z]*', false),
  ('insulte', 'b+a+s+t+a+r+d+(s|x|e|es|en|n)?', false),
  ('insulte', 'c+u+n+t+[a-z]*', false),
  ('insulte', 'd+i+c+k+h+e+a+d+[a-z]*', false),
  ('insulte', 'dick', false),
  ('insulte', 's+l+u+t+[a-z]*', false),
  ('insulte', 'w+h+o+r+e+[a-z]*', false),
  ('insulte', 'w+a+n+k+e+r+[a-z]*', false),
  ('insulte', 't+w+a+t+[a-z]*', false)
on conflict (category, pattern) do update set phrase = excluded.phrase;

-- Lettre pour lettre (même longueur) : minuscules, sans accents, chiffres et signes ramenés aux lettres.
create or replace function private.mod_normalize(t text) returns text
language sql immutable set search_path = '' as $$
  select translate(lower(coalesce(t, '')),
    'àáâãäåāăąæçćčďèéêëēėęěìíîïīįłñńňòóôõöøōőœŕřśšşßťùúûüūůűÿýžźż0134578@$€',
    'aaaaaaaaaacccdeeeeeeeeiiiiiilnnnooooooooorrsssstuuuuuuuyyzzzoieastbase');
$$;

create or replace function private.mod_clean(t text) returns text
language sql immutable set search_path = '' as $$
  select regexp_replace(coalesce(t, ''), '[​-‏⁠﻿­]', '', 'g');
$$;

-- Les mots séparés par une espace ; 3 lettres isolées de suite ou plus sont recollées (s a l o p e → salope).
create or replace function private.mod_merged(norm text) returns text
language plpgsql immutable set search_path = '' as $$
declare token text; run text := ''; out text[] := '{}';
begin
  foreach token in array regexp_split_to_array(norm, '[^a-z]+') loop
    continue when token = '';
    if length(token) = 1 then
      run := run || token;
      continue;
    end if;
    if length(run) >= 3 then out := out || run;
    elsif run <> '' then out := out || regexp_split_to_array(run, '');
    end if;
    run := '';
    out := out || token;
  end loop;
  if length(run) >= 3 then out := out || run;
  elsif run <> '' then out := out || regexp_split_to_array(run, '');
  end if;
  return array_to_string(out, ' ');
end $$;

create or replace function private.mod_regex(cat text, words_only boolean default false) returns text
language sql stable security definer set search_path = '' as $$
  select case when words_only then '^(' || string_agg(pattern, '|' order by pattern) || ')$'
              else '(^|[^a-z])(' || string_agg(pattern, '|' order by pattern) || ')($|[^a-z])' end
  from private.moderation_patterns where category = cat and not (words_only and phrase);
$$;

-- Catégorie trouvée (haine > sexuel > insulte > lien > numero) ou null.
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

create or replace function private.mod_mask_insults(t text) returns text
language plpgsql stable security definer set search_path = '' as $$
declare norm text := private.mod_normalize(t); re text := private.mod_regex('insulte', true);
        pos int := 1; s int; e int; word text; out text := t;
begin
  loop
    s := regexp_instr(norm, '[a-z]+', pos);
    exit when s = 0;
    e := regexp_instr(norm, '[a-z]+', pos, 1, 1);
    word := substr(norm, s, e - s);
    if word ~ re then out := overlay(out placing repeat('•', e - s) from s for e - s); end if;
    pos := e;
  end loop;
  return out;
end $$;

-- Verdict : {ok, category, text (masqué au besoin), message}. kind : name, word, offer, showcase (refus) ou message.
create or replace function private.moderation_verdict(p_text text, p_kind text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare body text := private.mod_clean(p_text); cat text; masked text; reason text;
begin
  if p_kind not in ('name', 'word', 'offer', 'showcase', 'message') then raise exception 'type de texte inconnu'; end if;
  cat := private.mod_hit(body, p_kind);
  if cat is null then return jsonb_build_object('ok', true, 'category', null, 'text', body, 'message', null); end if;
  if p_kind = 'message' and cat = 'insulte' then
    masked := private.mod_mask_insults(body);
    if private.mod_hit(masked, p_kind) is null then
      return jsonb_build_object('ok', true, 'category', cat, 'text', masked, 'message', null);
    end if;
  end if;
  reason := case cat when 'haine' then 'des propos haineux' when 'sexuel' then 'un contenu sexuel' when 'insulte' then 'une insulte'
                     when 'lien' then 'un lien' when 'numero' then 'un numéro de téléphone' else 'un mot interdit' end;
  return jsonb_build_object('ok', false, 'category', cat, 'text', body, 'message',
    case when p_kind = 'message' then 'Message non envoyé : il contient ' || reason || '. Les règles de Party l''interdisent.'
         else 'Ce texte n''est pas accepté : il contient ' || reason || '. Choisis-en un autre.' end);
end $$;

-- Pour les déclencheurs : le texte à garder, ou une erreur « content_refused: <phrase> » (affichée telle quelle).
create or replace function private.moderate_text(p_text text, p_kind text) returns text
language plpgsql stable security definer set search_path = '' as $$
declare v jsonb := private.moderation_verdict(p_text, p_kind);
begin
  if not (v ->> 'ok')::boolean then
    raise exception 'content_refused: %', v ->> 'message' using errcode = '23514';
  end if;
  return v ->> 'text';
end $$;

-- Pour les applis (et le Compagnon) : vérifier un texte avant de l'envoyer.
create or replace function public.moderation_check(p_text text, p_kind text default 'name') returns jsonb
language sql stable security definer set search_path = '' as $$
  select private.moderation_verdict(left(p_text, 4000), p_kind);
$$;

revoke all on function private.mod_normalize(text), private.mod_clean(text), private.mod_merged(text), private.mod_regex(text, boolean),
  private.mod_hit(text, text), private.mod_mask_insults(text), private.moderation_verdict(text, text), private.moderate_text(text, text)
  from public, anon, authenticated;
revoke all on function public.moderation_check(text, text) from public, anon;
grant execute on function public.moderation_check(text, text) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 5 (d'abord : les déclencheurs en ont besoin). Conditions d'utilisation et contact
-- --------------------------------------------------------------------------------------------------------------
create table if not exists private.moderation_settings (
  id integer primary key default 1 check (id = 1),
  terms_version text not null default '2026-11-04',
  terms_enforced boolean not null default false,
  contact_email text check (contact_email is null or contact_email ~ '^[^@\s]+@[^@\s]+\.[^@\s]+$')
);
insert into private.moderation_settings (id) values (1) on conflict (id) do nothing;
revoke all on private.moderation_settings from public, anon, authenticated;

create table if not exists public.terms_acceptances (
  user_id uuid not null references public.profiles(id) on delete cascade,
  version text not null check (char_length(version) <= 20),
  accepted_at timestamptz not null default now(),
  primary key (user_id, version)
);
alter table public.terms_acceptances enable row level security;
drop policy if exists "mes acceptations des conditions" on public.terms_acceptances;
create policy "mes acceptations des conditions" on public.terms_acceptances for select to authenticated
  using (user_id = (select auth.uid()));
revoke all on public.terms_acceptances from anon;
revoke insert, update, delete on public.terms_acceptances from authenticated;
grant select on public.terms_acceptances to authenticated;

create or replace function private.terms_accepted(uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.terms_acceptances a join private.moderation_settings s on s.terms_version = a.version
                 where a.user_id = uid);
$$;

-- Les déclencheurs l'appellent pour un contenu écrit par la personne connectée (jamais pour une action de l'admin
-- ou du système). Sans effet tant que l'admin n'a pas coché « Exiger les CGU ».
create or replace function private.require_terms(author uuid) returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if auth.uid() is null or author is distinct from auth.uid() then return; end if;
  if (select terms_enforced from private.moderation_settings where id = 1) and not private.terms_accepted(author) then
    raise exception 'terms_required: accepte les conditions d''utilisation de Party pour publier (Réglages › Confidentialité).'
      using errcode = '42501';
  end if;
end $$;

-- Visible de tous, même sans compte (page des conditions) : version, contact, exigence.
create or replace function public.moderation_public_info() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('terms_version', terms_version, 'contact_email', contact_email, 'terms_enforced', terms_enforced)
  from private.moderation_settings where id = 1;
$$;

create or replace function public.my_terms() returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('version', s.terms_version, 'accepted', private.terms_accepted(auth.uid()),
    'accepted_at', (select a.accepted_at from public.terms_acceptances a where a.user_id = auth.uid() and a.version = s.terms_version),
    'contact_email', s.contact_email, 'enforced', s.terms_enforced)
  from private.moderation_settings s where s.id = 1;
$$;

create or replace function public.accept_terms(p_version text) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null or not private.is_account_active(auth.uid()) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if p_version is distinct from (select terms_version from private.moderation_settings where id = 1) then
    raise exception 'terms_version: les conditions ont changé, relis la nouvelle version' using errcode = '22023';
  end if;
  insert into public.terms_acceptances (user_id, version) values (auth.uid(), p_version) on conflict do nothing;
  return public.my_terms();
end $$;

-- Réglages de la modération (Admin) : adresse de contact publiée, exiger les CGU.
create or replace function public.set_moderation_settings(p_contact_email text default null, p_terms_enforced boolean default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
begin
  if not private.is_member_admin() then raise exception 'forbidden: réservé aux admins' using errcode = '42501'; end if;
  update private.moderation_settings set
    contact_email = case when p_contact_email is null then contact_email else nullif(btrim(p_contact_email), '') end,
    terms_enforced = coalesce(p_terms_enforced, terms_enforced)
  where id = 1;
  perform private.audit('moderation.settings', null, jsonb_build_object('contact_email', p_contact_email, 'terms_enforced', p_terms_enforced));
  return public.moderation_public_info();
end $$;

revoke all on function private.terms_accepted(uuid), private.require_terms(uuid) from public, anon, authenticated;
revoke all on function public.moderation_public_info(), public.my_terms(), public.accept_terms(text),
  public.set_moderation_settings(text, boolean) from public, anon;
grant execute on function public.moderation_public_info() to anon, authenticated;
grant execute on function public.my_terms(), public.accept_terms(text), public.set_moderation_settings(text, boolean) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- 3. Blocage commun (public.direct_blocks)
-- --------------------------------------------------------------------------------------------------------------
comment on table public.direct_blocks is
  'Blocage commun à toute l''app (messages directs, mentions, invitations, fiche, Compagnon) : user_id a bloqué blocked_id.';

create or replace function private.blocked_either(a uuid, b uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select a is not null and b is not null and exists (select 1 from public.direct_blocks k
    where (k.user_id = a and k.blocked_id = b) or (k.user_id = b and k.blocked_id = a));
$$;
revoke all on function private.blocked_either(uuid, uuid) from public, anon;
grant execute on function private.blocked_either(uuid, uuid) to authenticated;

-- Pour le Compagnon et les écrans : un blocage existe-t-il entre moi et cette personne (dans un sens ou l'autre) ?
create or replace function public.blocked_with(target uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select private.blocked_either(auth.uid(), target);
$$;

-- Même règle que set_direct_block (gardée pour les anciennes versions), sous un nom commun.
create or replace function public.set_block(target uuid, blocked boolean) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform public.set_direct_block(target, blocked);
end $$;

-- Réglages › Confidentialité › Personnes bloquées.
create or replace function public.my_blocks() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', p.id, 'display_name', p.display_name, 'avatar_url', p.avatar_url,
                                               'at', k.created_at) order by k.created_at desc), '[]'::jsonb)
  from public.direct_blocks k join public.profiles p on p.id = k.blocked_id
  where k.user_id = auth.uid();
$$;
revoke all on function public.blocked_with(uuid), public.set_block(uuid, boolean), public.my_blocks() from public, anon;
grant execute on function public.blocked_with(uuid), public.set_block(uuid, boolean), public.my_blocks() to authenticated;

-- Invitations : refusées entre deux personnes dont l'une a bloqué l'autre.
create or replace function private.guard_invite_block() returns trigger
language plpgsql security definer set search_path = '' as $$
declare inviter uuid := auth.uid();
begin
  if tg_table_name = 'group_invitations' then inviter := coalesce(inviter, new.invited_by); end if;
  if new.user_id is not null and private.blocked_either(inviter, new.user_id) then
    raise exception 'blocked: tu ne peux pas inviter cette personne' using errcode = '42501';
  end if;
  return new;
end $$;
revoke all on function private.guard_invite_block() from public, anon, authenticated;
drop trigger if exists group_invitations_block on private.group_invitations;
create trigger group_invitations_block before insert on private.group_invitations
  for each row execute function private.guard_invite_block();
drop trigger if exists event_invites_block on public.event_invites;
create trigger event_invites_block before insert on public.event_invites
  for each row execute function private.guard_invite_block();

-- Notifications causées par une personne bloquée (message de groupe, réponse, @tout, invitations…) : jamais envoyées.
create or replace function private.drop_blocked_notification() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.kind in ('group_message', 'direct_message', 'message', 'group_invite', 'private_invite', 'group_join')
     and private.blocked_either(auth.uid(), new.user_id) then
    return null;
  end if;
  return new;
end $$;
revoke all on function private.drop_blocked_notification() from public, anon, authenticated;
drop trigger if exists notifications_blocked on public.notifications;
create trigger notifications_blocked before insert on public.notifications
  for each row execute function private.drop_blocked_notification();

-- Fiche d'un membre : réduite (surnom seul) pour qui a été bloqué par ce membre ; « blocked » : je l'ai bloqué.
do $$
declare
  def text := pg_get_functiondef('public.member_card(uuid)'::regprocedure);
  anchor text := 'identity := p.id = me or public.has_perm(''members.view_identity'');';
  me_anchor text := '''me'', p.id = me,';
begin
  if position('direct_blocks' in def) > 0 then return; end if;
  if position(anchor in def) = 0 or position(me_anchor in def) = 0 then
    raise exception 'member_card : repères introuvables, blocage non ajouté à la fiche';
  end if;
  def := replace(def, anchor, anchor
    || E'\n  if p.id <> me and exists (select 1 from public.direct_blocks k where k.user_id = p.id and k.blocked_id = me)'
    || E'\n     and not public.has_perm(''moderation.reports'') then'
    || E'\n    return jsonb_build_object(''id'', p.id, ''display_name'', p.display_name, ''avatar_url'', null, ''role'', p.role,'
    || E'\n      ''root'', false, ''me'', false, ''first_name'', null, ''last_name'', null, ''phone'', null, ''groups'', ''[]''::jsonb,'
    || E'\n      ''restricted'', true, ''blocked'', false);'
    || E'\n  end if;');
  def := replace(def, me_anchor, me_anchor || E'\n    ''blocked'', exists (select 1 from public.direct_blocks k where k.user_id = me and k.blocked_id = p.id),');
  execute def;
end $$;

-- --------------------------------------------------------------------------------------------------------------
-- 1 bis. Le filtre appliqué par la base aux textes des joueurs
-- --------------------------------------------------------------------------------------------------------------
-- Messages (groupe, direct, événement) : filtre (masque ou refus), CGU, citations retirées entre personnes bloquées.
-- (Nommés après *_guard : PostgreSQL lance les déclencheurs BEFORE par ordre alphabétique.)
create or replace function private.moderate_message() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if tg_op = 'INSERT' then
    perform private.require_terms(new.user_id);
  end if;
  if new.deleted_at is null and btrim(coalesce(new.body, '')) <> ''
     and (tg_op = 'INSERT' or new.body is distinct from old.body) then
    new.body := private.moderate_text(new.body, 'message');
  end if;
  return new;
end $$;
revoke all on function private.moderate_message() from public, anon, authenticated;

create or replace function private.unmention_blocked() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  new.mentions := coalesce((select array_agg(m) from unnest(new.mentions) m
                            where not private.blocked_either(new.user_id, m)), '{}');
  return new;
end $$;
revoke all on function private.unmention_blocked() from public, anon, authenticated;

drop trigger if exists group_messages_moderation on public.group_messages;
create trigger group_messages_moderation before insert or update of body on public.group_messages
  for each row execute function private.moderate_message();
drop trigger if exists group_messages_unmention on public.group_messages;
create trigger group_messages_unmention before insert on public.group_messages
  for each row execute function private.unmention_blocked();
drop trigger if exists direct_messages_moderation on public.direct_messages;
create trigger direct_messages_moderation before insert or update of body on public.direct_messages
  for each row execute function private.moderate_message();
drop trigger if exists messages_moderation on public.messages;
create trigger messages_moderation before insert or update of body on public.messages
  for each row execute function private.moderate_message();
drop trigger if exists messages_unmention on public.messages;
create trigger messages_unmention before insert on public.messages
  for each row execute function private.unmention_blocked();

-- Surnom : refusé s'il contient un mot interdit, un lien ou un numéro ; CGU avant le premier nom.
create or replace function private.moderate_profile_name() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if btrim(coalesce(new.display_name, '')) <> ''
     and (tg_op = 'INSERT' or new.display_name is distinct from old.display_name) then
    perform private.require_terms(new.id);
    new.display_name := private.moderate_text(new.display_name, 'name');
  end if;
  return new;
end $$;
revoke all on function private.moderate_profile_name() from public, anon, authenticated;
drop trigger if exists profiles_moderation on public.profiles;
create trigger profiles_moderation before insert or update of display_name on public.profiles
  for each row execute function private.moderate_profile_name();

-- Nom de groupe (créé par un membre) : même règle qu'un surnom.
create or replace function private.moderate_group_name() returns trigger
language plpgsql security definer set search_path = '' as $$
begin
  if new.system_key is null and (tg_op = 'INSERT' or new.name is distinct from old.name) then
    perform private.require_terms(auth.uid());
    new.name := private.moderate_text(new.name, 'name');
  end if;
  return new;
end $$;
revoke all on function private.moderate_group_name() from public, anon, authenticated;
drop trigger if exists member_groups_moderation on public.member_groups;
create trigger member_groups_moderation before insert or update of name on public.member_groups
  for each row execute function private.moderate_group_name();

-- --------------------------------------------------------------------------------------------------------------
-- 4 (droit d'abord). Droit « Modérer les signalements », donné au rôle Admin une seule fois
-- --------------------------------------------------------------------------------------------------------------
insert into public.permissions (key, grp, label, hint, sort) values
  ('moderation.reports', 'Membres', 'Modérer les signalements',
   'Lire les signalements, masquer un contenu, avertir ; suspendre ou bannir demande aussi « Bannir ou réintégrer un compte »', 35)
on conflict (key) do update set grp = excluded.grp, label = excluded.label, hint = excluded.hint, sort = excluded.sort;

do $$
begin
  if exists (select 1 from private.one_time_changes where name = 'moderation_reports_2026_11_04') then
    return;
  end if;
  insert into public.role_permissions (role, perm) values ('admin', 'moderation.reports') on conflict do nothing;
  insert into private.one_time_changes (name) values ('moderation_reports_2026_11_04');
end $$;

-- --------------------------------------------------------------------------------------------------------------
-- 2. Signalements
-- --------------------------------------------------------------------------------------------------------------
create table if not exists public.content_reports (
  id uuid primary key default gen_random_uuid(),
  reporter_id uuid references public.profiles(id) on delete set null,
  target_kind text not null check (target_kind in ('group_message', 'direct_message', 'event_message', 'profile', 'profile_photo',
                                                   'pet_name', 'pet_item', 'pet_offer', 'pet_showcase', 'pet_word')),
  target_id text not null check (char_length(target_id) between 1 and 100),
  target_user uuid references public.profiles(id) on delete cascade,
  reason text not null check (reason in ('harassment', 'shocking', 'spam', 'scam', 'other')),
  comment text check (char_length(comment) <= 500),
  snapshot jsonb not null default '{}'::jsonb,
  status text not null default 'open' check (status in ('open', 'actioned', 'dismissed')),
  resolution text,
  note text check (char_length(note) <= 500),
  handled_by uuid references public.profiles(id) on delete set null,
  handled_at timestamptz,
  created_at timestamptz not null default now()
);
create unique index if not exists content_reports_once on public.content_reports (reporter_id, target_kind, target_id)
  where status = 'open';
create index if not exists content_reports_queue on public.content_reports (status, created_at desc);
create index if not exists content_reports_by_reporter on public.content_reports (reporter_id, created_at desc);
create index if not exists content_reports_target on public.content_reports (target_kind, target_id);
create index if not exists content_reports_by_user on public.content_reports (target_user);
alter table public.content_reports enable row level security;
drop policy if exists "mes signalements" on public.content_reports;
create policy "mes signalements" on public.content_reports for select to authenticated
  using (reporter_id = (select auth.uid()));
revoke all on public.content_reports from anon;
revoke insert, update, delete on public.content_reports from authenticated;
grant select on public.content_reports to authenticated;

-- Points d'accroche du Compagnon (remplacés par sa migration) :
-- · report_snapshot_pet(kind, id, viewer) : {owner, text, …} si viewer voit ce contenu, sinon null ;
-- · moderation_hide_pet(kind, id) : retire ou remplace le contenu (nom d'origine, objet masqué…).
create or replace function private.report_snapshot_pet(p_kind text, p_id text, viewer uuid) returns jsonb
language sql stable security definer set search_path = '' as $$ select null::jsonb; $$;
create or replace function private.moderation_hide_pet(p_kind text, p_id text) returns void
language plpgsql security definer set search_path = '' as $$ begin return; end $$;
revoke all on function private.report_snapshot_pet(text, text, uuid), private.moderation_hide_pet(text, text)
  from public, anon, authenticated;

-- Ce que voit le modérateur : copie du contenu au moment du signalement (il peut avoir été supprimé depuis).
-- Null si la personne connectée ne voit pas ce contenu.
create or replace function private.report_snapshot(p_kind text, p_id text, viewer uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare gm public.group_messages; dm public.direct_messages; em public.messages; p public.profiles; uid uuid;
begin
  if p_kind like 'pet\_%' then return private.report_snapshot_pet(p_kind, p_id, viewer); end if;
  begin uid := p_id::uuid; exception when others then return null; end;
  if p_kind = 'group_message' then
    select * into gm from public.group_messages where id = uid;
    if gm.id is null or not private.reads_group(gm.group_id) then return null; end if;
    return jsonb_build_object('owner', gm.user_id, 'text', gm.body, 'photo_path', gm.photo_path, 'audio_path', gm.audio_path,
      'at', gm.created_at, 'place', (select name from public.member_groups where id = gm.group_id), 'group_id', gm.group_id);
  elsif p_kind = 'direct_message' then
    select * into dm from public.direct_messages where id = uid;
    if dm.id is null or not private.in_direct(dm.chat_id, viewer) then return null; end if;
    return jsonb_build_object('owner', dm.user_id, 'text', dm.body, 'photo_path', dm.photo_path, 'audio_path', dm.audio_path,
      'at', dm.created_at, 'place', 'Message direct', 'chat_id', dm.chat_id);
  elsif p_kind = 'event_message' then
    select * into em from public.messages where id = uid;
    if em.id is null or not public.can_see_event(em.event_id) then return null; end if;
    return jsonb_build_object('owner', em.user_id, 'text', em.body, 'at', em.created_at, 'event_id', em.event_id,
      'place', (select title from public.events where id = em.event_id));
  elsif p_kind in ('profile', 'profile_photo') then
    select * into p from public.profiles where id = uid and status = 'active';
    if p.id is null then return null; end if;
    return jsonb_build_object('owner', p.id, 'text', p.display_name,
      'photo_path', case when p_kind = 'profile_photo' then p.avatar_url end, 'place', 'Profil');
  end if;
  return null;
end $$;
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;

create or replace function public.report_content(p_kind text, p_target text, p_reason text, p_comment text default null)
returns uuid language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); snap jsonb; owner uuid; rid uuid; v_comment text := nullif(btrim(left(p_comment, 500)), '');
begin
  if me is null or not private.is_account_active(me) then raise exception 'Connexion requise' using errcode = '42501'; end if;
  if p_reason is null or p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'other') then
    raise exception 'reason: choisis une raison' using errcode = '22023';
  end if;
  if (select count(*) from public.content_reports where reporter_id = me and created_at > now() - interval '1 hour') >= 10
     or (select count(*) from public.content_reports where reporter_id = me and created_at > now() - interval '1 day') >= 30 then
    raise exception 'rate_limited: tu as fait beaucoup de signalements, réessaie plus tard' using errcode = '54000';
  end if;
  snap := private.report_snapshot(p_kind, p_target, me);
  if snap is null then raise exception 'not_found: ce contenu n''existe plus ou ne t''est pas visible' using errcode = 'P0002'; end if;
  owner := nullif(snap ->> 'owner', '')::uuid;
  if owner = me then raise exception 'self: tu ne peux pas signaler ton propre contenu' using errcode = '22023'; end if;
  select id into rid from public.content_reports
    where reporter_id = me and target_kind = p_kind and target_id = p_target and status = 'open';
  if rid is not null then
    update public.content_reports set reason = p_reason, comment = v_comment where id = rid;
    return rid;
  end if;
  insert into public.content_reports (reporter_id, target_kind, target_id, target_user, reason, comment, snapshot)
  values (me, p_kind, p_target, owner, p_reason, v_comment, snap - 'owner')
  returning id into rid;
  return rid;
end $$;

-- Mes signalements et leur suite (« En cours », « Traité », « Classé »).
create or replace function public.my_reports() returns jsonb
language sql stable security definer set search_path = '' as $$
  select coalesce(jsonb_agg(jsonb_build_object('id', r.id, 'kind', r.target_kind, 'reason', r.reason, 'status', r.status,
           'text', left(r.snapshot ->> 'text', 140), 'at', r.created_at, 'handled_at', r.handled_at) order by r.created_at desc), '[]'::jsonb)
  from public.content_reports r where r.reporter_id = auth.uid();
$$;
revoke all on function public.report_content(text, text, text, text), public.my_reports() from public, anon;
grant execute on function public.report_content(text, text, text, text), public.my_reports() to authenticated;

-- Notification des modérateurs (sans le contenu : seulement le type et la raison).
create or replace function private.notify_new_report() returns trigger
language plpgsql security definer set search_path = '' as $$
declare u uuid;
begin
  for u in select p.id from public.profiles p where p.status = 'active' and private.user_has(p.id, 'moderation.reports') loop
    perform public.queue_notification(u, 'report_new', null, 'Nouveau signalement',
      (case new.reason when 'harassment' then 'Harcèlement' when 'shocking' then 'Contenu choquant' when 'spam' then 'Spam'
                       when 'scam' then 'Arnaque ou vente' else 'Autre raison' end)
      || ' · ' || (case when new.target_kind in ('group_message', 'direct_message', 'event_message') then 'un message'
                        when new.target_kind = 'profile' then 'un profil' when new.target_kind = 'profile_photo' then 'une photo de profil'
                        else 'le Compagnon' end),
      'report:' || new.id, jsonb_build_object('report_id', new.id));
  end loop;
  return null;
end $$;
revoke all on function private.notify_new_report() from public, anon, authenticated;
drop trigger if exists content_reports_notify on public.content_reports;
create trigger content_reports_notify after insert on public.content_reports
  for each row execute function private.notify_new_report();

-- Photo de profil signalée : un modérateur peut retirer le fichier (l'API Storage refuse la suppression en SQL).
drop policy if exists "modérateurs retirent une photo signalée" on storage.objects;
create policy "modérateurs retirent une photo signalée" on storage.objects for delete to authenticated
  using (bucket_id = 'profile-photos' and (select public.has_perm('moderation.reports'))
         and exists (select 1 from public.content_reports r where r.target_kind = 'profile_photo' and r.snapshot ->> 'photo_path' = name));

-- --------------------------------------------------------------------------------------------------------------
-- 4. Sanctions, file et actions des modérateurs
-- --------------------------------------------------------------------------------------------------------------
create table if not exists public.moderation_sanctions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references public.profiles(id) on delete cascade,
  kind text not null check (kind in ('warn', 'suspend', 'ban')),
  ends_at timestamptz,
  lifted_at timestamptz,
  report_id uuid references public.content_reports(id) on delete set null,
  note text check (char_length(note) <= 500),
  created_by uuid references public.profiles(id) on delete set null,
  created_at timestamptz not null default now()
);
create index if not exists moderation_sanctions_user on public.moderation_sanctions (user_id, created_at desc);
alter table public.moderation_sanctions enable row level security;
drop policy if exists "mes sanctions" on public.moderation_sanctions;
create policy "mes sanctions" on public.moderation_sanctions for select to authenticated using (user_id = (select auth.uid()));
revoke all on public.moderation_sanctions from anon;
revoke insert, update, delete on public.moderation_sanctions from authenticated;
grant select on public.moderation_sanctions to authenticated;

create or replace function private.require_moderator() returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if not private.user_has(auth.uid(), 'moderation.reports') then
    raise exception 'forbidden: réservé aux modérateurs (droit « Modérer les signalements »)' using errcode = '42501';
  end if;
end $$;
revoke all on function private.require_moderator() from public, anon, authenticated;

create or replace function public.moderation_queue(p_status text default 'open', p_limit integer default 100) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
begin
  perform private.require_moderator();
  return coalesce((select jsonb_agg(q.row order by q.created_at desc) from (
    select r.created_at, jsonb_build_object(
      'id', r.id, 'kind', r.target_kind, 'target_id', r.target_id, 'reason', r.reason, 'comment', r.comment,
      'snapshot', r.snapshot, 'status', r.status, 'resolution', r.resolution, 'note', r.note, 'created_at', r.created_at,
      'handled_at', r.handled_at, 'handled_by', private.member_name(r.handled_by),
      'reporter', jsonb_build_object('id', r.reporter_id, 'name', private.member_name(r.reporter_id)),
      'target_user', case when t.id is null then null else jsonb_build_object('id', t.id, 'name', t.display_name,
                       'avatar_url', t.avatar_url, 'status', t.status, 'role', t.role) end,
      'same_target', (select count(*) from public.content_reports x where x.target_kind = r.target_kind and x.target_id = r.target_id),
      'user_reports', (select count(*) from public.content_reports x where x.target_user = r.target_user),
      'sanctions', coalesce((select jsonb_agg(jsonb_build_object('kind', s.kind, 'ends_at', s.ends_at, 'lifted_at', s.lifted_at,
                     'at', s.created_at) order by s.created_at desc)
                   from public.moderation_sanctions s where s.user_id = r.target_user), '[]'::jsonb)) as row
    from public.content_reports r left join public.profiles t on t.id = r.target_user
    where p_status = 'all' or r.status = p_status
    order by r.created_at desc
    limit greatest(1, least(coalesce(p_limit, 100), 300))) q), '[]'::jsonb);
end $$;

-- Masquer le contenu signalé (le même pour tous les signalements de ce contenu).
create or replace function private.moderation_hide(r public.content_reports) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare uid uuid;
begin
  if r.target_kind like 'pet\_%' then
    perform private.moderation_hide_pet(r.target_kind, r.target_id);
    return '{}'::jsonb;
  end if;
  uid := r.target_id::uuid;
  if r.target_kind = 'group_message' then
    update public.group_messages set body = '', photo_path = null, audio_path = null, mentions = '{}', mention_all = false,
      pinned = false, announcement = false, deleted_at = coalesce(deleted_at, now()), deleted_by_admin = true where id = uid;
    delete from public.group_message_reactions where message_id = uid;
  elsif r.target_kind = 'direct_message' then
    update public.direct_messages set body = '', photo_path = null, audio_path = null, pinned = false,
      deleted_at = coalesce(deleted_at, now()) where id = uid;
    delete from public.direct_message_reactions where message_id = uid;
  elsif r.target_kind = 'event_message' then
    update public.messages set body = '•', mentions = '{}', pinned = false, deleted_at = coalesce(deleted_at, now()) where id = uid;
  elsif r.target_kind = 'profile' then
    update public.profiles set display_name = 'Surnom masqué' where id = uid;
  elsif r.target_kind = 'profile_photo' then
    -- Le fichier se retire par l'API Storage (politique « modérateurs retirent une photo signalée ») : l'appli le fait.
    return jsonb_build_object('remove_photo', r.snapshot ->> 'photo_path');
  end if;
  return '{}'::jsonb;
end $$;
revoke all on function private.moderation_hide(public.content_reports) from public, anon, authenticated;

-- Actions : hide (masquer), warn (avertir), suspend (p_days jours), ban (bannir), dismiss (classer sans suite).
-- Suspendre et bannir changent le statut du COMPTE (identifiant), jamais une IP ; guard_profile vérifie en plus le rang.
create or replace function public.moderation_act(p_report uuid, p_action text, p_note text default null, p_days integer default null)
returns jsonb language plpgsql security definer set search_path = '' as $$
declare r public.content_reports; extra jsonb := '{}'::jsonb; msg text := nullif(btrim(left(p_note, 500)), '');
begin
  perform private.require_moderator();
  select * into r from public.content_reports where id = p_report for update;
  if r.id is null then raise exception 'not_found: signalement introuvable' using errcode = 'P0002'; end if;
  if p_action is null or p_action not in ('hide', 'warn', 'suspend', 'ban', 'dismiss') then
    raise exception 'Action inconnue' using errcode = '22023';
  end if;
  if p_action in ('warn', 'suspend', 'ban') and r.target_user is null then
    raise exception 'not_found: ce compte n''existe plus' using errcode = 'P0002';
  end if;
  if p_action in ('suspend', 'ban') then
    if r.target_user = auth.uid() then raise exception 'forbidden: pas sur ton propre compte' using errcode = '42501'; end if;
    if not private.user_has(auth.uid(), 'members.ban') then
      raise exception 'forbidden: suspendre ou bannir demande aussi le droit « Bannir ou réintégrer un compte »' using errcode = '42501';
    end if;
    if p_action = 'suspend' and (p_days is null or p_days not between 1 and 365) then
      raise exception 'days: choisis une durée de 1 à 365 jours' using errcode = '22023';
    end if;
    update public.profiles set status = 'banned' where id = r.target_user and status <> 'banned';
    insert into public.moderation_sanctions (user_id, kind, ends_at, report_id, note, created_by)
    values (r.target_user, p_action, case when p_action = 'suspend' then now() + make_interval(days => p_days) end, r.id, msg, auth.uid());
  elsif p_action = 'hide' then
    extra := private.moderation_hide(r);
  elsif p_action = 'warn' then
    insert into public.moderation_sanctions (user_id, kind, report_id, note, created_by)
    values (r.target_user, 'warn', r.id, msg, auth.uid());
    perform public.queue_notification(r.target_user, 'moderation_notice', null, 'Message de la modération',
      coalesce(msg, 'Un contenu que tu as publié ne respecte pas les conditions d''utilisation de Party.')
      || ' Merci de garder Party agréable pour tout le monde.', 'moderation_notice:' || r.id);
  end if;
  update public.content_reports set status = case when p_action = 'dismiss' then 'dismissed' else 'actioned' end,
    resolution = p_action, note = coalesce(msg, content_reports.note), handled_by = auth.uid(), handled_at = now()
  where id = r.id or (p_action in ('hide', 'dismiss') and status = 'open' and target_kind = r.target_kind and target_id = r.target_id);
  perform private.audit('moderation.' || p_action, r.target_user,
    jsonb_build_object('report', r.id, 'kind', r.target_kind, 'reason', r.reason, 'days', p_days, 'note', msg));
  return extra || jsonb_build_object('id', r.id, 'status', case when p_action = 'dismiss' then 'dismissed' else 'actioned' end);
end $$;

-- Lever une sanction (réintégrer avant la fin d'une suspension, ou annuler un bannissement).
create or replace function public.moderation_lift(p_user uuid) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform private.require_moderator();
  if not private.user_has(auth.uid(), 'members.ban') then
    raise exception 'forbidden: il faut le droit « Bannir ou réintégrer un compte »' using errcode = '42501';
  end if;
  update public.moderation_sanctions set lifted_at = now() where user_id = p_user and kind in ('suspend', 'ban') and lifted_at is null;
  update public.profiles set status = 'active' where id = p_user and status = 'banned';
  perform private.audit('moderation.lift', p_user, null);
end $$;

-- Fin des suspensions (toutes les 10 minutes) : le compte revient, sauf bannissement en cours.
create or replace function private.lift_expired_suspensions() returns integer
language plpgsql security definer set search_path = '' as $$
declare n integer := 0; s public.moderation_sanctions;
begin
  for s in select * from public.moderation_sanctions where kind = 'suspend' and lifted_at is null and ends_at <= now() loop
    update public.moderation_sanctions set lifted_at = now() where id = s.id;
    if not exists (select 1 from public.moderation_sanctions b where b.user_id = s.user_id and b.lifted_at is null
                   and (b.kind = 'ban' or (b.kind = 'suspend' and b.ends_at > now()))) then
      update public.profiles set status = 'active' where id = s.user_id and status = 'banned';
      n := n + 1;
    end if;
  end loop;
  -- Conservation : signalements traités gardés un an.
  delete from public.content_reports where status <> 'open' and handled_at < now() - interval '1 year';
  return n;
end $$;
revoke all on function private.lift_expired_suspensions() from public, anon, authenticated;

do $$
begin
  if exists (select 1 from cron.job where jobname = 'moderation-lift') then
    perform cron.unschedule('moderation-lift');
  end if;
  perform cron.schedule('moderation-lift', '*/10 * * * *', 'select private.lift_expired_suspensions();');
end $$;

revoke all on function public.moderation_queue(text, integer), public.moderation_act(uuid, text, text, integer),
  public.moderation_lift(uuid) from public, anon;
grant execute on function public.moderation_queue(text, integer), public.moderation_act(uuid, text, text, integer),
  public.moderation_lift(uuid) to authenticated;

-- --------------------------------------------------------------------------------------------------------------
-- Notifications : deux interrupteurs (règle permanente : chaque type a le sien)
-- --------------------------------------------------------------------------------------------------------------
alter table public.notification_prefs add column if not exists moderation_reports boolean not null default true;  -- modérateurs
alter table public.notification_prefs add column if not exists moderation_notices boolean not null default true;  -- tout le monde

do $$
declare
  def text := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  anchor text := 'when ''group_join'' then prefs.group_joins';
begin
  if position('''report_new''' in def) > 0 then return; end if;
  if position(anchor in def) = 0 then
    raise exception 'web_push_allowed : branche group_join introuvable, report_new / moderation_notice non ajoutés';
  end if;
  execute replace(def, anchor, anchor || E'\n    when ''report_new'' then coalesce(prefs.moderation_reports, true)'
                                       || E'\n    when ''moderation_notice'' then coalesce(prefs.moderation_notices, true)');
end $$;

-- Reçues aussi par les comptes Guest actifs (un avertissement vise n'importe quel compte).
do $$
declare
  def text := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  anchor text := '''direct_message'')';
begin
  if position('''moderation_notice''' in def) > 0 then return; end if;
  if position(anchor in def) = 0 then
    raise exception 'may_receive_push : liste des types introuvable, moderation_notice non ajouté';
  end if;
  execute replace(def, anchor, '''direct_message'', ''moderation_notice'', ''report_new'')');
end $$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261104200000', 'moderation') on conflict do nothing;
commit;

notify pgrst, 'reload schema';
