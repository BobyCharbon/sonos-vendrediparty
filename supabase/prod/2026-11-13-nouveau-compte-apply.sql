-- PROD, nouveau_compte (20261113100000). À appliquer SEULEMENT après un « Ok prod » donné pour CETTE migration.
-- Rejouable. Tout ou rien. Aucune donnée modifiée : une colonne (notification_prefs.member_signups, allumée),
-- un déclencheur sur profiles (« Nouveau compte » à ceux qui valident les membres), deux filtres de push complétés.
begin;
-- « Nouveau compte » pour les admins (avis 662065a54b22 de l'admin, 12.11.2026) : quand une personne a fini de créer son
-- compte (numéro vérifié, prénom, nom et surnom remplis), ceux qui valident les membres (droit members.approve) sont
-- prévenus. Un interrupteur dans Réglages › Notifications (notification_prefs.member_signups, allumé par défaut), respecté
-- par tous les canaux (règle : toute notification se coupe). Une seule fois par compte (clé member_signup:<id>).
-- Purement additive et rejouable.

alter table public.notification_prefs add column if not exists member_signups boolean not null default true;

create or replace function private.notify_member_signup() returns trigger
language plpgsql security definer set search_path = '' as $$
declare u uuid; who text;
begin
  if coalesce(btrim(new.first_name), '') = '' or coalesce(btrim(new.last_name), '') = ''
     or coalesce(btrim(new.display_name), '') = '' then
    return null;
  end if;
  if tg_op = 'UPDATE' and coalesce(btrim(old.first_name), '') <> '' and coalesce(btrim(old.last_name), '') <> ''
     and coalesce(btrim(old.display_name), '') <> '' then
    return null;  -- déjà complet avant : pas un nouveau compte
  end if;
  who := btrim(new.display_name) || ' (' || btrim(new.first_name) || ' ' || btrim(new.last_name) || ')';
  for u in select p.id from public.profiles p
           where p.status = 'active' and p.id <> new.id and private.user_has(p.id, 'members.approve') loop
    perform public.queue_notification(u, 'member_signup', null, '👋 Nouveau compte', left(who, 120) || ' vient de créer son compte.',
      'member_signup:' || new.id, jsonb_build_object('member', new.id, 'url', '/?tab=account'));
  end loop;
  return null;
end $$;
revoke all on function private.notify_member_signup() from public, anon, authenticated;
drop trigger if exists profiles_member_signup on public.profiles;
create trigger profiles_member_signup after insert or update of first_name, last_name, display_name on public.profiles
  for each row execute function private.notify_member_signup();

-- Interrupteur respecté partout (push web, iPhone) ; reçu par les comptes qui ont le droit (même Guest+ éventuel).
do $$ declare def text; anchor text := $a$    when 'link_join' then prefs.link_join$a$;
begin
  def := pg_get_functiondef('private.web_push_allowed(public.notifications)'::regprocedure);
  if position('''member_signup''' in def) = 0 then
    if position(anchor in def) = 0 then raise exception 'web_push_allowed : ancre link_join introuvable'; end if;
    def := replace(def, anchor, anchor || $a$
    when 'member_signup' then coalesce(prefs.member_signups, true)$a$);
    execute def;
  end if;
  def := pg_get_functiondef('private.may_receive_push(uuid, text)'::regprocedure);
  if position('''member_signup''' in def) = 0 then
    if position('''link_join'',' in def) = 0 then raise exception 'may_receive_push : ancre link_join introuvable'; end if;
    def := replace(def, '''link_join'',', '''link_join'', ''member_signup'',');
    execute def;
  end if;
end $$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261113100000', 'nouveau_compte') on conflict do nothing;
commit;
