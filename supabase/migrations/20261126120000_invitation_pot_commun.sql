-- Pot commun dit sur la page d'invitation (contrôle Apple du 26.11, 5.1.2) : invite_preview renvoie aussi `pot_enabled`,
-- pour que « Je viens ! » dise, comme la fiche, qu'en répondant Présent on entre dans le pot commun de l'événement.
-- Additive et rejouable : la fonction existante est ÉTENDUE (même définition, une clé de plus), rien d'autre ne change.
do $$
declare def text;
begin
  def := pg_get_functiondef('public.invite_preview(uuid, boolean)'::regprocedure);
  if position('''pot_enabled''' in def) = 0 then
    if position($a$'allow_maybe', ev.allow_maybe,$a$ in def) = 0 then
      raise exception 'invite_preview : ancre allow_maybe introuvable';
    end if;
    execute replace(def, $a$'allow_maybe', ev.allow_maybe,$a$, $a$'allow_maybe', ev.allow_maybe,
    'pot_enabled', coalesce(ev.pot_enabled, false),$a$);
  end if;
end $$;
