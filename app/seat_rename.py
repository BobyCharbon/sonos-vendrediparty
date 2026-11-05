"""Une place de jeu change d'identifiant : le téléphone d'un invité se connecte à son compte Party (avis 6bad207324a3).

Avant, la place restait à l'identifiant d'invité et le compte n'en recevait qu'un alias : la partie suivante lancée
depuis une salle, le Purify Test (réservé aux comptes), la liste des invités… voyaient alors deux personnes.
Désormais la place est renommée pour de bon, partout dans l'état de la partie (sous GAMES_LOCK, par l'appelant).

Inventaire des états indexés par identifiant (guest_id), jeu par jeu — tous couverts par le renommage générique
ci-dessous, vérifié par tests/test_seat_rename.py (aucune trace de l'ancien identifiant après renommage) :
- toutes les parties : players[].id, host, leads, kicked, removed, votes (clés et cibles), order, candidates,
  last (éliminé), tally, sips_log[].gid, aliases (cibles) ;
- salle de jeux : rvotes, rtally, rpts, rnames ;
- Undercover / Qui de nous ? / Je n'ai jamais : votes, order, candidates, last ;
- Blackjack : bj.seats, bj.hands, bj.chips, bj.rebuys ; Casino : casino.bets, chips, rebuys, stack, ready, results ;
- Le Divan : divan.hearts, divan.back[].by ; Tu me connais ? : tmc.duo (guesser, subject, answers), tmc.scores,
  tmc.pairs (clés « devin>sujet »), tmc.names, tmc.last ;
- Pyramide : pyr.order, hands, queue, late, last, claims[].gid, reveal, peeks[].gid, top, liars, memory, errors… ;
- Biskit : bk.order, await (gid, for), duel (a, b), reflex.taps, dice.roller… ;
- Quiz : quiz.scores, quiz.personal, quiz.cur (answers, locked, winner) ;
- Purify : purity.answers, submitted, scores ; Qui es-tu vraiment ? : psy.answers, psy.done ;
- Qui est le plus… ? : likely.voters, votes (clés et cibles), skipped, scores, result.counts / winners ;
- Pour ou contre : debate.voters, votes, skipped, first, proposals[].gid ;
- Le Masque : masque.answers, slots[].gid, authors[].gid, guessers, guesses (clés et valeurs), unmask, sent, scores,
  result / history (_author, _found) ;
- Le Reflet : reflet.passes, votes, skipped, scores, history[].gid ;
- Président : president (mains, ordre, échanges, pile.by, trail[].by…) ;
- Beer pong : bp.teams, bp.pending.gid ; Néon, L'île, Braquage : leurs scores et corps sont indexés par pid (public,
  inchangé), seuls players / host / leads changent.
Le renommage parcourt tout l'état : un champ ajouté plus tard à un jeu est couvert sans changer cette liste.

Sécurité : l'identifiant d'invité est choisi par le téléphone. Remplacer une chaîne partout n'est sûr que si elle ne
peut désigner rien d'autre qu'un joueur : l'ancien identifiant doit donc avoir la forme de ceux que l'app génère
(au moins 12 caractères, un chiffre), ne jamais être un compte (acct-…) ni un participant ajouté à la main
(manual-…), ni l'identifiant public d'un joueur ou de la partie. Sinon on garde l'ancien comportement (alias).
"""

MIN_ID_LENGTH = 12  # crypto.randomUUID (36) ou repli de l'app (base 36 + Date.now(), plus de 13)
PAIR_SEPARATOR = ">"  # Tu me connais ? : tmc.pairs["devin>sujet"]


def _id_shaped(gid: str) -> bool:
    return len(gid) >= MIN_ID_LENGTH and any(c.isdigit() for c in gid)


def can_rename(g: dict, old: str, new: str) -> bool:
    """La place de old peut devenir celle de new dans cette partie."""
    if not old or not new or old == new or old.startswith(("acct-", "manual-")) or not _id_shaped(old):
        return False
    players = g.get("players") or []
    seat = next((p for p in players if p["id"] == old), None)
    if seat is None or seat.get("manual") or any(p["id"] == new for p in players):
        return False
    if new in (g.get("kicked") or []):
        return False  # le compte est banni de cette partie : il n'hérite pas d'une place
    public = {g.get("id"), g.get("code")} | {p.get("pid") for p in players}
    return old not in public


def _key(key, old: str, new: str):
    if key == old:
        return new
    if isinstance(key, str) and PAIR_SEPARATOR in key:
        parts = key.split(PAIR_SEPARATOR)
        if old in parts:
            return PAIR_SEPARATOR.join(new if part == old else part for part in parts)
    return key


def _merge(primary, other):
    """Deux entrées pour la même personne (ex. points de salle gagnés avant et après la connexion) : on additionne
    les compteurs ; sinon celle du compte l'emporte."""
    number = (int, float)
    if isinstance(primary, number) and isinstance(other, number) and not isinstance(primary, bool) and not isinstance(other, bool):
        return primary + other
    if isinstance(primary, dict) and isinstance(other, dict):
        merged = dict(primary)
        for k, v in other.items():
            merged[k] = _merge(merged[k], v) if k in merged else v
        return merged
    return primary


def _rename_dict(d: dict, old: str, new: str):
    renamed: dict = {}
    for k, v in list(d.items()):
        nk = _key(k, old, new)
        _rename_in(v, old, new)
        if nk not in renamed:
            renamed[nk] = v
        elif nk == k:  # la clé déjà au nom du compte arrive après celle renommée : elle reste prioritaire
            renamed[nk] = _merge(v, renamed[nk])
        else:
            renamed[nk] = _merge(renamed[nk], v)
    d.clear()  # sur place : d'autres références (ex. Masque : result et history) pointent sur le même objet
    d.update(renamed)


def _rename_list(items: list, old: str, new: str):
    has_new = any(x == new for x in items if isinstance(x, str))
    out = []
    for x in items:
        if x == old and isinstance(x, str):
            if not has_new:  # déjà présent (liste d'identifiants) : pas de doublon
                out.append(new)
            continue
        _rename_in(x, old, new)
        out.append(x)
    items[:] = out


def _rename_in(node, old: str, new: str):
    if isinstance(node, dict):
        _rename_dict(node, old, new)
        for k, v in list(node.items()):
            if isinstance(v, str) and v == old:
                node[k] = new
    elif isinstance(node, list):
        _rename_list(node, old, new)


def rename_player(g: dict, old: str, new: str) -> bool:
    """Renomme la place old en new dans toute la partie (appelant : sous GAMES_LOCK). Les alias qui menaient à old
    mènent à new, et old lui-même devient un alias de new (un onglet resté ouvert sur l'ancienne identité continue
    de jouer la même place). Renvoie False si rien n'a été renommé (voir can_rename)."""
    if not can_rename(g, old, new):
        return False
    aliases = g.pop("aliases", None) or {}
    _rename_in(g, old, new)
    kept = {a: (new if o == old else o) for a, o in aliases.items() if a not in (old, new)}
    g["aliases"] = {**kept, old: new}
    return True
