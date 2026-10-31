"""Créer un événement en le décrivant (assistant IA) : la personne parle ou écrit, Claude remplit l'événement et pose
ses questions s'il manque quelque chose ; l'app montre le résultat, cherche l'adresse, puis la personne confirme.

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
VIP_AUDIENCE = "Vendredi Party"
PUBLIC_AUDIENCE = "Public (lien)"
ONLY_INVITEES = "Seulement les personnes invitées"
WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NOT_UNDERSTOOD = "Je n'ai pas réussi à comprendre la description. Réessaie, ou crée l'événement à la main."

SYSTEM = """Tu es l'assistant de l'app suisse « Party » (soirées et sorties entre amis, en Suisse romande). {me} te
décrit un événement qu'il ou elle organise, le plus souvent DICTÉ à voix haute : la reconnaissance vocale fait des
fautes (noms propres, lieux, chiffres, mots collés ou coupés). Reconstitue ce que la personne a VOULU dire, avec bon
sens, comme le ferait un ami qui l'écoute. Nous sommes le {now} (heure de Suisse).

Ce que tu remplis :
- title : court, naturel et précis (« Raclette chez {first} », « Bowling au Fun Planet », « Anniversaire de Tom »).
  « chez moi » = chez {first}.
- description : ce qui est utile aux invités, repris de ce qui a été dit (programme, quoi amener, tenue, transport…),
  bien rédigé, sans rien inventer.
- start / end : date et heure locales AAAA-MM-JJTHH:MM. Dates relatives : « samedi » = le prochain samedi ;
  « ce soir », « demain soir », « dans deux semaines », « le 14 » (prochain 14 à venir) ; « 19h », « 7 heures du soir »,
  « 20h30 ». Soirée sans heure de fin : end vide. Une date passée n'est jamais voulue.
- place_query : ce qu'il faut chercher sur une carte (« Fun Planet, Villeneuve VD », « Chemin des Vignes 4, Lutry »),
  en corrigeant les fautes de dictée des noms de lieux suisses ; vide si aucun lieu. place_name : nom court du lieu.
- price_chf : prix par personne en francs (0 si gratuit ou non dit). max_participants : 0 si pas de limite dite.
- category : la plus juste parmi la liste, ou vide si aucune ne va.
- audience : le groupe invité, parmi la liste ; « {vip} » si rien n'est dit ; « {only} » si la personne n'invite
  que des personnes nommées (« juste Léa et Tom »).
- invitees : les personnes invitées par leur nom, parmi la liste des personnes (rapproche les noms mal dictés :
  « Léa », « Léa Martin » ; « Tom » → « Thomas » s'il n'y a pas d'autre Tom). Vide si personne n'est nommé.
- pot : true si la personne veut un pot commun (partager les dépenses, « on fait les comptes »…).
- bring : ce que les invités peuvent amener, si c'est dit.
- summary : une phrase qui résume l'événement tel que tu l'as compris, en tutoyant.
- not_understood : les morceaux que tu n'as pas compris ou pas pu placer, cités tels quels avec ce que tu en penses
  (« "chez la Mère Royaume" : je n'ai pas trouvé ce lieu »). Vide si tout est clair.

S'il manque la date ou l'heure, ou si un point est vraiment ambigu (deux dates possibles, une heure sans matin/soir
évident, un lieu introuvable, un nom qui correspond à plusieurs personnes), status = « needs_info » et questions = les
questions précises, courtes, en tutoyant (une par point). Ne pose pas de question sur ce que tu peux raisonnablement
déduire. Sinon status = « ready » et questions vide. Garde toujours dans les champs tout ce qui est déjà compris.
Quand la personne répond ou corrige, applique exactement ce qu'elle dit au brouillon précédent.

Catégories : {categories}
Groupes (audience) : {audiences}
Personnes : {people}"""


def schema(categories: list[str], audiences: list[str], people: list[str]) -> dict:
    text = {"type": "string"}
    return {
        "type": "object",
        "properties": {
            "status": {"type": "string", "enum": ["ready", "needs_info"]},
            "questions": {"type": "array", "items": text},
            "title": text, "description": text, "start": text, "end": text,
            "place_query": text, "place_name": text,
            "price_chf": {"type": "number"}, "max_participants": {"type": "integer"},
            "category": {"type": "string", "enum": categories + [""]},
            "audience": {"type": "string", "enum": audiences},
            "invitees": {"type": "array", "items": {"type": "string", "enum": people or [""]}},
            "not_understood": {"type": "array", "items": text},
            "pot": {"type": "boolean"},
            "bring": {"type": "array", "items": text},
            "summary": text,
        },
        "required": ["status", "questions", "title", "description", "start", "end", "place_query", "place_name",
                     "price_chf", "max_participants", "category", "audience", "invitees", "not_understood", "pot",
                     "bring", "summary"],
        "additionalProperties": False,
    }


def local_time(value: str, now: datetime) -> datetime | None:
    """« 2026-11-07T20:00 » (heure de Suisse) → date avec fuseau ; rien si illisible ou déjà passée."""
    try:
        when = datetime.strptime(str(value or "")[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=ZURICH)
    except ValueError:
        return None
    return when if when > now else None


def clean_draft(raw: dict, now: datetime, categories: list[str], audiences: list[str], people: list[str]) -> dict:
    """Réponse de Claude → brouillon sûr : champs bornés, dates vérifiées, et les questions qui manquent ajoutées."""
    questions = [str(q).strip()[:200] for q in raw.get("questions") or [] if str(q).strip()][:5]
    title = str(raw.get("title") or "").strip()[:120]
    start = local_time(raw.get("start"), now)
    end = local_time(raw.get("end"), now)
    if end and start and end < start:
        end = None
    if not title and not any("titre" in q.lower() or "appeler" in q.lower() for q in questions):
        questions.append("Comment veux-tu appeler cet événement ?")
    if not start and not any(w in q.lower() for q in questions for w in ("quand", "date", "jour", "heure")):
        questions.append("Quel jour et à quelle heure ?")
    try:
        price = max(0.0, min(float(raw.get("price_chf") or 0), 10000.0))
        places = max(0, min(int(raw.get("max_participants") or 0), 10000))
    except (TypeError, ValueError):
        price, places = 0.0, 0
    return {
        "status": "ready" if title and start and not questions else "needs_info",
        "questions": questions,
        "title": title,
        "description": str(raw.get("description") or "").strip()[:2000],
        "start": start.strftime("%Y-%m-%dT%H:%M") if start else "",
        "end": end.strftime("%Y-%m-%dT%H:%M") if end else "",
        "place_query": str(raw.get("place_query") or "").strip()[:200],
        "place_name": str(raw.get("place_name") or "").strip()[:120],
        "price_chf": round(price, 2),
        "max_participants": places,
        "category": raw.get("category") if raw.get("category") in categories else "",
        "audience": raw.get("audience") if raw.get("audience") in audiences else VIP_AUDIENCE,
        "invitees": list(dict.fromkeys(n for n in raw.get("invitees") or [] if n in people))[:50],
        "not_understood": [str(n).strip()[:200] for n in raw.get("not_understood") or [] if str(n).strip()][:5],
        "pot": bool(raw.get("pot")),
        "bring": [str(b).strip()[:80] for b in raw.get("bring") or [] if str(b).strip()][:15],
        "summary": str(raw.get("summary") or "").strip()[:300],
    }


def safe_url(url) -> str | None:
    url = str(url or "").strip()[:500]
    return url if url.startswith("https://") else None


class Options:
    """Ce que la personne peut choisir : catégories (nom → id), groupes (nom → id ; None = Vendredi Party,
    « public » = lien), personnes (nom → id, l'annuaire que ses droits lui laissent voir) et son propre prénom."""

    def __init__(self, categories: dict[str, str], audiences: dict[str, str | None], people: dict[str, str], me: str):
        self.categories, self.audiences, self.people, self.me = categories, audiences, people, me

    def clean(self, raw: dict, now: datetime) -> dict:
        return clean_draft(raw, now, list(self.categories), list(self.audiences), list(self.people))


class EventAssistant:
    def __init__(self, assistant, accounts):
        self.ai = assistant
        self.accounts = accounts

    def _options(self, token: str) -> Options:
        r = self.accounts._get("GET", "/rest/v1/categories?select=id,name&archived=eq.false&order=sort", token)
        rows = r.json() if r.status_code == 200 else []
        categories = {c["name"]: c["id"] for c in rows if isinstance(c, dict)}
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
        return Options(categories, audiences, people, me)

    def _can_create(self, token: str) -> set[str]:
        perms = self.accounts._perms(token)
        if "events.create" not in perms:
            raise AccountError("Ton compte ne peut pas créer d'événement.")
        return perms

    def draft(self, token: str, turns: list[str], previous: dict | None) -> dict:
        """Ce que la personne a dit (description, puis ses réponses) → brouillon d'événement, et ses questions."""
        uid = self.ai._check(token)
        self._can_create(token)
        turns = [str(t).strip()[:MAX_TEXT] for t in turns if str(t).strip()][-MAX_TURNS:]
        if not turns:
            raise AccountError("Décris l'événement, à voix haute ou par écrit.")
        o = self._options(token)
        now = datetime.now(ZURICH)
        first = o.me.split()[0] if o.me else "moi"
        system = SYSTEM.format(now=f"{WEEKDAYS[now.weekday()]} {now:%d.%m.%Y %H:%M}", vip=VIP_AUDIENCE, only=ONLY_INVITEES,
                               me=o.me or "La personne", first=first,
                               categories=", ".join(o.categories) or "(aucune)", audiences=", ".join(o.audiences),
                               people=", ".join(o.people) or "(aucune)")
        # Conversation : la description, le brouillon renvoyé (avec ses questions), puis les réponses de la personne.
        messages = [{"role": "user", "content": turns[0]}]
        if previous and len(turns) > 1:
            messages += [{"role": "assistant", "content": json.dumps(previous, ensure_ascii=False)[:6000]},
                         {"role": "user", "content": "\n".join(turns[1:])}]
        elif len(turns) > 1:
            messages[0]["content"] += "\n\nPuis : " + "\n".join(turns[1:])
        client = self.ai._client_or_error()
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS, system=system,
                output_config={"effort": EFFORT, "format": {"type": "json_schema",
                                                            "schema": schema(list(o.categories), list(o.audiences), list(o.people))}},
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

    def create(self, token: str, draft: dict, place: dict | None) -> dict:
        """Brouillon confirmé (après le compte à rebours de l'app) → événement, écrit avec la session de la personne."""
        uid = self.ai.allowed(token)
        perms = self._can_create(token)
        o = self._options(token)
        now = datetime.now(ZURICH)
        d = o.clean({**draft, "questions": []}, now)
        if d["status"] != "ready":
            raise AccountError("Il manque encore le titre ou la date.")
        if o.audiences.get(d["audience"]) == "people" and not d["invitees"]:
            raise AccountError("Dis qui inviter : personne n'est nommé.")
        place = place if isinstance(place, dict) else {}
        audience = o.audiences.get(d["audience"])
        row = {
            "title": d["title"], "description": d["description"], "category_id": o.categories.get(d["category"]),
            "date_mode": "fixed", "starts_at": local_time(d["start"], now).isoformat(),
            "ends_at": local_time(d["end"], now).isoformat() if d["end"] else None,
            "location_name": (str(place.get("name") or "").strip() or d["place_name"])[:120] or None,
            "location_address": str(place.get("address") or "").strip()[:300] or None,
            "location_url": safe_url(place.get("url")),
            "price_chf": d["price_chf"] or None, "max_participants": d["max_participants"] or None,
            "visibility": "all" if audience in (None, "public") else "invited",
            "public_link": audience == "public", "pot_enabled": d["pot"], "reminders": REMINDERS,
            "created_by": uid, "status": "draft",
        }
        r = self.accounts._get("POST", "/rest/v1/events?select=id", token, json=row,
                               headers={"Prefer": "return=representation"})
        rows = r.json() if r.status_code in (200, 201) else None
        if not rows:
            raise AccountError("L'événement n'a pas pu être créé. Réessaie, ou crée-le à la main.")
        eid = rows[0]["id"]
        if audience not in (None, "public", "people"):
            self.accounts._get("POST", "/rest/v1/event_groups", token, json={"event_id": eid, "group_id": audience})
        invited = [o.people[n] for n in d["invitees"] if n in o.people and o.people[n] != uid]
        if invited and audience != "public":
            self.accounts._get("POST", "/rest/v1/event_invites", token,
                               json=[{"event_id": eid, "user_id": who} for who in invited])
        if d["bring"]:
            self.accounts._get("POST", "/rest/v1/bring_items", token,
                               json=[{"event_id": eid, "label": b, "sort": i} for i, b in enumerate(d["bring"])])
        status = "published" if "events.publish_direct" in perms else "pending"
        p = self.accounts._get("PATCH", f"/rest/v1/events?id=eq.{eid}", token, json={"status": status})
        if p.status_code not in (200, 204):
            raise AccountError("L'événement est enregistré en brouillon : ouvre-le pour le publier.")
        return {"id": eid, "status": status, "title": d["title"]}
