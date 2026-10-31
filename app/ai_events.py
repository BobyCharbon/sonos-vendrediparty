"""Créer un événement en le décrivant (assistant IA) : la personne parle ou écrit, Claude remplit l'événement et pose
ses questions s'il manque quelque chose ; l'app montre le récapitulatif complet, cherche le lieu, puis la personne
confirme. L'IA remplit et modifie TOUS les champs du formulaire web (EventForm) : date fixe ou sondage de dates, lieu,
prix et paiement, places et liste d'attente, accompagnants, réponses, invités, co-organisateurs, tags, mini-sondages,
qui amène quoi, pot commun, discussion, notification.

L'événement est écrit avec la session de la personne (règles de la base) : l'IA ne peut rien faire de plus qu'elle.
Comme dans le formulaire web : créé en brouillon, puis publié (droit « publier directement ») ou proposé."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .accounts import AccountError

# Créer un événement demande de vraiment comprendre ce qui est dit (dates relatives, lieux, personnes) : le modèle le
# plus intelligent, avec une réflexion poussée (≈ 3 à 5 centimes par message).
MODEL = "claude-opus-5-5"
EFFORT = "high"
MAX_TOKENS = 16000

ZURICH = ZoneInfo("Europe/Zurich")
MAX_TEXT = 4000
MAX_TURNS = 8
REMINDERS = ["7d", "1d", "2h", "0h"]
UNLIMITED_PLUS_ONES = 10  # comme le formulaire web (types.ts)
VIP_AUDIENCE = "Vendredi Party"
PUBLIC_AUDIENCE = "Public (lien)"
ONLY_INVITEES = "Seulement les personnes invitées"
WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NOT_UNDERSTOOD = "Je n'ai pas réussi à comprendre la description. Réessaie, ou crée l'événement à la main."

SYSTEM = """Tu es l'assistant de l'app suisse « Party » (soirées et sorties entre amis, en Suisse romande). {me} te
décrit un événement qu'il ou elle organise, le plus souvent DICTÉ à voix haute : la reconnaissance vocale fait des
fautes (noms propres, lieux, chiffres, mots collés ou coupés). Reconstitue ce que la personne a VOULU dire, avec bon
sens, comme le ferait un ami qui l'écoute. Nous sommes le {now} (heure de Suisse).

Tu remplis TOUT le formulaire de l'événement, et tu le modifies quand la personne le demande (« enlève le sondage »,
« mets 15 places », « pas d'accompagnants », « ajoute Léa en co-organisatrice »…). Champs :
- title : court, naturel et précis (« Raclette chez {first} », « Fondue au Café de Collex »). « chez moi » = chez {first}.
- description : ce qui est utile aux invités, repris de ce qui a été dit (programme, tenue, transport…), bien rédigé,
  sans rien inventer. N'y recopie pas ce qui a son propre champ (sondages, qui amène quoi, prix).
- date_mode : « fixed » (une date) ou « poll » (la personne veut faire voter une date : « on vote pour la date »,
  « vendredi ou samedi ? »). start / end : date et heure locales AAAA-MM-JJTHH:MM (date fixe) ; « samedi » = le
  prochain samedi ; « 19h », « 7 heures du soir » ; sans heure de fin : end vide. date_options : les dates proposées
  au vote (poll, au moins deux) ; poll_deadline : fin du vote si dite. Une date passée n'est jamais voulue.
- place_query : ce qu'il faut chercher sur une carte (« Café de Collex, Collex-Bossy », « Chemin des Vignes 4, Lutry »),
  en corrigeant les fautes de dictée ; vide si aucun lieu. place_name : nom court du lieu. place_broad : une recherche
  plus large du même lieu si le nom a pu être mal dicté : type de lieu et ville (« bar techno, Ferney-Voltaire ») ; vide
  pour une adresse précise.
- price_chf : prix par personne (0 si gratuit ou non dit). payment_info : comment payer (« TWINT », « sur place »,
  « billets en ligne »).
- max_participants : 0 = pas de limite. waitlist : liste d'attente quand c'est plein (true par défaut).
- plus_ones : accompagnants (+1) permis (true par défaut) ; max_plus_ones : 0 = sans limite.
- allow_maybe : réponse « Peut-être » permise (true par défaut). rsvp_deadline : date limite de réponse si dite.
- show_participants : liste des participants visible (true par défaut). forum : discussion de l'événement (true par
  défaut). notify : prévenir les invités à la publication (true par défaut).
- category : la plus juste parmi la liste, ou vide. tags : parmi la liste des tags, seulement s'ils vont vraiment.
- audience : le groupe invité, parmi la liste ; « {vip} » si rien n'est dit ; « {only} » si la personne n'invite
  que des personnes nommées. invitees : personnes invitées par leur nom, parmi la liste des personnes (rapproche les
  noms mal dictés). organizers : co-organisateurs nommés, parmi la liste des personnes.
- polls : les mini-sondages demandés (« un sondage pour savoir qui mange la fondue ou autre chose ») : question claire
  et options (« Fondue moitié-moitié », « Autre plat ») ; multiple : plusieurs réponses permises ; anonymous : votes
  cachés ; add_options : les invités peuvent ajouter des options (« ouvert », « chacun propose »).
- bring : « qui amène quoi » : la liste de ce que l'organisateur demande (« salade », « dessert », « boissons »,
  « 2 bouteilles de vin ») ; chaque invité choisira ce qu'il amène.
- pot : pot commun pour partager les dépenses.
- summary : une phrase qui résume l'événement tel que tu l'as compris, en tutoyant.
- not_understood : ce que tu n'as pas compris ou pas pu placer, cité avec ce que tu en penses. Vide si tout est clair.

S'il manque la date (ou les dates à voter), ou si un point est vraiment ambigu (deux dates possibles, une heure sans
matin/soir évident, un nom qui correspond à plusieurs personnes), status = « needs_info » et questions = les questions
précises, courtes, en tutoyant (une par point). Ne pose pas de question sur ce que tu peux déduire. Sinon status =
« ready ». Garde toujours tout ce qui est déjà compris ; quand la personne répond ou corrige, applique exactement ce
qu'elle dit au brouillon précédent sans rien perdre d'autre.

Catégories : {categories}
Tags : {tags}
Groupes (audience) : {audiences}
Personnes : {people}"""


def schema(choices: dict[str, list[str]]) -> dict:
    text = {"type": "string"}
    texts = {"type": "array", "items": text}
    flag = {"type": "boolean"}
    count = {"type": "integer"}

    def among(name: str) -> dict:
        return {"type": "array", "items": {"type": "string", "enum": choices[name] or [""]}}

    poll = {"type": "object",
            "properties": {"question": text, "options": texts, "multiple": flag, "anonymous": flag, "add_options": flag},
            "required": ["question", "options", "multiple", "anonymous", "add_options"], "additionalProperties": False}
    properties = {
        "status": {"type": "string", "enum": ["ready", "needs_info"]}, "questions": texts,
        "title": text, "description": text,
        "date_mode": {"type": "string", "enum": ["fixed", "poll"]}, "start": text, "end": text,
        "date_options": texts, "poll_deadline": text,
        "place_query": text, "place_name": text, "place_broad": text,
        "price_chf": {"type": "number"}, "payment_info": text,
        "max_participants": count, "waitlist": flag, "plus_ones": flag, "max_plus_ones": count,
        "allow_maybe": flag, "rsvp_deadline": text, "show_participants": flag, "forum": flag, "notify": flag,
        "category": {"type": "string", "enum": choices["categories"] + [""]}, "tags": among("tags"),
        "audience": {"type": "string", "enum": choices["audiences"]},
        "invitees": among("people"), "organizers": among("people"),
        "polls": {"type": "array", "items": poll}, "bring": texts, "pot": flag,
        "summary": text, "not_understood": texts,
    }
    return {"type": "object", "properties": properties, "required": list(properties), "additionalProperties": False}


def local_time(value: str, now: datetime) -> datetime | None:
    """« 2026-11-07T20:00 » (heure de Suisse) → date avec fuseau ; rien si illisible ou déjà passée."""
    try:
        when = datetime.strptime(str(value or "")[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=ZURICH)
    except ValueError:
        return None
    return when if when > now else None


def _text(raw: dict, key: str, limit: int) -> str:
    return str(raw.get(key) or "").strip()[:limit]


def _texts(values, limit: int, most: int) -> list[str]:
    return list(dict.fromkeys(str(v).strip()[:limit] for v in values or [] if str(v).strip()))[:most]


def _number(value, top: float, kind=float):
    try:
        return max(kind(0), min(kind(value or 0), kind(top)))
    except (TypeError, ValueError):
        return kind(0)


def _flag(raw: dict, key: str, default: bool) -> bool:
    return raw[key] if isinstance(raw.get(key), bool) else default


def _when(value, now: datetime) -> str:
    t = local_time(value, now)
    return t.strftime("%Y-%m-%dT%H:%M") if t else ""


def clean_draft(raw: dict, now: datetime, choices: dict[str, list[str]]) -> dict:
    """Réponse de Claude → brouillon sûr : champs bornés, dates vérifiées, choix limités aux listes connues, et les
    questions qui manquent ajoutées."""
    questions = _texts(raw.get("questions"), 200, 5)
    title = _text(raw, "title", 120)
    poll_mode = raw.get("date_mode") == "poll"
    start = _when(raw.get("start"), now) if not poll_mode else ""
    end = _when(raw.get("end"), now) if start else ""
    if end and end < start:
        end = ""
    slots = sorted({s for s in (_when(v, now) for v in raw.get("date_options") or []) if s})[:10] if poll_mode else []
    if not title and not any("titre" in q.lower() or "appeler" in q.lower() for q in questions):
        questions.append("Comment veux-tu appeler cet événement ?")
    dated = len(slots) >= 2 if poll_mode else bool(start)
    if not dated and not any(w in q.lower() for q in questions for w in ("quand", "date", "jour", "heure")):
        questions.append("Quelles dates proposer au vote ?" if poll_mode else "Quel jour et à quelle heure ?")
    polls = []
    for p in (raw.get("polls") or [])[:5]:
        question = str((p or {}).get("question") or "").strip()[:200]
        options = _texts((p or {}).get("options"), 120, 12)
        if question and (len(options) >= 2 or (p or {}).get("add_options")):
            polls.append({"question": question, "options": options, "multiple": bool(p.get("multiple")),
                          "anonymous": bool(p.get("anonymous")), "add_options": bool(p.get("add_options"))})
    return {
        "status": "ready" if title and dated and not questions else "needs_info",
        "questions": questions,
        "title": title,
        "description": _text(raw, "description", 2000),
        "date_mode": "poll" if poll_mode else "fixed",
        "start": start, "end": end, "date_options": slots,
        "poll_deadline": _when(raw.get("poll_deadline"), now) if poll_mode else "",
        "place_query": _text(raw, "place_query", 200),
        "place_name": _text(raw, "place_name", 120),
        "place_broad": _text(raw, "place_broad", 200),
        "price_chf": round(_number(raw.get("price_chf"), 10000.0), 2),
        "payment_info": _text(raw, "payment_info", 200),
        "max_participants": _number(raw.get("max_participants"), 10000, int),
        "waitlist": _flag(raw, "waitlist", True),
        "plus_ones": _flag(raw, "plus_ones", True),
        "max_plus_ones": _number(raw.get("max_plus_ones"), UNLIMITED_PLUS_ONES - 1, int),
        "allow_maybe": _flag(raw, "allow_maybe", True),
        "rsvp_deadline": _when(raw.get("rsvp_deadline"), now),
        "show_participants": _flag(raw, "show_participants", True),
        "forum": _flag(raw, "forum", True),
        "notify": _flag(raw, "notify", True),
        "category": raw.get("category") if raw.get("category") in choices["categories"] else "",
        "tags": [t for t in _texts(raw.get("tags"), 60, 10) if t in choices["tags"]],
        "audience": raw.get("audience") if raw.get("audience") in choices["audiences"] else VIP_AUDIENCE,
        "invitees": [n for n in _texts(raw.get("invitees"), 80, 50) if n in choices["people"]],
        "organizers": [n for n in _texts(raw.get("organizers"), 80, 10) if n in choices["people"]],
        "polls": polls,
        "bring": _texts(raw.get("bring"), 80, 20),
        "pot": bool(raw.get("pot")),
        "summary": _text(raw, "summary", 300),
        "not_understood": _texts(raw.get("not_understood"), 200, 5),
    }


def safe_url(url) -> str | None:
    url = str(url or "").strip()[:500]
    return url if url.startswith("https://") else None


class Options:
    """Ce que la personne peut choisir : catégories et tags (nom → id), groupes (nom → id ; None = Vendredi Party,
    « people » = seulement les invités nommés, « public » = lien), personnes (nom → id, l'annuaire que ses droits lui
    laissent voir) et son propre prénom."""

    def __init__(self, categories: dict[str, str], tags: dict[str, str], audiences: dict[str, str | None],
                 people: dict[str, str], me: str):
        self.categories, self.tags, self.audiences, self.people, self.me = categories, tags, audiences, people, me

    @property
    def choices(self) -> dict[str, list[str]]:
        return {"categories": list(self.categories), "tags": list(self.tags), "audiences": list(self.audiences),
                "people": list(self.people)}

    def clean(self, raw: dict, now: datetime) -> dict:
        return clean_draft(raw, now, self.choices)


class EventAssistant:
    def __init__(self, assistant, accounts):
        self.ai = assistant
        self.accounts = accounts

    def _rows(self, token: str, path: str) -> list[dict]:
        r = self.accounts._get("GET", path, token)
        rows = r.json() if r.status_code == 200 else []
        return [x for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []

    def _options(self, token: str) -> Options:
        categories = {c["name"]: c["id"] for c in self._rows(token, "/rest/v1/categories?select=id,name&archived=eq.false&order=sort")}
        tags = {t["name"]: t["id"] for t in self._rows(token, "/rest/v1/tags?select=id,name&archived=eq.false&order=name")}
        mine = self.accounts.groups(token)
        audiences: dict[str, str | None] = {VIP_AUDIENCE: None}
        for g in mine["groups"]:
            if not g["system"] and g["name"] not in audiences:
                audiences[g["name"]] = g["id"]
        audiences[ONLY_INVITEES] = "people"
        audiences[PUBLIC_AUDIENCE] = "public"
        people: dict[str, str] = {}
        for p in mine.get("people", []):
            people.setdefault(p["name"], p["id"])  # deux personnes au même nom : l'IA demandera laquelle
        try:
            me = self.accounts.link(token).get("name") or ""
        except AccountError:
            me = ""
        return Options(categories, tags, audiences, people, me)

    def _can_create(self, token: str) -> set[str]:
        perms = self.accounts._perms(token)
        if "events.create" not in perms:
            raise AccountError("Ton compte ne peut pas créer d'événement.")
        return perms

    def draft(self, token: str, turns: list[str], previous: dict | None) -> dict:
        """Ce que la personne a dit (description, puis ses réponses et corrections) → brouillon complet et questions."""
        uid = self.ai._check(token)
        self._can_create(token)
        turns = [str(t).strip()[:MAX_TEXT] for t in turns if str(t).strip()][-MAX_TURNS:]
        if not turns:
            raise AccountError("Décris l'événement, à voix haute ou par écrit.")
        o = self._options(token)
        now = datetime.now(ZURICH)
        system = SYSTEM.format(now=f"{WEEKDAYS[now.weekday()]} {now:%d.%m.%Y %H:%M}", vip=VIP_AUDIENCE, only=ONLY_INVITEES,
                               me=o.me or "La personne", first=o.me.split()[0] if o.me else "moi",
                               categories=", ".join(o.categories) or "(aucune)", tags=", ".join(o.tags) or "(aucun)",
                               audiences=", ".join(o.audiences), people=", ".join(o.people) or "(aucune)")
        # Conversation : la description, le brouillon renvoyé (avec ses questions), puis les réponses de la personne.
        messages = [{"role": "user", "content": turns[0]}]
        if previous and len(turns) > 1:
            messages += [{"role": "assistant", "content": json.dumps(previous, ensure_ascii=False)[:8000]},
                         {"role": "user", "content": "\n".join(turns[1:])}]
        elif len(turns) > 1:
            messages[0]["content"] += "\n\nPuis : " + "\n".join(turns[1:])
        client = self.ai._client_or_error()
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS, system=system,
                output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": schema(o.choices)}},
                messages=messages)
        except Exception as e:  # réseau ou API : message clair, détail dans le journal du serveur
            self.ai.warn("Brouillon d'événement impossible", e)
            raise AccountError("L'assistant ne répond pas. Réessaie dans un instant.") from None
        self.ai._log(uid, token, "event", getattr(response, "usage", None), MODEL, " ⏎ ".join(turns))
        if response.stop_reason in ("refusal", "max_tokens"):
            raise AccountError(NOT_UNDERSTOOD)
        try:
            raw = json.loads(next(b.text for b in response.content if getattr(b, "type", "") == "text"))
        except (StopIteration, ValueError):
            raise AccountError(NOT_UNDERSTOOD) from None
        return o.clean(raw, now)

    def _event_row(self, d: dict, o: Options, place: dict, uid: str, now: datetime) -> dict:
        audience = o.audiences.get(d["audience"])
        fixed = d["date_mode"] == "fixed"
        return {
            "title": d["title"], "description": d["description"], "category_id": o.categories.get(d["category"]),
            "date_mode": d["date_mode"],
            "starts_at": local_time(d["start"], now).isoformat() if fixed else None,
            "ends_at": local_time(d["end"], now).isoformat() if fixed and d["end"] else None,
            "poll_deadline": local_time(d["poll_deadline"], now).isoformat() if d["poll_deadline"] else None,
            "location_name": (str(place.get("name") or "").strip() or d["place_name"])[:120] or None,
            "location_address": str(place.get("address") or "").strip()[:300] or None,
            "location_url": safe_url(place.get("url")),
            "price_chf": d["price_chf"] or None, "payment_info": d["payment_info"] or None,
            "max_participants": d["max_participants"] or None, "waitlist_enabled": d["waitlist"],
            "allow_plus_ones": d["plus_ones"], "max_plus_ones": d["max_plus_ones"] or UNLIMITED_PLUS_ONES,
            "allow_maybe": d["allow_maybe"],
            "rsvp_deadline": local_time(d["rsvp_deadline"], now).isoformat() if d["rsvp_deadline"] else None,
            "visibility": "all" if audience in (None, "public") else "invited", "public_link": audience == "public",
            "show_participants": d["show_participants"], "forum_enabled": d["forum"], "notify_on_publish": d["notify"],
            "pot_enabled": d["pot"], "reminders": REMINDERS, "created_by": uid, "status": "draft",
        }

    def _add(self, token: str, path: str, rows, what: str, problems: list[str], one: bool = False):
        """Ajout lié à l'événement ; un échec n'annule pas l'événement mais il est signalé à la personne."""
        r = self.accounts._get("POST", path, token, json=rows, headers={"Prefer": "return=representation"} if one else None)
        if r.status_code not in (200, 201, 204):
            problems.append(what)
            return None
        return r.json()[0] if one and r.json() else None

    def create(self, token: str, draft: dict, place: dict | None) -> dict:
        """Brouillon confirmé (après le compte à rebours de l'app) → événement complet, écrit avec la session de la personne."""
        uid = self.ai.allowed(token)
        perms = self._can_create(token)
        o = self._options(token)
        now = datetime.now(ZURICH)
        d = o.clean({**draft, "questions": []}, now)
        if d["status"] != "ready":
            raise AccountError("Il manque encore le titre ou la date.")
        audience = o.audiences.get(d["audience"])
        if audience == "people" and not d["invitees"]:
            raise AccountError("Dis qui inviter : personne n'est nommé.")
        r = self.accounts._get("POST", "/rest/v1/events?select=id", token,
                               json=self._event_row(d, o, place if isinstance(place, dict) else {}, uid, now),
                               headers={"Prefer": "return=representation"})
        rows = r.json() if r.status_code in (200, 201) else None
        if not rows:
            raise AccountError("L'événement n'a pas pu être créé. Réessaie, ou crée-le à la main.")
        eid = rows[0]["id"]
        problems: list[str] = []
        if audience not in (None, "public", "people"):
            self._add(token, "/rest/v1/event_groups", {"event_id": eid, "group_id": audience}, "le groupe invité", problems)
        invited = [o.people[n] for n in d["invitees"] if o.people[n] != uid]
        if invited and audience != "public":
            self._add(token, "/rest/v1/event_invites", [{"event_id": eid, "user_id": w} for w in invited], "les invitations", problems)
        helpers = [o.people[n] for n in d["organizers"] if o.people[n] != uid]
        if helpers:
            self._add(token, "/rest/v1/event_organizers", [{"event_id": eid, "user_id": w} for w in helpers],
                      "les co-organisateurs", problems)
        if d["tags"]:
            self._add(token, "/rest/v1/event_tags", [{"event_id": eid, "tag_id": o.tags[t]} for t in d["tags"]], "les tags", problems)
        if d["date_mode"] == "poll":
            self._add(token, "/rest/v1/date_options",
                      [{"event_id": eid, "starts_at": local_time(s, now).isoformat(), "proposed_by": uid} for s in d["date_options"]],
                      "les dates à voter", problems)
        for i, p in enumerate(d["polls"]):
            made = self._add(token, "/rest/v1/polls?select=id", {
                "event_id": eid, "question": p["question"], "multiple_choice": p["multiple"], "anonymous": p["anonymous"],
                "members_can_add_options": p["add_options"], "created_by": uid, "sort": i}, f"le sondage « {p['question']} »",
                problems, one=True)
            if made and p["options"]:
                self._add(token, "/rest/v1/poll_options",
                          [{"poll_id": made["id"], "label": label, "created_by": uid, "sort": j} for j, label in enumerate(p["options"])],
                          f"les choix du sondage « {p['question']} »", problems)
        if d["bring"]:
            self._add(token, "/rest/v1/bring_items", [{"event_id": eid, "label": b, "sort": i} for i, b in enumerate(d["bring"])],
                      "« qui amène quoi »", problems)
        status = "published" if "events.publish_direct" in perms else "pending"
        p = self.accounts._get("PATCH", f"/rest/v1/events?id=eq.{eid}", token, json={"status": status})
        if p.status_code not in (200, 204):
            raise AccountError("L'événement est enregistré en brouillon : ouvre-le pour le publier.")
        return {"id": eid, "status": status, "title": d["title"], "problems": problems}
