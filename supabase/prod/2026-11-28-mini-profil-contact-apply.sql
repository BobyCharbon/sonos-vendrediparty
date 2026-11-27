-- PROD, mini-profil d'un contact du répertoire (20261128090000, recette de nuit du 28.11) : pour un contact de l'iPhone
-- inscrit sur Party, « Envoyer un message » propose la demande de message au lieu d'être grisé, et la personne apparaît
-- dans « Tes contacts sur Party ». Nouvelle fonction seulement (aucune ancre, aucune fonction existante modifiée).
-- Testé sur TEST le 28.11 (deux comptes Guest : member_mini « none », empreinte juste « request », empreinte fausse
-- « none » + 1 échec noté, sans empreinte « none »). Retour arrière : 2026-11-28-mini-profil-contact-rollback.sql.
-- Seulement après le « Ok prod » de l'admin, AVEC le serveur (app/chat_rpc.py : RELAY) et le nouveau build iPhone.
begin;
create or replace function public.member_mini_contact(target uuid, contact_hash text) returns jsonb
language plpgsql volatile security definer set search_path = '' as $$
declare me uuid := auth.uid(); m jsonb; ok boolean;
begin
  m := public.member_mini(target);
  if m is null or coalesce(m ->> 'link', 'none') <> 'none' or coalesce((m ->> 'blocked_me')::boolean, false)
     or coalesce((m ->> 'blocked')::boolean, false)
     or nullif(btrim(coalesce(contact_hash, '')), '') is null
     or (select count(*) from private.contact_hash_fails f where f.user_id = me and f.at > now() - interval '24 hours') >= 20 then
    return m;
  end if;
  ok := contact_hash ~ '^[0-9a-f]{64}$' and exists (
    select 1 from public.profiles p, private.contact_key k
    where p.id = target and k.id = 1 and p.phone ~ '^[1-9][0-9]{7,14}$'
      and encode(extensions.hmac('+' || p.phone, k.key, 'sha256'), 'hex') = contact_hash);
  if not ok then
    insert into private.contact_hash_fails (user_id) values (me);
    return m;
  end if;
  return jsonb_set(m, '{link}', to_jsonb(coalesce(private.dm_check(me, target, true) ->> 'link', 'none')));
end $$;

revoke all on function public.member_mini_contact(uuid, text) from public, anon;
grant execute on function public.member_mini_contact(uuid, text) to authenticated;
insert into supabase_migrations.schema_migrations (version, name) values ('20261128090000', 'mini_profil_contact') on conflict do nothing;
commit;
