-- Pronos entre amis (avis f071c5f46e3d, 17.11.2026). Revue de conformité : jamais d'argent, de mise, de pot, de lot ni
-- d'enjeu (Apple 5.1.1(ix), 5.3.4 ; LJAr ; ANJ) : « pour l'honneur », des points au classement du groupe, rien d'autre.
--
-- · Un prono = une question posée par un membre au profil complet (CGU) à un de SES groupes (jamais Membres Vendredi
--   Party), aux participants d'un événement qu'il voit (« Pronos de la soirée »), à des personnes choisies parmi celles
--   qu'il a croisées, et / ou par lien (connexion Party, profil complet, CGU, puis on joue).
-- · Types : choix (2 à 8), nombre (le plus proche gagne), réponse libre (l'organisateur coche les gagnants), une personne.
-- · Réponses CACHÉES par la base (organisateur et admins compris) jusqu'au dévoilement : à la fin des pronos
--   (reveal = 'close') ou quand l'organisateur donne le résultat (reveal = 'result'). Réponse libre : toujours à la fin
--   (l'organisateur doit les lire pour cocher les gagnants). Avant : on voit seulement QUI a joué.
-- · Après la première réponse : question et choix figés ; la fin se déplace ; « Annuler » (aucun point).
-- · Points : 1 à 10 par bonne réponse, choisis par l'organisateur ; classement par groupe, remis à zéro par qui gère le groupe.
-- · Textes (question, choix, réponse libre) : filtre commun + refus de l'argent, des mises et de l'alcool ; « Signaler »
--   (prono, prono_answer) ; blocage : jamais dans le prono de l'autre, jamais vu, jamais notifié.
-- · Notifications : prono_new, prono_result, prono_due (à l'organisateur : la fin est passée) ; interrupteur
--   notification_prefs.pronos. Signal temps réel « prono:<id> » à chaque changement.
-- Tout par fonctions (schéma private, aucun accès direct). Purement additive et rejouable.

create table if not exists private.pronos (
  id uuid primary key default gen_random_uuid(),
  created_by uuid not null references public.profiles (id) on delete cascade,
  group_id uuid references public.member_groups (id) on delete cascade,
  event_id uuid references public.events (id) on delete cascade,
  question text not null check (char_length(question) between 3 and 200),
  kind text not null check (kind in ('choice', 'number', 'text', 'person')),
  points int not null default 3 check (points between 1 and 10),
  closes_at timestamptz not null,
  reveal text not null default 'close' check (reveal in ('close', 'result')),
  result_option uuid,
  result_number numeric,
  result_person uuid references public.profiles (id) on delete set null,
  result_at timestamptz,
  cancelled_at timestamptz,
  link_token text unique,
  link_stopped_at timestamptz,
  due_notified_at timestamptz,
  hidden_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index if not exists pronos_group on private.pronos (group_id) where group_id is not null;
create index if not exists pronos_event on private.pronos (event_id) where event_id is not null;
create index if not exists pronos_due on private.pronos (closes_at) where result_at is null and cancelled_at is null and due_notified_at is null;

create table if not exists private.prono_options (
  id uuid primary key default gen_random_uuid(),
  prono_id uuid not null references private.pronos (id) on delete cascade,
  position int not null,
  label text not null check (char_length(label) between 1 and 60)
);
create index if not exists prono_options_prono on private.prono_options (prono_id, position);

create table if not exists private.prono_players (
  prono_id uuid not null references private.pronos (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  via text not null check (via in ('invite', 'link')),
  added_at timestamptz not null default now(),
  primary key (prono_id, user_id)
);
create index if not exists prono_players_user on private.prono_players (user_id);

create table if not exists private.prono_answers (
  prono_id uuid not null references private.pronos (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  option_id uuid references private.prono_options (id) on delete cascade,
  number numeric,
  answer_text text check (answer_text is null or char_length(answer_text) between 1 and 80),
  person_id uuid references public.profiles (id) on delete cascade,
  winner boolean not null default false,
  hidden_at timestamptz,
  answered_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  primary key (prono_id, user_id)
);
create index if not exists prono_answers_user on private.prono_answers (user_id);

create table if not exists private.prono_board_resets (
  group_id uuid primary key references public.member_groups (id) on delete cascade,
  reset_at timestamptz not null default now()
);

alter table private.pronos enable row level security;
alter table private.prono_options enable row level security;
alter table private.prono_players enable row level security;
alter table private.prono_answers enable row level security;
alter table private.prono_board_resets enable row level security;
revoke all on private.pronos, private.prono_options, private.prono_players, private.prono_answers, private.prono_board_resets
  from public, anon, authenticated;

alter table public.notification_prefs add column if not exists pronos boolean not null default true;

-- ───────────── Aides ─────────────

-- Pour l'honneur : ni argent, ni mise, ni pot, ni alcool (revue de conformité du 17.11). Accents et majuscules ignorés.
create or replace function private.prono_text(t text, what text) returns text
language plpgsql stable security definer set search_path = '' as $$
declare s text := btrim(regexp_replace(coalesce(t, ''), '\s+', ' ', 'g')); l text;
begin
  if s = '' then raise exception 'invalid: % vide.', what using errcode = '22023'; end if;
  l := translate(lower(s), 'àâäáãåçéèêëíìîïñóòôöõúùûüýÿœ', 'aaaaaaceeeeiiiinooooouuuuyyo');
  if l ~ '[€$£]' or l ~ '\d\s*\.-' or l ~ '\d\s*(chf|eur|euros?|fr|francs?|balles?|cts?)\M'
     or l ~ '\m(chf|euros?|francs?|balles|thunes?|fric|pognon|argent|mise|mises|miser|misez|mise|pari|parie|parier|pariez|parions|paries|cagnotte|pot commun|jackpot|twint|revolut|paypal|tournee|tournees|shots?|alcool|bieres?|vins?|vodka|whisky|tequila|rhum|gin|bourre|bourres|bourree|bourrees|cuite|ivre|ivres|soulard)\M' then
    raise exception 'content_refused: Les pronos se jouent pour l''honneur : pas d''argent, de mise ni de boisson.' using errcode = '23514';
  end if;
  return private.moderate_text(s, 'name');
end $$;
revoke all on function private.prono_text(text, text) from public, anon, authenticated;

create or replace function private.prono_organizes(e uuid, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.events where id = e and created_by = uid)
      or exists (select 1 from public.event_organizers where event_id = e and user_id = uid);
$$;
revoke all on function private.prono_organizes(uuid, uuid) from public, anon, authenticated;

-- Qui joue : l'organisateur, les membres du groupe, les participants (Présent / Peut-être) et l'organisation de
-- l'événement, les personnes invitées ou venues par le lien. Jamais en blocage avec l'organisateur, compte actif.
create or replace function private.prono_can_play(p private.pronos, uid uuid) returns boolean
language sql stable security definer set search_path = '' as $$
  select uid is not null and p.hidden_at is null and private.is_account_active(uid)
    and (uid = p.created_by or not private.blocked_either(p.created_by, uid))
    and (uid = p.created_by
      or (p.group_id is not null and private.in_group_now(p.group_id, uid))
      or (p.event_id is not null and (private.prono_organizes(p.event_id, uid)
          or exists (select 1 from public.rsvps r where r.event_id = p.event_id and r.user_id = uid and r.status in ('yes', 'maybe'))))
      or exists (select 1 from private.prono_players x where x.prono_id = p.id and x.user_id = uid));
$$;
revoke all on function private.prono_can_play(private.pronos, uuid) from public, anon, authenticated;

-- Toutes les personnes du prono (notifications, choix « une personne »).
create or replace function private.prono_people(p private.pronos) returns setof uuid
language sql stable security definer set search_path = '' as $$
  select u from (
    select p.created_by as u
    union select m.user_id from public.member_group_members m where p.group_id is not null and m.group_id = p.group_id
    union select r.user_id from public.rsvps r where p.event_id is not null and r.event_id = p.event_id and r.status in ('yes', 'maybe')
    union select o.user_id from public.event_organizers o where p.event_id is not null and o.event_id = p.event_id
    union select e.created_by from public.events e where p.event_id is not null and e.id = p.event_id
    union select x.user_id from private.prono_players x where x.prono_id = p.id
  ) s where u is not null and private.prono_can_play(p, u);
$$;
revoke all on function private.prono_people(private.pronos) from public, anon, authenticated;

create or replace function private.prono_state(p private.pronos) returns text
language sql stable set search_path = '' as $$
  select case when p.cancelled_at is not null then 'cancelled' when p.result_at is not null then 'done'
              when p.closes_at > now() then 'open' else 'closed' end;
$$;
revoke all on function private.prono_state(private.pronos) from public, anon, authenticated;

-- Réponses visibles : résultat donné, ou fin passée quand l'organisateur a choisi « à la fin » (réponse libre : toujours).
create or replace function private.prono_revealed(p private.pronos) returns boolean
language sql stable set search_path = '' as $$
  select p.result_at is not null
      or (p.reveal = 'close' and p.closes_at <= now() and (p.cancelled_at is null or p.cancelled_at >= p.closes_at));
$$;
revoke all on function private.prono_revealed(private.pronos) from public, anon, authenticated;

create or replace function private.prono_face(uid uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('id', p.id, 'name', p.display_name, 'avatar_url', p.avatar_url, 'me', p.id = auth.uid())
  from public.profiles p where p.id = uid;
$$;
revoke all on function private.prono_face(uuid) from public, anon, authenticated;

-- Personnes que je peux inviter une à une : croisées à un événement, ou dans un de mes groupes (jamais tout le site).
create or replace function private.prono_known(me uuid) returns setof uuid
language sql stable security definer set search_path = '' as $$
  with mine as (select id from private.met_events(me) m(id))
  select distinct u from (
    select r.user_id as u from public.rsvps r where r.event_id in (select id from mine) and r.status in ('yes', 'maybe')
    union select o.user_id from public.event_organizers o where o.event_id in (select id from mine)
    union select e.created_by from public.events e where e.id in (select id from mine)
    union select m2.user_id from public.member_group_members m1
      join public.member_groups g on g.id = m1.group_id and g.system_key is null
      join public.member_group_members m2 on m2.group_id = m1.group_id
      where m1.user_id = me
  ) s where u is not null and u <> me;
$$;
revoke all on function private.prono_known(uuid) from public, anon, authenticated;

create or replace function private.prono_signal(p private.pronos) returns void
language plpgsql security definer set search_path = '' as $$
begin
  perform private.party_signal('prono:' || p.id);
  if p.group_id is not null then perform private.party_signal('pronos:' || p.group_id); end if;
  if p.event_id is not null then perform private.party_signal('pronos:' || p.event_id); end if;
end $$;
revoke all on function private.prono_signal(private.pronos) from public, anon, authenticated;

create or replace function private.prono_where(p private.pronos) returns text
language sql stable security definer set search_path = '' as $$
  select coalesce((select g.name from public.member_groups g where g.id = p.group_id),
                  (select e.title from public.events e where e.id = p.event_id),
                  (select x.display_name from public.profiles x where x.id = p.created_by));
$$;
revoke all on function private.prono_where(private.pronos) from public, anon, authenticated;

create or replace function private.prono_when(t timestamptz) returns text
language sql stable set search_path = '' as $$
  select to_char(t at time zone 'Europe/Zurich', 'DD.MM à HH24:MI');
$$;
revoke all on function private.prono_when(timestamptz) from public, anon, authenticated;

-- « Nouveau prono » aux personnes données (jamais l'organisateur, jamais en blocage : queue_notification / trigger).
create or replace function private.prono_notify_new(p private.pronos, people uuid[]) returns void
language plpgsql security definer set search_path = '' as $$
declare u uuid;
begin
  foreach u in array coalesce(people, '{}') loop
    perform public.queue_notification(u, 'prono_new', null, '🔮 Nouveau prono · ' || private.prono_where(p),
      p.question || ' · à jouer jusqu''au ' || private.prono_when(p.closes_at),
      'prono_new:' || p.id || ':' || u, jsonb_build_object('prono_id', p.id, 'url', '/?tab=events&prono=' || p.id));
  end loop;
end $$;
revoke all on function private.prono_notify_new(private.pronos, uuid[]) from public, anon, authenticated;

-- ───────────── Lecture ─────────────

create or replace function private.prono_json(p private.pronos, me uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare st text := private.prono_state(p); rev boolean := private.prono_revealed(p); mine boolean := p.created_by = me;
        locked boolean := exists (select 1 from private.prono_answers a where a.prono_id = p.id);
        a private.prono_answers;
begin
  select * into a from private.prono_answers x where x.prono_id = p.id and x.user_id = me;
  return jsonb_build_object(
    'id', p.id, 'question', p.question, 'kind', p.kind, 'points', p.points, 'closes_at', p.closes_at,
    'reveal', p.reveal, 'state', st, 'revealed', rev, 'created_at', p.created_at, 'mine', mine, 'locked', locked,
    'creator', private.prono_face(p.created_by),
    'group', (select jsonb_build_object('id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color, 'photo', g.photo_path)
              from public.member_groups g where g.id = p.group_id),
    'event', (select jsonb_build_object('id', e.id, 'title', e.title, 'starts_at', e.starts_at) from public.events e where e.id = p.event_id),
    'options', coalesce((select jsonb_agg(jsonb_build_object('id', o.id, 'label', o.label,
        'count', case when rev then (select count(*) from private.prono_answers x where x.option_id = o.id and x.hidden_at is null) end,
        'correct', p.result_option = o.id) order by o.position)
      from private.prono_options o where o.prono_id = p.id), '[]'::jsonb),
    'candidates', case when p.kind = 'person' then coalesce((select jsonb_agg(private.prono_face(u.u) order by pr.display_name)
        from private.prono_people(p) u(u) join public.profiles pr on pr.id = u.u
        where not private.blocked_either(me, u.u)), '[]'::jsonb) end,
    'my_answer', case when a.user_id is not null then jsonb_build_object('option_id', a.option_id, 'number', a.number,
        'text', a.answer_text, 'person_id', a.person_id, 'winner', a.winner) end,
    'answered', coalesce((select jsonb_agg(private.prono_face(x.user_id) order by x.answered_at)
        from private.prono_answers x where x.prono_id = p.id and not private.blocked_either(me, x.user_id)), '[]'::jsonb),
    'players', (select count(*) from private.prono_people(p)),
    'answers', case when rev then coalesce((select jsonb_agg(jsonb_build_object('user', private.prono_face(x.user_id),
        'option_id', x.option_id, 'number', x.number, 'text', case when x.hidden_at is null then x.answer_text end,
        'hidden', x.hidden_at is not null, 'person', case when x.person_id is not null then private.prono_face(x.person_id) end,
        'winner', x.winner) order by x.winner desc, x.answered_at)
      from private.prono_answers x where x.prono_id = p.id and not private.blocked_either(me, x.user_id)), '[]'::jsonb) end,
    'result', case when p.result_at is not null then jsonb_build_object('option_id', p.result_option, 'number', p.result_number,
        'person', case when p.result_person is not null then private.prono_face(p.result_person) end, 'at', p.result_at) end,
    'winners', case when p.result_at is not null then coalesce((select jsonb_agg(private.prono_face(x.user_id) order by x.answered_at)
        from private.prono_answers x where x.prono_id = p.id and x.winner and not private.blocked_either(me, x.user_id)), '[]'::jsonb) end,
    'can_answer', st = 'open' and private.prono_can_play(p, me),
    'can_edit', mine and st = 'open' and not locked,
    'can_move_end', mine and st in ('open', 'closed'),
    'can_result', mine and st = 'closed' and (p.kind <> 'text' or rev),
    'can_cancel', mine and st in ('open', 'closed'),
    'link', case when mine then jsonb_build_object('token', case when p.link_stopped_at is null then p.link_token end,
        'path', case when p.link_token is not null and p.link_stopped_at is null then '/prono/' || p.link_token end) end);
end $$;
revoke all on function private.prono_json(private.pronos, uuid) from public, anon, authenticated;

create or replace function public.prono_get(id uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  select * into p from private.pronos x where x.id = prono_get.id;
  if p.id is null or not private.prono_can_play(p, me) then
    raise exception 'not_found: Ce prono n''existe plus ou ne t''est pas ouvert.' using errcode = 'PT404';
  end if;
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_get(uuid) from public, anon;
grant execute on function public.prono_get(uuid) to authenticated;

-- Liste : tous mes pronos (app « Pronos »), ceux d'un groupe, ou ceux d'un événement. Cartes légères.
create or replace function public.prono_list(group_id uuid default null, event_id uuid default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  return coalesce((select jsonb_agg(c.j order by c.rank, c.at desc) from (
    select case private.prono_state(p) when 'closed' then case when p.created_by = me then 0 else 2 end when 'open' then 1
                when 'done' then 3 else 4 end as rank,
      coalesce(p.result_at, p.closes_at) as at,
      jsonb_build_object('id', p.id, 'question', p.question, 'kind', p.kind, 'points', p.points, 'closes_at', p.closes_at,
        'state', private.prono_state(p), 'revealed', private.prono_revealed(p), 'mine', p.created_by = me,
        'creator', private.prono_face(p.created_by),
        'group', (select jsonb_build_object('id', g.id, 'name', g.name, 'emoji', g.emoji, 'color', g.color) from public.member_groups g where g.id = p.group_id),
        'event', (select jsonb_build_object('id', e.id, 'title', e.title) from public.events e where e.id = p.event_id),
        'answered_count', (select count(*) from private.prono_answers x where x.prono_id = p.id),
        'players', (select count(*) from private.prono_people(p)),
        'faces', coalesce((select jsonb_agg(f.face) from (select private.prono_face(x.user_id) as face from private.prono_answers x
            where x.prono_id = p.id and not private.blocked_either(me, x.user_id) order by x.answered_at desc limit 5) f), '[]'::jsonb),
        'answered', exists (select 1 from private.prono_answers x where x.prono_id = p.id and x.user_id = me),
        'won', exists (select 1 from private.prono_answers x where x.prono_id = p.id and x.user_id = me and x.winner),
        'winners', case when p.result_at is not null then coalesce((select jsonb_agg(w.face) from (select private.prono_face(x.user_id) as face
            from private.prono_answers x where x.prono_id = p.id and x.winner and not private.blocked_either(me, x.user_id)
            order by x.answered_at limit 6) w), '[]'::jsonb) end,
        'winners_count', case when p.result_at is not null then (select count(*) from private.prono_answers x where x.prono_id = p.id and x.winner) end
      ) as j
    from private.pronos p
    where p.hidden_at is null
      and (prono_list.group_id is null or p.group_id = prono_list.group_id)
      and (prono_list.event_id is null or p.event_id = prono_list.event_id)
      and (prono_list.group_id is not null or prono_list.event_id is not null
           or p.created_by = me or exists (select 1 from private.prono_answers x where x.prono_id = p.id and x.user_id = me)
           or exists (select 1 from private.prono_players x where x.prono_id = p.id and x.user_id = me)
           or (p.group_id is not null and private.in_group_now(p.group_id, me))
           or (p.event_id is not null and (private.prono_organizes(p.event_id, me)
               or exists (select 1 from public.rsvps r where r.event_id = p.event_id and r.user_id = me and r.status in ('yes', 'maybe')))))
      and private.prono_can_play(p, me)
    order by p.created_at desc limit 200) c), '[]'::jsonb);
end $$;
revoke all on function public.prono_list(uuid, uuid) from public, anon;
grant execute on function public.prono_list(uuid, uuid) to authenticated;

-- Pastille : pronos ouverts où je n'ai pas encore joué + résultats à donner.
create or replace function public.prono_badge() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); l jsonb := public.prono_list(null, null);
begin
  return jsonb_build_object(
    'to_play', (select count(*) from jsonb_array_elements(l) c where c ->> 'state' = 'open' and not (c ->> 'answered')::boolean),
    'to_result', (select count(*) from jsonb_array_elements(l) c where c ->> 'state' = 'closed' and (c ->> 'mine')::boolean),
    'me', me);
end $$;
revoke all on function public.prono_badge() from public, anon;
grant execute on function public.prono_badge() to authenticated;

-- Personnes à inviter une à une (croisées à un événement ou dans mes groupes), sans les bloqués.
create or replace function public.prono_suggestions() returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid();
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  return coalesce((select jsonb_agg(jsonb_build_object('id', p.id, 'name', p.display_name, 'avatar_url', p.avatar_url) order by p.display_name)
    from private.prono_known(me) k(u) join public.profiles p on p.id = k.u and p.status = 'active'
    where not private.blocked_either(me, p.id)), '[]'::jsonb);
end $$;
revoke all on function public.prono_suggestions() from public, anon;
grant execute on function public.prono_suggestions() to authenticated;

-- ───────────── Création, modification ─────────────

create or replace function private.prono_check_author(me uuid) returns void
language plpgsql stable security definer set search_path = '' as $$
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.identity_complete(me) then
    raise exception 'profile_required: Complète ton profil (prénom, nom, surnom) pour jouer aux pronos.' using errcode = '42501';
  end if;
  perform private.require_terms(me);
end $$;
revoke all on function private.prono_check_author(uuid) from public, anon, authenticated;

-- body : question, kind, options [texte], points, closes_at, reveal, group_id, event_id, people [uuid], link (bool).
create or replace function public.prono_create(body jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; k text := body ->> 'kind'; q text; ends timestamptz; g uuid; e uuid;
        opts text[] := '{}'; o text; i int := 0; ppl uuid[] := '{}'; u uuid; pts int := coalesce((body ->> 'points')::int, 3);
        rv text := coalesce(body ->> 'reveal', 'close'); notify uuid[];
begin
  perform private.prono_check_author(me);
  if (select count(*) from private.pronos x where x.created_by = me and x.created_at > now() - interval '1 day') >= 30 then
    raise exception 'rate_limited: Beaucoup de pronos aujourd''hui : réessaie demain.' using errcode = '54000';
  end if;
  if k is null or k not in ('choice', 'number', 'text', 'person') then
    raise exception 'invalid: Choisis le type de réponse.' using errcode = '22023';
  end if;
  q := private.prono_text(body ->> 'question', 'La question');
  if char_length(q) < 3 or char_length(q) > 200 then raise exception 'invalid: Question de 3 à 200 caractères.' using errcode = '22023'; end if;
  if pts < 1 or pts > 10 then raise exception 'invalid: De 1 à 10 points.' using errcode = '22023'; end if;
  if rv not in ('close', 'result') then raise exception 'invalid: Dévoilement inconnu.' using errcode = '22023'; end if;
  if k = 'text' then rv := 'close'; end if;  -- l'organisateur lit les réponses pour cocher les gagnants
  begin ends := (body ->> 'closes_at')::timestamptz; exception when others then ends := null; end;
  if ends is null or ends < now() + interval '5 minutes' or ends > now() + interval '366 days' then
    raise exception 'invalid: La fin des pronos : dans 5 minutes au moins, un an au plus.' using errcode = '22023';
  end if;
  g := nullif(body ->> 'group_id', '')::uuid;
  e := nullif(body ->> 'event_id', '')::uuid;
  if g is not null then
    if not exists (select 1 from public.member_groups x where x.id = g and x.system_key is null) or not private.in_group_now(g, me) then
      raise exception 'forbidden: Seulement dans un de tes groupes (jamais Membres Vendredi Party).' using errcode = '42501';
    end if;
  end if;
  if e is not null then
    if not public.can_see_event(e) or not exists (select 1 from public.events x where x.id = e and x.status = 'published') then
      raise exception 'forbidden: Tu ne vois pas cet événement.' using errcode = '42501';
    end if;
  end if;
  if jsonb_typeof(body -> 'people') = 'array' then
    select coalesce(array_agg(distinct v::uuid), '{}') into ppl from jsonb_array_elements_text(body -> 'people') v;
    ppl := array_remove(ppl, me);
    if cardinality(ppl) > 100 then raise exception 'invalid: 100 personnes au plus.' using errcode = '22023'; end if;
    foreach u in array ppl loop
      if private.blocked_either(me, u) or not private.is_account_active(u) or not exists (select 1 from private.prono_known(me) k(x) where k.x = u) then
        raise exception 'forbidden: Tu ne peux inviter que des personnes croisées dans Party.' using errcode = '42501';
      end if;
    end loop;
  end if;
  if g is null and e is null and cardinality(ppl) = 0 and not coalesce((body ->> 'link')::boolean, false) then
    raise exception 'invalid: Choisis qui joue : un groupe, des personnes ou un lien.' using errcode = '22023';
  end if;
  if k = 'choice' then
    if jsonb_typeof(body -> 'options') <> 'array' then raise exception 'invalid: Ajoute les choix.' using errcode = '22023'; end if;
    for o in select v from jsonb_array_elements_text(body -> 'options') v loop
      if btrim(coalesce(o, '')) <> '' then opts := opts || private.prono_text(o, 'Un choix'); end if;
    end loop;
    if cardinality(opts) < 2 or cardinality(opts) > 8 then raise exception 'invalid: De 2 à 8 choix.' using errcode = '22023'; end if;
    if (select count(distinct lower(x)) from unnest(opts) x) < cardinality(opts) then
      raise exception 'invalid: Deux choix sont identiques.' using errcode = '22023';
    end if;
    if exists (select 1 from unnest(opts) x where char_length(x) > 60) then raise exception 'invalid: 60 caractères au plus par choix.' using errcode = '22023'; end if;
  end if;
  insert into private.pronos (created_by, group_id, event_id, question, kind, points, closes_at, reveal, link_token)
  values (me, g, e, q, k, pts, ends, rv,
          case when coalesce((body ->> 'link')::boolean, false)
               then replace(replace(rtrim(encode(extensions.gen_random_bytes(18), 'base64'), '='), '+', '-'), '/', '_') end)
  returning * into p;
  foreach o in array opts loop
    i := i + 1;
    insert into private.prono_options (prono_id, position, label) values (p.id, i, o);
  end loop;
  insert into private.prono_players (prono_id, user_id, via) select p.id, x, 'invite' from unnest(ppl) x on conflict do nothing;
  select array_agg(u2) into notify from private.prono_people(p) u2;
  perform private.prono_notify_new(p, notify);
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_create(jsonb) from public, anon;
grant execute on function public.prono_create(jsonb) to authenticated;

-- Modifier : tout tant que personne n'a joué ; ensuite seulement la fin (et les points, tant que pas de résultat).
create or replace function public.prono_update(id uuid, body jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; locked boolean; ends timestamptz; o text; i int := 0; opts text[] := '{}';
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.id = prono_update.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono le modifie.' using errcode = '42501'; end if;
  if private.prono_state(p) not in ('open', 'closed') then raise exception 'invalid: Ce prono est terminé.' using errcode = '22023'; end if;
  locked := exists (select 1 from private.prono_answers a where a.prono_id = p.id);
  if body ? 'closes_at' then
    begin ends := (body ->> 'closes_at')::timestamptz; exception when others then ends := null; end;
    if ends is null or ends < now() + interval '1 minute' or ends > now() + interval '366 days' then
      raise exception 'invalid: La fin des pronos : dans le futur, un an au plus.' using errcode = '22023';
    end if;
    if p.reveal = 'close' and p.closes_at <= now() then
      raise exception 'invalid: Les réponses sont déjà dévoilées : la fin ne bouge plus.' using errcode = '22023';
    end if;
    update private.pronos x set closes_at = ends, due_notified_at = null, updated_at = now() where x.id = p.id returning * into p;
  end if;
  if body ? 'points' then
    if (body ->> 'points')::int not between 1 and 10 then raise exception 'invalid: De 1 à 10 points.' using errcode = '22023'; end if;
    update private.pronos x set points = (body ->> 'points')::int, updated_at = now() where x.id = p.id returning * into p;
  end if;
  if body ? 'question' or body ? 'options' or body ? 'reveal' then
    if locked then
      raise exception 'locked: Quelqu''un a déjà joué : la question et les choix ne changent plus.' using errcode = '22023';
    end if;
    if body ? 'question' then
      update private.pronos x set question = private.prono_text(body ->> 'question', 'La question'), updated_at = now()
        where x.id = p.id returning * into p;
    end if;
    if body ? 'reveal' and p.kind <> 'text' and body ->> 'reveal' in ('close', 'result') then
      update private.pronos x set reveal = body ->> 'reveal' where x.id = p.id returning * into p;
    end if;
    if body ? 'options' and p.kind = 'choice' then
      for o in select v from jsonb_array_elements_text(body -> 'options') v loop
        if btrim(coalesce(o, '')) <> '' then opts := opts || private.prono_text(o, 'Un choix'); end if;
      end loop;
      if cardinality(opts) < 2 or cardinality(opts) > 8 then raise exception 'invalid: De 2 à 8 choix.' using errcode = '22023'; end if;
      delete from private.prono_options x where x.prono_id = p.id;
      foreach o in array opts loop
        i := i + 1;
        insert into private.prono_options (prono_id, position, label) values (p.id, i, left(o, 60));
      end loop;
    end if;
  end if;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_update(uuid, jsonb) from public, anon;
grant execute on function public.prono_update(uuid, jsonb) to authenticated;

-- Ajouter des personnes après coup (prévenues), ou allumer / arrêter le lien.
create or replace function public.prono_invite(id uuid, people uuid[]) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; u uuid; added uuid[] := '{}';
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.id = prono_invite.id;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono invite.' using errcode = '42501'; end if;
  if private.prono_state(p) <> 'open' then raise exception 'invalid: Les pronos sont fermés.' using errcode = '22023'; end if;
  if cardinality(coalesce(people, '{}')) > 100 then raise exception 'invalid: 100 personnes au plus.' using errcode = '22023'; end if;
  foreach u in array coalesce(people, '{}') loop
    continue when u = me or private.prono_can_play(p, u);
    if private.blocked_either(me, u) or not private.is_account_active(u) or not exists (select 1 from private.prono_known(me) k(x) where k.x = u) then
      raise exception 'forbidden: Tu ne peux inviter que des personnes croisées dans Party.' using errcode = '42501';
    end if;
    insert into private.prono_players (prono_id, user_id, via) values (p.id, u, 'invite') on conflict do nothing;
    added := added || u;
  end loop;
  perform private.prono_notify_new(p, added);
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_invite(uuid, uuid[]) from public, anon;
grant execute on function public.prono_invite(uuid, uuid[]) to authenticated;

create or replace function public.prono_set_link(id uuid, active boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.id = prono_set_link.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono gère son lien.' using errcode = '42501'; end if;
  if active then
    update private.pronos x set link_stopped_at = null,
      link_token = coalesce(x.link_token, replace(replace(rtrim(encode(extensions.gen_random_bytes(18), 'base64'), '='), '+', '-'), '/', '_'))
      where x.id = p.id returning * into p;
  else
    update private.pronos x set link_stopped_at = now() where x.id = p.id returning * into p;
  end if;
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_set_link(uuid, boolean) from public, anon;
grant execute on function public.prono_set_link(uuid, boolean) to authenticated;

-- Le lien : ce que voit la personne connectée avant de jouer, puis « Jouer » l'ajoute.
create or replace function public.prono_link_info(token text) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  select * into p from private.pronos x where x.link_token = prono_link_info.token and x.link_stopped_at is null and x.hidden_at is null;
  if p.id is null or private.prono_state(p) <> 'open' or private.blocked_either(me, p.created_by) then
    raise exception 'not_found: Ce lien ne marche plus : les pronos sont fermés ou le lien a été arrêté.' using errcode = 'PT404';
  end if;
  return jsonb_build_object('id', p.id, 'question', p.question, 'closes_at', p.closes_at, 'creator', private.prono_face(p.created_by),
    'joined', private.prono_can_play(p, me),
    'missing', case when not private.identity_complete(me) then 'profile'
                    when (select terms_enforced from private.moderation_settings where id = 1) and not private.terms_accepted(me) then 'terms' end);
end $$;
revoke all on function public.prono_link_info(text) from public, anon;
grant execute on function public.prono_link_info(text) to authenticated;

create or replace function public.prono_join(token text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.link_token = prono_join.token and x.link_stopped_at is null and x.hidden_at is null;
  if p.id is null or private.prono_state(p) <> 'open' or private.blocked_either(me, p.created_by) then
    raise exception 'not_found: Ce lien ne marche plus : les pronos sont fermés ou le lien a été arrêté.' using errcode = 'PT404';
  end if;
  if not private.prono_can_play(p, me) then
    insert into private.prono_players (prono_id, user_id, via) values (p.id, me, 'link') on conflict do nothing;
    perform private.prono_signal(p);
  end if;
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_join(text) from public, anon;
grant execute on function public.prono_join(text) to authenticated;

-- ───────────── Jouer ─────────────

-- answer : option_id | number | text | person_id. Modifiable jusqu'à la fin.
create or replace function public.prono_answer(id uuid, answer jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; opt uuid; num numeric; txt text; per uuid;
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.id = prono_answer.id;
  if p.id is null or not private.prono_can_play(p, me) then
    raise exception 'not_found: Ce prono n''existe plus ou ne t''est pas ouvert.' using errcode = 'PT404';
  end if;
  if private.prono_state(p) <> 'open' then raise exception 'closed: Les pronos sont fermés.' using errcode = '22023'; end if;
  if p.kind = 'choice' then
    opt := nullif(answer ->> 'option_id', '')::uuid;
    if not exists (select 1 from private.prono_options o where o.id = opt and o.prono_id = p.id) then
      raise exception 'invalid: Choisis une des réponses.' using errcode = '22023';
    end if;
  elsif p.kind = 'number' then
    begin num := (answer ->> 'number')::numeric; exception when others then num := null; end;
    if num is null or abs(num) > 1e9 then raise exception 'invalid: Écris un nombre.' using errcode = '22023'; end if;
  elsif p.kind = 'text' then
    txt := private.prono_text(answer ->> 'text', 'Ta réponse');
    if char_length(txt) > 80 then raise exception 'invalid: 80 caractères au plus.' using errcode = '22023'; end if;
  else
    per := nullif(answer ->> 'person_id', '')::uuid;
    if per is null or private.blocked_either(me, per) or not exists (select 1 from private.prono_people(p) u where u = per) then
      raise exception 'invalid: Choisis une personne du prono.' using errcode = '22023';
    end if;
  end if;
  insert into private.prono_answers (prono_id, user_id, option_id, number, answer_text, person_id)
  values (p.id, me, opt, num, txt, per)
  on conflict (prono_id, user_id) do update set option_id = excluded.option_id, number = excluded.number,
    answer_text = excluded.answer_text, person_id = excluded.person_id, hidden_at = null, updated_at = now();
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_answer(uuid, jsonb) from public, anon;
grant execute on function public.prono_answer(uuid, jsonb) to authenticated;

-- ───────────── Fin, résultat, annulation ─────────────

-- Fermer tout de suite (l'organisateur n'attend pas la date).
create or replace function public.prono_close_now(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  select * into p from private.pronos x where x.id = prono_close_now.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono le ferme.' using errcode = '42501'; end if;
  if private.prono_state(p) <> 'open' then raise exception 'invalid: Les pronos sont déjà fermés.' using errcode = '22023'; end if;
  update private.pronos x set closes_at = now(), due_notified_at = now(), updated_at = now() where x.id = p.id returning * into p;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_close_now(uuid) from public, anon;
grant execute on function public.prono_close_now(uuid) to authenticated;

-- body : option_id (choix) | number (nombre : le plus proche gagne) | person_id | winners [uuid] (réponse libre, ou
-- pour remplacer le calcul). Dévoile tout et prévient chaque joueur (gagnant ou non).
create or replace function public.prono_result(id uuid, body jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; opt uuid; num numeric; per uuid; wins uuid[]; best numeric; a private.prono_answers;
        label text;
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.id = prono_result.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono donne le résultat.' using errcode = '42501'; end if;
  if private.prono_state(p) <> 'closed' then raise exception 'invalid: Le résultat se donne une fois les pronos fermés.' using errcode = '22023'; end if;
  if p.kind = 'choice' then
    opt := nullif(body ->> 'option_id', '')::uuid;
    select o.label into label from private.prono_options o where o.id = opt and o.prono_id = p.id;
    if label is null then raise exception 'invalid: Touche la bonne réponse.' using errcode = '22023'; end if;
    select coalesce(array_agg(x.user_id), '{}') into wins from private.prono_answers x where x.prono_id = p.id and x.option_id = opt;
  elsif p.kind = 'number' then
    begin num := (body ->> 'number')::numeric; exception when others then num := null; end;
    if num is null then raise exception 'invalid: Écris le résultat.' using errcode = '22023'; end if;
    select min(abs(x.number - num)) into best from private.prono_answers x where x.prono_id = p.id;
    select coalesce(array_agg(x.user_id), '{}') into wins from private.prono_answers x where x.prono_id = p.id and abs(x.number - num) = best;
    label := trim(trailing '.' from trim(trailing '0' from num::text));
  elsif p.kind = 'person' then
    per := nullif(body ->> 'person_id', '')::uuid;
    if per is null or not exists (select 1 from private.prono_people(p) u where u = per) then
      raise exception 'invalid: Choisis la bonne personne.' using errcode = '22023';
    end if;
    select coalesce(array_agg(x.user_id), '{}') into wins from private.prono_answers x where x.prono_id = p.id and x.person_id = per;
    select pr.display_name into label from public.profiles pr where pr.id = per;
  end if;
  if jsonb_typeof(body -> 'winners') = 'array' then
    select coalesce(array_agg(distinct v::uuid), '{}') into wins from jsonb_array_elements_text(body -> 'winners') v
      where exists (select 1 from private.prono_answers x where x.prono_id = p.id and x.user_id = v::uuid);
  elsif p.kind = 'text' then
    raise exception 'invalid: Coche les bonnes réponses.' using errcode = '22023';
  end if;
  update private.prono_answers x set winner = x.user_id = any (wins) where x.prono_id = p.id;
  update private.pronos x set result_option = opt, result_number = num, result_person = per, result_at = now(), updated_at = now()
    where x.id = p.id returning * into p;
  for a in select * from private.prono_answers x where x.prono_id = p.id loop
    perform public.queue_notification(a.user_id, 'prono_result', null, '🔮 Résultat du prono · ' || private.prono_where(p),
      case when a.winner then 'Tu avais vu juste : +' || p.points || ' point' || case when p.points > 1 then 's' else '' end || ' · ' || p.question
           else coalesce('Réponse : ' || label || ' · ', '') || p.question end,
      'prono_result:' || p.id || ':' || a.user_id, jsonb_build_object('prono_id', p.id, 'url', '/?tab=events&prono=' || p.id));
  end loop;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_result(uuid, jsonb) from public, anon;
grant execute on function public.prono_result(uuid, jsonb) to authenticated;

-- Annuler (ou « Pas de résultat ») : aucun point ; les réponses restent cachées si elles ne l'étaient pas déjà.
create or replace function public.prono_cancel(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  select * into p from private.pronos x where x.id = prono_cancel.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono l''annule.' using errcode = '42501'; end if;
  if private.prono_state(p) not in ('open', 'closed') then raise exception 'invalid: Ce prono est déjà terminé.' using errcode = '22023'; end if;
  update private.prono_answers x set winner = false where x.prono_id = p.id;
  update private.pronos x set cancelled_at = now(), updated_at = now() where x.id = p.id returning * into p;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_cancel(uuid) from public, anon;
grant execute on function public.prono_cancel(uuid) to authenticated;

-- Supprimer un prono (organisateur) : tant que personne n'a joué, ou une fois terminé / annulé.
create or replace function public.prono_delete(id uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  select * into p from private.pronos x where x.id = prono_delete.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono le supprime.' using errcode = '42501'; end if;
  if private.prono_state(p) in ('open', 'closed') and exists (select 1 from private.prono_answers a where a.prono_id = p.id) then
    raise exception 'locked: Des personnes ont joué : annule le prono plutôt.' using errcode = '22023';
  end if;
  delete from private.pronos x where x.id = p.id;
  perform private.prono_signal(p);
end $$;
revoke all on function public.prono_delete(uuid) from public, anon;
grant execute on function public.prono_delete(uuid) to authenticated;

-- ───────────── Classement ─────────────

create or replace function public.prono_board(group_id uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); since timestamptz := (select r.reset_at from private.prono_board_resets r where r.group_id = prono_board.group_id);
begin
  if not private.is_account_active(me) or not private.in_group_now(prono_board.group_id, me) then
    raise exception 'forbidden: Réservé aux membres du groupe.' using errcode = '42501';
  end if;
  return jsonb_build_object('since', since, 'manage', private.manages_group(prono_board.group_id),
    'pronos', (select count(*) from private.pronos p where p.group_id = prono_board.group_id and p.result_at is not null
               and p.cancelled_at is null and p.hidden_at is null and (since is null or p.result_at > since)),
    'rows', coalesce((select jsonb_agg(jsonb_build_object('user', private.prono_face(r.user_id), 'points', r.pts, 'right', r.ok,
               'played', r.played) order by r.pts desc, r.ok desc, r.played) from (
      select a.user_id, sum(case when a.winner then p.points else 0 end) as pts, count(*) filter (where a.winner) as ok, count(*) as played
      from private.prono_answers a join private.pronos p on p.id = a.prono_id
      where p.group_id = prono_board.group_id and p.result_at is not null and p.cancelled_at is null and p.hidden_at is null
        and (since is null or p.result_at > since) and private.in_group_now(prono_board.group_id, a.user_id)
        and not private.blocked_either(me, a.user_id)
      group by a.user_id) r), '[]'::jsonb));
end $$;
revoke all on function public.prono_board(uuid) from public, anon;
grant execute on function public.prono_board(uuid) to authenticated;

create or replace function public.prono_board_reset(group_id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
begin
  if not private.manages_group(prono_board_reset.group_id) then
    raise exception 'forbidden: Réservé à qui gère le groupe.' using errcode = '42501';
  end if;
  insert into private.prono_board_resets (group_id, reset_at) values (prono_board_reset.group_id, now())
  on conflict on constraint prono_board_resets_pkey do update set reset_at = now();
  perform private.party_signal('pronos:' || prono_board_reset.group_id);
  return public.prono_board(prono_board_reset.group_id);
end $$;
revoke all on function public.prono_board_reset(uuid) from public, anon;
grant execute on function public.prono_board_reset(uuid) to authenticated;

-- ───────────── Rappel à l'organisateur (pg_cron) ─────────────

create or replace function private.prono_tick() returns void
language plpgsql security definer set search_path = '' as $$
declare p private.pronos;
begin
  for p in select * from private.pronos x where x.result_at is null and x.cancelled_at is null and x.due_notified_at is null
           and x.closes_at <= now() and x.hidden_at is null limit 500 loop
    update private.pronos x set due_notified_at = now() where x.id = p.id;
    if exists (select 1 from private.prono_answers a where a.prono_id = p.id) then
      insert into public.notifications (user_id, kind, event_id, title, body, data, dedupe_key)
      values (p.created_by, 'prono_due', null, '🔮 Les pronos sont fermés',
        'Donne le résultat : ' || p.question, jsonb_build_object('kind', 'prono_due', 'prono_id', p.id, 'url', '/?tab=events&prono=' || p.id), 'prono_due:' || p.id)
      on conflict (user_id, dedupe_key) where dedupe_key is not null do nothing;
    end if;
    perform private.prono_signal(p);
  end loop;
end $$;
revoke all on function private.prono_tick() from public, anon, authenticated;
select cron.unschedule('pronos-tick') where exists (select 1 from cron.job where jobname = 'pronos-tick');
select cron.schedule('pronos-tick', '*/5 * * * *', 'select private.prono_tick();');

-- ───────────── Modération : signaler, masquer ; notifications : interrupteur, blocage ─────────────

do $$ declare def text;
begin
  def := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position('''prono''' in def) = 0 then
    if position('''agenda_link''::text' in def) = 0 then raise exception 'content_reports : ancre agenda_link introuvable'; end if;
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(def, '''agenda_link''::text', '''agenda_link''::text, ''prono''::text, ''prono_answer''::text');
  end if;

  def := pg_get_functiondef('private.report_snapshot(text,text,uuid)'::regprocedure);
  if position('''prono''' in def) = 0 then
    if position($a$  elsif p_kind in ('profile', 'profile_photo') then$a$ in def) = 0 then raise exception 'report_snapshot : ancre profile introuvable'; end if;
    execute replace(def, $a$  elsif p_kind in ('profile', 'profile_photo') then$a$, $a$  elsif p_kind in ('prono', 'prono_answer') then
    return private.prono_report_snapshot(p_kind, uid, viewer);
  elsif p_kind in ('profile', 'profile_photo') then$a$);
  end if;

  -- Réponse signalée (cible « <prono>:<auteur> », pas un uuid) : traitée avant la conversion de target_id.
  def := pg_get_functiondef('private.moderation_hide(public.content_reports)'::regprocedure);
  if position('''prono''' in def) = 0 then
    if position($a$  uid := r.target_id::uuid;$a$ in def) = 0 or position($a$  elsif r.target_kind = 'profile' then$a$ in def) = 0 then
      raise exception 'moderation_hide : ancres introuvables';
    end if;
    def := replace(def, $a$  uid := r.target_id::uuid;$a$, $a$  if r.target_kind = 'prono_answer' then
    update private.prono_answers set hidden_at = now(), answer_text = null
      where prono_id = (r.snapshot ->> 'prono_id')::uuid and user_id = r.target_user;
    return '{}'::jsonb;
  end if;
  uid := r.target_id::uuid;$a$);
    execute replace(def, $a$  elsif r.target_kind = 'profile' then$a$, $a$  elsif r.target_kind = 'prono' then
    update private.pronos set hidden_at = coalesce(hidden_at, now()) where id = uid;
  elsif r.target_kind = 'profile' then$a$);
  end if;

  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position('''prono''' in def) = 0 then
    if position($a$when new.target_kind = 'bring_item' then 'un objet à amener'$a$ in def) = 0 then raise exception 'notify_new_report : ancre introuvable'; end if;
    execute replace(def, $a$when new.target_kind = 'bring_item' then 'un objet à amener'$a$,
      $a$when new.target_kind = 'bring_item' then 'un objet à amener'
                        when new.target_kind in ('prono', 'prono_answer') then 'un prono'$a$);
  end if;

  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''prono_new''' in def) = 0 then
    if position($a$    when 'group_added' then coalesce(prefs.group_added, true)$a$ in def) = 0 then raise exception 'web_push_allowed : ancre group_added introuvable'; end if;
    execute replace(def, $a$    when 'group_added' then coalesce(prefs.group_added, true)$a$, $a$    when 'group_added' then coalesce(prefs.group_added, true)
    when 'prono_new' then coalesce(prefs.pronos, true)
    when 'prono_result' then coalesce(prefs.pronos, true)
    when 'prono_due' then coalesce(prefs.pronos, true)$a$);
  end if;

  def := pg_get_functiondef('private.may_receive_push(uuid,text)'::regprocedure);
  if position('''prono_new''' in def) = 0 then
    if position('''group_added'',' in def) = 0 then raise exception 'may_receive_push : ancre group_added introuvable'; end if;
    execute replace(def, '''group_added'',', '''group_added'', ''prono_new'', ''prono_result'', ''prono_due'',');
  end if;

  def := pg_get_functiondef('private.drop_blocked_notification()'::regprocedure);
  if position('''prono_new''' in def) = 0 then
    if position('''group_added'')' in def) = 0 then raise exception 'drop_blocked_notification : ancre group_added introuvable'; end if;
    execute replace(def, '''group_added'')', '''group_added'', ''prono_new'', ''prono_result'')');
  end if;
end $$;

-- Copie gardée par le signalement : la question (prono) ou la réponse libre (prono_answer, cible = son auteur).
-- Lu seulement par qui joue au prono ; une réponse ne se signale qu'une fois dévoilée.
create or replace function private.prono_report_snapshot(p_kind text, uid uuid, viewer uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare p private.pronos;
begin
  if p_kind = 'prono' then
    select * into p from private.pronos where id = uid;
    if p.id is null or not private.prono_can_play(p, viewer) then return null; end if;
    return jsonb_build_object('owner', p.created_by, 'prono_id', p.id, 'at', p.created_at, 'place', 'Prono',
      'text', p.question || coalesce(E'\n' || (select string_agg('· ' || o.label, E'\n' order by o.position)
                                               from private.prono_options o where o.prono_id = p.id), ''));
  end if;
  return null;  -- prono_answer : signalé par public.prono_report_answer (cible « <prono>:<auteur> »)
end $$;
revoke all on function private.prono_report_snapshot(text, uuid, uuid) from public, anon, authenticated;

-- Signaler la réponse libre de quelqu'un (cible lisible : « <prono>:<auteur> », 73 caractères).
create or replace function public.prono_report_answer(id uuid, author uuid, reason text, comment text default null) returns uuid
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; a private.prono_answers; rid uuid;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if reason is null or reason not in ('harassment', 'shocking', 'spam', 'scam', 'other') then
    raise exception 'reason: choisis une raison' using errcode = '22023';
  end if;
  select * into p from private.pronos x where x.id = prono_report_answer.id;
  select * into a from private.prono_answers x where x.prono_id = prono_report_answer.id and x.user_id = author;
  if p.id is null or a.user_id is null or a.answer_text is null or not private.prono_can_play(p, me) or not private.prono_revealed(p) then
    raise exception 'not_found: ce contenu n''existe plus ou ne t''est pas visible' using errcode = 'PT404';
  end if;
  if author = me then raise exception 'self: tu ne peux pas signaler ton propre contenu' using errcode = '22023'; end if;
  if (select count(*) from public.content_reports where reporter_id = me and created_at > now() - interval '1 hour') >= 10 then
    raise exception 'rate_limited: tu as fait beaucoup de signalements, réessaie plus tard' using errcode = '54000';
  end if;
  select r.id into rid from public.content_reports r where r.reporter_id = me and r.target_kind = 'prono_answer'
    and r.target_id = p.id || ':' || author and r.status = 'open';
  if rid is not null then return rid; end if;
  insert into public.content_reports (reporter_id, target_kind, target_id, target_user, reason, comment, snapshot)
  values (me, 'prono_answer', p.id || ':' || author, author, reason, nullif(btrim(left(comment, 500)), ''),
          jsonb_build_object('text', a.answer_text, 'prono_id', p.id, 'place', 'Réponse à un prono · ' || p.question, 'at', a.updated_at))
  returning content_reports.id into rid;
  return rid;
end $$;
revoke all on function public.prono_report_answer(uuid, uuid, text, text) from public, anon;
grant execute on function public.prono_report_answer(uuid, uuid, text, text) to authenticated;

notify pgrst, 'reload schema';
