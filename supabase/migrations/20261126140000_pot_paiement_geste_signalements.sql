-- Contrôle Apple du 26.11.2026, tour 2 (côté base). Purement additive et rejouable ; tout est ÉTENDU par ancre sur la
-- définition en place (jamais réécrit), valable sur la prod (ancres vérifiées en lecture seule le 26.11) comme sur TEST.
-- Passe APRÈS 20261126130000_pot_commun_cgu_signaler.sql.
--
-- 1. Pot commun : la décision de l'admin est gardée (les « Présent » d'un événement sont ajoutés d'office au pot), MAIS
--    les moyens de paiement d'un membre (IBAN, titulaire, liens, note) ne sont montrés aux autres qu'avec SON geste :
--    colonne public.tc_members.show_payment (vrai pour qui a créé le pot, l'a rejoint par son lien ou a repris un prénom ;
--    faux pour qui est ajouté par la base, tc_event_sync, ou par un autre membre) et public.tc_set_show_payment(p_group, p_on).
--    Le nom reste visible. Lecture : tc_group_json (« payment » des autres seulement si show_payment, champ
--    « show_payment » de chaque membre) et la politique RLS de public.tc_payment.
-- 2. Photos et vocaux de la discussion d'un événement (chat-photos/<événement>/) : seulement à qui est dans la discussion
--    (private.event_chat_member : Présent / Peut-être et l'organisation), plus à quiconque « voit » l'événement.
-- 3. Signaler le NOM d'un groupe : type 'group' (report_content, cible = id du groupe, membres et qui le gère ; jamais
--    Membres Vendredi Party) ; « Masquer » remplace le nom par « Groupe renommé par la modération ».
-- 4. Ticket d'une dépense signalée (tc_expense) : copié dans moderation-evidence au signalement (comme un message), et
--    lisible par les modérateurs tant que le signalement est ouvert (politique de stockage sur tc-receipts).

-- 1. Pot commun : moyens de paiement montrés par geste ---------------------------------------------------------------------
do $$
begin
  if not exists (select 1 from information_schema.columns
                 where table_schema = 'public' and table_name = 'tc_members' and column_name = 'show_payment') then
    alter table public.tc_members add column show_payment boolean not null default false;
    -- Existant : vrai pour le créateur du pot et pour tout compte d'un pot SANS événement (entré par le lien ou en le
    -- créant) ; faux pour les autres membres d'un pot d'événement (ajoutés d'office par la base).
    update public.tc_members m set show_payment = true
      from public.tc_groups g
      where g.id = m.group_id and m.user_id is not null and (m.user_id = g.created_by or g.event_id is null);
  end if;
end $$;

-- Contrat (web : rpc tc_set_show_payment({p_group, p_on}) ; iPhone : POST /api/account/tricount/show-payment).
drop function if exists public.tc_set_show_payment(uuid, boolean);
create or replace function public.tc_set_show_payment(p_group uuid, p_on boolean) returns boolean
language plpgsql security definer set search_path = '' as $$
begin
  if auth.uid() is null then raise exception 'forbidden: connecte-toi' using errcode = '42501'; end if;
  update public.tc_members set show_payment = coalesce(p_on, false)
    where group_id = p_group and user_id = auth.uid() and left_at is null;
  if not found then raise exception 'forbidden: tu ne fais pas partie de ce pot' using errcode = '42501'; end if;
  return coalesce(p_on, false);
end $$;
revoke all on function public.tc_set_show_payment(uuid, boolean) from public, anon;
grant execute on function public.tc_set_show_payment(uuid, boolean) to authenticated;

drop policy if exists "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment;
create policy "tricount : son profil de paiement et celui de ses co-membres" on public.tc_payment for select to authenticated
  using (user_id = (select auth.uid()) or exists (
    select 1 from public.tc_members mine join public.tc_members theirs on theirs.group_id = mine.group_id
    where mine.user_id = (select auth.uid()) and mine.left_at is null
      and theirs.user_id = tc_payment.user_id and theirs.left_at is null and theirs.show_payment));

do $$ declare def text;
begin
  def := pg_get_functiondef('private.tc_group_json(uuid)'::regprocedure);
  if position('m.show_payment' in def) = 0 then
    if position($a$'left', m.left_at is not null,$a$ in def) = 0
       or position($a$'payment', case when m.user_id is not null and m.left_at is null then$a$ in def) = 0 then
      raise exception 'tc_group_json : ancres left / payment introuvables';
    end if;
    def := replace(def, $a$'left', m.left_at is not null,$a$, $a$'left', m.left_at is not null, 'show_payment', m.show_payment,$a$);
    def := replace(def, $a$'payment', case when m.user_id is not null and m.left_at is null then$a$,
      $a$'payment', case when m.user_id is not null and m.left_at is null and (m.show_payment or m.user_id = auth.uid()) then$a$);
    execute def;
  end if;

  def := pg_get_functiondef('private.tc_event_sync(uuid)'::regprocedure);
  if position('show_payment' in def) = 0 then
    if position(E'  insert into public.tc_members (group_id, user_id, name)\n  select grp, ev.created_by, left(' in def) = 0 then
      raise exception 'tc_event_sync : ancre organisateur introuvable';
    end if;
    -- L'organisateur a créé le pot (il l'a activé) : ses moyens de paiement sont montrés ; les présents, non.
    execute replace(def, E'  insert into public.tc_members (group_id, user_id, name)\n  select grp, ev.created_by, left(',
                         E'  insert into public.tc_members (group_id, user_id, show_payment, name)\n  select grp, ev.created_by, true, left(');
  end if;

  def := pg_get_functiondef('public.tc_create(text,text,text,text)'::regprocedure);
  if position('show_payment' in def) = 0 then
    if position('insert into public.tc_members (group_id, user_id, name) values (grp, auth.uid(), btrim(my_name));' in def) = 0 then
      raise exception 'tc_create : ancre insert introuvable';
    end if;
    execute replace(def, 'insert into public.tc_members (group_id, user_id, name) values (grp, auth.uid(), btrim(my_name));',
                         'insert into public.tc_members (group_id, user_id, name, show_payment) values (grp, auth.uid(), btrim(my_name), true);');
  end if;

  def := pg_get_functiondef('public.tc_join(uuid,text,uuid)'::regprocedure);
  if position('show_payment' in def) = 0 then
    if position('update public.tc_members set left_at = null where id = existing;' in def) = 0
       or position('update public.tc_members set user_id = auth.uid() where id = claim' in def) = 0
       or position('insert into public.tc_members (group_id, user_id, name) values (grp, auth.uid(), btrim(my_name));' in def) = 0 then
      raise exception 'tc_join : ancres introuvables';
    end if;
    -- Revenir après être parti, reprendre un prénom ou entrer par le lien : son geste. Déjà membre (ajouté d'office) qui
    -- rouvre le lien : rien ne change.
    def := replace(def, 'update public.tc_members set left_at = null where id = existing;',
                        'update public.tc_members set show_payment = show_payment or left_at is not null, left_at = null where id = existing;');
    def := replace(def, 'update public.tc_members set user_id = auth.uid() where id = claim',
                        'update public.tc_members set user_id = auth.uid(), show_payment = true where id = claim');
    def := replace(def, 'insert into public.tc_members (group_id, user_id, name) values (grp, auth.uid(), btrim(my_name));',
                        'insert into public.tc_members (group_id, user_id, name, show_payment) values (grp, auth.uid(), btrim(my_name), true);');
    execute def;
  end if;
end $$;

-- 2. Photos et vocaux d'un événement : seulement à qui est dans la discussion ----------------------------------------------
-- La règle de stockage s'évalue avec le rôle de la personne : sans ce droit, TOUTE lecture du stockage échouait
-- (« permission denied for function event_chat_member »). Le schéma private n'est pas exposé par l'API.
grant execute on function private.event_chat_member(uuid, uuid) to authenticated;
drop policy if exists "voir les photos d'un événement" on storage.objects;
create policy "voir les photos d'un événement" on storage.objects for select to authenticated
  using (bucket_id = 'chat-photos' and (storage.foldername(name))[1] ~ '^[0-9a-f-]{36}$'
         and exists (select 1 from public.events ev where ev.id = ((storage.foldername(name))[1])::uuid)
         and private.event_chat_member(((storage.foldername(name))[1])::uuid, (select auth.uid())));

-- 3 et 4. Signalements : nom d'un groupe, ticket d'une dépense ----------------------------------------------------------------
create or replace function private.group_report_snapshot(uid uuid, viewer uuid) returns jsonb
language sql stable security definer set search_path = '' as $$
  select jsonb_build_object('owner', mg.created_by, 'text', mg.name, 'group_id', mg.id, 'place', 'Nom du groupe')
  from public.member_groups mg
  where mg.id = uid and mg.system_key is null
    and (private.in_group(mg.id, viewer) or mg.created_by = viewer or private.manages_group(mg.id));
$$;
revoke all on function private.group_report_snapshot(uuid, uuid) from public, anon, authenticated;

-- Ticket d'une dépense signalée et encore ouverte : lisible par les modérateurs (lien signé du serveur).
create or replace function private.tc_receipt_reported(path text) returns boolean
language sql stable security definer set search_path = '' as $$
  select exists (select 1 from public.content_reports r
                 where r.target_kind = 'tc_expense' and r.status = 'open' and r.snapshot ->> 'photo_path' = path);
$$;
revoke all on function private.tc_receipt_reported(text) from public, anon;
grant execute on function private.tc_receipt_reported(text) to authenticated;

drop policy if exists "modération : voir un ticket signalé" on storage.objects;
create policy "modération : voir un ticket signalé" on storage.objects for select to authenticated
  using (bucket_id = 'tc-receipts' and (select public.has_perm('moderation.reports')) and private.tc_receipt_reported(name));

do $$ declare def text;
begin
  def := pg_get_constraintdef((select oid from pg_constraint where conname = 'content_reports_target_kind_check'
                                and conrelid = 'public.content_reports'::regclass));
  if position('''group''::text' in def) = 0 then
    if position('''pet_word''::text' in def) = 0 then raise exception 'content_reports : ancre pet_word introuvable'; end if;
    alter table public.content_reports drop constraint content_reports_target_kind_check;
    execute 'alter table public.content_reports add constraint content_reports_target_kind_check '
      || replace(def, '''pet_word''::text', '''pet_word''::text, ''group''::text');
  end if;

  def := pg_get_functiondef('private.report_snapshot(text,text,uuid)'::regprocedure);
  if position('group_report_snapshot' in def) = 0 then
    if position($a$  elsif p_kind in ('profile', 'profile_photo') then$a$ in def) = 0 then raise exception 'report_snapshot : ancre profile introuvable'; end if;
    execute replace(def, $a$  elsif p_kind in ('profile', 'profile_photo') then$a$, $a$  elsif p_kind = 'group' then
    return private.group_report_snapshot(uid, viewer);
  elsif p_kind in ('profile', 'profile_photo') then$a$);
  end if;

  def := pg_get_functiondef('private.moderation_hide(public.content_reports)'::regprocedure);
  if position($a$r.target_kind = 'group' then$a$ in def) = 0 then
    if position($a$  elsif r.target_kind = 'profile' then$a$ in def) = 0 then raise exception 'moderation_hide : ancre profile introuvable'; end if;
    execute replace(def, $a$  elsif r.target_kind = 'profile' then$a$, $a$  elsif r.target_kind = 'group' then
    update public.member_groups set name = 'Groupe renommé par la modération' where id = uid and system_key is null;
  elsif r.target_kind = 'profile' then$a$);
  end if;

  def := pg_get_functiondef('private.notify_new_report()'::regprocedure);
  if position($a$new.target_kind = 'group' then$a$ in def) = 0 then
    if position($a$else 'Zicou' end)$a$ in def) = 0 then raise exception 'notify_new_report : ancre Zicou introuvable'; end if;
    execute replace(def, $a$else 'Zicou' end)$a$, $a$when new.target_kind = 'group' then 'le nom d''un groupe'
                        else 'Zicou' end)$a$);
  end if;

  def := pg_get_functiondef('private.notify_content_hidden(public.content_reports)'::regprocedure);
  if position($a$r.target_kind = 'group' then$a$ in def) = 0 then
    if position($a$               when r.target_kind = 'group_photo' then 'La photo de ton groupe a été retirée'$a$ in def) = 0 then
      raise exception 'notify_content_hidden : ancre group_photo introuvable';
    end if;
    execute replace(def, $a$               when r.target_kind = 'group_photo' then 'La photo de ton groupe a été retirée'$a$,
      $a$               when r.target_kind = 'group_photo' then 'La photo de ton groupe a été retirée'
               when r.target_kind = 'group' then 'Le nom de ton groupe a été remplacé'$a$);
  end if;

  -- Ticket d'une dépense : copié comme la photo d'un message (preuve gardée même si la dépense est effacée).
  def := pg_get_functiondef('public.report_content(text,text,text,text,boolean)'::regprocedure);
  if position($a$(is_msg or p_kind = 'tc_expense')$a$ in def) = 0 then
    if position($a$  if is_msg and (snap ->> 'photo_path' is not null or snap ->> 'audio_path' is not null) then$a$ in def) = 0 then
      raise exception 'report_content : ancre preuve introuvable';
    end if;
    execute replace(def, $a$  if is_msg and (snap ->> 'photo_path' is not null or snap ->> 'audio_path' is not null) then$a$,
      $a$  if (is_msg or p_kind = 'tc_expense') and (snap ->> 'photo_path' is not null or snap ->> 'audio_path' is not null) then$a$);
  end if;

  def := pg_get_functiondef('private.moderation_copy_evidence(uuid,jsonb)'::regprocedure);
  if position('tc-receipts' in def) = 0 then
    if position($a$'bucketId', 'chat-photos'$a$ in def) = 0 then raise exception 'moderation_copy_evidence : ancre chat-photos introuvable'; end if;
    execute replace(def, $a$'bucketId', 'chat-photos'$a$,
      $a$'bucketId', case when snap ->> 'bucket' = 'tc-receipts' then 'tc-receipts' else 'chat-photos' end$a$);
  end if;
end $$;
revoke all on function private.report_snapshot(text, text, uuid) from public, anon, authenticated;
revoke all on function private.moderation_hide(public.content_reports) from public, anon, authenticated;
revoke all on function private.moderation_copy_evidence(uuid, jsonb) from public, anon, authenticated;
