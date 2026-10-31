"""Créer un événement en le décrivant (assistant IA) : la personne parle ou écrit, Claude remplit l'événement et pose
ses questions s'il manque quelque chose ; l'app montre le résultat, cherche l'adresse, puis la personne confirme.

L'événement est écrit avec la session de la personne (règles de la base) : l'IA ne peut rien faire de plus qu'elle.
Comme dans le formulaire web : créé en brouillon, puis publié (droit « publier directement ») ou proposé."""
import json
from datetime import datetime
from zoneinfo import ZoneInfo

from .accounts import AccountError
from .assistant import MAX_TOKENS, MODEL

ZURICH = ZoneInfo("Europe/Zurich")
MAX_TEXT = 4000
MAX_TURNS = 8
REMINDERS = ["7d", "1d", "2h", "0h"]
VIP_AUDIENCE = "Vendredi Party"
PUBLIC_AUDIENCE = "Public (lien)"
WEEKDAYS = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]
NOT_UNDERSTOOD = "Je n'ai pas réussi à comprendre la description. Réessaie, ou crée l'événement à la main."

SYSTEM = """Tu aides à créer un événement entre amis dans l'app suisse « Party », à partir de ce qu'une personne a dit
(souvent dicté à voix haute : fautes de reconnaissance vocale possibles). Nous sommes le {now} (heure de Suisse).

Tu remplis l'événement :
- title : court et clair (« Raclette chez Léa », « Bowling à Lausanne »).
- description : quelques phrases utiles reprises de ce qui a été dit (programme, quoi amener, code vestimentaire…),
  sans inventer.
- start / end : date et heure locales au format AAAA-MM-JJTHH:MM ; « samedi » = le prochain samedi à venir ; sans heure
  de fin dite, end reste vide. Une date passée n'est jamais voulue.
- place_query : ce qu'il faut chercher sur une carte pour trouver le lieu (« Pizzeria Da Mario, Lausanne »,
  « Rue du Lac 12, Vevey ») ; vide si aucun lieu. place_name : le nom court du lieu (« Chez Léa », « Da Mario »).
- price_chf : prix par personne en francs (0 si gratuit ou non dit). max_participants : 0 si pas de limite dite.
- category : la plus juste parmi la liste, ou vide. audience : qui est invité, parmi la liste ; « {vip} » si rien n'est dit.
- pot : true si la personne veut un pot commun pour partager les dépenses.
- bring : ce que les invités peuvent amener, si c'est dit (« salade », « boissons »).
- summary : une phrase qui résume l'événement tel que tu l'as compris.

S'il manque le titre (ou de quoi en faire un) ou la date, ou si quelque chose est ambigu (« vendredi » alors qu'on est
vendredi soir, une heure sans matin/soir, deux lieux possibles…), status = « needs_info » et questions = les questions
précises à poser, en français, courtes, en tutoyant. Sinon status = « ready » et questions vide. Garde dans les champs
tout ce qui est déjà compris. Les réponses suivantes de la personne complètent ou corrigent le brouillon.

Catégories : {categories}
Invités possibles (audience) : {audiences}"""


def schema(categories: list[str], audiences: list[str]) -> dict:
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
            "pot": {"type": "boolean"},
            "bring": {"type": "array", "items": text},
            "summary": text,
        },
        "required": ["status", "questions", "title", "description", "start", "end", "place_query", "place_name",
                     "price_chf", "max_participants", "category", "audience", "pot", "bring", "summary"],
        "additionalProperties": False,
    }


def local_time(value: str, now: datetime) -> datetime | None:
    """« 2026-11-07T20:00 » (heure de Suisse) → date avec fuseau ; rien si illisible ou déjà passée."""
    try:
        when = datetime.strptime(str(value or "")[:16], "%Y-%m-%dT%H:%M").replace(tzinfo=ZURICH)
    except ValueError:
        return None
    return when if when > now else None


def clean_draft(raw: dict, now: datetime, categories: list[str], audiences: list[str]) -> dict:
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
        "pot": bool(raw.get("pot")),
        "bring": [str(b).strip()[:80] for b in raw.get("bring") or [] if str(b).strip()][:15],
        "summary": str(raw.get("summary") or "").strip()[:300],
    }


def safe_url(url) -> str | None:
    url = str(url or "").strip()[:500]
    return url if url.startswith("https://") else None


class EventAssistant:
    def __init__(self, assistant, accounts):
        self.ai = assistant
        self.accounts = accounts

    def _options(self, token: str) -> tuple[dict[str, str], dict[str, str | None]]:
        """Catégories (nom → id) et invités possibles (nom → groupe ; None = Vendredi Party, « public » = lien)."""
        r = self.accounts._get("GET", "/rest/v1/categories?select=id,name&archived=eq.false&order=sort", token)
        rows = r.json() if r.status_code == 200 else []
        categories = {c["name"]: c["id"] for c in rows if isinstance(c, dict)}
        audiences: dict[str, str | None] = {VIP_AUDIENCE: None}
        for g in self.accounts.groups(token)["groups"]:
            if not g["system"] and g["name"] not in audiences:
                audiences[g["name"]] = g["id"]
        audiences[PUBLIC_AUDIENCE] = "public"
        return categories, audiences

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
        categories, audiences = self._options(token)
        now = datetime.now(ZURICH)
        system = SYSTEM.format(now=f"{WEEKDAYS[now.weekday()]} {now:%d.%m.%Y %H:%M}", vip=VIP_AUDIENCE,
                               categories=", ".join(categories) or "(aucune)", audiences=", ".join(audiences))
        said = "Description de l'événement :\n" + turns[0]
        if len(turns) > 1:
            said += "\n\nRéponses et précisions données ensuite :\n" + "\n".join(f"- {t}" for t in turns[1:])
        if previous:
            said += "\n\nBrouillon actuel (à compléter ou corriger) :\n" + json.dumps(previous, ensure_ascii=False)[:4000]
        client = self.ai._client_or_error()
        try:
            response = client.messages.create(
                model=MODEL, max_tokens=MAX_TOKENS, system=system,
                output_config={"effort": "low",
                               "format": {"type": "json_schema", "schema": schema(list(categories), list(audiences))}},
                messages=[{"role": "user", "content": said}])
        except Exception as e:  # réseau ou API : message clair, détail dans le journal du serveur
            self.ai.warn("Brouillon d'événement impossible", e)
            raise AccountError("L'assistant ne répond pas. Réessaie dans un instant.") from None
        self.ai._log(uid, token, "event", getattr(response, "usage", None))
        if response.stop_reason in ("refusal", "max_tokens"):
            raise AccountError(NOT_UNDERSTOOD)
        try:
            raw = json.loads(next(b.text for b in response.content if getattr(b, "type", "") == "text"))
        except (StopIteration, ValueError):
            raise AccountError(NOT_UNDERSTOOD) from None
        return clean_draft(raw, now, list(categories), list(audiences))

    def create(self, token: str, draft: dict, place: dict | None) -> dict:
        """Brouillon confirmé (après le compte à rebours de l'app) → événement, écrit avec la session de la personne."""
        uid = self.ai.allowed(token)
        perms = self._can_create(token)
        categories, audiences = self._options(token)
        now = datetime.now(ZURICH)
        d = clean_draft({**draft, "questions": []}, now, list(categories), list(audiences))
        if d["status"] != "ready":
            raise AccountError("Il manque encore le titre ou la date.")
        place = place if isinstance(place, dict) else {}
        audience = audiences.get(d["audience"])
        row = {
            "title": d["title"], "description": d["description"], "category_id": categories.get(d["category"]),
            "date_mode": "fixed", "starts_at": local_time(d["start"], now).isoformat(),
            "ends_at": local_time(d["end"], now).isoformat() if d["end"] else None,
            "location_name": (str(place.get("name") or "").strip() or d["place_name"])[:120] or None,
            "location_address": str(place.get("address") or "").strip()[:300] or None,
            "location_url": safe_url(place.get("url")),
            "price_chf": d["price_chf"] or None, "max_participants": d["max_participants"] or None,
            "visibility": "invited" if audience not in (None, "public") else "all",
            "public_link": audience == "public", "pot_enabled": d["pot"], "reminders": REMINDERS,
            "created_by": uid, "status": "draft",
        }
        r = self.accounts._get("POST", "/rest/v1/events?select=id", token, json=row,
                               headers={"Prefer": "return=representation"})
        rows = r.json() if r.status_code in (200, 201) else None
        if not rows:
            raise AccountError("L'événement n'a pas pu être créé. Réessaie, ou crée-le à la main.")
        eid = rows[0]["id"]
        if audience not in (None, "public"):
            self.accounts._get("POST", "/rest/v1/event_groups", token, json={"event_id": eid, "group_id": audience})
        if d["bring"]:
            self.accounts._get("POST", "/rest/v1/bring_items", token,
                               json=[{"event_id": eid, "label": b, "sort": i} for i, b in enumerate(d["bring"])])
        status = "published" if "events.publish_direct" in perms else "pending"
        p = self.accounts._get("PATCH", f"/rest/v1/events?id=eq.{eid}", token, json={"status": status})
        if p.status_code not in (200, 204):
            raise AccountError("L'événement est enregistré en brouillon : ouvre-le pour le publier.")
        return {"id": eid, "status": status, "title": d["title"]}
