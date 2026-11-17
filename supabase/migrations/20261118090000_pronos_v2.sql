-- Pronos v2 (18.11.2026) : nouveaux types, patates, contestation, réactions, trophées, saison.
-- Revue de conformité « patates » du 18.11 (règles 🔴 1 à 8) : monnaie pour rire, GRATUITE et SANS AUCUNE VALEUR.
-- · Patates jamais achetées, vendues, échangées ni transférées : aucune fonction de don ou de transfert ; un sac par
--   personne ET par terrain (groupe « g:<uuid> » ou événement « e:<uuid> ») ; aucun lien avec les pièces de Zicou, le bar,
--   les billets ou le Pot commun. Sac de départ 100 ; chaque lundi 00:00 (heure de Suisse), un sac sous 100 remonte à 100
--   (calcul paresseux à la lecture, refill_week), au-dessus il ne bouge pas. Jamais négatif. 0 à 20 par prono.
-- · Partage du champ seulement (somme nulle, jamais de cote fixe, jamais de patates créées par le jardin) :
--   récolte_i = planté_i × champ / planté_gagnants, arrondi vers le bas, reste au plus fort reste. Tout est rendu si
--   personne n'a vu juste, si tous ont vu juste (« Unanimes ! »), si moins de 2 personnes ont planté, ou si le prono est
--   annulé. Patates « en attente » pendant 12 h de contestation, versées ensuite par pronos-tick.
-- · Contestation : un joueur (jamais l'organisateur) conteste avec une raison ; vote des joueurs 24 h ; majorité
--   « pas juste » ou égalité → prono annulé et tout rendu.
-- · Nouveaux types : yesno, overunder (ligne en demi-unité), when (heure la plus proche, « C'est arrivé ! »),
--   majority (la réponse la plus choisie gagne, tranché tout seul à la fin ; égalité = rendu), award (Trophée de la
--   soirée : catégorie POSITIVE de la liste fermée, au moins 3 votants, jamais de patates, on peut se retirer).
-- · Réactions, modèles prêts (jamais d'alcool), saison mensuelle (récolte nette), historique de SON sac seulement.
-- · Filtre étendu (sites de jeux d'argent, vendre / acheter des patates) ; motif de signalement « money ».
-- · Notifications prono_soon, prono_result (avec la récolte), prono_contest : interrupteur pronos, blocages respectés.
-- Les fonctions propres aux Pronos sont recréées (signatures et clés gardées) ; les fonctions partagées s'ÉTENDENT par
-- ancre. Tout par fonctions (schéma private, aucun accès direct). Purement additive et rejouable.

-- ───────────── Colonnes ─────────────

alter table private.pronos drop constraint if exists pronos_kind_check;
alter table private.pronos add constraint pronos_kind_check
  check (kind in ('choice', 'number', 'text', 'person', 'yesno', 'overunder', 'when', 'majority', 'award'));
alter table private.pronos add column if not exists line numeric;
alter table private.pronos add column if not exists not_over boolean not null default false;
alter table private.pronos add column if not exists rules text check (rules is null or char_length(rules) between 1 and 200);
alter table private.pronos add column if not exists template text check (template is null or template ~ '^[a-z0-9_]{1,40}$');
alter table private.pronos add column if not exists patates boolean not null default false;
alter table private.pronos add column if not exists award text;
alter table private.pronos add column if not exists result_time timestamptz;
alter table private.pronos add column if not exists settled_at timestamptz;
alter table private.pronos add column if not exists contest_until timestamptz;
alter table private.pronos add column if not exists vote_until timestamptz;
alter table private.pronos add column if not exists vote_done_at timestamptz;
alter table private.pronos add column if not exists soon_notified_at timestamptz;
alter table private.pronos add column if not exists cancel_reason text
  check (cancel_reason is null or cancel_reason in ('organizer', 'tie', 'few', 'contest', 'no_result', 'hidden'));

alter table private.prono_answers add column if not exists stake int not null default 0 check (stake between 0 and 20);
alter table private.prono_answers add column if not exists harvest int check (harvest is null or harvest >= 0);
alter table private.prono_answers add column if not exists answer_at timestamptz;

-- Pronos d'avant (sans patates) : déjà « réglés ».
update private.pronos set settled_at = coalesce(cancelled_at, result_at)
  where settled_at is null and (result_at is not null or cancelled_at is not null) and contest_until is null;

create index if not exists pronos_settle on private.pronos (contest_until) where result_at is not null and settled_at is null;
create index if not exists pronos_soon on private.pronos (closes_at)
  where result_at is null and cancelled_at is null and soon_notified_at is null;

-- ───────────── Tables ─────────────

-- Trophées : liste FERMÉE de catégories positives (jamais « le plus bourré », jamais une moquerie).
create table if not exists private.prono_award_categories (
  id text primary key,
  emoji text not null,
  label text not null,
  position int not null
);
insert into private.prono_award_categories (id, emoji, label, position) values
  ('ambiance', '🎉', 'Ambianceur·euse', 1),
  ('piste', '💃', 'Roi / Reine de la piste', 2),
  ('fou_rire', '😂', 'Fou rire', 3),
  ('look', '👗', 'Meilleur look', 4),
  ('chef', '🍳', 'Chef·fe de la soirée', 5),
  ('voix', '🎤', 'Voix d''or', 6),
  ('accueil', '🤝', 'Le / la plus accueillant·e', 7),
  ('danse', '🕺', 'Danse de la soirée', 8)
on conflict (id) do update set emoji = excluded.emoji, label = excluded.label, position = excluded.position;

-- Un sac par personne et par terrain. Jamais négatif ; aucune fonction de transfert.
create table if not exists private.prono_bags (
  terrain text not null check (terrain ~ '^[ge]:[0-9a-f-]{36}$'),
  user_id uuid not null references public.profiles (id) on delete cascade,
  group_id uuid references public.member_groups (id) on delete cascade,
  event_id uuid references public.events (id) on delete cascade,
  balance int not null default 100 check (balance >= 0),
  refill_week date not null,
  primary key (terrain, user_id),
  check ((group_id is not null) <> (event_id is not null))
);
create index if not exists prono_bags_user on private.prono_bags (user_id);

create table if not exists private.prono_bag_moves (
  id bigint generated always as identity primary key,
  terrain text not null,
  user_id uuid not null references public.profiles (id) on delete cascade,
  group_id uuid references public.member_groups (id) on delete cascade,
  event_id uuid references public.events (id) on delete cascade,
  prono_id uuid references private.pronos (id) on delete set null,
  delta int not null,
  reason text not null check (reason in ('start', 'refill', 'plant', 'unplant', 'refund', 'harvest')),
  at timestamptz not null default now()
);
create index if not exists prono_bag_moves_user on private.prono_bag_moves (user_id, terrain, at desc);
create index if not exists prono_bag_moves_prono on private.prono_bag_moves (prono_id) where prono_id is not null;

create table if not exists private.prono_contests (
  prono_id uuid not null references private.pronos (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  reason text not null check (char_length(reason) between 1 and 200),
  at timestamptz not null default now(),
  primary key (prono_id, user_id)
);

create table if not exists private.prono_contest_votes (
  prono_id uuid not null references private.pronos (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  fair boolean not null,
  at timestamptz not null default now(),
  primary key (prono_id, user_id)
);

create table if not exists private.prono_reactions (
  prono_id uuid not null references private.pronos (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  emoji text not null check (emoji in ('😂', '🔥', '🥔', '👀', '🤯', '👏')),
  at timestamptz not null default now(),
  primary key (prono_id, user_id, emoji)
);

create table if not exists private.prono_optouts (
  prono_id uuid not null references private.pronos (id) on delete cascade,
  user_id uuid not null references public.profiles (id) on delete cascade,
  at timestamptz not null default now(),
  primary key (prono_id, user_id)
);

alter table private.prono_award_categories enable row level security;
alter table private.prono_bags enable row level security;
alter table private.prono_bag_moves enable row level security;
alter table private.prono_contests enable row level security;
alter table private.prono_contest_votes enable row level security;
alter table private.prono_reactions enable row level security;
alter table private.prono_optouts enable row level security;
revoke all on private.prono_award_categories, private.prono_bags, private.prono_bag_moves, private.prono_contests,
  private.prono_contest_votes, private.prono_reactions, private.prono_optouts from public, anon, authenticated;

-- Interrupteur des patates EN BASE (le web parle à la base directement) : éteint par défaut (prod), allumé sur TEST
-- à la main. Éteint : aucune patate plantée, aucun sac montré ; les pronos restent pour l'honneur (points).
create table if not exists private.prono_settings (
  id int primary key default 1 check (id = 1),
  patates_enabled boolean not null default false
);
insert into private.prono_settings (id) values (1) on conflict (id) do nothing;
alter table private.prono_settings enable row level security;
revoke all on private.prono_settings from public, anon, authenticated;

create or replace function private.patates_on() returns boolean
language sql stable security definer set search_path = '' as $$
  select coalesce((select s.patates_enabled from private.prono_settings s where s.id = 1), false);
$$;
revoke all on function private.patates_on() from public, anon, authenticated;

-- ───────────── Filtre : pour rire ─────────────

-- Ni argent, ni boisson, ni site de jeux d'argent, ni vente / achat de patates. Accents et majuscules ignorés.
create or replace function private.prono_text(t text, what text) returns text
language plpgsql stable security definer set search_path = '' as $$
declare s text := btrim(regexp_replace(coalesce(t, ''), '\s+', ' ', 'g')); l text;
begin
  if s = '' then raise exception 'invalid: % vide.', what using errcode = '22023'; end if;
  l := translate(lower(s), 'àâäáãåçéèêëíìîïñóòôöõúùûüýÿœ', 'aaaaaaceeeeiiiinooooouuuuyyo');
  if l ~ '[€$£💰💵💶💷🎰]' or l ~ '\d\s*\.-' or l ~ '\d\s*(chf|eur|euros?|fr|francs?|balles?|cts?)\M'
     or l ~ '\m(chf|euros?|francs?|balles|thunes?|fric|pognon|argent|mise|mises|miser|misez|pari|parie|parier|pariez|parions|paries|cagnotte|pot commun|jackpot|twint|revolut|paypal|tournee|tournees|shots?|alcool|bieres?|vins?|vodka|whisky|tequila|rhum|gin|bourre|bourres|bourree|bourrees|cuite|ivre|ivres|soulard)\M' then
    raise exception 'content_refused: Les pronos se jouent pour rire : pas d''argent ni de boisson.' using errcode = '23514';
  end if;
  if l ~ '\m(betclic|unibet|winamax|swisslos|loterie romande|jouez ?sport|pmu|bwin|betway|pokerstars|parions ?sport|zebet|bookmakers?|bookmakeurs?|casinos?|paris sportifs?)\M' then
    raise exception 'content_refused: Pas de jeux d''argent ni de sites de jeux dans les pronos.' using errcode = '23514';
  end if;
  if l ~ '\m(vend|vends|vendre|vendu|vendue|vendus|vente|achat|achete|achetes|acheter|achetez|rachete|racheter|rachetes|troque|troquer|echange|echanger|echanges)\M.{0,40}\mpatates?\M'
     or l ~ '\mpatates?\M.{0,20}\m(a vendre|a acheter|contre de l|contre des sous)\M' then
    raise exception 'content_refused: Les patates ne se vendent pas, ne s''achètent pas et ne s''échangent pas.' using errcode = '23514';
  end if;
  return private.moderate_text(s, 'name');
end $$;
revoke all on function private.prono_text(text, text) from public, anon, authenticated;

-- ───────────── Sac (patates) ─────────────

create or replace function private.prono_terrain(p private.pronos) returns text
language sql immutable set search_path = '' as $$
  select case when p.group_id is not null then 'g:' || p.group_id when p.event_id is not null then 'e:' || p.event_id end;
$$;
revoke all on function private.prono_terrain(private.pronos) from public, anon, authenticated;

-- Lundi de la semaine en cours, heure de Suisse ; prochaine remontée : lundi suivant 00:00 (Suisse).
create or replace function private.prono_monday() returns date
language sql stable set search_path = '' as $$
  select date_trunc('week', now() at time zone 'Europe/Zurich')::date;
$$;
revoke all on function private.prono_monday() from public, anon, authenticated;

create or replace function private.prono_refill_at() returns timestamptz
language sql stable set search_path = '' as $$
  select ((private.prono_monday() + 7)::timestamp at time zone 'Europe/Zurich');
$$;
revoke all on function private.prono_refill_at() from public, anon, authenticated;

-- Solde vu (sans écrire) : 100 si pas encore de sac, 100 si la remontée du lundi est due, sinon le solde.
create or replace function private.prono_bag_balance(t text, uid uuid) returns int
language sql stable security definer set search_path = '' as $$
  select coalesce((select case when b.refill_week < private.prono_monday() and b.balance < 100 then 100 else b.balance end
                   from private.prono_bags b where b.terrain = t and b.user_id = uid), 100);
$$;
revoke all on function private.prono_bag_balance(text, uuid) from public, anon, authenticated;

-- Crée le sac (100, « start ») ou applique la remontée paresseuse du lundi ; verrouille la ligne ; rend le solde.
create or replace function private.prono_bag_touch(t text, uid uuid) returns int
language plpgsql security definer set search_path = '' as $$
declare b private.prono_bags; wk date := private.prono_monday(); g uuid; e uuid;
begin
  if t is null or t !~ '^[ge]:' or uid is null then raise exception 'invalid: Pas de sac ici.' using errcode = '22023'; end if;
  if t like 'g:%' then g := substr(t, 3)::uuid; else e := substr(t, 3)::uuid; end if;
  insert into private.prono_bags (terrain, user_id, group_id, event_id, balance, refill_week)
  values (t, uid, g, e, 100, wk) on conflict (terrain, user_id) do nothing returning * into b;
  if b.user_id is not null then
    insert into private.prono_bag_moves (terrain, user_id, group_id, event_id, delta, reason) values (t, uid, g, e, 100, 'start');
    return 100;
  end if;
  select * into b from private.prono_bags x where x.terrain = t and x.user_id = uid for update;
  if b.refill_week < wk then
    if b.balance < 100 then
      insert into private.prono_bag_moves (terrain, user_id, group_id, event_id, delta, reason)
      values (t, uid, g, e, 100 - b.balance, 'refill');
      update private.prono_bags x set balance = 100, refill_week = wk where x.terrain = t and x.user_id = uid returning * into b;
    else
      update private.prono_bags x set refill_week = wk where x.terrain = t and x.user_id = uid returning * into b;
    end if;
  end if;
  return b.balance;
end $$;
revoke all on function private.prono_bag_touch(text, uuid) from public, anon, authenticated;

-- Seul chemin qui change un sac : planter, reprendre, rendre, récolter (jamais d'une personne à une autre).
create or replace function private.prono_bag_add(t text, uid uuid, pid uuid, delta int, why text) returns int
language plpgsql security definer set search_path = '' as $$
declare nb int;
begin
  perform private.prono_bag_touch(t, uid);
  update private.prono_bags x set balance = x.balance + delta where x.terrain = t and x.user_id = uid returning x.balance into nb;
  insert into private.prono_bag_moves (terrain, user_id, group_id, event_id, prono_id, delta, reason)
  values (t, uid, case when t like 'g:%' then substr(t, 3)::uuid end, case when t like 'e:%' then substr(t, 3)::uuid end,
          pid, delta, why);
  return nb;
end $$;
revoke all on function private.prono_bag_add(text, uuid, uuid, int, text) from public, anon, authenticated;

-- Partage du champ (somme nulle) : back = ce que chaque planteur reçoit ; refund = tout est rendu.
create or replace function private.prono_split(p private.pronos)
returns table (user_id uuid, stake int, back int, refund boolean)
language plpgsql stable security definer set search_path = '' as $$
declare f int; n int; g int; rem int;
begin
  select coalesce(sum(a.stake), 0), count(*), coalesce(sum(a.stake) filter (where a.winner), 0) into f, n, g
    from private.prono_answers a where a.prono_id = p.id and a.stake > 0;
  if n = 0 then return; end if;
  if p.cancelled_at is not null or n < 2 or g = 0 or g = f then
    return query select a.user_id, a.stake, a.stake, true from private.prono_answers a where a.prono_id = p.id and a.stake > 0;
    return;
  end if;
  select f - coalesce(sum((a.stake * f) / g), 0) into rem
    from private.prono_answers a where a.prono_id = p.id and a.stake > 0 and a.winner;
  return query
    select w.user_id, w.stake, (w.base + case when w.rn <= rem then 1 else 0 end)::int, false from (
      select a.user_id, a.stake, (a.stake * f) / g as base,
             row_number() over (order by (a.stake * f) % g desc, a.answered_at, a.user_id) as rn
      from private.prono_answers a where a.prono_id = p.id and a.stake > 0 and a.winner) w
    union all
    select a.user_id, a.stake, 0, false from private.prono_answers a where a.prono_id = p.id and a.stake > 0 and not a.winner;
end $$;
revoke all on function private.prono_split(private.pronos) from public, anon, authenticated;

-- Versement (une seule fois) : récolte ou patates rendues, harvest noté sur chaque réponse.
create or replace function private.prono_settle(pid uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare p private.pronos; s record; t text;
begin
  select * into p from private.pronos x where x.id = pid for update;
  if p.id is null or p.settled_at is not null then return; end if;
  t := private.prono_terrain(p);
  if p.patates and t is not null then
    for s in select * from private.prono_split(p) loop
      if s.back > 0 then
        perform private.prono_bag_add(t, s.user_id, p.id, s.back, case when s.refund then 'refund' else 'harvest' end);
      end if;
      update private.prono_answers x set harvest = s.back where x.prono_id = p.id and x.user_id = s.user_id;
    end loop;
    update private.prono_answers x set harvest = 0 where x.prono_id = p.id and x.stake = 0;
  end if;
  update private.pronos x set settled_at = now(), updated_at = now() where x.id = p.id returning * into p;
  perform private.prono_signal(p);
end $$;
revoke all on function private.prono_settle(uuid) from public, anon, authenticated;

-- ───────────── Notifications du résultat ─────────────

-- « 🔮 Tu l'avais vu ! +18 🥔 » ; « La réponse était … » (rien après une perte, jamais culpabilisant).
create or replace function private.prono_notify_result(pid uuid, label text) returns void
language plpgsql security definer set search_path = '' as $$
declare p private.pronos; r record; body text; pts text; names text; cat private.prono_award_categories; laur uuid[];
        data jsonb;
begin
  select * into p from private.pronos x where x.id = pid;
  data := jsonb_build_object('prono_id', p.id, 'url', '/?tab=events&prono=' || p.id);
  if p.kind = 'award' then
    select * into cat from private.prono_award_categories c where c.id = p.award;
    select array_agg(l.person_id) into laur from private.prono_laureates(p) l;
    select string_agg(pr.display_name, ', ' order by pr.display_name) into names from public.profiles pr where pr.id = any (laur);
    for r in select distinct u from (select a.user_id as u from private.prono_answers a where a.prono_id = p.id
                                     union select unnest(laur)) z loop
      perform public.queue_notification(r.u, 'prono_result', null, '🏆 Trophée de la soirée · ' || private.prono_where(p),
        case when r.u = any (laur) then 'C''est toi : ' || coalesce(cat.emoji || ' ' || cat.label, 'le trophée') || ' !'
             else coalesce(cat.emoji || ' ' || cat.label || ' : ', '') || coalesce(names, '') end,
        'prono_result:' || p.id || ':' || r.u, data);
    end loop;
    return;
  end if;
  pts := '+' || p.points || ' point' || case when p.points > 1 then 's' else '' end;
  for r in select a.user_id, a.winner, a.stake, z.back, coalesce(z.refund, false) as refund
           from private.prono_answers a left join private.prono_split(p) z on z.user_id = a.user_id
           where a.prono_id = p.id loop
    if r.winner then
      if p.patates and r.stake > 0 then
        body := '🔮 Tu l''avais vu ! ' || case when r.refund then 'Tes ' || r.stake || ' 🥔 sont rendues' else '+' || r.back || ' 🥔' end
                || ' · ' || pts || ' · ' || p.question;
      else
        body := 'Tu avais vu juste : ' || pts || ' · ' || p.question;
      end if;
    else
      body := coalesce('La réponse était ' || label || ' · ', '')
              || case when p.patates and r.stake > 0 and r.refund then 'tes ' || r.stake || ' 🥔 sont rendues · ' else '' end
              || p.question;
    end if;
    perform public.queue_notification(r.user_id, 'prono_result', null, '🔮 Résultat du prono · ' || private.prono_where(p),
      body, 'prono_result:' || p.id || ':' || r.user_id, data);
  end loop;
end $$;
revoke all on function private.prono_notify_result(uuid, text) from public, anon, authenticated;

-- Trophée : la ou les personnes les plus votées (égalité : toutes).
create or replace function private.prono_laureates(p private.pronos) returns table (person_id uuid, votes bigint)
language sql stable security definer set search_path = '' as $$
  with t as (select a.person_id, count(*) as votes from private.prono_answers a
             where a.prono_id = p.id and a.person_id is not null group by a.person_id)
  select t.person_id, t.votes from t where t.votes = (select max(votes) from t);
$$;
revoke all on function private.prono_laureates(private.pronos) from public, anon, authenticated;

-- ───────────── Résolution automatique (majority, award), fin de contestation ─────────────

create or replace function private.prono_auto_result(pid uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare p private.pronos; top uuid; topn int; ties int; voters int; lab text; r record;
begin
  select * into p from private.pronos x where x.id = pid for update;
  if p.id is null or p.kind not in ('majority', 'award') or p.result_at is not null or p.cancelled_at is not null
     or p.closes_at > now() then return; end if;
  if p.kind = 'majority' then
    select count(*) into voters from private.prono_answers a where a.prono_id = p.id and a.option_id is not null;
    select a.option_id, count(*) into top, topn from private.prono_answers a where a.prono_id = p.id and a.option_id is not null
      group by a.option_id order by count(*) desc limit 1;
    select count(*) into ties from (select a.option_id from private.prono_answers a where a.prono_id = p.id and a.option_id is not null
      group by a.option_id having count(*) = topn) z;
    if voters = 0 or ties > 1 then
      update private.prono_answers x set winner = false where x.prono_id = p.id;
      update private.pronos x set cancelled_at = now(), cancel_reason = case when voters = 0 then 'few' else 'tie' end,
        updated_at = now() where x.id = p.id returning * into p;
      if voters > 0 then
        for r in select a.user_id, a.stake from private.prono_answers a where a.prono_id = p.id loop
          perform public.queue_notification(r.user_id, 'prono_result', null, '🔮 Résultat du prono · ' || private.prono_where(p),
            'Égalité dans la bande ! ' || case when p.patates and r.stake > 0 then 'Tes ' || r.stake || ' 🥔 sont rendues · ' else '' end
            || p.question, 'prono_result:' || p.id || ':' || r.user_id,
            jsonb_build_object('prono_id', p.id, 'url', '/?tab=events&prono=' || p.id));
        end loop;
      end if;
      perform private.prono_settle(p.id);
      perform private.prono_signal(p);
      return;
    end if;
    update private.prono_answers x set winner = (x.option_id = top) where x.prono_id = p.id;
    update private.pronos x set result_option = top, result_at = now(), updated_at = now() where x.id = p.id returning * into p;
    select o.label into lab from private.prono_options o where o.id = top;
  else
    select count(*) into voters from private.prono_answers a where a.prono_id = p.id and a.person_id is not null;
    if voters < 3 then
      update private.pronos x set cancelled_at = now(), cancel_reason = 'few', updated_at = now() where x.id = p.id returning * into p;
      perform private.prono_settle(p.id);
      perform private.prono_signal(p);
      return;
    end if;
    select l.person_id into top from private.prono_laureates(p) l join public.profiles pr on pr.id = l.person_id
      order by pr.display_name limit 1;
    update private.prono_answers x set winner = false where x.prono_id = p.id;
    update private.pronos x set result_person = top, result_at = now(), updated_at = now() where x.id = p.id returning * into p;
  end if;
  perform private.prono_settle(p.id);  -- tranché par la bande : pas de contestation
  perform private.prono_notify_result(p.id, lab);
  perform private.prono_signal(p);
end $$;
revoke all on function private.prono_auto_result(uuid) from public, anon, authenticated;

-- Fin du délai de contestation ou du vote : majorité « pas juste » ou égalité → annulé, tout rendu ; sinon versement.
create or replace function private.prono_finish(pid uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare p private.pronos; f int; u int; eligible int;
begin
  select * into p from private.pronos x where x.id = pid for update;
  if p.id is null then return; end if;
  if p.cancelled_at is not null then perform private.prono_settle(p.id); return; end if;
  if p.result_at is null then return; end if;
  if p.vote_until is not null and p.vote_done_at is null then
    select count(*) filter (where v.fair), count(*) filter (where not v.fair) into f, u
      from private.prono_contest_votes v join private.prono_answers a on a.prono_id = v.prono_id and a.user_id = v.user_id
      where v.prono_id = p.id and v.user_id <> p.created_by;
    select count(*) into eligible from private.prono_answers a where a.prono_id = p.id and a.user_id <> p.created_by;
    if p.vote_until > now() and f + u < eligible then return; end if;
    if u >= f then
      update private.prono_answers x set winner = false where x.prono_id = p.id;
      update private.pronos x set vote_done_at = now(), cancelled_at = now(), cancel_reason = 'contest', updated_at = now()
        where x.id = p.id returning * into p;
    else
      update private.pronos x set vote_done_at = now(), updated_at = now() where x.id = p.id returning * into p;
    end if;
    perform private.prono_settle(p.id);
    perform private.prono_signal(p);
    return;
  end if;
  if p.vote_until is null and p.contest_until is not null and p.contest_until <= now() then
    perform private.prono_settle(p.id);
  end if;
end $$;
revoke all on function private.prono_finish(uuid) from public, anon, authenticated;

-- ───────────── Lecture ─────────────

create or replace function private.prono_json(p private.pronos, me uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare st text := private.prono_state(p); rev boolean := private.prono_revealed(p); mine boolean := p.created_by = me;
        locked boolean := exists (select 1 from private.prono_answers a where a.prono_id = p.id);
        a private.prono_answers; cat private.prono_award_categories; plays boolean := private.prono_can_play(p, me);
        auto boolean := p.kind in ('majority', 'award'); vote_open boolean; has_opts boolean;
        done boolean := p.result_at is not null and p.cancelled_at is null;
begin
  select * into a from private.prono_answers x where x.prono_id = p.id and x.user_id = me;
  select * into cat from private.prono_award_categories c where c.id = p.award;
  vote_open := p.vote_until is not null and p.vote_done_at is null and p.vote_until > now() and p.cancelled_at is null;
  has_opts := p.kind in ('choice', 'yesno', 'overunder', 'majority');
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
    'candidates', case when p.kind in ('person', 'award') then coalesce((select jsonb_agg(private.prono_face(u.u) order by pr.display_name)
        from private.prono_people(p) u(u) join public.profiles pr on pr.id = u.u
        where not private.blocked_either(me, u.u)
          and (p.kind <> 'award' or (u.u <> me and not exists (select 1 from private.prono_optouts o where o.prono_id = p.id and o.user_id = u.u)))),
        '[]'::jsonb) end,
    'my_answer', case when a.user_id is not null then jsonb_build_object('option_id', a.option_id, 'number', a.number,
        'text', a.answer_text, 'person_id', a.person_id, 'winner', a.winner, 'stake', a.stake, 'answer_at', a.answer_at,
        'harvest', a.harvest) end,
    'answered', coalesce((select jsonb_agg(private.prono_face(x.user_id) order by x.answered_at)
        from private.prono_answers x where x.prono_id = p.id and not private.blocked_either(me, x.user_id)), '[]'::jsonb),
    'players', (select count(*) from private.prono_people(p)),
    'answers', case when rev then coalesce((select jsonb_agg(jsonb_build_object('user', private.prono_face(x.user_id),
        'option_id', x.option_id, 'number', x.number, 'text', case when x.hidden_at is null then x.answer_text end,
        'hidden', x.hidden_at is not null,
        'person', case when x.person_id is not null and (p.kind <> 'award' or x.user_id = me) then private.prono_face(x.person_id) end,
        'winner', x.winner, 'stake', x.stake, 'harvest', x.harvest, 'answer_at', x.answer_at)
        order by x.winner desc, x.answered_at)
      from private.prono_answers x where x.prono_id = p.id and not private.blocked_either(me, x.user_id)), '[]'::jsonb) end,
    'result', case when p.result_at is not null then jsonb_build_object('option_id', p.result_option, 'number', p.result_number,
        'person', case when p.result_person is not null then private.prono_face(p.result_person) end, 'at', p.result_at,
        'time', p.result_time, 'by_player', p.kind not in ('majority', 'award')
           and exists (select 1 from private.prono_answers x where x.prono_id = p.id and x.user_id = p.created_by),
        'people', case when p.kind = 'award' then coalesce((select jsonb_agg(private.prono_face(l.person_id) || jsonb_build_object('votes', l.votes))
           from private.prono_laureates(p) l where not private.blocked_either(me, l.person_id)), '[]'::jsonb) end) end,
    'winners', case when p.result_at is not null then coalesce((select jsonb_agg(private.prono_face(x.user_id) order by x.answered_at)
        from private.prono_answers x where x.prono_id = p.id and x.winner and not private.blocked_either(me, x.user_id)), '[]'::jsonb) end,
    'can_answer', st = 'open' and plays,
    'can_edit', mine and st = 'open' and not locked,
    'can_move_end', mine and st in ('open', 'closed'),
    'can_result', mine and not auto and st = 'closed' and (p.kind <> 'text' or rev),
    'can_cancel', mine and st in ('open', 'closed'),
    'link', case when mine then jsonb_build_object('token', case when p.link_stopped_at is null then p.link_token end,
        'path', case when p.link_token is not null and p.link_stopped_at is null then '/prono/' || p.link_token end) end)
  || jsonb_build_object(
    'line', p.line, 'not_over', p.not_over, 'rules', p.rules, 'template', p.template, 'patates', p.patates,
    'award', p.award, 'award_emoji', cat.emoji, 'award_label', cat.label,
    'terrain', case when p.group_id is not null then jsonb_build_object('kind', 'group', 'id', p.group_id)
                    when p.event_id is not null then jsonb_build_object('kind', 'event', 'id', p.event_id) end,
    'field', case when p.patates then jsonb_build_object(
        'total', (select coalesce(sum(x.stake), 0) from private.prono_answers x where x.prono_id = p.id),
        'planters', (select count(*) from private.prono_answers x where x.prono_id = p.id and x.stake > 0),
        'by_option', case when rev and has_opts then coalesce((select jsonb_agg(jsonb_build_object('option_id', o.id,
            'total', (select coalesce(sum(x.stake), 0) from private.prono_answers x where x.option_id = o.id)) order by o.position)
          from private.prono_options o where o.prono_id = p.id), '[]'::jsonb) end) end,
    'bag', case when p.patates and plays and private.prono_terrain(p) is not null then jsonb_build_object(
        'balance', private.prono_bag_balance(private.prono_terrain(p), me), 'refill_at', private.prono_refill_at(), 'max_stake', 20) end,
    'settled', p.settled_at is not null,
    'cancel_reason', p.cancel_reason,
    'contest', case when p.result_at is not null and not auto then jsonb_build_object(
        'until', p.contest_until,
        'open', p.cancelled_at is null and p.vote_done_at is null and p.contest_until > now(),
        'contested', p.vote_until is not null,
        'vote_until', p.vote_until,
        'vote_open', vote_open,
        'fair', (select count(*) from private.prono_contest_votes v where v.prono_id = p.id and v.fair),
        'unfair', (select count(*) from private.prono_contest_votes v where v.prono_id = p.id and not v.fair),
        'my_vote', (select v.fair from private.prono_contest_votes v where v.prono_id = p.id and v.user_id = me),
        'can_contest', a.user_id is not null and not mine and p.cancelled_at is null and p.vote_done_at is null
          and p.contest_until > now() and not exists (select 1 from private.prono_contests c where c.prono_id = p.id and c.user_id = me),
        'can_vote', a.user_id is not null and not mine and vote_open,
        'reasons', coalesce((select jsonb_agg(jsonb_build_object('user', private.prono_face(c.user_id), 'reason', c.reason, 'at', c.at)
            order by c.at) from private.prono_contests c where c.prono_id = p.id and not private.blocked_either(me, c.user_id)), '[]'::jsonb)) end,
    'rarity', case when done and p.kind <> 'award' then jsonb_build_object(
        'right', (select count(*) from private.prono_answers x where x.prono_id = p.id and x.winner),
        'of', (select count(*) from private.prono_answers x where x.prono_id = p.id)) end,
    'unanimous', done and p.kind <> 'award' and locked
        and not exists (select 1 from private.prono_answers x where x.prono_id = p.id and not x.winner),
    'reactions', coalesce((select jsonb_agg(jsonb_build_object('emoji', r.emoji, 'count', r.n, 'mine', r.mine) order by r.n desc, r.emoji)
        from (select x.emoji, count(*) as n, bool_or(x.user_id = me) as mine from private.prono_reactions x
              where x.prono_id = p.id and not private.blocked_either(me, x.user_id) group by x.emoji) r), '[]'::jsonb),
    'optout', case when p.kind = 'award' then exists (select 1 from private.prono_optouts o where o.prono_id = p.id and o.user_id = me) end,
    'can_happen', p.kind = 'when' and mine and st in ('open', 'closed'),
    'patates_on', private.patates_on());
end $$;
revoke all on function private.prono_json(private.pronos, uuid) from public, anon, authenticated;

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
      ) || jsonb_build_object(
        'patates', p.patates,
        'field_total', case when p.patates then (select coalesce(sum(x.stake), 0) from private.prono_answers x where x.prono_id = p.id) end,
        'my_stake', (select x.stake from private.prono_answers x where x.prono_id = p.id and x.user_id = me),
        'my_harvest', (select x.harvest from private.prono_answers x where x.prono_id = p.id and x.user_id = me),
        'template', p.template, 'award', p.award,
        'award_emoji', (select c.emoji from private.prono_award_categories c where c.id = p.award),
        'award_label', (select c.label from private.prono_award_categories c where c.id = p.award),
        'line', p.line, 'settled', p.settled_at is not null, 'cancel_reason', p.cancel_reason,
        'closes_soon', private.prono_state(p) = 'open' and p.closes_at <= now() + interval '1 hour',
        'cover', (select jsonb_build_object('color', g.color, 'emoji', g.emoji, 'photo', g.photo_path)
                  from public.member_groups g where g.id = p.group_id),
        'patates_on', private.patates_on()
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

-- ───────────── Création, modification ─────────────

-- Ligne « Plus / Moins » : demi-unité (7,5), jamais d'égalité possible.
create or replace function private.prono_line_label(l numeric) returns text
language sql immutable set search_path = '' as $$
  select replace(trim(trailing '.' from trim(trailing '0' from l::text)), '.', ',');
$$;
revoke all on function private.prono_line_label(numeric) from public, anon, authenticated;

-- body : question, kind, options [texte], points, closes_at, reveal, group_id, event_id, people [uuid], link (bool),
-- et (v2) line, not_over, rules, template, award, patates.
create or replace function public.prono_create(body jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; k text := body ->> 'kind'; q text; ends timestamptz; g uuid; e uuid;
        opts text[] := '{}'; o text; i int := 0; ppl uuid[] := '{}'; u uuid; pts int := coalesce((body ->> 'points')::int, 3);
        rv text := coalesce(body ->> 'reveal', 'close'); notify uuid[]; v_line numeric; v_rules text; v_award text;
        v_tpl text := nullif(body ->> 'template', ''); v_pat boolean := coalesce((body ->> 'patates')::boolean, false);
        v_not_over boolean := coalesce((body ->> 'not_over')::boolean, false);
begin
  perform private.prono_check_author(me);
  if (select count(*) from private.pronos x where x.created_by = me and x.created_at > now() - interval '1 day') >= 30 then
    raise exception 'rate_limited: Beaucoup de pronos aujourd''hui : réessaie demain.' using errcode = '54000';
  end if;
  if k is null or k not in ('choice', 'number', 'text', 'person', 'yesno', 'overunder', 'when', 'majority', 'award') then
    raise exception 'invalid: Choisis le type de réponse.' using errcode = '22023';
  end if;
  if v_pat and not private.patates_on() then
    raise exception 'forbidden: Les patates arrivent bientôt.' using errcode = '42501';
  end if;
  if k = 'award' then
    v_award := body ->> 'award';
    if v_award is null or not exists (select 1 from private.prono_award_categories c where c.id = v_award) then
      raise exception 'invalid: Choisis un trophée de la liste.' using errcode = '22023';
    end if;
    if nullif(btrim(coalesce(body ->> 'question', '')), '') is null then
      select 'Qui mérite le trophée « ' || c.label || ' » ?' into q from private.prono_award_categories c where c.id = v_award;
    end if;
  end if;
  q := private.prono_text(coalesce(q, body ->> 'question'), 'La question');
  if char_length(q) < 3 or char_length(q) > 200 then raise exception 'invalid: Question de 3 à 200 caractères.' using errcode = '22023'; end if;
  if pts < 1 or pts > 10 then raise exception 'invalid: De 1 à 10 points.' using errcode = '22023'; end if;
  if rv not in ('close', 'result') then raise exception 'invalid: Dévoilement inconnu.' using errcode = '22023'; end if;
  if k in ('text', 'majority') then rv := 'close'; end if;  -- réponse libre : l'organisateur lit ; majorité : tranchée à la fin
  if k = 'award' then rv := 'result'; end if;             -- trophée : dévoilé seulement avec 3 votants au moins
  if v_not_over and k not in ('number', 'when') then v_not_over := false; end if;
  if nullif(btrim(coalesce(body ->> 'rules', '')), '') is not null then
    v_rules := private.prono_text(body ->> 'rules', 'Comment on tranche');
    if char_length(v_rules) > 200 then raise exception 'invalid: « Comment on tranche ? » : 200 caractères au plus.' using errcode = '22023'; end if;
  end if;
  if v_tpl is not null and v_tpl !~ '^[a-z0-9_]{1,40}$' then v_tpl := null; end if;
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
  if v_pat then
    if g is null and e is null then
      raise exception 'invalid: Les patates se plantent seulement dans un groupe ou un événement.' using errcode = '22023';
    end if;
    if k in ('award', 'text') then
      raise exception 'invalid: Ce type de prono se joue sans patates.' using errcode = '22023';
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
  if k in ('choice', 'majority') then
    if jsonb_typeof(body -> 'options') is distinct from 'array' then raise exception 'invalid: Ajoute les choix.' using errcode = '22023'; end if;
    for o in select v from jsonb_array_elements_text(body -> 'options') v loop
      if btrim(coalesce(o, '')) <> '' then opts := opts || private.prono_text(o, 'Un choix'); end if;
    end loop;
    if cardinality(opts) < 2 or cardinality(opts) > 8 then raise exception 'invalid: De 2 à 8 choix.' using errcode = '22023'; end if;
    if (select count(distinct lower(x)) from unnest(opts) x) < cardinality(opts) then
      raise exception 'invalid: Deux choix sont identiques.' using errcode = '22023';
    end if;
    if exists (select 1 from unnest(opts) x where char_length(x) > 60) then raise exception 'invalid: 60 caractères au plus par choix.' using errcode = '22023'; end if;
  elsif k = 'yesno' then
    opts := array['Oui', 'Non'];
  elsif k = 'overunder' then
    begin v_line := (body ->> 'line')::numeric; exception when others then v_line := null; end;
    if v_line is null or abs(v_line) > 1e6 or v_line - floor(v_line) <> 0.5 then
      raise exception 'invalid: La ligne se termine par ,5 (par exemple 7,5) : jamais d''égalité.' using errcode = '22023';
    end if;
    opts := array['Plus de ' || private.prono_line_label(v_line), 'Moins de ' || private.prono_line_label(v_line)];
  end if;
  insert into private.pronos (created_by, group_id, event_id, question, kind, points, closes_at, reveal, link_token,
                              line, not_over, rules, template, patates, award)
  values (me, g, e, q, k, pts, ends, rv,
          case when coalesce((body ->> 'link')::boolean, false)
               then replace(replace(rtrim(encode(extensions.gen_random_bytes(18), 'base64'), '='), '+', '-'), '/', '_') end,
          v_line, v_not_over, v_rules, v_tpl, v_pat, v_award)
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

-- Modifier : tout tant que personne n'a joué ; ensuite seulement la fin, les points (tant que pas de résultat) et
-- « Comment on tranche ? » (compléter, jamais réécrire).
create or replace function public.prono_update(id uuid, body jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; locked boolean; ends timestamptz; o text; i int := 0; opts text[] := '{}';
        v_rules text; v_line numeric;
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
    update private.pronos x set closes_at = ends, due_notified_at = null, soon_notified_at = null, updated_at = now()
      where x.id = p.id returning * into p;
  end if;
  if body ? 'points' then
    if (body ->> 'points')::int not between 1 and 10 then raise exception 'invalid: De 1 à 10 points.' using errcode = '22023'; end if;
    update private.pronos x set points = (body ->> 'points')::int, updated_at = now() where x.id = p.id returning * into p;
  end if;
  if body ? 'rules' then
    v_rules := case when nullif(btrim(coalesce(body ->> 'rules', '')), '') is not null then private.prono_text(body ->> 'rules', 'Comment on tranche') end;
    if char_length(v_rules) > 200 then raise exception 'invalid: « Comment on tranche ? » : 200 caractères au plus.' using errcode = '22023'; end if;
    if locked and p.rules is not null and (v_rules is null or left(v_rules, char_length(p.rules)) <> p.rules) then
      raise exception 'locked: Quelqu''un a déjà joué : « Comment on tranche ? » se complète, sans être réécrit.' using errcode = '22023';
    end if;
    update private.pronos x set rules = v_rules, updated_at = now() where x.id = p.id returning * into p;
  end if;
  if body ? 'question' or body ? 'options' or body ? 'reveal' or body ? 'line' or body ? 'not_over' or body ? 'patates' or body ? 'award' then
    if locked then
      raise exception 'locked: Quelqu''un a déjà joué : la question et les choix ne changent plus.' using errcode = '22023';
    end if;
    if body ? 'question' then
      update private.pronos x set question = private.prono_text(body ->> 'question', 'La question'), updated_at = now()
        where x.id = p.id returning * into p;
    end if;
    if body ? 'reveal' and p.kind not in ('text', 'majority', 'award') and body ->> 'reveal' in ('close', 'result') then
      update private.pronos x set reveal = body ->> 'reveal' where x.id = p.id returning * into p;
    end if;
    if body ? 'not_over' then
      update private.pronos x set not_over = coalesce((body ->> 'not_over')::boolean, false) and p.kind in ('number', 'when')
        where x.id = p.id returning * into p;
    end if;
    if body ? 'patates' then
      if coalesce((body ->> 'patates')::boolean, false) then
        if not private.patates_on() then
          raise exception 'forbidden: Les patates arrivent bientôt.' using errcode = '42501';
        end if;
        if private.prono_terrain(p) is null or p.kind in ('award', 'text') then
          raise exception 'invalid: Les patates se plantent seulement dans un groupe ou un événement, sur un prono à réponse.' using errcode = '22023';
        end if;
      end if;
      update private.pronos x set patates = coalesce((body ->> 'patates')::boolean, false) where x.id = p.id returning * into p;
    end if;
    if body ? 'award' and p.kind = 'award' then
      if not exists (select 1 from private.prono_award_categories c where c.id = body ->> 'award') then
        raise exception 'invalid: Choisis un trophée de la liste.' using errcode = '22023';
      end if;
      update private.pronos x set award = body ->> 'award' where x.id = p.id returning * into p;
    end if;
    if body ? 'line' and p.kind = 'overunder' then
      begin v_line := (body ->> 'line')::numeric; exception when others then v_line := null; end;
      if v_line is null or abs(v_line) > 1e6 or v_line - floor(v_line) <> 0.5 then
        raise exception 'invalid: La ligne se termine par ,5 (par exemple 7,5) : jamais d''égalité.' using errcode = '22023';
      end if;
      update private.pronos x set line = v_line where x.id = p.id returning * into p;
      update private.prono_options x set label = case x.position when 1 then 'Plus de ' else 'Moins de ' end || private.prono_line_label(v_line)
        where x.prono_id = p.id;
    end if;
    if body ? 'options' and p.kind in ('choice', 'majority') then
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

-- ───────────── Jouer ─────────────

-- answer : option_id | number | text | person_id | answer_at, et stake (0 à 20 🥔, sac suffisant, patates seulement).
-- Modifiable jusqu'à la fin ; une clé absente garde la réponse d'avant (changer seulement les patates).
create or replace function public.prono_answer(id uuid, answer jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; old private.prono_answers; opt uuid; num numeric; txt text; per uuid;
        at_ timestamptz; stk int; delta int; bal int; t text;
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.id = prono_answer.id;
  if p.id is null or not private.prono_can_play(p, me) then
    raise exception 'not_found: Ce prono n''existe plus ou ne t''est pas ouvert.' using errcode = 'PT404';
  end if;
  if private.prono_state(p) <> 'open' then raise exception 'closed: Les pronos sont fermés.' using errcode = '22023'; end if;
  answer := coalesce(answer, '{}'::jsonb);
  select * into old from private.prono_answers x where x.prono_id = p.id and x.user_id = me for update;
  if p.kind in ('choice', 'yesno', 'overunder', 'majority') then
    opt := case when answer ? 'option_id' or old.user_id is null then nullif(answer ->> 'option_id', '')::uuid else old.option_id end;
    if not exists (select 1 from private.prono_options o where o.id = opt and o.prono_id = p.id) then
      raise exception 'invalid: Choisis une des réponses.' using errcode = '22023';
    end if;
  elsif p.kind = 'number' then
    if answer ? 'number' or old.user_id is null then
      begin num := (answer ->> 'number')::numeric; exception when others then num := null; end;
    else num := old.number; end if;
    if num is null or abs(num) > 1e9 then raise exception 'invalid: Écris un nombre.' using errcode = '22023'; end if;
  elsif p.kind = 'text' then
    txt := case when answer ? 'text' or old.user_id is null then private.prono_text(answer ->> 'text', 'Ta réponse') else old.answer_text end;
    if txt is null then raise exception 'invalid: Écris ta réponse.' using errcode = '22023'; end if;
    if char_length(txt) > 80 then raise exception 'invalid: 80 caractères au plus.' using errcode = '22023'; end if;
  elsif p.kind = 'when' then
    if answer ? 'answer_at' or old.user_id is null then
      begin at_ := (answer ->> 'answer_at')::timestamptz; exception when others then at_ := null; end;
    else at_ := old.answer_at; end if;
    if at_ is null or at_ < now() - interval '1 year' or at_ > now() + interval '2 years' then
      raise exception 'invalid: Choisis une date et une heure.' using errcode = '22023';
    end if;
  else
    per := case when answer ? 'person_id' or old.user_id is null then nullif(answer ->> 'person_id', '')::uuid else old.person_id end;
    if per is null or private.blocked_either(me, per) or not exists (select 1 from private.prono_people(p) u where u = per) then
      raise exception 'invalid: Choisis une personne du prono.' using errcode = '22023';
    end if;
    if p.kind = 'award' then
      if per = me then raise exception 'invalid: Vote pour quelqu''un d''autre.' using errcode = '22023'; end if;
      if exists (select 1 from private.prono_optouts o where o.prono_id = p.id and o.user_id = per) then
        raise exception 'invalid: Cette personne s''est retirée de ce trophée.' using errcode = '22023';
      end if;
    end if;
  end if;
  if answer ? 'stake' then
    begin stk := (answer ->> 'stake')::int; exception when others then stk := null; end;
    if stk is null or stk < 0 or stk > 20 then raise exception 'invalid: De 0 à 20 🥔 par prono.' using errcode = '22023'; end if;
  else
    stk := coalesce(old.stake, 0);
  end if;
  delta := stk - coalesce(old.stake, 0);
  if stk > 0 and not p.patates then raise exception 'invalid: Ce prono se joue sans patates.' using errcode = '22023'; end if;
  if delta > 0 and not private.patates_on() then raise exception 'forbidden: Les patates arrivent bientôt.' using errcode = '42501'; end if;
  if delta <> 0 then
    t := private.prono_terrain(p);
    bal := private.prono_bag_touch(t, me);
    if delta > bal then
      raise exception 'not_enough: Ton sac n''a que % 🥔.', bal using errcode = '22023';
    end if;
    perform private.prono_bag_add(t, me, p.id, -delta, case when delta > 0 then 'plant' else 'unplant' end);
  end if;
  insert into private.prono_answers (prono_id, user_id, option_id, number, answer_text, person_id, answer_at, stake)
  values (p.id, me, opt, num, txt, per, at_, stk)
  on conflict (prono_id, user_id) do update set option_id = excluded.option_id, number = excluded.number,
    answer_text = excluded.answer_text, person_id = excluded.person_id, answer_at = excluded.answer_at, stake = excluded.stake,
    hidden_at = null, updated_at = now();
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_answer(uuid, jsonb) from public, anon;
grant execute on function public.prono_answer(uuid, jsonb) to authenticated;

-- ───────────── Fin, résultat, annulation ─────────────

create or replace function public.prono_close_now(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  select * into p from private.pronos x where x.id = prono_close_now.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono le ferme.' using errcode = '42501'; end if;
  if private.prono_state(p) <> 'open' then raise exception 'invalid: Les pronos sont déjà fermés.' using errcode = '22023'; end if;
  update private.pronos x set closes_at = now(), due_notified_at = now(), soon_notified_at = now(), updated_at = now()
    where x.id = p.id returning * into p;
  if p.kind in ('majority', 'award') then
    perform private.prono_auto_result(p.id);
    select * into p from private.pronos x where x.id = p.id;
  end if;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_close_now(uuid) from public, anon;
grant execute on function public.prono_close_now(uuid) to authenticated;

-- body : option_id (choix, oui / non, plus / moins) | number (nombre ; plus / moins : la valeur) | time (« quand » ;
-- absent : maintenant, « C'est arrivé ! ») | person_id | winners [uuid] (réponse libre, ou pour remplacer le calcul).
-- Dévoile, prévient chaque joueur, ouvre 12 h de contestation ; patates versées ensuite (tout de suite s'il n'y en a pas).
create or replace function public.prono_result(id uuid, body jsonb) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; opt uuid; num numeric; per uuid; tm timestamptz; wins uuid[]; best numeric;
        label text; st text;
begin
  perform private.prono_check_author(me);
  body := coalesce(body, '{}'::jsonb);
  select * into p from private.pronos x where x.id = prono_result.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono donne le résultat.' using errcode = '42501'; end if;
  if p.kind in ('majority', 'award') then
    raise exception 'invalid: Ce prono se tranche tout seul à la fin.' using errcode = '22023';
  end if;
  st := private.prono_state(p);
  if not (st = 'closed' or (st = 'open' and p.kind = 'when')) then
    raise exception 'invalid: Le résultat se donne une fois les pronos fermés.' using errcode = '22023';
  end if;
  if p.kind in ('choice', 'yesno') then
    opt := nullif(body ->> 'option_id', '')::uuid;
    select o.label into label from private.prono_options o where o.id = opt and o.prono_id = p.id;
    if label is null then raise exception 'invalid: Touche la bonne réponse.' using errcode = '22023'; end if;
    select coalesce(array_agg(x.user_id), '{}') into wins from private.prono_answers x where x.prono_id = p.id and x.option_id = opt;
  elsif p.kind = 'overunder' then
    if body ? 'number' then
      begin num := (body ->> 'number')::numeric; exception when others then num := null; end;
      if num is null then raise exception 'invalid: Écris le résultat.' using errcode = '22023'; end if;
      select o.id into opt from private.prono_options o where o.prono_id = p.id and o.position = case when num > p.line then 1 else 2 end;
    else
      opt := nullif(body ->> 'option_id', '')::uuid;
    end if;
    select o.label into label from private.prono_options o where o.id = opt and o.prono_id = p.id;
    if label is null then raise exception 'invalid: Touche la bonne réponse.' using errcode = '22023'; end if;
    select coalesce(array_agg(x.user_id), '{}') into wins from private.prono_answers x where x.prono_id = p.id and x.option_id = opt;
  elsif p.kind = 'number' then
    begin num := (body ->> 'number')::numeric; exception when others then num := null; end;
    if num is null then raise exception 'invalid: Écris le résultat.' using errcode = '22023'; end if;
    -- Le plus proche ; « sans dépasser » : ceux au-dessus sont écartés, sauf si tout le monde l'est.
    select min(abs(x.number - num)) into best from private.prono_answers x where x.prono_id = p.id
      and (not p.not_over or x.number <= num
           or not exists (select 1 from private.prono_answers y where y.prono_id = p.id and y.number <= num));
    select coalesce(array_agg(x.user_id), '{}') into wins from private.prono_answers x where x.prono_id = p.id and abs(x.number - num) = best
      and (not p.not_over or x.number <= num
           or not exists (select 1 from private.prono_answers y where y.prono_id = p.id and y.number <= num));
    label := trim(trailing '.' from trim(trailing '0' from num::text));
  elsif p.kind = 'when' then
    if nullif(body ->> 'time', '') is null then tm := now();
    else
      begin tm := (body ->> 'time')::timestamptz; exception when others then tm := null; end;
      if tm is null then raise exception 'invalid: Choisis la date et l''heure.' using errcode = '22023'; end if;
    end if;
    select min(abs(extract(epoch from x.answer_at - tm))) into best from private.prono_answers x where x.prono_id = p.id
      and (not p.not_over or x.answer_at <= tm
           or not exists (select 1 from private.prono_answers y where y.prono_id = p.id and y.answer_at <= tm));
    select coalesce(array_agg(x.user_id), '{}') into wins from private.prono_answers x where x.prono_id = p.id
      and abs(extract(epoch from x.answer_at - tm)) = best
      and (not p.not_over or x.answer_at <= tm
           or not exists (select 1 from private.prono_answers y where y.prono_id = p.id and y.answer_at <= tm));
    label := private.prono_when(tm);
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
  update private.prono_answers x set winner = coalesce(x.user_id = any (wins), false) where x.prono_id = p.id;
  update private.pronos x set result_option = opt, result_number = num, result_person = per, result_time = tm,
    closes_at = least(x.closes_at, now()), due_notified_at = coalesce(x.due_notified_at, now()),
    result_at = now(), contest_until = now() + interval '12 hours', updated_at = now()
    where x.id = p.id returning * into p;
  if not exists (select 1 from private.prono_answers x where x.prono_id = p.id and x.stake > 0) then
    perform private.prono_settle(p.id);  -- aucune patate : rien à attendre
  end if;
  perform private.prono_notify_result(p.id, label);
  select * into p from private.pronos x where x.id = p.id;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_result(uuid, jsonb) from public, anon;
grant execute on function public.prono_result(uuid, jsonb) to authenticated;

-- Annuler (ou « Pas de résultat ») : aucun point, toutes les patates rendues ; les réponses restent cachées si elles
-- ne l'étaient pas déjà.
create or replace function public.prono_cancel(id uuid) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  select * into p from private.pronos x where x.id = prono_cancel.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono l''annule.' using errcode = '42501'; end if;
  if private.prono_state(p) not in ('open', 'closed') then raise exception 'invalid: Ce prono est déjà terminé.' using errcode = '22023'; end if;
  update private.prono_answers x set winner = false where x.prono_id = p.id;
  update private.pronos x set cancelled_at = now(), cancel_reason = 'organizer', updated_at = now() where x.id = p.id returning * into p;
  perform private.prono_settle(p.id);
  select * into p from private.pronos x where x.id = p.id;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_cancel(uuid) from public, anon;
grant execute on function public.prono_cancel(uuid) to authenticated;

-- Supprimer un prono (organisateur) : tant que personne n'a joué, ou une fois terminé / annulé et les patates réglées.
create or replace function public.prono_delete(id uuid) returns void
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  select * into p from private.pronos x where x.id = prono_delete.id for update;
  if p.id is null or p.created_by <> me then raise exception 'forbidden: Seul l''organisateur du prono le supprime.' using errcode = '42501'; end if;
  if private.prono_state(p) in ('open', 'closed') and exists (select 1 from private.prono_answers a where a.prono_id = p.id) then
    raise exception 'locked: Des personnes ont joué : annule le prono plutôt.' using errcode = '22023';
  end if;
  if p.settled_at is null and exists (select 1 from private.prono_answers a where a.prono_id = p.id and a.stake > 0) then
    raise exception 'locked: Des patates sont encore dans le champ : attends la fin de la contestation.' using errcode = '22023';
  end if;
  delete from private.pronos x where x.id = p.id;
  perform private.prono_signal(p);
end $$;
revoke all on function public.prono_delete(uuid) from public, anon;
grant execute on function public.prono_delete(uuid) to authenticated;

-- ───────────── Contestation ─────────────

-- Un joueur (jamais celui qui a donné le résultat) conteste, une fois, pendant 12 h : vote des joueurs 24 h.
create or replace function public.prono_contest(id uuid, reason text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; r text; u uuid;
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.id = prono_contest.id for update;
  if p.id is null or not private.prono_can_play(p, me) then
    raise exception 'not_found: Ce prono n''existe plus ou ne t''est pas ouvert.' using errcode = 'PT404';
  end if;
  if p.kind in ('majority', 'award') then raise exception 'invalid: Ce prono se tranche tout seul : rien à contester.' using errcode = '22023'; end if;
  if p.result_at is null or p.cancelled_at is not null then raise exception 'invalid: Il n''y a pas de résultat à contester.' using errcode = '22023'; end if;
  if p.created_by = me then raise exception 'forbidden: Tu as donné le résultat : tu ne peux pas le contester.' using errcode = '42501'; end if;
  if not exists (select 1 from private.prono_answers a where a.prono_id = p.id and a.user_id = me) then
    raise exception 'forbidden: Seuls les joueurs contestent un résultat.' using errcode = '42501';
  end if;
  if p.vote_done_at is not null or p.contest_until is null or p.contest_until <= now() then
    raise exception 'closed: Le délai pour contester est passé.' using errcode = '22023';
  end if;
  if exists (select 1 from private.prono_contests c where c.prono_id = p.id and c.user_id = me) then
    raise exception 'already: Tu as déjà contesté ce résultat.' using errcode = '22023';
  end if;
  r := left(private.prono_text(reason, 'La raison'), 200);
  insert into private.prono_contests (prono_id, user_id, reason) values (p.id, me, r);
  insert into private.prono_contest_votes (prono_id, user_id, fair) values (p.id, me, false)
    on conflict (prono_id, user_id) do update set fair = false, at = now();
  if p.vote_until is null then
    update private.pronos x set vote_until = now() + interval '24 hours', updated_at = now() where x.id = p.id returning * into p;
    for u in select a.user_id from private.prono_answers a where a.prono_id = p.id and a.user_id <> me
             union select p.created_by loop
      continue when u = me or private.blocked_either(me, u);
      perform public.queue_notification(u, 'prono_contest', null, '🔮 Prono contesté · ' || private.prono_where(p),
        'Un résultat est contesté : donne ton avis · ' || p.question, 'prono_contest:' || p.id || ':' || u,
        jsonb_build_object('prono_id', p.id, 'url', '/?tab=events&prono=' || p.id));
    end loop;
  end if;
  perform private.prono_finish(p.id);  -- tout le monde a voté : tranché tout de suite
  select * into p from private.pronos x where x.id = p.id;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_contest(uuid, text) from public, anon;
grant execute on function public.prono_contest(uuid, text) to authenticated;

-- « C'est juste » (fair = true) ou « Pas juste » : joueurs du prono, jamais l'organisateur ; modifiable pendant le vote.
create or replace function public.prono_contest_vote(id uuid, fair boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  perform private.prono_check_author(me);
  select * into p from private.pronos x where x.id = prono_contest_vote.id for update;
  if p.id is null or not private.prono_can_play(p, me) then
    raise exception 'not_found: Ce prono n''existe plus ou ne t''est pas ouvert.' using errcode = 'PT404';
  end if;
  if prono_contest_vote.fair is null then raise exception 'invalid: Juste ou pas juste ?' using errcode = '22023'; end if;
  if p.created_by = me then raise exception 'forbidden: Tu as donné le résultat : tu ne votes pas.' using errcode = '42501'; end if;
  if not exists (select 1 from private.prono_answers a where a.prono_id = p.id and a.user_id = me) then
    raise exception 'forbidden: Seuls les joueurs votent.' using errcode = '42501';
  end if;
  if p.vote_until is null or p.vote_done_at is not null or p.vote_until <= now() or p.cancelled_at is not null then
    raise exception 'closed: Le vote est terminé.' using errcode = '22023';
  end if;
  insert into private.prono_contest_votes (prono_id, user_id, fair) values (p.id, me, prono_contest_vote.fair)
    on conflict (prono_id, user_id) do update set fair = excluded.fair, at = now();
  perform private.prono_finish(p.id);
  select * into p from private.pronos x where x.id = p.id;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_contest_vote(uuid, boolean) from public, anon;
grant execute on function public.prono_contest_vote(uuid, boolean) to authenticated;

-- ───────────── Réactions, trophée ─────────────

create or replace function public.prono_react(id uuid, emoji text) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  select * into p from private.pronos x where x.id = prono_react.id;
  if p.id is null or not private.prono_can_play(p, me) then
    raise exception 'not_found: Ce prono n''existe plus ou ne t''est pas ouvert.' using errcode = 'PT404';
  end if;
  if prono_react.emoji is null or prono_react.emoji not in ('😂', '🔥', '🥔', '👀', '🤯', '👏') then
    raise exception 'invalid: Réaction inconnue.' using errcode = '22023';
  end if;
  delete from private.prono_reactions x where x.prono_id = p.id and x.user_id = me and x.emoji = prono_react.emoji;
  if not found then
    insert into private.prono_reactions (prono_id, user_id, emoji) values (p.id, me, prono_react.emoji);
  end if;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_react(uuid, text) from public, anon;
grant execute on function public.prono_react(uuid, text) to authenticated;

-- Se retirer de la liste d'un trophée (ses votes reçus partent : les votants revotent).
create or replace function public.prono_optout(id uuid, "out" boolean) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  select * into p from private.pronos x where x.id = prono_optout.id for update;
  if p.id is null or not private.prono_can_play(p, me) then
    raise exception 'not_found: Ce prono n''existe plus ou ne t''est pas ouvert.' using errcode = 'PT404';
  end if;
  if p.kind <> 'award' then raise exception 'invalid: Seulement pour un trophée.' using errcode = '22023'; end if;
  if private.prono_state(p) <> 'open' then raise exception 'closed: Les votes sont fermés.' using errcode = '22023'; end if;
  if coalesce(prono_optout."out", true) then
    insert into private.prono_optouts (prono_id, user_id) values (p.id, me) on conflict do nothing;
    delete from private.prono_answers x where x.prono_id = p.id and x.person_id = me;
  else
    delete from private.prono_optouts x where x.prono_id = p.id and x.user_id = me;
  end if;
  perform private.prono_signal(p);
  return private.prono_json(p, me);
end $$;
revoke all on function public.prono_optout(uuid, boolean) from public, anon;
grant execute on function public.prono_optout(uuid, boolean) to authenticated;

-- ───────────── Sac, historique, saison ─────────────

create or replace function private.prono_terrain_of(g uuid, e uuid, me uuid) returns text
language plpgsql stable security definer set search_path = '' as $$
begin
  if (g is null) = (e is null) then raise exception 'invalid: Choisis un groupe ou un événement.' using errcode = '22023'; end if;
  if g is not null then
    if not private.in_group_now(g, me) then raise exception 'forbidden: Réservé aux membres du groupe.' using errcode = '42501'; end if;
    return 'g:' || g;
  end if;
  if not public.can_see_event(e) then raise exception 'forbidden: Tu ne vois pas cet événement.' using errcode = '42501'; end if;
  return 'e:' || e;
end $$;
revoke all on function private.prono_terrain_of(uuid, uuid, uuid) from public, anon, authenticated;

-- Récolte nette d'une personne sur un terrain, pour un mois (heure de Suisse) : versé − planté des pronos réglés.
create or replace function private.prono_net(t text, uid uuid, m date) returns int
language sql stable security definer set search_path = '' as $$
  select coalesce(sum(a.harvest - a.stake), 0)::int
  from private.prono_answers a join private.pronos p on p.id = a.prono_id
  where a.user_id = uid and p.patates and a.harvest is not null and private.prono_terrain(p) = t
    and p.settled_at >= (m::timestamp at time zone 'Europe/Zurich')
    and p.settled_at < ((m + interval '1 month')::timestamp at time zone 'Europe/Zurich');
$$;
revoke all on function private.prono_net(text, uuid, date) from public, anon, authenticated;

-- Mon sac sur un terrain (null si les patates sont éteintes).
create or replace function public.prono_bag(group_id uuid default null, event_id uuid default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); t text; bal int; m date := date_trunc('month', now() at time zone 'Europe/Zurich')::date;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.patates_on() then return null; end if;
  t := private.prono_terrain_of(prono_bag.group_id, prono_bag.event_id, me);
  bal := private.prono_bag_touch(t, me);
  return jsonb_build_object('balance', bal, 'refill_at', private.prono_refill_at(), 'max_stake', 20,
    'season', jsonb_build_object('month', m, 'harvest_net', private.prono_net(t, me, m)));
end $$;
revoke all on function public.prono_bag(uuid, uuid) from public, anon;
grant execute on function public.prono_bag(uuid, uuid) to authenticated;

-- SON historique seulement (60 derniers mouvements) ; sans terrain : tous ses sacs. [] si les patates sont éteintes.
create or replace function public.prono_bag_history(group_id uuid default null, event_id uuid default null) returns jsonb
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); t text;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if not private.patates_on() then return '[]'::jsonb; end if;
  if prono_bag_history.group_id is not null or prono_bag_history.event_id is not null then
    t := private.prono_terrain_of(prono_bag_history.group_id, prono_bag_history.event_id, me);
    perform private.prono_bag_touch(t, me);
  end if;
  return coalesce((select jsonb_agg(jsonb_build_object('at', h.at, 'delta', h.delta, 'reason', h.reason,
      'terrain', case when h.group_id is not null then jsonb_build_object('kind', 'group', 'id', h.group_id)
                      else jsonb_build_object('kind', 'event', 'id', h.event_id) end,
      'prono', case when h.prono_id is not null then (select jsonb_build_object('id', p.id,
                 'question', case when p.hidden_at is null then p.question end) from private.pronos p where p.id = h.prono_id) end)
      order by h.at desc, h.id desc)
    from (select * from private.prono_bag_moves x where x.user_id = me and (t is null or x.terrain = t)
          order by x.at desc, x.id desc limit 60) h), '[]'::jsonb);
end $$;
revoke all on function public.prono_bag_history(uuid, uuid) from public, anon;
grant execute on function public.prono_bag_history(uuid, uuid) to authenticated;

-- Saison (mois, heure de Suisse) d'un groupe : récolte nette, justesse ; rang et mouvement depuis la veille.
-- Jamais de classement au sac ni de « +/− » entre deux personnes. Bloqués exclus. null si les patates sont éteintes.
create or replace function public.prono_season(group_id uuid, month date default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); g uuid := prono_season.group_id; m date; m0 timestamptz; m1 timestamptz; cur boolean; rws jsonb;
begin
  if not private.is_account_active(me) or g is null or not private.in_group_now(g, me) then
    raise exception 'forbidden: Réservé aux membres du groupe.' using errcode = '42501';
  end if;
  if not private.patates_on() then return null; end if;
  m := date_trunc('month', coalesce(prono_season.month, (now() at time zone 'Europe/Zurich')::date))::date;
  m0 := m::timestamp at time zone 'Europe/Zurich';
  m1 := (m + interval '1 month')::timestamp at time zone 'Europe/Zurich';
  cur := now() >= m0 and now() < m1;
  with base as (
    select a.user_id, p.settled_at,
           case when p.patates and a.harvest is not null then a.harvest - a.stake else 0 end as net,
           p.cancelled_at is null and a.winner as ok, p.cancelled_at is null as counted
    from private.prono_answers a join private.pronos p on p.id = a.prono_id
    where p.group_id = g and p.hidden_at is null and p.kind <> 'award' and p.settled_at >= m0 and p.settled_at < m1
      and private.in_group_now(g, a.user_id) and not private.blocked_either(me, a.user_id)),
  now_rows as (select b.user_id, sum(b.net)::int as net, count(*) filter (where b.ok) as ok, count(*) filter (where b.counted) as played
               from base b group by b.user_id),
  ranked as (select r.*, rank() over (order by r.net desc, r.ok desc) as rk from now_rows r),
  before as (select b.user_id, rank() over (order by sum(b.net) desc, count(*) filter (where b.ok) desc) as rk
             from base b where b.settled_at <= now() - interval '1 day' group by b.user_id)
  select coalesce(jsonb_agg(jsonb_build_object('user', private.prono_face(r.user_id), 'harvest_net', r.net, 'right', r.ok,
           'played', r.played, 'rank', r.rk, 'move', case when cur and bf.rk is not null then bf.rk - r.rk end)
           order by r.rk, r.played desc), '[]'::jsonb)
    into rws from ranked r left join before bf on bf.user_id = r.user_id;
  return jsonb_build_object('month', m, 'rows', rws,
    'me', (select x from jsonb_array_elements(rws) x where (x -> 'user' ->> 'id')::uuid = me limit 1));
end $$;
revoke all on function public.prono_season(uuid, date) from public, anon;
grant execute on function public.prono_season(uuid, date) to authenticated;

-- ───────────── Modèles prêts (jamais d'alcool, jamais d'argent) ─────────────

create or replace function public.prono_templates() returns jsonb
language sql stable security definer set search_path = '' as $$
  select $j$[
    {"id": "dernier", "kind": "person", "emoji": "🐢", "title": "Le dernier arrivé", "question": "Qui arrive en dernier ?",
     "hint": "Chacun devine qui sera le plus en retard."},
    {"id": "heure_arrivee", "kind": "when", "emoji": "⏰", "title": "L'heure d'arrivée", "question": "À quelle heure Max arrive ?",
     "hint": "Remplace Max par le bon prénom. L'heure la plus proche l'emporte."},
    {"id": "retard", "kind": "number", "emoji": "⏱️", "title": "Les minutes de retard", "question": "Combien de minutes de retard pour Max ?",
     "hint": "Le nombre le plus proche l'emporte."},
    {"id": "match", "kind": "choice", "emoji": "⚽", "title": "Le match de ce soir", "question": "Le match de ce soir : qui gagne ?",
     "options": ["Équipe A", "Match nul", "Équipe B"], "hint": "Écris le nom des deux équipes."},
    {"id": "buts", "kind": "overunder", "emoji": "🥅", "title": "Plus ou moins de buts", "question": "Plus ou moins de 2,5 buts dans le match ?",
     "line": 2.5, "hint": "La ligne se termine par ,5 : jamais d'égalité."},
    {"id": "score", "kind": "number", "emoji": "🔢", "title": "Le nombre de buts", "question": "Combien de buts dans le match ?",
     "hint": "Le nombre le plus proche l'emporte."},
    {"id": "babyfoot", "kind": "number", "emoji": "🎯", "title": "Les parties de baby-foot", "question": "Combien de parties de baby-foot ce soir ?",
     "hint": "Le nombre le plus proche l'emporte."},
    {"id": "babyfoot_champion", "kind": "person", "emoji": "🏓", "title": "Le roi du baby-foot", "question": "Qui gagne le plus de parties de baby-foot ?",
     "hint": "Une personne de la bande."},
    {"id": "karaoke", "kind": "person", "emoji": "🎤", "title": "Le premier au karaoké", "question": "Qui ose le karaoké en premier ?",
     "hint": "Une personne de la bande."},
    {"id": "piste", "kind": "when", "emoji": "💃", "title": "La piste se remplit", "question": "À quelle heure la piste de danse se remplit ?",
     "hint": "L'heure la plus proche l'emporte."},
    {"id": "dernier_parti", "kind": "when", "emoji": "🌙", "title": "Le dernier départ", "question": "À quelle heure part le dernier invité ?",
     "hint": "L'heure la plus proche l'emporte."},
    {"id": "premier_parti", "kind": "person", "emoji": "🚪", "title": "Le premier départ", "question": "Qui part en premier ?",
     "hint": "Une personne de la bande."},
    {"id": "photos", "kind": "person", "emoji": "📸", "title": "Le photographe", "question": "Qui prend le plus de photos ce soir ?",
     "hint": "Une personne de la bande."},
    {"id": "invites", "kind": "number", "emoji": "👫", "title": "Le nombre de personnes", "question": "Combien de personnes à la soirée ?",
     "hint": "Le nombre le plus proche l'emporte."},
    {"id": "pluie", "kind": "yesno", "emoji": "🌧️", "title": "Il va pleuvoir ?", "question": "Il va pleuvoir samedi ?",
     "hint": "Oui ou non."},
    {"id": "celine", "kind": "yesno", "emoji": "🎶", "title": "Le tube de la soirée", "question": "Quelqu'un met du Céline Dion ce soir ?",
     "hint": "Oui ou non."},
    {"id": "preferes", "kind": "majority", "emoji": "🤔", "title": "Tu préfères…", "question": "Tu préfères : montagne ou mer ?",
     "options": ["Montagne", "Mer"], "hint": "La réponse la plus choisie l'emporte, toute seule à la fin."},
    {"id": "bande_pense", "kind": "majority", "emoji": "👥", "title": "Devine ce que pense la bande", "question": "Fondue ou raclette : que choisira la bande ?",
     "options": ["Fondue", "Raclette"], "hint": "Devine la réponse la plus choisie : tranché tout seul à la fin."},
    {"id": "film", "kind": "majority", "emoji": "🎬", "title": "Le film du soir", "question": "Quel film la bande choisira ?",
     "options": ["Comédie", "Action", "Horreur"], "hint": "La réponse la plus choisie l'emporte."},
    {"id": "libre", "kind": "text", "emoji": "✍️", "title": "Réponse libre", "question": "Le mot de la soirée ?",
     "hint": "Tu coches les bonnes réponses à la fin."}
  ]$j$::jsonb || jsonb_build_array(jsonb_build_object('id', 'trophee', 'kind', 'award', 'emoji', '🏆', 'title', 'Trophée de la soirée',
    'question', 'Qui mérite le trophée « Ambianceur·euse » ?', 'award', 'ambiance',
    'hint', 'Vote pour une personne. Dévoilé avec 3 votes au moins ; chacun peut se retirer de la liste.',
    'awards', (select jsonb_agg(jsonb_build_object('id', c.id, 'emoji', c.emoji, 'label', c.label) order by c.position)
               from private.prono_award_categories c)));
$$;
revoke all on function public.prono_templates() from public, anon;
grant execute on function public.prono_templates() to authenticated;

-- ───────────── Classement (points) : sans les trophées ─────────────

create or replace function public.prono_board(group_id uuid) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare me uuid := auth.uid(); since timestamptz := (select r.reset_at from private.prono_board_resets r where r.group_id = prono_board.group_id);
begin
  if not private.is_account_active(me) or not private.in_group_now(prono_board.group_id, me) then
    raise exception 'forbidden: Réservé aux membres du groupe.' using errcode = '42501';
  end if;
  return jsonb_build_object('since', since, 'manage', private.manages_group(prono_board.group_id),
    'pronos', (select count(*) from private.pronos p where p.group_id = prono_board.group_id and p.result_at is not null
               and p.cancelled_at is null and p.hidden_at is null and p.kind <> 'award' and (since is null or p.result_at > since)),
    'rows', coalesce((select jsonb_agg(jsonb_build_object('user', private.prono_face(r.user_id), 'points', r.pts, 'right', r.ok,
               'played', r.played) order by r.pts desc, r.ok desc, r.played) from (
      select a.user_id, sum(case when a.winner then p.points else 0 end) as pts, count(*) filter (where a.winner) as ok, count(*) as played
      from private.prono_answers a join private.pronos p on p.id = a.prono_id
      where p.group_id = prono_board.group_id and p.result_at is not null and p.cancelled_at is null and p.hidden_at is null
        and p.kind <> 'award' and (since is null or p.result_at > since) and private.in_group_now(prono_board.group_id, a.user_id)
        and not private.blocked_either(me, a.user_id)
      group by a.user_id) r), '[]'::jsonb));
end $$;
revoke all on function public.prono_board(uuid) from public, anon;
grant execute on function public.prono_board(uuid) to authenticated;

-- ───────────── pronos-tick (pg_cron, 5 min) ─────────────

create or replace function private.prono_tick() returns void
language plpgsql security definer set search_path = '' as $$
declare p private.pronos; u uuid;
begin
  -- Majorité et trophée : tranchés tout seuls à la fin.
  for p in select * from private.pronos x where x.kind in ('majority', 'award') and x.result_at is null and x.cancelled_at is null
           and x.closes_at <= now() and x.hidden_at is null limit 500 loop
    perform private.prono_auto_result(p.id);
  end loop;
  -- Rappel à l'organisateur : la fin est passée, donne le résultat.
  for p in select * from private.pronos x where x.result_at is null and x.cancelled_at is null and x.due_notified_at is null
           and x.closes_at <= now() and x.hidden_at is null and x.kind not in ('majority', 'award') limit 500 loop
    update private.pronos x set due_notified_at = now() where x.id = p.id;
    if exists (select 1 from private.prono_answers a where a.prono_id = p.id) then
      insert into public.notifications (user_id, kind, event_id, title, body, data, dedupe_key)
      values (p.created_by, 'prono_due', null, '🔮 Les pronos sont fermés',
        'Donne le résultat : ' || p.question, jsonb_build_object('kind', 'prono_due', 'prono_id', p.id, 'url', '/?tab=events&prono=' || p.id), 'prono_due:' || p.id)
      on conflict (user_id, dedupe_key) where dedupe_key is not null do nothing;
    end if;
    perform private.prono_signal(p);
  end loop;
  -- Une heure avant la fin, une fois, seulement à qui n'a pas joué (jamais l'organisateur).
  for p in select * from private.pronos x where x.result_at is null and x.cancelled_at is null and x.soon_notified_at is null
           and x.hidden_at is null and x.closes_at > now() and x.closes_at <= now() + interval '1 hour'
           and x.created_at <= now() - interval '1 hour' limit 500 loop
    update private.pronos x set soon_notified_at = now() where x.id = p.id;
    for u in select z from private.prono_people(p) z where z <> p.created_by
             and not exists (select 1 from private.prono_answers a where a.prono_id = p.id and a.user_id = z) loop
      perform public.queue_notification(u, 'prono_soon', null, '🔮 Le prono se termine bientôt · ' || private.prono_where(p),
        p.question || ' · jusqu''au ' || private.prono_when(p.closes_at), 'prono_soon:' || p.id || ':' || u,
        jsonb_build_object('prono_id', p.id, 'url', '/?tab=events&prono=' || p.id));
    end loop;
  end loop;
  -- Annulés pas encore réglés : tout rendu.
  for p in select * from private.pronos x where x.settled_at is null and x.cancelled_at is not null limit 500 loop
    perform private.prono_settle(p.id);
  end loop;
  -- Fin de la contestation (12 h) ou du vote (24 h) : versement, ou annulation et tout rendu.
  for p in select * from private.pronos x where x.result_at is not null and x.cancelled_at is null and (
             (x.settled_at is null and x.vote_until is null and x.contest_until <= now())
          or (x.vote_until is not null and x.vote_done_at is null and x.vote_until <= now())) limit 500 loop
    perform private.prono_finish(p.id);
  end loop;
  -- Sans résultat 7 jours après la fin : annulé, tout rendu.
  for p in select * from private.pronos x where x.result_at is null and x.cancelled_at is null
           and x.closes_at <= now() - interval '7 days' limit 500 loop
    update private.prono_answers x set winner = false where x.prono_id = p.id;
    update private.pronos x set cancelled_at = now(), cancel_reason = 'no_result', updated_at = now() where x.id = p.id;
    perform private.prono_settle(p.id);
  end loop;
  -- Prono masqué par la modération, patates pas encore réglées : annulé, tout rendu.
  for p in select * from private.pronos x where x.hidden_at is not null and x.settled_at is null and x.cancelled_at is null limit 500 loop
    update private.prono_answers x set winner = false where x.prono_id = p.id;
    update private.pronos x set cancelled_at = now(), cancel_reason = 'hidden', updated_at = now() where x.id = p.id;
    perform private.prono_settle(p.id);
  end loop;
end $$;
revoke all on function private.prono_tick() from public, anon, authenticated;
select cron.unschedule('pronos-tick') where exists (select 1 from cron.job where jobname = 'pronos-tick');
select cron.schedule('pronos-tick', '*/5 * * * *', 'select private.prono_tick();');

-- ───────────── Signaler : motif « money » ─────────────

create or replace function public.prono_report_answer(id uuid, author uuid, reason text, comment text default null) returns uuid
language plpgsql security definer set search_path = '' as $$
declare me uuid := auth.uid(); p private.pronos; a private.prono_answers; rid uuid;
begin
  if not private.is_account_active(me) then raise exception 'forbidden: Connexion requise' using errcode = '42501'; end if;
  if reason is null or reason not in ('harassment', 'shocking', 'spam', 'scam', 'money', 'other') then
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

-- ───────────── Fonctions partagées : extension par ancre (raise si l'ancre manque) ─────────────

do $$ declare def text;
begin
  -- Motif « money » : « Demande d'argent ou vente de patates ».
  def := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_reason_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position('''money''' in def) = 0 then
    if position('''other''::text' in def) = 0 then raise exception 'content_reports : ancre other introuvable'; end if;
    alter table public.content_reports drop constraint content_reports_reason_check;
    execute 'alter table public.content_reports add constraint content_reports_reason_check '
      || replace(def, '''other''::text', '''other''::text, ''money''::text');
  end if;

  def := pg_get_functiondef('public.report_content(text,text,text,text)'::regprocedure);
  if position('''money''' in def) = 0 then
    if position($a$p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'other')$a$ in def) = 0 then
      raise exception 'report_content : ancre des raisons introuvable';
    end if;
    execute replace(def, $a$p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'other')$a$,
                         $a$p_reason not in ('harassment', 'shocking', 'spam', 'scam', 'money', 'other')$a$);
  end if;

  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position('''money''' in def) = 0 then
    if position($a$when 'scam' then 'Arnaque ou vente'$a$ in def) = 0 then raise exception 'notify_new_report : ancre scam introuvable'; end if;
    execute replace(def, $a$when 'scam' then 'Arnaque ou vente'$a$,
      $a$when 'scam' then 'Arnaque ou vente' when 'money' then 'Demande d''argent ou vente de patates'$a$);
  end if;

  -- Notifications prono_soon et prono_contest : interrupteur pronos, comptes actifs, blocages.
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''prono_soon''' in def) = 0 then
    if position($a$    when 'prono_due' then coalesce(prefs.pronos, true)$a$ in def) = 0 then raise exception 'web_push_allowed : ancre prono_due introuvable'; end if;
    execute replace(def, $a$    when 'prono_due' then coalesce(prefs.pronos, true)$a$, $a$    when 'prono_due' then coalesce(prefs.pronos, true)
    when 'prono_soon' then coalesce(prefs.pronos, true)
    when 'prono_contest' then coalesce(prefs.pronos, true)$a$);
  end if;

  def := pg_get_functiondef('private.may_receive_push(uuid,text)'::regprocedure);
  if position('''prono_soon''' in def) = 0 then
    if position('''prono_due'',' in def) = 0 then raise exception 'may_receive_push : ancre prono_due introuvable'; end if;
    execute replace(def, '''prono_due'',', '''prono_due'', ''prono_soon'', ''prono_contest'',');
  end if;

  def := pg_get_functiondef('private.drop_blocked_notification()'::regprocedure);
  if position('''prono_contest''' in def) = 0 then
    if position('''prono_result'')' in def) = 0 then raise exception 'drop_blocked_notification : ancre prono_result introuvable'; end if;
    execute replace(def, '''prono_result'')', '''prono_result'', ''prono_contest'')');
  end if;
end $$;

notify pgrst, 'reload schema';
