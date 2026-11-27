-- Contact du répertoire inscrit sur Party (recette de nuit du 28.11) : le mini-profil disait « Tu ne peux pas lui écrire
-- pour l'instant » et la personne manquait dans « Tes contacts sur Party ». Cause : member_mini calcule le lien avec
-- private.dm_link(me, id), sans la preuve « contact » ; entre deux comptes Guest (sans events.view, sans Membres VP en
-- commun), seul le contact ouvre une DEMANDE de message (règle des Discussions v2), donc le lien valait « none ».
-- Correction : public.member_mini_contact(target, contact_hash) = member_mini, dont le lien « none » devient celui de
-- private.dm_check(me, target, true) quand l'empreinte du numéro (même clé que contacts_match / open_direct_chat) est
-- juste. Même plafond qu'open_direct_chat : 20 empreintes fausses par 24 h, notées dans private.contact_hash_fails, puis
-- plus aucune n'est essayée (pas de devinette de numéros). Aucune règle ne change : open_direct_chat décidait déjà ainsi.
-- Purement additive et rejouable (nouvelle fonction, create or replace).

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
