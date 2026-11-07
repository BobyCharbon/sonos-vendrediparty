"""Phase « annonces » du banc des bots (base de TEST réglée comme la prod, CGU exigées) : annonces d'événement aux
groupes (décision de l'admin du 06.11.2026, migration 20261106220000), par les vrais écrans.

Bot Olga (organisatrice, simple membre du groupe « Bots ») publie trois événements réservés au groupe « Bots » avec
« Prévenir le groupe » : Bot Ada (créatrice du groupe) accepte le premier, Bot Côme (Co-admin, admin du groupe) refuse
le deuxième, personne ne répond au troisième (48 h simulées en reculant la date de la demande dans la base de TEST,
puis la tâche planifiée). Bot Victor (membre du groupe) n'est prévenu que des annonces parties. Olga publie aussi un
événement PUBLIC (aucun interrupteur, aucune annonce) et un quatrième de groupe SANS annonce, pour le parcours iPhone
(tests/bots/ios/BotsAnnouncementsUITests.swift). Personne de réel n'est prévenu : groupes de bots, quarantaine active.
Usage : .venv/bin/python -m tests.bots.run annonces"""
from __future__ import annotations

from tests.bots.bench import load_state, phone, save_state
from tests.bots.common import BY_KEY, q, sql
from tests.bots.flows import accept_terms_if_asked, audience_invite_groups, day, fill, set_date, submit, toggle

TITLES = {"accept": "Bot Annonce acceptée", "refuse": "Bot Annonce refusée", "silence": "Bot Annonce sans réponse",
          "ios": "Bot Annonce iPhone", "public": "Bot Annonce publique", "proposed": "Bot Annonce groupe à valider"}
REQUEST_SENTENCE = "Ta demande sera envoyée à l’admin du groupe ; sans réponse sous 48 h, l’annonce part automatiquement."


def uid(key: str) -> str:
    return sql(f"select id from public.profiles where phone = {q(BY_KEY[key].phone)}")[0]["id"]


def announcement(eid: str) -> dict:
    rows = sql(f"""select a.status, (select display_name from public.profiles where id = a.answered_by) answered_by
                   from public.event_announcements a where a.event_id = {q(eid)}""")
    return rows[0] if rows else {}


def told(eid: str, key: str, kind: str) -> int:
    return sql(f"""select count(*) n from public.notifications where user_id = {q(uid(key))} and kind = {q(kind)}
                   and (event_id = {q(eid)} or data->>'target_event' = {q(eid)})""")[0]["n"]


def create_for_group(p, title: str, offset: int, announce: bool, public: bool = False, group: str = "Bots") -> str | None:
    """Formulaire « Proposer » : groupe « Bots » (ou public), « Prévenir le groupe » selon announce, puis Publier."""
    page = p.page
    p.goto("/events/event/new")
    p.see(page.get_by_label("Titre", exact=True), "le formulaire")
    fill(p, "Titre", title)
    fill(p, "Description", "Événement de test des bots (banc tests/bots, annonces). Ignorer.")
    set_date(p, "Début", day(offset), "19:30")
    fill(p, "Lieu", "Salle des bots, Vevey")
    if public:
        p.tap(page.get_by_role("button", name="Publique + lien"), "Publique + lien")
        page.wait_for_timeout(800)
        if page.get_by_label("Prévenir le groupe", exact=True).count():
            p.flag("🔴", "« Prévenir le groupe » proposé pour un événement public")
        else:
            p.log("public : pas d'interrupteur « Prévenir le groupe » (attendu)")
    else:
        audience_invite_groups(p, [group])
        sw = page.get_by_label("Prévenir le groupe", exact=True)
        if not p.see(sw, "l'interrupteur « Prévenir le groupe »"):
            p.flag("🔴", "« Prévenir le groupe » absent pour un événement de groupe")
            return None
        if sw.is_checked():
            p.flag("🔴", "« Prévenir le groupe » allumé par défaut")
        if announce:
            toggle(p, "Prévenir le groupe", True)
            if group == "Bots":
                p.expect_or_flag(page.get_by_text(REQUEST_SENTENCE, exact=True), "la phrase « Ta demande sera envoyée à l’admin du groupe… »", "🔴")
        p.shot(f"formulaire-{'annonce' if announce else 'sans-annonce'}")
    return submit(p, "Publier")


def phase_annonces(browser, origin, only):
    state = load_state()
    ids: dict[str, str] = dict(state.get("annonces", {}))

    # 1. L'organisatrice demande (trois fois), publie un public, et un de groupe sans annonce (pour l'iPhone).
    p = phone(browser, "orga1", origin, "annonces-demande")
    try:
        p.sign_in()
        for key, offset, announce, public in (("accept", 20, True, False), ("refuse", 21, True, False),
                                              ("silence", 22, True, False), ("ios", 23, False, False), ("public", 24, False, True)):
            if key in ids:
                continue
            with p.step(f"créer « {TITLES[key]} »"):
                eid = create_for_group(p, TITLES[key], offset, announce, public)
                if eid:
                    ids[key] = eid
                    save_state(annonces=ids)
                    if announce:
                        p.expect_or_flag(p.page.get_by_text("Annonce en attente", exact=False), "« Annonce en attente » sur la fiche", "🔴")
                        p.shot(f"fiche-{key}")
    finally:
        p.close()

    for key in ("accept", "refuse", "silence"):
        if key in ids:
            a = announcement(ids[key])
            p_ok = a.get("status") == "pending" and told(ids[key], "vip1", "private_invite") == 0
            v_ok = told(ids[key], "admin", "announce_request") == 1 and told(ids[key], "coadmin", "announce_request") == 1
            print(f"annonces : {TITLES[key]} → {a} ; membres non prévenus={p_ok} ; Ada et Côme prévenus={v_ok}", flush=True)
            if not (p_ok and v_ok):
                from tests.bots.bench import anomaly
                anomaly("orga1", "🔴", f"demande « {TITLES[key]} » mal ouverte", f"{a} membres_ok={p_ok} valideurs_ok={v_ok}")
    if "public" in ids:
        n = sql(f"select count(*) n from public.event_announcements where event_id = {q(ids['public'])}")[0]["n"]
        print(f"annonces : public → {n} demande(s) (attendu 0)", flush=True)

    # 2. Bot Ada (créatrice du groupe) accepte dans Activité › À valider.
    answer(browser, origin, "admin", ids.get("accept"), TITLES["accept"], accept=True)
    # 3. Bot Côme (Co-admin, admin du groupe) refuse.
    answer(browser, origin, "coadmin", ids.get("refuse"), TITLES["refuse"], accept=False)

    # 4. Sans réponse : 48 h simulées (date de la demande reculée de 49 h dans la base de TEST), puis la tâche planifiée.
    if "silence" in ids:
        sql(f"update public.event_announcements set requested_at = now() - interval '49 hours' where event_id = {q(ids['silence'])} and status = 'pending'")
        n = sql("select private.auto_accept_announcements() n")[0]["n"]
        print(f"annonces : tâche planifiée → {n} annonce(s) partie(s) d'office ; {announcement(ids['silence'])}", flush=True)

    # 5. Ce que voient l'organisatrice et un membre du groupe.
    results(browser, origin, ids)
    # 6. Q3 (06.11) : groupe « Bots 2 » avec validation ; accepter l'événement envoie aussi l'annonce demandée.
    proposed_group_event(browser, origin, ids)
    save_state(annonces=ids)


def proposed_group_event(browser, origin, ids: dict) -> None:
    gid = sql("select id from public.member_groups where name = 'Bots 2'")[0]["id"]
    was = sql(f"select events_need_approval, announce_mode from public.member_groups where id = {q(gid)}")[0]
    sql(f"update public.member_groups set events_need_approval = true, announce_mode = 'request' where id = {q(gid)}")
    try:
        if "proposed" not in ids:
            p = phone(browser, "orga1", origin, "annonces-groupe-a-valider")
            try:
                p.sign_in()
                eid = create_for_group(p, TITLES["proposed"], 25, True, group="Bots 2")
                if eid:
                    ids["proposed"] = eid
                    save_state(annonces=ids)
                    p.expect_or_flag(p.page.get_by_text("En attente de validation du groupe", exact=False), "« En attente de validation du groupe »", "🟠")
                    p.shot("fiche-groupe-a-valider")
            finally:
                p.close()
        eid = ids.get("proposed")
        if not eid:
            return
        before = told(eid, "vip4", "private_invite")
        a = phone(browser, "admin", origin, "annonces-groupe-accepte")
        try:
            a.sign_in()
            a.goto("/events/activity")
            card = a.page.get_by_label(f"Événement à valider : {TITLES['proposed']}, pour Bots 2")
            if a.expect_or_flag(card, "la carte « Événement à valider »", "🔴", timeout=20000):
                a.expect_or_flag(card.get_by_text("accepté, le groupe reçoit aussi la notification", exact=False), "la phrase « le groupe reçoit aussi la notification »", "🟠")
                a.shot("evenement-a-valider")
                a.tap(card.get_by_role("button", name="Accepter"), "Accepter (événement + annonce)")
                a.page.wait_for_timeout(2500)
                a.shot("evenement-accepte")
        finally:
            a.close()
        ann = announcement(eid)
        after = told(eid, "vip4", "private_invite")
        extra = sql(f"select count(*) n from public.notifications where kind = 'announce_request' and data->>'target_event' = {q(eid)}")[0]["n"]
        print(f"annonces : Q3 → annonce {ann} ; Violette prévenue {before} → {after} (attendu 0 → 1) ; seconde demande {extra} (attendu 0)", flush=True)
        if ann.get("status") != "accepted" or after != 1 or before != 0 or extra:
            from tests.bots.bench import anomaly
            anomaly("admin", "🔴", "accepter l'événement n'envoie pas l'annonce demandée (Q3)", f"{ann} {before}->{after} demandes={extra}")
    finally:
        sql(f"update public.member_groups set events_need_approval = {str(was['events_need_approval']).lower()}, "
            f"announce_mode = {q(was['announce_mode'])} where id = {q(gid)}")


def answer(browser, origin, key: str, eid: str | None, title: str, accept: bool) -> None:
    if not eid:
        return
    p = phone(browser, key, origin, f"annonces-{'accepte' if accept else 'refuse'}")
    page = p.page
    try:
        p.sign_in()
        p.goto("/events/activity")
        accept_terms_if_asked(p)
        card = page.get_by_label(f"Annonce à valider : {title}, pour Bots")
        if not p.expect_or_flag(card, f"la carte « Annonce à valider : {title} »", "🔴", timeout=20000):
            return
        p.expect_or_flag(card.get_by_text(f"On t’invite à « {title} » avec le groupe Bots.", exact=True), "l'aperçu du message", "🟠")
        p.shot("a-valider")
        p.tap(card.get_by_role("button", name="Accepter" if accept else "Refuser"), "Accepter" if accept else "Refuser")
        page.wait_for_timeout(2500)
        sentence = "C’est parti : Bots est prévenu." if accept else "Refusé : Bots n’est pas prévenu, l’événement reste visible."
        p.expect_or_flag(page.get_by_text(sentence, exact=True), f"« {sentence} »", "🟠")
        p.shot("repondu")
        a = announcement(eid)
        p.log(f"base : {a}")
        if a.get("status") != ("accepted" if accept else "refused"):
            p.flag("🔴", f"la réponse de {BY_KEY[key].nickname} n'est pas enregistrée", str(a))
    finally:
        p.close()


def results(browser, origin, ids: dict) -> None:
    expected = {"accept": ("Annonce envoyée (acceptée par Bot Ada)", 1, "announce_accepted"),
                "refuse": ("Annonce refusée par Bot Côme", 0, "announce_refused"),
                "silence": ("Annonce envoyée (sans réponse en 48 h)", 1, "announce_accepted")}
    p = phone(browser, "orga1", origin, "annonces-statuts")
    try:
        p.sign_in()
        for key, (status, invites, kind) in expected.items():
            if key not in ids:
                continue
            with p.step(f"statut de « {TITLES[key]} »"):
                p.goto(f"/events/event/{ids[key]}")
                p.expect_or_flag(p.page.get_by_text(status, exact=False), f"« {status} » sur la fiche", "🔴")
                p.shot(f"statut-{key}")
            got = told(ids[key], "vip1", "private_invite")
            mine = told(ids[key], "orga1", kind)
            print(f"annonces : {TITLES[key]} → Victor prévenu {got} fois (attendu {invites}) ; Olga « {kind} » {mine} (attendu 1)", flush=True)
            if got != invites or mine != 1:
                p.flag("🔴", f"notifications de « {TITLES[key]} » inattendues", f"victor={got} olga={mine}")
        p.goto("/events/activity")
        for text in ("Ton annonce a été acceptée", "Ton annonce a été refusée", "Ton annonce est partie"):
            p.expect_or_flag(p.page.get_by_text(text, exact=True).first, f"« {text} » dans Activité", "🟠")
        p.shot("activite-organisatrice")
    finally:
        p.close()
    v = phone(browser, "vip1", origin, "annonces-membre")
    try:
        v.sign_in()
        if "refuse" in ids:  # refusée : pas de notification, mais l'événement reste visible par le groupe
            v.goto(f"/events/event/{ids['refuse']}")
            v.expect_or_flag(v.page.get_by_text(TITLES["refuse"], exact=True).first, "l'événement refusé reste visible", "🔴")
            v.shot("refuse-visible")
        v.goto("/events/activity")
        v.shot("activite-membre")
    finally:
        v.close()
