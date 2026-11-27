-- PROD, lot 9 (27.11, contrôle Apple tour 5, Apple 1.2) — migration 20261127120000 : co-organisateur refusé en blocage
-- avec le créateur de l'événement, blocage qui retire les co-organisateurs croisés, join_group_by_link et join_event_by_link
-- refusés en blocage (créateur, auteur du lien ; message neutre), photo jamais demandée dans les messages de profil.
-- ORDRE : APRÈS 2026-11-23-reglages-groupe-admin-apply.sql et 2026-11-26-pot-cgu-signaler-apply.sql (qui redéfinissent
-- join_group_by_link : appliqués après, ils effaceraient ce correctif) et APRÈS 2026-11-27-suppression-blocage-apply.sql
-- (qui crée private.guard_coorganizer_block : sans lui, ce fichier refuse et rien n'est modifié).
-- Testé sur TEST le 27.11 : tests/supabase_live/test_blocage_suite_live.py, test_blocage_coorganisateur_live.py ; retour
-- arrière essayé puis réapplication. Rejouable (rien si déjà fait). Retour arrière : 2026-11-27-blocage-suite-rollback.sql.
begin;
-- Lot 9 (27.11, contrôle Apple tour 5, Apple 1.2), additive et rejouable. Passe APRÈS 20261127110000 (qui crée
-- private.guard_coorganizer_block) et après 20261123110000 / 20261126130000 (qui redéfinissent join_group_by_link).
-- 1. Co-organisateur : refusé aussi quand la personne est en blocage avec le CRÉATEUR de l'événement (un co-organisateur
--    tiers ne peut plus l'ajouter). Service (séries récurrentes, auth.uid() null) : inchangé, pour ne jamais faire
--    échouer private.spawn_series.
-- 2. set_direct_block : quand A bloque B, B quitte les co-organisateurs des événements créés par A, et A ceux des
--    événements créés par B (le créateur n'est jamais touché ; les autres événements, non plus).
-- 3. join_group_by_link : refusé en blocage avec le créateur du groupe ou l'auteur du lien (message neutre).
-- 4. join_event_by_link (ancienne fonction, encore appelable) : même contrôle que accept_invite (créateur, auteur du lien).
-- 5. La photo n'est jamais exigée : « prénom, surnom et photo) » devient « prénom et surnom) » partout où il reste.
-- Toutes les ancres sont vérifiées AVANT la moindre modification : une ancre manquante = rien n'est modifié.

do $patch$
declare
  p record;
  def text;
  defs text[] := '{}';
begin
  for p in select * from (values
    ('private.guard_coorganizer_block()',
     'créateur de l''événement (20261127120000)',
     $a$  if private.blocked_either(auth.uid(), new.user_id) then
$a$,
     $a$  if private.blocked_either(auth.uid(), new.user_id)
     or (auth.uid() is not null and private.blocked_either(
           (select e.created_by from public.events e where e.id = new.event_id), new.user_id)) then -- créateur de l'événement (20261127120000)
$a$),
    ('public.set_direct_block(uuid,boolean)',
     'plus co-organisateurs l''un de l''autre (20261127120000)',
     $a$    insert into public.direct_blocks (user_id, blocked_id) values (auth.uid(), target) on conflict do nothing;
$a$,
     $a$    insert into public.direct_blocks (user_id, blocked_id) values (auth.uid(), target) on conflict do nothing;
    -- plus co-organisateurs l'un de l'autre (20261127120000) : le créateur reste, les autres événements aussi.
    delete from public.event_organizers o using public.events e
      where e.id = o.event_id and o.user_id <> e.created_by
        and ((e.created_by = auth.uid() and o.user_id = target) or (e.created_by = target and o.user_id = auth.uid()));
$a$),
    ('public.join_group_by_link(uuid)',
     'Tu ne peux pas rejoindre ce groupe.',
     $a$  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
$a$,
     $a$  if grp is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  -- En blocage avec le créateur du groupe ou l'auteur du lien : n'entre pas, sans dire qui a bloqué (20261127120000).
  if private.blocked_either(auth.uid(), (select g.created_by from public.member_groups g where g.id = grp))
     or exists (select 1 from public.member_groups g where g.id = grp and g.invite_token = join_group_by_link.token
                  and private.blocked_either(auth.uid(), g.invite_token_by))
     or exists (select 1 from private.invite_links l where l.token = join_group_by_link.token
                  and private.blocked_either(auth.uid(), l.created_by)) then
    raise exception 'Tu ne peux pas rejoindre ce groupe.' using errcode = '42501';
  end if;
$a$),
    ('public.join_event_by_link(uuid)',
     'sans dire qui a bloqué, comme accept_invite (20261127120000)',
     $a$  if ev.id is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
$a$,
     $a$  if ev.id is null then raise exception 'Ce lien d''invitation n''est plus valable'; end if;
  -- En blocage avec l'organisateur ou l'auteur du lien : n'entre pas, sans dire qui a bloqué, comme accept_invite (20261127120000).
  if private.blocked_either(ev.created_by, auth.uid())
     or exists (select 1 from private.invite_links l where l.token = join_event_by_link.token
                  and private.blocked_either(l.created_by, auth.uid())) then
    raise exception 'Tu ne peux pas répondre à cette invitation.' using errcode = '42501';
  end if;
$a$)) v(fn, marker, anchor, repl)
  loop
    if to_regprocedure(p.fn) is null then
      raise exception '% introuvable (appliquer d''abord 20261127110000), rien n''est modifié', p.fn;
    end if;
    def := pg_get_functiondef(p.fn::regprocedure);
    continue when position(p.marker in def) > 0;
    if position(p.anchor in def) = 0 then
      raise exception '% : ancre introuvable, rien n''est modifié', p.fn;
    end if;
    defs := defs || replace(def, p.anchor, p.repl);
  end loop;
  for i in 1 .. coalesce(array_length(defs, 1), 0) loop
    execute defs[i];
  end loop;

  -- 5. Photo facultative (rien à faire si déjà retirée).
  for p in select pr.oid::regprocedure as fn from pg_proc pr join pg_namespace n on n.oid = pr.pronamespace
            where n.nspname in ('public', 'private') and pr.prosrc like '%prénom, surnom et photo)%' loop
    execute replace(pg_get_functiondef(p.fn), 'prénom, surnom et photo)', 'prénom et surnom)');
  end loop;
end $patch$;

insert into supabase_migrations.schema_migrations (version, name) values ('20261127120000', 'blocage_suite') on conflict do nothing;
commit;
