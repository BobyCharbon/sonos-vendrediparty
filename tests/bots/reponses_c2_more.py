"""Campagne 2, agent 04 (suite) : sondage de dates, mini-sondage, qui amène quoi, forum, agenda .ics, dernière place
prise en même temps par 3 bots. Lancé par tests.bots.reponses_c2 (même ligne de commande)."""
from __future__ import annotations

import asyncio
import re
import threading
import urllib.parse

import httpx

from tests.bots import flows as f
from tests.bots.bench import load_state, phone, save_state
from tests.bots.common import BY_KEY, sql
from tests.bots.reponses_c2 import api, check_counts, ev, mine, open_event, rows, tap_rsvp

VOTE = {"Oui": "yes", "Si besoin": "if_needed", "Non": "no"}


def _slots(p) -> list[str]:
    labels = p.page.get_by_role("button", name=re.compile(r"^Oui : ")).all()
    return [b.get_attribute("aria-label").split(" : ", 1)[1] for b in labels]


def _votes(event_key: str) -> list[dict]:
    return sql(f"""select p.display_name name, o.starts_at, v.vote from public.date_votes v
                   join public.date_options o on o.id = v.option_id join public.profiles p on p.id = v.user_id
                   where o.event_id = '{ev(event_key)}' order by 2, 1""")


def _vote_round(browser, origin, event_key: str, plan: dict) -> None:
    for key, answers in plan.items():
        p = phone(browser, key, origin, f"c2-{event_key}")
        page = p.page
        try:
            open_event(p, event_key)
            with p.step("voter sur chaque créneau"):
                for slot, a in zip(_slots(p), answers):
                    p.tap(page.get_by_role("button", name=f"{a} : {slot}"), f"{a} pour {slot}")
                    page.wait_for_timeout(1200)
                    f.accept_terms_if_asked(p)
                p.shot("votes")
            if key == "vip2":
                with p.step("changer d'avis : Oui → Non sur le 1er, puis re-toucher Non (retire le vote)"):
                    slot = _slots(p)[0]
                    p.tap(page.get_by_role("button", name=f"Non : {slot}"), "Non (1er créneau)")
                    page.wait_for_timeout(1500)
                    v = [x for x in _votes(event_key) if x["name"] == "Bot Vera"]
                    p.log(f"base : {v}")
                    p.tap(page.get_by_role("button", name=f"Non : {slot}"), "Non encore (retirer)")
                    page.wait_for_timeout(1500)
                    v2 = [x for x in _votes(event_key) if x["name"] == "Bot Vera"]
                    p.log(f"base après 2e toucher : {v2}")
                    if len(v2) != len(v) - 1:
                        p.flag("🟠", "sondage de dates : re-toucher son vote ne le retire pas", f"{v} → {v2}")
                    p.tap(page.get_by_role("button", name=f"Oui : {slot}"), "Oui (remettre)")
                    page.wait_for_timeout(1500)
                with p.step("proposer une date déjà proposée (refus attendu)"):
                    first = sql(f"select starts_at from public.date_options where event_id = '{ev(event_key)}' order by 1 limit 1")[0]["starts_at"]
                    p.log(f"1er créneau en base : {first}")
                with p.step("proposer une date dans le passé"):
                    f.set_date(p, "Proposer une date", f.day(-3), "20:00")
                    p.tap(page.get_by_role("button", name="Ajouter", exact=True).first, "Ajouter (date passée)")
                    page.wait_for_timeout(2000)
                    p.shot("date-passee")
                    past = sql(f"select starts_at from public.date_options where event_id = '{ev(event_key)}' and starts_at < now()")
                    p.log(f"créneaux passés en base : {past}")
                    if past:
                        p.flag("🟡", "sondage de dates : on peut proposer une date déjà passée", str(past))
                with p.step("proposer une nouvelle date"):
                    f.set_date(p, "Proposer une date", f.day(24), "20:00")
                    p.tap(page.get_by_role("button", name="Ajouter", exact=True).first, "Ajouter la date")
                    page.wait_for_timeout(2000)
                    p.shot("date-proposee")
                    p.log(f"créneaux visibles : {_slots(p)}")
            p.scroll_to_bottom("fiche sondage")
        finally:
            p.close()


def _fix(browser, origin, event_key: str) -> dict:
    before_votes = _votes(event_key)
    p = phone(browser, "orga1", origin, f"c2-{event_key}-fixer")
    page = p.page
    try:
        open_event(p, event_key)
        p.shot("resultats")
        p.dump("resultats")
        with p.step("Fixer cette date (la plus votée)"):
            p.tap(page.get_by_role("button", name="Fixer cette date").first, "Fixer cette date")
            page.wait_for_timeout(3500)
            p.shot("apres-fixer")
            p.dump("apres-fixer")
        e = sql(f"select date_mode, starts_at from public.events where id = '{ev(event_key)}'")[0]
        p.log(f"base : {e}")
        if e["date_mode"] != "fixed":
            err = page.get_by_text(re.compile("Peut-être|désactivée|erreur", re.I)).first
            p.flag("🔴", f"« Fixer cette date » échoue ({event_key}) : l'événement reste en sondage",
                   f"message à l'écran : {err.inner_text() if err.count() else '(aucun)'} ; votes : {before_votes}")
        else:
            check_counts(p, event_key, "date fixée")
        return {"event": e, "votes": before_votes, "rsvps": rows(event_key)}
    finally:
        p.close()


def phase_dates(browser, origin, only):
    plan = {"vip2": ("Oui", "Non", "Si besoin"), "membre1": ("Oui", "Oui", "Non"), "membre2": ("Si besoin", "Oui", "Oui"),
            "guest2": ("Oui", "Si besoin", "Non"), "vip3": ("Oui", "Non", "Non"), "vip4": ("Oui", "Si besoin", "Si besoin")}
    _vote_round(browser, origin, "dates", plan)
    out = _fix(browser, origin, "dates")
    print("sondage normal :", out, flush=True)
    # Vérification de la conversion : Oui → Présent, Si besoin → Peut-être, 3 places → liste d'attente.
    e_start = out["event"]["starts_at"]
    want = {v["name"]: v["vote"] for v in out["votes"] if v["starts_at"] == e_start}
    got = {r["name"]: (r["status"], r["waitlisted"]) for r in out["rsvps"]}
    print("votes du créneau fixé :", want, "\nréponses :", got, flush=True)
    bad = [n for n, v in want.items() if v != "no" and got.get(n, (None,))[0] != {"yes": "yes", "if_needed": "maybe"}[v]]
    if bad:
        p = phone(browser, "orga1", origin, "c2-dates-fixer")
        p.flag("🔴", "date fixée : votes mal convertis en réponses", f"votes {want} ; réponses {got}")
        p.close()
    save_state(c2_dates=out)
    # Vote après la date fixée : plus de boutons ; un votant converti voit « Ta réponse ».
    p = phone(browser, "membre1", origin, "c2-dates-apres")
    try:
        open_event(p, "dates")
        p.shot("apres-fixation")
        p.dump("apres-fixation")
        r = mine("dates", "membre1")
        p.log(f"base : {r}")
        if r and r.get("set_by"):
            note = p.page.get_by_text(re.compile("C’est l’organisateur qui a noté ta réponse")).count()
            p.log(f"« l'organisateur a noté ta réponse » affiché : {bool(note)}")
    finally:
        p.close()


def phase_dates_sans_peutetre(browser, origin, only):
    plan = {"vip2": ("Si besoin", "Non", "Non"), "membre1": ("Oui", "Non", "Non"), "membre2": ("Si besoin", "Oui", "Non")}
    _vote_round(browser, origin, "dates_sans_peutetre", plan)
    out = _fix(browser, origin, "dates_sans_peutetre")
    print("sondage sans Peut-être :", out, flush=True)
    save_state(c2_dates_sans_peutetre=out)


def phase_sondage(browser, origin, only):
    """Mini-sondage à 1 choix : voter, changer, re-toucher ; résultats cachés avant de voter ; proposer une option."""
    p = phone(browser, "vip3", origin, "c2-sondage")
    page = p.page
    poll = sql(f"select id from public.polls where event_id = '{ev('places')}'")[0]["id"]

    def my_votes() -> list:
        return sql(f"""select o.label from public.poll_votes v join public.poll_options o on o.id = v.option_id
                       where v.poll_id = '{poll}' and v.user_id = '{api('vip3').uid}' order by 1""")
    try:
        open_event(p, "places")
        sec = page.get_by_text("Raclette ou fondue ?").first
        sec.scroll_into_view_if_needed()
        p.shot("sondage-avant")
        hidden = page.get_by_text("Les résultats s’affichent après ton vote.").count()
        p.log(f"« résultats après ton vote » : {bool(hidden)}")
        for label in ("Raclette", "Fondue", "Fondue", "Raclette"):
            with p.step(f"toucher « {label} »"):
                p.tap(page.get_by_role("button", name=re.compile(rf"^{label}")).first, label)
                page.wait_for_timeout(1800)
                p.log(f"base : {my_votes()}")
        v = my_votes()
        if v != [{"label": "Raclette"}]:
            p.flag("🔴", "mini-sondage : vote final faux (Raclette attendu)", str(v))
        p.shot("sondage-apres")
        with p.step("proposer une option"):
            box = page.get_by_placeholder("Proposer une option")
            p.type(box, "Les deux !", "l'option")
            p.tap(box.locator("xpath=../..").get_by_role("button", name="Ajouter"), "Ajouter (option)")
            page.wait_for_timeout(2000)
            p.expect_or_flag(page.get_by_role("button", name=re.compile("^Les deux !")).first, "la nouvelle option")
            p.shot("option-ajoutee")
    finally:
        p.close()
    # Deux bots votent Fondue au même moment (concurrence) et les résultats.
    p = phone(browser, "orga1", origin, "c2-sondage")
    try:
        open_event(p, "places")
        page = p.page
        page.get_by_text("Raclette ou fondue ?").first.scroll_into_view_if_needed()
        p.shot("sondage-organisatrice")
        with p.step("Clore le sondage puis Rouvrir"):
            p.tap(page.get_by_role("button", name="Clore le sondage"), "Clore le sondage")
            page.wait_for_timeout(1800)
            p.expect_or_flag(page.get_by_text("Ce sondage est clos."), "« Ce sondage est clos. »")
            r = api("vip2").post("poll_votes", {"poll_id": poll, "option_id": sql(f"select id from public.poll_options where poll_id='{poll}' limit 1")[0]["id"],
                                                "user_id": api("vip2").uid})
            p.log(f"vote API sondage clos : {r.status_code} {r.text[:150]}")
            if r.status_code < 300:
                p.flag("🔴", "sondage clos : la base accepte encore un vote")
            p.tap(page.get_by_role("button", name="Rouvrir"), "Rouvrir")
            page.wait_for_timeout(1500)
    finally:
        p.close()


def phase_objets(browser, origin, only):
    """Qui amène quoi : prendre / rendre ; quantités (6 bouteilles) ; ajouter / retirer son objet ; surplus."""
    items = {r["label"]: r["id"] for r in sql(f"select id, label from public.bring_items where event_id = '{ev('places')}'")}

    def claims():
        return sql(f"""select p.display_name name, c.quantity from public.bring_claims c join public.profiles p on p.id = c.user_id
                       where c.item_id = '{items['Bouteilles de jus']}' order by 1""")
    p = phone(browser, "vip1", origin, "c2-objets")
    page = p.page
    try:
        open_event(p, "places")
        page.get_by_text("Qui amène quoi").first.scroll_into_view_if_needed()
        p.shot("objets")
        with p.step("Je prends (Pain) puis Je ne prends plus"):
            p.tap(page.get_by_role("button", name="Je prends").first, "Je prends")
            page.wait_for_timeout(1800)
            who = sql(f"select claimed_by from public.bring_items where id = '{items['Pain']}'")[0]["claimed_by"]
            if who != api("vip1").uid:
                p.flag("🔴", "« Je prends » pas enregistré", str(who))
            p.tap(page.get_by_role("button", name="Je ne prends plus").first, "Je ne prends plus")
            page.wait_for_timeout(1800)
            who = sql(f"select claimed_by from public.bring_items where id = '{items['Pain']}'")[0]["claimed_by"]
            if who:
                p.flag("🔴", "« Je ne prends plus » pas enregistré", str(who))
            p.tap(page.get_by_role("button", name="Je prends").first, "Je prends (encore)")
            page.wait_for_timeout(1500)
        with p.step("J'en amène 4 bouteilles (+ ×4) puis − ×1"):
            row = page.get_by_text("Bouteilles de jus").first.locator("xpath=../..")
            for i in range(4):
                p.tap(row.get_by_role("button", name="+", exact=True), f"+ bouteille ({i + 1})")
                page.wait_for_timeout(1300)
            p.tap(row.get_by_role("button", name="−", exact=True), "− bouteille")
            page.wait_for_timeout(1500)
            p.shot("bouteilles")
            c = claims()
            p.log(f"base : {c}")
            if c != [{"name": "Bot Victor", "quantity": 3}]:
                p.flag("🔴", "quantités : 3 bouteilles attendues pour Victor", str(c))
        with p.step("ajouter son objet puis le retirer"):
            box = page.get_by_placeholder("Ce que j’amène")
            p.type(box, "Chips paprika", "ce que j'amène")
            p.tap(box.locator("xpath=../..").get_by_role("button", name="Ajouter"), "Ajouter (objet)")
            page.wait_for_timeout(2000)
            p.expect_or_flag(page.get_by_text("Chips paprika"), "« Chips paprika »")
            p.shot("chips")
            p.tap(page.get_by_text("Chips paprika").locator("xpath=../..").get_by_role("button", name="Retirer"), "Retirer (Chips)")
            page.wait_for_timeout(2000)
            left = sql(f"select 1 from public.bring_items where event_id = '{ev('places')}' and label = 'Chips paprika'")
            if left:
                p.flag("🔴", "« Retirer » son objet : il reste en base")
        with p.step("ajouter un objet vide (refus attendu)"):
            box = page.get_by_placeholder("Ce que j’amène")
            box.fill("   ")
            p.tap(box.locator("xpath=../..").get_by_role("button", name="Ajouter"), "Ajouter (vide)")
            page.wait_for_timeout(1200)
    finally:
        p.close()
    # Vera prend le Pain déjà pris par Victor (API, comme un écran pas rafraîchi) ; 3 bots prennent les 3 dernières
    # bouteilles chacun en même temps (il en reste 3 : un seul doit pouvoir en prendre 3).
    r = api("vip2").patch(f"bring_items?id=eq.{items['Pain']}", {"claimed_by": api("vip2").uid})
    print("Vera prend le Pain de Victor (API) :", r.status_code, r.text[:200], flush=True)
    results = {}

    def grab(k):
        results[k] = api(k).post("bring_claims", {"item_id": items["Bouteilles de jus"], "user_id": api(k).uid, "quantity": 3},
                                 prefer="return=minimal").status_code
    for k in ("vip2", "vip3", "vip4"):
        api(k)
    ts = [threading.Thread(target=grab, args=(k,)) for k in ("vip2", "vip3", "vip4")]
    [t.start() for t in ts]
    [t.join() for t in ts]
    c = claims()
    print("3 bots × 3 bouteilles en même temps :", results, c, flush=True)
    total = sum(x["quantity"] for x in c)
    p = phone(browser, "vip2", origin, "c2-objets")
    try:
        open_event(p, "places")
        p.page.get_by_text("Qui amène quoi").first.scroll_into_view_if_needed()
        p.shot("objets-apres-concurrence")
        if total > 6:
            p.flag("🔴", "qui amène quoi : plus de bouteilles promises que demandées (concurrence)", f"{c} ; {results}")
        p.expect_or_flag(p.page.get_by_text(re.compile(rf"^{total} / 6$")).first, f"« {total} / 6 »")
    finally:
        p.close()


def _long_press(p, locator, what: str) -> None:
    """Appui long réel (événements tactiles CDP, 800 ms)."""
    box = locator.bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    p.log(f"appui long sur « {what} »")
    cdp = p.ctx.new_cdp_session(p.page)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": x, "y": y}]})
    p.page.wait_for_timeout(800)
    cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
    cdp.detach()
    p.page.wait_for_timeout(500)


def _messages() -> list[dict]:
    return sql(f"""select m.id, p.display_name name, m.body, m.reply_to, m.mentions, m.pinned, m.deleted_at
                   from public.messages m join public.profiles p on p.id = m.user_id
                   where m.event_id = '{ev('places')}' order by m.created_at""")


def _write(p, text: str) -> None:
    box = p.page.get_by_label("Message", exact=True)
    p.type(box, text, "le message")
    p.tap(p.page.get_by_role("button", name="Envoyer", exact=True), "Envoyer")
    p.page.wait_for_timeout(2500)
    if f.accept_terms_if_asked(p):
        p.page.wait_for_timeout(2500)


def phase_forum(browser, origin, only):
    chat = f"/events/event/{ev('places')}/chat"
    p = phone(browser, "vip1", origin, "c2-forum")
    try:
        p.goto(chat)
        p.page.wait_for_timeout(3000)
        with p.step("écrire"):
            _write(p, "Coucou tout le monde, qui prend le dessert ?")
            p.expect_or_flag(p.page.get_by_text("Coucou tout le monde").last, "son message", "🔴")
        with p.step("taper @ : suggestions de noms ?"):
            box = p.page.get_by_label("Message", exact=True)
            box.fill("@Bot V")
            p.page.wait_for_timeout(1200)
            p.shot("arobase")
            sugg = p.page.get_by_role("button", name=re.compile(r"Bot V(era|alentin|iolette)")).count()
            p.log(f"suggestions affichées : {sugg}")
            if not sugg:
                p.flag("🟡", "forum d'événement : « @ pour citer » n'ouvre aucune suggestion de nom (la discussion de groupe en a)")
            box.fill("")
        with p.step("message vide / espaces : Envoyer désactivé"):
            p.page.get_by_label("Message", exact=True).fill("    ")
            dis = p.page.get_by_role("button", name="Envoyer", exact=True)
            p.log(f"Envoyer désactivé pour des espaces : {dis.is_disabled() or dis.get_attribute('aria-disabled')}")
            p.page.get_by_label("Message", exact=True).fill("")
        p.shot("apres")
    finally:
        p.close()
    p = phone(browser, "vip2", origin, "c2-forum")
    try:
        p.goto(chat)
        p.page.wait_for_timeout(3000)
        with p.step("citer (appui long) et mentionner @Bot Victor"):
            _long_press(p, p.page.get_by_text("Coucou tout le monde").last, "le message de Victor")
            p.shot("reponse-a")
            p.expect_or_flag(p.page.get_by_text(re.compile("^↪ Réponse à Bot Victor")), "« ↪ Réponse à Bot Victor »")
            _write(p, "@Bot Victor moi je prends le dessert !")
            m = [x for x in _messages() if x["name"] == "Bot Vera"]
            p.log(f"base : {m}")
            if not m or not m[-1]["reply_to"]:
                p.flag("🟠", "citer : la réponse n'est pas liée au message cité")
            if not m or api("vip1").uid not in (m[-1]["mentions"] or []):
                p.flag("🟠", "@Bot Victor : la mention n'est pas enregistrée", str(m))
            p.shot("citation")
        with p.step("signaler le message de Victor"):
            p.tap(p.page.get_by_role("button", name="Signaler le message de Bot Victor").first, "Signaler")
            sheet = p.page.get_by_label("Signaler", exact=True)
            sheet.wait_for(timeout=8000)
            p.shot("feuille-signaler")
            p.tap(sheet.get_by_role("radio").first, "premier motif")
            p.tap(sheet.get_by_role("button", name="Envoyer"), "Envoyer le signalement")
            p.page.wait_for_timeout(2500)
            p.shot("signale")
    finally:
        p.close()
    p = phone(browser, "orga1", origin, "c2-forum")
    try:
        p.goto(chat)
        p.page.wait_for_timeout(3000)
        with p.step("épingler le message de Vera"):
            row = p.page.get_by_text("moi je prends le dessert").last.locator("xpath=ancestor::*[.//*[text()='Épingler']][1]")
            p.tap(row.get_by_text("Épingler").first, "Épingler")
            p.page.wait_for_timeout(2000)
            p.expect_or_flag(p.page.get_by_text(re.compile("^Épinglé")).first, "le bandeau « Épinglé »")
            p.shot("epingle")
            pinned = [x for x in _messages() if x["pinned"]]
            if not pinned:
                p.flag("🔴", "Épingler : rien en base")
        with p.step("l'organisatrice peut-elle supprimer le message d'un invité ?"):
            n = p.page.get_by_text("Supprimer").count()
            p.log(f"liens « Supprimer » vus par l'organisatrice : {n}")
    finally:
        p.close()
    p = phone(browser, "vip1", origin, "c2-forum")
    try:
        p.goto(chat)
        p.page.wait_for_timeout(3000)
        with p.step("supprimer son message"):
            row = p.page.get_by_text("Coucou tout le monde").last.locator("xpath=ancestor::*[.//*[text()='Supprimer']][1]")
            p.tap(row.get_by_text("Supprimer").first, "Supprimer")
            p.page.wait_for_timeout(2000)
            p.shot("supprime")
            if p.page.get_by_text("Coucou tout le monde").count():
                p.flag("🔴", "Supprimer : le message reste affiché")
        # Le texte supprimé reste-t-il lisible par les autres (API) ?
        r = api("vip3").get(f"messages?event_id=eq.{ev('places')}&deleted_at=not.is.null&select=body")
        p.log(f"messages supprimés lisibles par Valentin : {r.text[:200]}")
        if r.status_code == 200 and "Coucou" in r.text:
            p.flag("🟠", "forum : le texte d'un message supprimé reste lisible par tous les invités (API)", r.text[:200])
        # Retour à la fiche : l'aperçu de la discussion ne montre plus le message supprimé.
        p.goto(f"/events/event/{ev('places')}")
        p.page.wait_for_timeout(3000)
        if p.page.get_by_text("Coucou tout le monde").count():
            p.flag("🟠", "fiche : l'aperçu de la discussion montre encore le message supprimé")
        p.shot("apercu-discussion")
    finally:
        p.close()
    # Co-admin (chat.moderate) supprime le message de Vera.
    p = phone(browser, "coadmin", origin, "c2-forum")
    try:
        p.goto(chat)
        p.page.wait_for_timeout(3000)
        with p.step("co-admin : supprimer le message de Vera"):
            row = p.page.get_by_text("moi je prends le dessert").last.locator("xpath=ancestor::*[.//*[text()='Supprimer']][1]")
            p.tap(row.get_by_text("Supprimer").first, "Supprimer (modération)")
            p.page.wait_for_timeout(2500)
            m = [x for x in _messages() if x["name"] == "Bot Vera"]
            p.log(f"base : {m}")
            if m and not m[-1]["deleted_at"]:
                p.flag("🔴", "co-admin : « Supprimer » ne supprime pas le message d'un autre", str(m))
            pinned = sql(f"select count(*) n from public.messages where event_id = '{ev('places')}' and pinned and deleted_at is null")
            p.shot("modere")
            if p.page.get_by_text(re.compile("^Épinglé")).count():
                p.flag("🟡", "message supprimé : le bandeau « Épinglé » reste affiché", str(pinned))
    finally:
        p.close()
    reports = sql(f"""select r.* from private.reports r where r.created_at > now() - interval '1 hour' order by r.created_at desc limit 3""") \
        if sql("select to_regclass('private.reports') t")[0]["t"] else []
    print("signalements :", reports, flush=True)


def phase_agenda(browser, origin, only):
    """« Ajouter à mon agenda » : iPhone → fichier .ics ; Android → Google Agenda ; contenu vérifié."""
    e = sql(f"select title, starts_at, ends_at, location_name, location_address, description from public.events where id = '{ev('places')}'")[0]
    p = phone(browser, "vip1", origin, "c2-agenda")
    try:
        open_event(p, "places")
        tap_rsvp(p, "Présent")
        captured = {}
        p.page.on("request", lambda req: captured.setdefault("url", req.url) if "calendar.ics" in req.url else None)
        with p.step("iPhone : Ajouter à mon agenda"):
            p.tap(p.page.get_by_role("button", name="Ajouter à mon agenda"), "Ajouter à mon agenda")
            p.page.wait_for_timeout(2500)
        url = captured.get("url") or p.page.url
        p.log(f"adresse .ics : {url}")
        if "calendar.ics" not in url:
            p.flag("🔴", "iPhone : « Ajouter à mon agenda » n'ouvre pas le fichier .ics", url)
        else:
            body = httpx.get(url.replace("localhost", "127.0.0.1"), timeout=20).text
            (p.dir / "agenda.ics").write_text(body)
            unfolded = body.replace("\r\n ", "")
            p.log(f".ics : {unfolded[:600]!r}")
            stamp = lambda iso: re.sub(r"[-:]", "", iso.replace(" ", "T"))[:15]
            checks = {"SUMMARY": e["title"].replace(",", "\\,").replace(";", "\\;"), "DTSTART": None, "LOCATION": "Salle des bots"}
            problems = [k for k, v in checks.items() if v and v not in unfolded]
            from datetime import datetime, timezone
            start = datetime.fromisoformat(e["starts_at"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            end = datetime.fromisoformat(e["ends_at"]).astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            if f"DTSTART:{start}" not in unfolded:
                problems.append(f"DTSTART {start}")
            if f"DTEND:{end}" not in unfolded:
                problems.append(f"DTEND {end}")
            if "BEGIN:VALARM" not in unfolded or f"/events/event/{ev('places')}" not in unfolded:
                problems.append("alarme ou lien de la fiche")
            if problems:
                p.flag("🔴", "fichier .ics : contenu faux", ", ".join(problems))
        p.shot("agenda")
    finally:
        p.close()
    p = phone(browser, "vip2", origin, "c2-agenda")
    try:
        open_event(p, "places")
        with p.step("Android : Ajouter à mon agenda → Google Agenda"):
            with p.ctx.expect_page(timeout=8000) as new:
                p.tap(p.page.get_by_role("button", name="Ajouter à mon agenda"), "Ajouter à mon agenda")
            url = new.value.url
            p.log(f"onglet ouvert : {url[:300]}")
            qs = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
            if qs.get("text", [""])[0] != e["title"]:
                p.flag("🟠", "Google Agenda : titre faux", str(qs.get("text")))
            new.value.close()
    finally:
        p.close()
    # Lieu très long (nom + adresse > 300 caractères) : le serveur refuse-t-il le fichier ?
    long_loc = "Salle " + "très " * 40 + "longue"
    r = httpx.get(f"{load_state()['origin']}/api/calendar.ics", params={
        "uid": ev("places"), "title": e["title"], "start": "2026-12-01T19:00:00Z", "end": "2026-12-01T22:00:00Z",
        "location": long_loc + ", Rue du Lac 12, 1800 Vevey", "description": "x", "url": ""}, timeout=20)
    print("ics lieu long :", r.status_code, r.text[:200], flush=True)
    if r.status_code != 200:
        p = phone(browser, "vip1", origin, "c2-agenda")
        p.flag("🟡", f"agenda : un lieu de plus de 300 caractères fait échouer le fichier .ics (HTTP {r.status_code})")
        p.close()


async def _race(origin: str, keys: list[str], event_id: str, out: dict) -> None:
    from playwright.async_api import async_playwright
    from tests.bots.bench import OUT, PHONES
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        pages = {}
        for k in keys:
            b = BY_KEY[k]
            ctx = await browser.new_context(base_url=origin, locale="fr-CH", timezone_id="Europe/Zurich",
                                            storage_state=str(OUT / k / "storage.json"),
                                            record_video_dir=str(OUT / k / "video-tmp-course"), **PHONES[b.device])
            page = await ctx.new_page()
            await page.goto(f"{origin}/events/event/{event_id}")
            await page.get_by_role("radiogroup").first.wait_for(timeout=30000)
            await page.wait_for_timeout(1500)
            pages[k] = page
        btns = {k: pages[k].get_by_role("radiogroup").first.get_by_role("button", name="Présent", exact=True) for k in keys}
        await asyncio.gather(*(btns[k].tap() for k in keys))
        await asyncio.sleep(4)
        for k in keys:
            await pages[k].screenshot(path=str(OUT / k / "c2-course-apres.png"))
            out[k] = await pages[k].get_by_role("radiogroup").first.locator("xpath=..").inner_text()
            await pages[k].context.close()
        await browser.close()


def phase_course(browser, origin, only):
    """3 bots touchent « Présent » au même instant pour la dernière place (3 places, 2 prises)."""
    keys = ["vip1", "vip2", "vip3"]
    for k in keys:  # départ : les trois Absents, 2 places prises sur 3
        api(k).patch(f"rsvps?event_id=eq.{ev('course')}&user_id=eq.{api(k).uid}", {"status": "no"})
    print("départ :", rows("course"), flush=True)
    out = {}
    # La course tourne dans son propre fil (Playwright asynchrone) : le fil principal porte déjà la boucle synchrone.
    t = threading.Thread(target=lambda: asyncio.run(_race(origin, keys, ev("course"), out)))
    t.start()
    t.join()
    db = rows("course")
    taken = sum(1 + r["plus_ones"] for r in db if r["status"] == "yes" and not r["waitlisted"])
    print("course (écran) :", out, "\nbase :", db, flush=True)
    save_state(c2_course=db)
    if taken > 3:
        p = phone(browser, "vip1", origin, "c2-course")
        p.flag("🔴", f"dernière place prise en même temps : {taken} présents pour 3 places (surréservation)", str(db))
        p.close()
    # Même course à l'API, répétée (10 manches, 3 bots), pour mesurer la fréquence.
    over = 0
    for i in range(int(load_state().get('c2_course_rounds', 10))):
        for k in keys:
            api(k).patch(f"rsvps?event_id=eq.{ev('course')}&user_id=eq.{api(k).uid}", {"status": "no"})
        res = {}

        def go(k):
            r = api(k).patch(f"rsvps?event_id=eq.{ev('course')}&user_id=eq.{api(k).uid}", {"status": "yes"})
            res[k] = r.status_code
        ts = [threading.Thread(target=go, args=(k,)) for k in keys]
        [t.start() for t in ts]
        [t.join() for t in ts]
        d = rows("course")
        n = sum(1 + r["plus_ones"] for r in d if r["status"] == "yes" and not r["waitlisted"])
        over += n > 3
        print(f"manche {i + 1} : {n} présents confirmés / 3 ; {res}", flush=True)
    save_state(c2_course_api_over=over)
    if over:
        p = phone(browser, "vip1", origin, "c2-course")
        p.flag("🔴", f"concurrence (API) : surréservation dans {over} manche(s) sur 10", "apply_waitlist sans verrou")
        p.close()
    p = phone(browser, "vip3", origin, "c2-course")
    try:
        open_event(p, "course")
        check_counts(p, "course", "après la course")
        p.shot("course-fiche")
    finally:
        p.close()


def phase_fixer(browser, origin, only):
    """L'organisatrice fixe la date des deux sondages (votes déjà donnés) ; conversion vérifiée en base."""
    for key in ("dates_sans_peutetre", "dates"):
        out = _fix(browser, origin, key)
        print(key, "→", out, flush=True)
        save_state(**{f"c2_fix_{key}": out})
        if out["event"]["date_mode"] == "fixed":
            want = {v["name"]: v["vote"] for v in out["votes"] if v["starts_at"] == out["event"]["starts_at"]}
            got = {r["name"]: r["status"] for r in out["rsvps"]}
            bad = {n: (v, got.get(n)) for n, v in want.items() if v != "no" and got.get(n) != {"yes": "yes", "if_needed": "maybe"}[v]}
            print("conversion :", want, got, bad, flush=True)
            if bad:
                p = phone(browser, "orga1", origin, f"c2-{key}-fixer")
                p.flag("🔴", f"date fixée ({key}) : votes mal convertis", str(bad))
                p.close()


def phase_bouteilles(browser, origin, only):
    """Rythme normal (un toucher toutes les 2 s, bouton actif) : 3 × « + » doit donner 3 bouteilles."""
    item = sql(f"select id from public.bring_items where event_id = '{ev('places')}' and quantity is not null")[0]["id"]
    sql(f"delete from public.bring_claims where item_id = '{item}' and user_id = '{api('vip1').uid}'")
    p = phone(browser, "vip1", origin, "c2-bouteilles")
    page = p.page
    try:
        open_event(p, "places")
        row = page.get_by_text("Bouteilles de jus").first.locator("xpath=../..")
        row.scroll_into_view_if_needed()
        p.shot("avant")
        seen = []
        for i in range(3):
            p.tap(row.get_by_role("button", name="+", exact=True), f"+ bouteille ({i + 1})")
            page.wait_for_timeout(2000)
            mine_db = sql(f"select quantity from public.bring_claims where item_id = '{item}' and user_id = '{api('vip1').uid}'")
            shown = row.inner_text().replace("\n", " ")[:120]
            seen.append((mine_db, shown))
            p.log(f"après « + » n°{i + 1} : base {mine_db} ; écran « {shown} »")
        page.wait_for_timeout(8000)
        final = sql(f"select quantity from public.bring_claims where item_id = '{item}' and user_id = '{api('vip1').uid}'")
        p.shot("apres")
        p.log(f"final : {final}")
        if not final or final[0]["quantity"] != 3:
            p.flag("🟠", "qui amène quoi : 3 touchers sur « + » (toutes les 2 s) n'amènent pas 3 bouteilles",
                   f"base finale {final} ; pas à pas {seen} (le « + » se réactive avant que la fiche relue ne donne le nouveau compte)")
    finally:
        p.close()


def phase_verif(browser, origin, only):
    """Contre-vérification à machine plus calme : sondage clos → « Rouvrir » ; épingler → bandeau « Épinglé »."""
    p = phone(browser, "orga1", origin, "c2-verif")
    page = p.page
    try:
        open_event(p, "places")
        poll = sql(f"select id, closes_at from public.polls where event_id = '{ev('places')}'")[0]
        p.log(f"base : sondage clos le {poll['closes_at']}")
        page.get_by_text("Raclette ou fondue ?").first.scroll_into_view_if_needed()
        p.shot("sondage-clos")
        p.expect_or_flag(page.get_by_text("Ce sondage est clos."), "« Ce sondage est clos. » (sondage clos en base)")
        with p.step("Rouvrir"):
            p.tap(page.get_by_role("button", name="Rouvrir"), "Rouvrir")
            for _ in range(10):
                page.wait_for_timeout(1500)
                if not sql(f"select closes_at from public.polls where id = '{poll['id']}'")[0]["closes_at"]:
                    break
            p.expect_or_flag(page.get_by_role("button", name="Clore le sondage"), "« Clore le sondage » après réouverture")
            p.shot("rouvert")
        p.goto(f"/events/event/{ev('places')}/chat")
        page.get_by_label("Message", exact=True).wait_for(timeout=90000)
        page.wait_for_timeout(2000)
        with p.step("écrire puis épingler"):
            box = page.get_by_label("Message", exact=True)
            p.type(box, "Info : rendez-vous à 19h45 devant la salle", "le message")
            p.tap(page.get_by_role("button", name="Envoyer", exact=True), "Envoyer")
            p.see(page.get_by_text("rendez-vous à 19h45").last, "son message", 45000)
            row = page.get_by_text("rendez-vous à 19h45").last.locator("xpath=ancestor::*[.//*[text()='Épingler']][1]")
            p.tap(row.get_by_text("Épingler").first, "Épingler")
            ok = p.see(page.get_by_text(re.compile("^Épinglé")).first, "le bandeau « Épinglé »", 30000)
            p.shot("epingle")
            p.log(f"bandeau « Épinglé » : {ok} ; base : {sql(f'''select pinned from public.messages where event_id = '{ev('places')}' and body like 'Info : rendez-vous%' ''')}")
            if not ok:
                p.flag("🟠", "Épingler : le bandeau « Épinglé » n'apparaît pas (base : épinglé)")
    finally:
        p.close()


def phase_mot(browser, origin, only):
    """Le « petit mot perso pour l'organisateur » de Vera : Valentin (simple invité) le voit-il ?"""
    p = phone(browser, "vip3", origin, "c2-mot")
    try:
        open_event(p, "places")
        note = p.page.get_by_text(re.compile("allergique aux noix")).first
        if p.see(note, "le mot de Vera", 20000):
            note.scroll_into_view_if_needed()
            p.shot("mot-de-vera-visible")
            p.flag("🟠", "« Un petit mot perso pour l'organisateur » est affiché à tous les invités (« Qui vient ? »)",
                   "Bot Valentin lit le mot de Bot Vera « Je suis allergique aux noix (pour Olga) » ; RLS rsvps : toute la ligne lisible")
    finally:
        p.close()
