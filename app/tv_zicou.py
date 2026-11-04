"""Les Zicou de la soirée sur l'Apple TV (décision G de l'admin, 04.11.2026) : le Zicou de chaque PRÉSENT (soirée liée
à un événement) ET de chaque joueur avec compte de la partie regardée (même sans événement lié, décision du 04.11.2026)
danse dans le coin musique de l'app Apple TV (ios/PartyTV), une seule fois chacun.

Le serveur Party n'a aucun accès direct aux Zicou (ils vivent dans Supabase, lus avec le jeton de leur propriétaire).
Quand l'app d'un présent revérifie son accès sans code (/api/join/account, toutes les 2 min, avec son propre jeton),
le serveur relit son Zicou EN LECTURE (pet_load, sans compter d'ouverture) et n'en garde ici, en mémoire, que l'aspect :
stade, humeur, variante, accessoires portés, shiny. La télé (/api/tv/zicou, hôte seulement) ne reçoit que les comptes
qui ont encore un accès « Présent » à la soirée, et ceux qui jouent à la partie regardée (aspect relu quand leur app
relie le compte, /api/account/link, au plus toutes les 90 s).

Jamais envoyé à la télé : identifiant du compte, nom du Zicou (texte libre), jauges, souvenirs, vitrine, photo.
Le nom affiché est le surnom du compte s'il passe la modération (app/moderation.py), sinon rien."""
import copy
import hashlib
import threading
import time
from datetime import datetime, timezone

from . import moderation, pet, pet_collection

REFRESH_SECONDS = 90          # un même Zicou n'est pas relu plus souvent (l'app revérifie toutes les 2 min)
KEEP_SECONDS = 6 * 3600       # au-delà, un aspect jamais rafraîchi n'est plus montré
SHOWN_STAGES = ("egg", "baby", "teen", "adult")   # un Zicou envolé ne danse pas
NAME_MAX = 20
MAX_LISTED = 60               # la télé fait tourner les Zicou visibles ; au-delà, inutile de tout envoyer


def tv_name(raw) -> str | None:
    """Surnom montrable sur la télé : modéré (refusé → rien), sans espaces superflus, court."""
    name = " ".join(str(raw or "").split())[:NAME_MAX]
    if not name:
        return None
    verdict = moderation.check(name, "name")
    return verdict.text if verdict.ok else None


def look(life: dict, now: datetime) -> dict | None:
    """Aspect d'un Zicou, vécu jusqu'à maintenant sans rien enregistrer ; None s'il ne doit pas danser."""
    try:
        seen = pet.friend_view(copy.deepcopy(life), now)
        acc = pet_collection.worn(life)
    except (KeyError, TypeError, ValueError):
        return None   # état illisible : ce Zicou n'apparaît pas plutôt que de tout casser
    if seen["stage"] not in SHOWN_STAGES:
        return None
    return {"stage": seen["stage"], "emotion": seen["emotion"], "variant": seen["variant"],
            "acc": {str(k): str(v) for k, v in acc.items()}, "shiny": bool(life.get("shiny")),
            "dye": pet_collection.dyes_worn(life)}


def tv_key(gid: str) -> str:
    """Identité stable et opaque pour la télé (rotation, animations) : jamais l'identifiant du compte."""
    return hashlib.sha256(f"tv-zicou:{gid}".encode()).hexdigest()[:12]


class SoireeZicous:
    def __init__(self, clock=time.time):
        self.clock = clock
        self.lock = threading.Lock()
        self.entries: dict[str, dict] = {}   # compte → {"at", "name", "look"}

    def due(self, uid: str) -> bool:
        with self.lock:
            entry = self.entries.get(uid)
        return entry is None or self.clock() - entry["at"] >= REFRESH_SECONDS

    def note(self, uid: str, name, life) -> None:
        """Aspect relu pour un présent (life : le personnage tel que la base le garde ; None : pas de Zicou)."""
        now = self.clock()
        shown = look(life, datetime.fromtimestamp(now, timezone.utc)) if isinstance(life, dict) else None
        with self.lock:
            if shown is None:
                self.entries.pop(uid, None)
            else:
                self.entries[uid] = {"at": now, "name": tv_name(name), "look": shown}

    def listed(self, present: set[str], gid_of, pid_of) -> list[dict]:
        """Zicou à montrer : `present` (présents et joueurs de la partie regardée, chacun une fois), aspect assez récent ;
        `pid_of(gid)` → place dans la partie regardée."""
        now = self.clock()
        with self.lock:
            rows = [(uid, e) for uid, e in self.entries.items() if uid in present and now - e["at"] < KEEP_SECONDS]
        out = []
        for uid, e in rows:
            gid = gid_of(uid)
            out.append({"key": tv_key(gid), "name": e["name"], **e["look"], "pid": pid_of(gid)})
        out.sort(key=lambda z: z["key"])
        return out[:MAX_LISTED]


def read_member(accounts, pets, token: str, uid: str) -> tuple[str, dict | None]:
    """(surnom, personnage ou None), lus avec le jeton du présent. Lecture seulement : pet_load sans ouverture comptée."""
    r = accounts._get("GET", f"/rest/v1/rpc/get_member_directory?id=eq.{uid}&select=display_name", token)
    rows = r.json() if r.status_code == 200 else []
    name = rows[0].get("display_name") if isinstance(rows, list) and rows and isinstance(rows[0], dict) else ""
    data = pets._rpc(token, "pet_load", {"p_src": None}, "Le Zicou n'a pas pu être lu.")
    saved = data.get("pet") if isinstance(data, dict) else None
    life = saved.get("life") if isinstance(saved, dict) else None
    return name or "", life if isinstance(life, dict) else None
