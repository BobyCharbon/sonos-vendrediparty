-- Zicou sur la fiche profil (avis de l'admin, 4 novembre 2026) : « depuis n'importe où, si on clique sur le profil d'une
-- personne, on doit voir son Zicou » ; sans Zicou, un œuf terne qui donne envie d'en avoir un.
-- Purement additif et rejouable. Prérequis : 20261104210000 (Compagnon, collection : pet_friends_of sans les bloqués)
-- et 20261104200000 (blocage commun : private.blocked_either).
--
-- public.pet_profile(p_member, p_key) : lue SEULEMENT par le serveur Party (clé du serveur, comme pet_load), qui n'en
-- renvoie que l'apparence publique (app/pet_profile.py : stade, humeur, tenue, shiny, génération, âge ; jamais jauges,
-- pièces ni inventaire). Visible par tout membre actif qui peut ouvrir la fiche (public.member_card), sauf blocage dans
-- un sens ou l'autre : null (le serveur répond 404, sans dire pourquoi). Jamais owner ; le titre de vitrine (texte
-- d'un joueur) est retiré. « friend » : visite possible (même règle que pet_friend) ; « mine » : le lecteur a un Zicou.

create or replace function public.pet_profile(p_member uuid, p_key text default null) returns jsonb
language plpgsql stable security definer set search_path = '' as $$
declare
  me uuid := private.pet_server_guard(p_key);
  l jsonb;
begin
  if p_member is null or private.blocked_either(me, p_member)
     or not exists (select 1 from public.profiles where id = p_member and status = 'active') then
    return null;
  end if;
  select p.life into l from public.pets p where p.user_id = p_member and p.stage <> 'dead';
  if l ? 'showcase' and jsonb_typeof(l -> 'showcase') = 'object' then
    l := jsonb_set(l, '{showcase,title}', '""');
  end if;
  return jsonb_build_object(
    'life', l,
    'me', p_member = me,
    'friend', p_member <> me and l is not null
              and exists (select 1 from private.pet_friends_of(me) f where f = p_member),
    'mine', exists (select 1 from public.pets p where p.user_id = me and p.stage <> 'dead'));
end;
$$;
revoke all on function public.pet_profile(uuid, text) from public, anon;
grant execute on function public.pet_profile(uuid, text) to authenticated;

notify pgrst, 'reload schema';
