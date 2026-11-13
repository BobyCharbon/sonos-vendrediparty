"""Modifier un événement déjà publié en parlant (« décale à 21h », « ajoute Tom », « mets 15 bouteilles de vin ») :
l'événement est relu en brouillon (mêmes champs que la création), l'IA applique la demande, l'app montre la liste des
changements, puis tout est écrit avec la session de la personne (règles de la base : seul qui peut modifier modifie).
Les invités sont prévenus par la base quand la date ou le lieu change ; sur demande, un message dans la discussion de
l'événement récapitule tous les changements."""
from datetime import datetime

from .accounts import AccountError, db_refusal
from .ai_events import (LATER_PLACE, ONLY_INVITEES, PUBLIC_AUDIENCE, VIP_AUDIENCE, ZURICH, EventAssistant, Options,
                        bring_row, local_time)

SELECT = ("*, category:categories(name), event_tags(tag_id), event_organizers(user_id), event_invites(user_id, via_group),"
          " event_groups(group_id), date_options(starts_at), polls(id, question, poll_options(label)),"
          " bring_items(id, label, quantity, added_by, sort)")
NOT_ALLOWED = "Tu ne peux pas modifier cet événement."
MAX_CHANGES = 20


def _local(value) -> str:
    try:
        return datetime.fromisoformat(str(value)).astimezone(ZURICH).strftime("%Y-%m-%dT%H:%M") if value else ""
    except ValueError:
        return ""


def bring_text(item: dict) -> str:
    """Objet en base → texte du brouillon (« 15 Bouteilles de vin » si partagé), le chemin inverse de bring_row."""
    return f"{item['quantity']} {item['label']}" if item.get("quantity") else item["label"]


def kept(e: dict) -> str | None:
    """Événement réservé à Vendredi Party : ce public reste proposé à qui le modifie, même hors du groupe."""
    return VIP_AUDIENCE if e.get("visibility") == "all" and not e.get("public_link") else None


def audience_of(e: dict, o: Options) -> str:
    if e.get("public_link"):
        return PUBLIC_AUDIENCE
    names = {gid: name for name, gid in o.audiences.items() if isinstance(gid, str) and gid not in ("people", "public")}
    groups = [names[g["group_id"]] for g in e.get("event_groups") or [] if g["group_id"] in names]
    if groups:
        return groups[0]
    return VIP_AUDIENCE if e.get("visibility") == "all" else ONLY_INVITEES


def draft_of(e: dict, o: Options) -> dict:
    """Événement en base → brouillon au format de l'IA (celui qu'elle renvoie à la création)."""
    person = {pid: name for name, pid in o.people.items()}
    tag = {tid: name for name, tid in o.tags.items()}
    later = (e.get("location_name") or "") == LATER_PLACE and not e.get("location_address")
    place = "" if later else e.get("location_address") or e.get("location_name") or ""
    home = str(e.get("location_name") or "").lower().startswith("chez ")
    return {
        "status": "ready", "questions": [], "title": e.get("title") or "", "description": e.get("description") or "",
        "date_mode": e.get("date_mode") or "fixed", "start": _local(e.get("starts_at")), "end": _local(e.get("ends_at")),
        "date_options": sorted(_local(d["starts_at"]) for d in e.get("date_options") or []),
        "poll_deadline": _local(e.get("poll_deadline")),
        "place_kind": "later" if later else ("home" if home else "venue") if place else "none",
        "place_query": place, "place_name": e.get("location_name") or "", "place_broad": "",
        "address_complete": bool(place) or later,
        "price_chf": float(e.get("price_chf") or 0), "payment_info": e.get("payment_info") or "",
        "max_participants": e.get("max_participants") or 0, "waitlist": bool(e.get("waitlist_enabled", True)),
        "plus_ones": bool(e.get("allow_plus_ones", True)), "max_plus_ones": e.get("max_plus_ones") or 0,
        "allow_maybe": bool(e.get("allow_maybe", True)), "rsvp_deadline": _local(e.get("rsvp_deadline")),
        "show_participants": bool(e.get("show_participants", True)), "forum": bool(e.get("forum_enabled", True)),
        "notify": bool(e.get("notify_on_publish", True)),
        "category": (e.get("category") or {}).get("name") or "",
        "tags": [tag[t["tag_id"]] for t in e.get("event_tags") or [] if t["tag_id"] in tag],
        "audience": audience_of(e, o),
        "invitees": [person[i["user_id"]] for i in e.get("event_invites") or []
                     if not i.get("via_group") and i["user_id"] in person],
        "organizers": [person[x["user_id"]] for x in e.get("event_organizers") or [] if x["user_id"] in person],
        "polls": [{"question": p["question"], "options": [x["label"] for x in p.get("poll_options") or []],
                   "multiple": False, "anonymous": False, "add_options": False} for p in e.get("polls") or []],
        "bring": [bring_text(b) for b in sorted(e.get("bring_items") or [], key=lambda b: b.get("sort") or 0)
                  if not b.get("added_by")],
        "pot": bool(e.get("pot_enabled")), "summary": "", "not_understood": [], "cover_url": e.get("cover_url") or "",
    }


def _listed(before: list[str], after: list[str], what: str) -> list[str]:
    added = [x for x in after if x not in before]
    removed = [x for x in before if x not in after]
    return ([f"{what} : + {', '.join(added)}"] if added else []) + ([f"{what} : − {', '.join(removed)}"] if removed else [])


def _shown(key: str, value) -> str:
    text = str(value or "—")
    return text.replace("T", " à ", 1) if key in ("start", "end", "rsvp_deadline") and value else text


def changes(old: dict, new: dict) -> list[str]:
    """Ce qui change, en mots simples (montré avant d'enregistrer, et envoyé aux invités si demandé)."""
    out = []
    labels = [("title", "Titre"), ("start", "Début"), ("end", "Fin"), ("place_query", "Lieu"), ("price_chf", "Prix (CHF)"),
              ("max_participants", "Places (0 = illimité)"), ("payment_info", "Paiement"), ("rsvp_deadline", "Réponse avant")]
    for key, label in labels:
        if key == "place_query" and new.get("place_kind") == "later" and old.get("place_kind") != "later":
            out.append(f"Lieu : {LATER_PLACE.lower()}")
        elif old.get(key) != new.get(key):
            out.append(f"{label} : {_shown(key, new.get(key))}")
    if old.get("description") != new.get("description"):
        out.append("Description mise à jour")
    for key, yes, no in [("plus_ones", "Accompagnants permis", "Pas d'accompagnant"),
                         ("pot", "Pot commun ouvert", "Plus de pot commun"),
                         ("forum", "Discussion ouverte", "Discussion fermée"),
                         ("allow_maybe", "« Peut-être » permis", "Plus de « Peut-être »")]:
        if old.get(key) != new.get(key):
            out.append(yes if new.get(key) else no)
    if old.get("audience") != new.get("audience"):
        out.append(f"Invités : {new.get('audience')}")
    out += _listed(old.get("date_options") or [], new.get("date_options") or [], "Dates à voter")
    out += _listed(old.get("bring") or [], new.get("bring") or [], "Qui amène quoi")
    out += _listed([p["question"] for p in old.get("polls") or []], [p["question"] for p in new.get("polls") or []], "Sondages")
    out += _listed(old.get("invitees") or [], new.get("invitees") or [], "Invités nommés")
    out += _listed(old.get("organizers") or [], new.get("organizers") or [], "Co-organisateurs")
    out += _listed(old.get("tags") or [], new.get("tags") or [], "Tags")
    return out[:MAX_CHANGES]


class EventEditor:
    def __init__(self, events: EventAssistant):
        self.events = events
        self.accounts = events.accounts

    def _event(self, token: str, eid: str) -> dict:
        r = self.accounts._get("GET", f"/rest/v1/events?id=eq.{eid}&select={SELECT}", token)
        rows = r.json() if r.status_code == 200 else []
        if not rows:
            raise AccountError("Événement introuvable.")
        return rows[0]

    def _check(self, token: str, e: dict) -> str:
        uid = self.events.ai.allowed(token)
        perms = self.accounts._perms(token)
        mine = e.get("created_by") == uid or any(x["user_id"] == uid for x in e.get("event_organizers") or [])
        if not (mine or "events.manage_all" in perms):
            raise AccountError(NOT_ALLOWED)
        return uid

    def load(self, token: str, eid: str) -> dict:
        """L'événement tel qu'il est, en brouillon, et son lieu actuel (gardé tant qu'on ne parle pas d'un autre)."""
        e = self._event(token, eid)
        self._check(token, e)
        place = {"name": e.get("location_name") or "", "address": e.get("location_address") or "",
                 "url": e.get("location_url") or ""}
        return {"draft": draft_of(e, self.events._options(token, keep=kept(e))), "place": place}

    def draft(self, token: str, eid: str, turns: list[str]) -> dict:
        """Ce que la personne demande → l'événement modifié et la liste des changements (rien n'est encore écrit)."""
        e = self._event(token, eid)
        self._check(token, e)
        current = draft_of(e, self.events._options(token, keep=kept(e)))
        new = self.events.draft(token, turns, current, editing=True)
        return {"draft": new, "changes": changes(current, new)}

    def save(self, token: str, eid: str, draft: dict, place: dict | None, announce: bool) -> dict:
        e = self._event(token, eid)
        uid = self._check(token, e)
        o = self.events._options(token, keep=kept(e))
        now = datetime.now(ZURICH)
        before = draft_of(e, o)
        d = o.clean({**draft, "questions": []}, now)
        if not d["title"] or (d["date_mode"] == "fixed" and not d["start"]):
            raise AccountError("Il manque le titre ou la date.")
        row = self.events._event_row(d, o, place if isinstance(place, dict) else {}, uid, now)
        for key in ("created_by", "status", "reminders"):
            row.pop(key)
        # Lieu inchangé : on garde l'adresse et le lien actuels ; « lieu à définir » remplace le lieu (avis 2237524ab14b).
        if not isinstance(place, dict) and d["place_kind"] != "later":
            for key in ("location_name", "location_address", "location_url"):
                row.pop(key)
        r = self.accounts._get("PATCH", f"/rest/v1/events?id=eq.{eid}", token, json=row,
                               headers={"Prefer": "return=representation"})
        if r.status_code not in (200, 204):
            raise db_refusal(r, NOT_ALLOWED)
        if r.status_code == 200 and not r.json():
            raise AccountError(NOT_ALLOWED)
        problems: list[str] = []
        self._sync_lists(token, eid, e, d, o, uid, now, problems)
        done = changes(before, d)
        if announce and done and d["forum"]:
            body = "✏️ Événement mis à jour :\n" + "\n".join(f"• {c}" for c in done)
            self.events._add(token, "/rest/v1/messages", {"event_id": eid, "user_id": uid, "body": body[:4000]},
                             "le message aux invités", problems)
        return {"id": eid, "title": d["title"], "changes": done, "problems": problems}

    def _drop(self, token: str, path: str, what: str, problems: list[str]):
        if self.accounts._get("DELETE", path, token).status_code not in (200, 204):
            problems.append(what)

    def _sync_lists(self, token, eid, e, d, o, uid, now, problems):
        self._sync_bring(token, eid, e, d, problems)
        self._sync_polls(token, eid, e, d, uid, problems)
        # Sa propre ligne n'est jamais touchée : un co-organisateur ne figure pas dans son brouillon (il ne se nomme pas),
        # il se retirait donc lui-même et perdait la main sur l'événement.
        self._sync_people(token, eid, "event_invites",
                          {i["user_id"] for i in e.get("event_invites") or [] if not i.get("via_group")} - {uid},
                          {o.people[n] for n in d["invitees"]} - {uid}, "les invitations", problems)
        self._sync_people(token, eid, "event_organizers", {x["user_id"] for x in e.get("event_organizers") or []} - {uid},
                          {o.people[n] for n in d["organizers"]} - {uid}, "les co-organisateurs", problems)
        old_tags = {t["tag_id"] for t in e.get("event_tags") or []}
        new_tags = {o.tags[t] for t in d["tags"]}
        if new_tags - old_tags:
            self.events._add(token, "/rest/v1/event_tags", [{"event_id": eid, "tag_id": t} for t in new_tags - old_tags],
                             "les tags", problems)
        for t in old_tags - new_tags:
            self._drop(token, f"/rest/v1/event_tags?event_id=eq.{eid}&tag_id=eq.{t}", "les tags", problems)
        if d["date_mode"] == "poll":  # une date déjà proposée n'est pas retirée : des votes peuvent y être
            known = {_local(x["starts_at"]) for x in e.get("date_options") or []}
            fresh = [s for s in d["date_options"] if s not in known]
            if fresh:
                self.events._add(token, "/rest/v1/date_options",
                                 [{"event_id": eid, "starts_at": local_time(s, now).isoformat(), "proposed_by": uid} for s in fresh],
                                 "les dates à voter", problems)

    def _sync_bring(self, token, eid, e, d, problems):
        """Qui amène quoi : un objet gardé garde ses réponses (seule sa quantité change) ; les ajouts des invités
        eux-mêmes (added_by) ne sont jamais touchés."""
        left = [b for b in e.get("bring_items") or [] if not b.get("added_by")]
        for i, text in enumerate(d["bring"]):
            wanted = bring_row(text)
            same = next((b for b in left if b["label"].lower() == wanted["label"].lower()), None)
            if not same:
                self.events._add(token, "/rest/v1/bring_items", {"event_id": eid, "sort": 100 + i, **wanted}, f"« {text} »", problems)
                continue
            left = [b for b in left if b["id"] != same["id"]]
            if same.get("quantity") != wanted.get("quantity"):
                r = self.accounts._get("PATCH", f"/rest/v1/bring_items?id=eq.{same['id']}", token,
                                       json={"quantity": wanted.get("quantity")})
                if r.status_code not in (200, 204):
                    problems.append(f"la quantité de « {same['label']} »")
        for gone in left:
            self._drop(token, f"/rest/v1/bring_items?id=eq.{gone['id']}", f"le retrait de « {gone['label']} »", problems)

    def _sync_polls(self, token, eid, e, d, uid, problems):
        """Sondages : les nouveaux sont créés, ceux que la personne a retirés sont supprimés (les autres restent tels quels)."""
        old_polls = {p["question"]: p["id"] for p in e.get("polls") or []}
        for i, p in enumerate(d["polls"]):
            if p["question"] in old_polls:
                continue
            made = self.events._add(token, "/rest/v1/polls?select=id", {
                "event_id": eid, "question": p["question"], "multiple_choice": p["multiple"], "anonymous": p["anonymous"],
                "members_can_add_options": p["add_options"], "created_by": uid, "sort": 100 + i},
                f"le sondage « {p['question']} »", problems, one=True)
            if made and p["options"]:
                self.events._add(token, "/rest/v1/poll_options",
                                 [{"poll_id": made["id"], "label": label, "created_by": uid, "sort": j}
                                  for j, label in enumerate(p["options"])],
                                 f"les choix du sondage « {p['question']} »", problems)
        kept = {p["question"] for p in d["polls"]}
        for question, pid in old_polls.items():
            if question not in kept:
                self._drop(token, f"/rest/v1/polls?id=eq.{pid}", f"le retrait du sondage « {question} »", problems)

    def _sync_people(self, token, eid, table, before: set, after: set, what: str, problems: list[str]):
        if after - before:
            self.events._add(token, f"/rest/v1/{table}", [{"event_id": eid, "user_id": w} for w in after - before], what, problems)
        for w in before - after:
            self._drop(token, f"/rest/v1/{table}?event_id=eq.{eid}&user_id=eq.{w}", what, problems)
