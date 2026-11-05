"""Compagnon : lecture / écriture du personnage dans Supabase (au nom du compte connecté, fonctions pet_* de la
migration 20261104130000_compagnon.sql) et parties de Party terminées (récompenses). Le calcul de vie est dans
app/pet.py ; ici, on charge, on fait vivre jusqu'à maintenant, on applique, on enregistre."""
import base64
import copy
import hashlib
import hmac
import json
import logging
import os
import random
import secrets
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import (moderation, pet, pet_bar, pet_coll_store, pet_collection, pet_feast, pet_loop, pet_profile, pet_reactions, pet_streak, pet_welcome,
               pet_xp)
from .accounts import AccountError

SAVE_ATTEMPTS = 2   # un conflit (autre appareil) : on relit et on rejoue une fois

# Clé du serveur Party (playtest « Marc », 4.11) : variable d'environnement PET_SECRET = le secret « pet_server_key » du
# coffre de la base (migration 20261104170000). Elle seule permet d'écrire un personnage (pet_load / pet_save /
# pet_gift) et elle rend les tirages imprévisibles (HMAC). Jamais envoyée au navigateur, jamais dans le dépôt.
SECRET_ENV = "PET_SECRET"
KEYED_RPC = ("pet_load", "pet_save", "pet_gift", "pet_pot_get", "pet_pot_give", "pet_mint", "pet_cert_set", "pet_awards_claim", "pet_event_coins_claim",
             "pet_profile")
_PROCESS_KEY = secrets.token_bytes(32)   # dernier repli (disque illisible) : hasard imprévisible, jamais une valeur connue
SECRET_FILE = "pet_secret"
_ENROLLED: set[str] = set()               # clés déjà enrôlées dans la base par ce processus
log = logging.getLogger("party.pet")
_WARNED: list[bool] = []


def _warn_once() -> None:
    _WARNED.append(True)
    log.warning("Compagnon : %s manquant, la base refusera d'enregistrer les personnages", SECRET_ENV)

# Mini-jeu « Attrape les notes » : partie tirée par le serveur (jeton signé), score calculé ici d'après les notes
# attrapées — jamais un score déclaré par le téléphone.
GAME_MS = 20000            # durée d'une partie (app/static/pet/pet.js)
GAME_NOTES = 30            # notes lancées pendant une partie (une toutes les 650 ms)
GAME_GRACE_MS = 1500       # réseau, minuteurs du navigateur : la partie peut sembler finir un peu plus tôt
GAME_MAX_AGE_S = 600       # au-delà de 10 min, la partie a expiré
GAMES_KEPT = 12            # jetons déjà joués gardés (une partie ne compte qu'une fois)

# Débit : un compte ne peut pas appeler /api/pet/* plus de 60 fois par minute (un humain en est très loin).
RATE_LIMIT, RATE_WINDOW = 60, 60.0


class PetUnavailable(pet.PetError):
    """Base injoignable ou en panne : passager (HTTP 503)."""


class PetConflict(pet.PetError):
    pass


class PetNotAdopted(pet.PetError):
    """Pas encore de Zicou : seule l'adoption explicite (action « adopt ») pond l'œuf (bug du 5.11 : feuille d'accueil
    fermée, et pourtant l'onglet Zicou pondait l'œuf qui éclosait)."""


NOT_ADOPTED_TEXT = "Adopte d'abord ton Zicou 🥚"
NOT_ADOPTED = {"adopted": False, "pet": None, "news": [], "effect": None}


def load_secret(data_dir: Path | None) -> tuple[str, bool]:
    """(clé du serveur, vient de PET_SECRET ?). La variable d'environnement est prioritaire ; sinon une clé aléatoire
    forte, créée une seule fois dans DATA_DIR/pet_secret (fichier 0600) et réutilisée ensuite : le serveur ne casse
    jamais faute de variable (la clé est alors enrôlée dans la base au premier besoin, voir PetStore._enroll)."""
    env = os.environ.get(SECRET_ENV, "").strip()
    if env:
        return env, True
    if data_dir is None:
        return "", False
    path = Path(data_dir) / SECRET_FILE
    try:
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w") as f:
                f.write(secrets.token_hex(32))
        text = path.read_text().strip()
        return (text, False) if len(text) >= 32 else ("", False)
    except FileExistsError:   # créé au même instant par un autre processus
        return path.read_text().strip(), False
    except OSError as e:
        log.error("Compagnon : clé du serveur illisible dans %s (%s)", path, e)
        return "", False


class AccountRate:
    """Limite de débit par compte (fenêtre glissante), pour les routes /api/pet/*."""

    def __init__(self, limit: int = RATE_LIMIT, window: float = RATE_WINDOW, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self.lock = threading.Lock()
        self.hits: dict[str, list[float]] = {}

    def allow(self, key: str) -> bool:
        now = self.clock()
        with self.lock:
            if len(self.hits) > 5000:   # ménage : comptes inactifs
                self.hits = {k: v for k, v in self.hits.items() if v and now - v[-1] < self.window}
            recent = [t for t in self.hits.get(key, []) if now - t < self.window]
            if len(recent) >= self.limit:
                self.hits[key] = recent
                return False
            self.hits[key] = recent + [now]
            return True


def rate_key(token: str) -> str:
    """Le compte d'un jeton (champ sub, lu sans vérifier : seulement pour compter) ; sinon l'empreinte du jeton."""
    try:
        payload = token.split(".")[1]
        sub = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4))).get("sub")
        if isinstance(sub, str) and sub:
            return "sub:" + sub
    except (IndexError, ValueError, AttributeError):
        pass
    return "tok:" + hashlib.sha256(token.encode()).hexdigest()


# Parties de Party, titres ajoutés, Méninges : notés par le serveur pour les réactions de Zicou (app/pet_reactions.py).
PartyLog = pet_reactions.ActivityLog


def _now() -> datetime:
    return datetime.now(timezone.utc)


SRC_ALIASES = {"notif": "notification", "notification": "notification", "tab": "tab", "widget": "widget", "link": "link"}

REWARD_TEXT = {"brain": "🧠 Bonus Méninges : il est tout fier de toi", "party": "🎮 Bonus partie de Party : quelle ambiance !",
               "music": "🎶 Bonus musique : il a dansé sur ton son"}
EVENT_TEXT = {"hatched": "🐣 L'œuf a éclos !", "died": "🕊️ Il s'est envolé…", "egg": "🥚 Un nouvel œuf est arrivé"}
STAGE_TEXT = {"teen": "ado", "adult": "adulte"}
VARIANT_TEXT = {"star": " étoile ✨", "classic": "", "wild": " rebelle 😜"}


def news_lines(name: str, events: list[dict], got: list[dict], applied: list[dict], unlocked: list[str]) -> list[dict]:
    lines = []
    gone = any(e["kind"] == "died" for e in events)
    for e in events:
        if e["kind"] == "evolved" and gone:
            continue   # envolé : jamais « devenu adulte rebelle » en même temps (playtest « Léa »)
        if e["kind"] == "evolved":
            lines.append({"kind": "evolved", "text": f"🎉 {name} est devenu {STAGE_TEXT[e['stage']]}{VARIANT_TEXT[e['variant']]} !"})
        elif e["kind"] in EVENT_TEXT:
            lines.append({"kind": e["kind"], "text": EVENT_TEXT[e["kind"]]})
    lines += [{"kind": "reward", "text": f"{REWARD_TEXT[g['source']]} (+{g['coins']} 🪙)" if g.get("coins")
               else REWARD_TEXT[g["source"]]} for g in got if g["kind"] == "reward"]
    lines += [{"kind": "event_coins", "text": f"🪩 Pièces de « {g['event'] or 'ta soirée'} » : +{g['coins']} 🪙"}
              for g in got if g["kind"] == "event_coins"]
    for a in applied:
        _, what, emoji = pet.GIFTS[a["kind"]]
        later = " (il la savourera après le festin en cours)" if a.get("feast") == "later" else ""
        lines.append({"kind": "gift", "text": f"{emoji} {a['from']} lui a offert {what}{later}"})
    labels = {o[0]: (o[1], o[2]) for o in pet.OUTFITS}
    lines += [{"kind": "unlocked", "text": f"{labels[u][1]} Nouvelle tenue : {labels[u][0]}"} for u in unlocked]
    return lines


def xp_gain(life: dict, owner: dict, kind: str, now: datetime) -> list[dict]:
    """XP d'un geste (app/pet_xp.py), doublée par une Pizza dorée ; le badge de niveau suit dans life (vu des amis).
    Rien pour un œuf ou un Zicou envolé. Renvoie la nouvelle à montrer (niveau gagné) ou rien."""
    if life.get("stage") in ("egg", "dead"):
        return []
    got = pet_xp.gain(owner, kind, now, pet_feast.xp_factor(life, now))
    if not got:
        return []
    life["lvl"] = pet_xp.badge(owner)
    if not got["level_up"]:
        return []
    star = f" ★{got['stars']}" if got["stars"] else ""
    return [{"kind": "level", "text": f"⭐ {life['name']} passe au niveau {got['level']}{star} !"}]


def loop_lines(name: str, events: list[dict]) -> list[dict]:
    """Nouvelles de la boucle du jour (série, missions, nuit douce) : toujours douces, jamais de reproche."""
    lines = []
    for e in events:
        if e.get("id") in pet_loop.TEMPLATES:   # mission : avec le nom actuel
            e = {**e, "text": pet_loop.named(e, name)}
        text = LOOP_TEXT.get(e["kind"])
        if e["kind"] == "broken":
            text = BROKEN_REPAIR if e.get("repair") else BROKEN_PLAIN
        if text:
            lines.append({"kind": e["kind"], "text": text.format(n=name, **{k: v for k, v in e.items() if k != "kind"})})
    return lines


LOOP_TEXT = {
    "soft_night": "🌙 Nuit douce : {n} a super bien dormi (+{coins} pièces)",
    "protected": "❄️ Ta série est restée au chaud : ce jour-là était protégé",
    "freeze_earned": "❄️ Nouveau gel gagné ({freezes}/2) : il protégera un jour de pause",
    "milestone_reward": "🔥 Palier de {days} jours : {label}",
    "repaired": "🔥 Série retrouvée : {count} jours !",
    "woke_up": "☀️ {n} se réveille en te voyant",
    "woke_early": "🌙 Réveillé un peu tôt : la nuit douce, ce sera pour une prochaine fois",
    "mission": "🎯 Mission réussie : {text}",
    "bonus_ready": "🎁 3 missions sur 3 : le coffre bonus est prêt !",
    "week_done": "🏆 Mission de la semaine réussie : +{coins} pièces",
}
BROKEN_REPAIR = "🔥 Nouvelle série ! Ta série de {was} jours peut revenir : 1 partie de Méninges + 1 soin d'ici demain soir"
BROKEN_PLAIN = "🔥 C'est reparti pour une nouvelle série, {n} est content de te voir"


class PetStore:
    def __init__(self, accounts, party_log: PartyLog, clock=_now, rng=None, secret: str | None = None,
                 enroll: bool = False):
        self.accounts = accounts      # app.accounts.Accounts
        self.party = party_log
        self.clock = clock
        self.rng = rng                # tests : un hasard imposé ; sinon HMAC(clé du serveur, compte, jour, usage)
        self.secret = (os.environ.get(SECRET_ENV, "") if secret is None else secret).strip()
        self.enroll = enroll and bool(self.secret)   # clé propre au serveur (sans PET_SECRET) : à enrôler dans la base
        if not self.secret and not _WARNED:
            _warn_once()
        root = self.secret.encode() if self.secret else _PROCESS_KEY
        self.rng_key = hmac.new(root, b"party-pet:rng:v1", hashlib.sha256).digest()
        self.game_key = hmac.new(root, b"party-pet:game:v1", hashlib.sha256).digest()

    def seed(self, uid: str, day: str, purpose: str) -> int:
        """Graine d'un tirage : HMAC-SHA256(clé du serveur, compte|jour|usage). Imprévisible sans la clé (playtest :
        avec sha256 seul, on prédisait les coffres « rares » de l'année), mais toujours la même pour un même coffre
        (rejouable après un conflit, et vérifiable par l'admin qui a la clé : voir verify_roll)."""
        return int(hmac.new(self.rng_key, f"{uid}|{day}|{purpose}".encode(), hashlib.sha256).hexdigest(), 16)

    def _rng(self, uid: str, now: datetime, purpose: str):
        """Hasard des coffres et des missions : tiré ici, jamais par le navigateur (voir seed)."""
        if self.rng is not None:
            return self.rng
        return random.Random(self.seed(uid, now.astimezone(pet.TZ).date().isoformat(), purpose))

    def verify_roll(self, uid: str, day: str, purpose: str = "chest") -> float:
        """Pour l'admin : le jet (`roll`, gardé dans le résultat du coffre) que ce coffre devait donner ce jour-là."""
        return round(random.Random(self.seed(uid, day, purpose)).random(), 6)

    # ── Mini-jeu : jeton de partie signé ──

    def _game_sig(self, uid: str, start: int, nonce: str) -> str:
        return hmac.new(self.game_key, f"{uid}|{start}|{nonce}".encode(), hashlib.sha256).hexdigest()[:32]

    def game(self, token: str) -> dict:
        """Une partie du jeu des notes commence : jeton signé (compte, heure de début du serveur, numéro unique)."""
        uid = str(self.accounts._uid(token))
        start, nonce = int(self.clock().timestamp() * 1000), secrets.token_hex(8)
        return {"game": f"{start}.{nonce}.{self._game_sig(uid, start, nonce)}", "notes": GAME_NOTES, "ms": GAME_MS}

    def _game_score(self, uid: str, game: str, hits: int, now: datetime, owner: dict) -> int:
        """Score d'une partie, calculé par le serveur : jeton à lui, signé, joué jusqu'au bout (20 s au moins), pas déjà
        compté, notes attrapées ≤ notes lancées. Le score = part des notes attrapées (0–100)."""
        try:
            start_text, nonce, sig = game.split(".")
            start = int(start_text)
        except ValueError:
            raise pet.PetError("Cette partie n'a pas pu être comptée. Rejoue !") from None
        elapsed = now.timestamp() * 1000 - start
        loop = pet_loop.loop_of(owner)
        if (not hmac.compare_digest(sig, self._game_sig(uid, start, nonce)) or nonce in loop["games"]
                or not GAME_MS - GAME_GRACE_MS <= elapsed <= GAME_MAX_AGE_S * 1000 or not 0 <= hits <= GAME_NOTES):
            raise pet.PetError("Cette partie n'a pas pu être comptée. Rejoue !")
        loop["games"] = (loop["games"] + [nonce])[-GAMES_KEPT:]
        return min(pet.PLAY_SCORE_MAX, round(100 * hits / GAME_NOTES))

    def _enroll(self, token: str) -> bool:
        """Enrôle la clé propre au serveur (une fois par processus) ; True si la base l'accepte désormais."""
        if not self.enroll or self.secret in _ENROLLED:
            return False
        try:
            r = self.accounts._get("POST", "/rest/v1/rpc/pet_server_enroll", token, json={"p_key": self.secret})
        except AccountError:
            return False
        if r.status_code == 200 and r.content.strip() == b"true":
            _ENROLLED.add(self.secret)
            log.warning("Compagnon : clé du serveur (DATA_DIR/%s) enrôlée dans la base", SECRET_FILE)
            return True
        log.error("Compagnon : la base refuse d'enrôler la clé du serveur (une autre est déjà enrôlée ?)")
        return False

    def _rpc(self, token: str, name: str, args: dict, fallback: str, retry: bool = True):
        """Jeton vérifié d'abord (AccountError → 401) ; refus de la base → PetError (400) ; conflit → PetConflict ;
        panne → PetUnavailable (503)."""
        self.accounts._uid(token)
        if name in KEYED_RPC:
            args = {**args, "p_key": self.secret}
        try:
            r = self.accounts._get("POST", f"/rest/v1/rpc/{name}", token, json=args)
        except AccountError as e:
            raise PetUnavailable(str(e)) from e
        if r.status_code >= 500:
            raise PetUnavailable("Zicou ne répond pas. Réessaie dans un instant.")
        if r.status_code == 401:
            raise AccountError("Ta connexion a expiré. Reconnecte-toi.")
        if r.status_code not in (200, 204):
            try:
                message = str(r.json().get("message", ""))
            except ValueError:
                message = ""
            kind, _, text = message.partition(": ")
            if kind == "conflict":
                raise PetConflict(text or fallback)
            if kind == "server" and retry and self._enroll(token):
                return self._rpc(token, name, args, fallback, retry=False)
            if kind == "server":   # clé du serveur absente ou fausse (PET_SECRET) : panne de configuration, pas sa faute
                log.error("Compagnon : la base refuse la clé du serveur (%s)", SECRET_ENV)
                raise PetUnavailable(text or fallback)
            raise pet.PetError(text if text else fallback)
        try:
            return r.json() if r.content else None
        except ValueError as e:
            raise PetUnavailable(fallback) from e

    # ── Mon compagnon ──

    def _live(self, token: str, src: str | None = None) -> dict:
        """Charge et fait vivre jusqu'à maintenant (récompenses, cadeaux, boucle du jour), sans encore enregistrer.
        `src` (tab, notification, widget, link) : une ouverture, comptée par la base (pet_opens) ; None = pas une
        ouverture (action, visite d'ami)."""
        data = self._rpc(token, "pet_load", {"p_src": src}, "Ton Zicou n'a pas pu être chargé.")
        data = data if isinstance(data, dict) else {}
        now = self.clock()
        saved = data.get("pet") if isinstance(data.get("pet"), dict) else None
        if saved:
            life, owner, version, journal = saved["life"], saved["owner"], int(saved.get("version") or 0), []
        else:
            life, owner = pet.new_pet(now)
            version, journal = 0, [{"kind": "egg", "detail": {"gen": 1}}]
        life, owner = copy.deepcopy(life), copy.deepcopy(owner)
        events = pet.advance(life, now, owner)
        uid = self.accounts._uid(token)
        gid = self.accounts.gid(uid)
        life, owner, loop_events = pet_loop.visit(life, owner, now, self._rng(str(uid), now, "day"), src=src, seed=str(uid))
        brain_before = owner["stats"].get("brain", 0)
        life, owner, got = pet.rewards(life, owner, now, data.get("brain") or [], self.party.times(gid, "party"),
                                       self.party.times(gid, "music"))
        # Pièces d'un événement (droit « zicou.event_coins ») : versées par la base aux présents, rangées ici une fois.
        grants = [g for g in data.get("coins") or [] if isinstance(g, dict)]
        life, owner, coins_got, coins_done = pet.event_coins(life, owner, now, grants)
        got += coins_got
        # Réactions de Zicou (app/pet_reactions.py) : ce compte a-t-il un Zicou (pas encore enregistré = pas adopté) ?
        self.party.mark_pet(gid, life["name"] if saved else None, life["stage"] not in ("egg", "dead"))
        loop_events += self._brain_played(owner, owner["stats"].get("brain", 0) - brain_before, now)
        xp_news = []
        for g in got:   # XP de jeu (Méninges, parties de Party sans alcool) ; jamais pour un titre ajouté
            if g["kind"] == "reward" and g["source"] in ("brain", "party"):
                xp_news += xp_gain(life, owner, "game", now)
        received = [g for g in data.get("gifts") or [] if isinstance(g, dict)]
        life, owner, applied = pet.gifts(life, owner, now, received)
        unlocked = pet.unlock(owner)
        journal += [{"kind": e["kind"], "detail": {k: v for k, v in e.items() if k != "kind"}} for e in events]
        journal += [{"kind": "reward", "detail": {"source": g["source"]}} for g in got if g["kind"] == "reward"]
        journal += [{"kind": "event_coins", "detail": {"coins": g["coins"]}} for g in got if g["kind"] == "event_coins"]
        journal += [{"kind": "gift_received", "detail": {"kind": a["kind"]}} for a in applied]
        s = {"now": now, "life": life, "owner": owner, "version": version, "journal": journal, "seed": str(uid),
             "gift_ids": [str(g.get("id")) for g in received if g.get("id")],
             "coins_applied": coins_done,
             "changed": not saved or bool(events or got or applied or unlocked or loop_events or coins_done),
             "news": news_lines(life["name"], events, got, applied, unlocked) + loop_lines(life["name"], loop_events)
             + xp_news}
        pet_coll_store.enrich(self, token, s, data, events)   # collection : shiny, cadeaux d'événement, certificats
        if pet_bar.ensure(s["owner"], now):   # barre « petit cadeau » (app/pet_bar.py) : part de maintenant
            s["changed"] = True
        pet_welcome.apply(s, events)   # toute première éclosion : cadeau de bienvenue garanti (app/pet_welcome.py)
        s["fresh"] = not saved
        return s

    @staticmethod
    def _brain_played(owner: dict, games: int, now: datetime) -> list[dict]:
        """Parties de Méninges nouvelles : missions, et rattrapage de série en cours."""
        if games <= 0:
            return []
        events = pet_loop.note(owner, "brain", now, games)
        owner["streak"], more = pet_streak.repair_progress(owner.get("streak"), "brain", now.astimezone(pet.TZ).date())
        return events + pet_loop.streak_rewards(owner, more) + more

    def _save(self, token: str, s: dict, cared: bool) -> None:
        proj = pet.projections(s["life"], s["now"])
        nudge = pet_loop.nudge(s["life"], s["owner"], s["now"], s["seed"], proj["hungry_at"])
        self._rpc(token, "pet_save", {
            "p_life": s["life"], "p_owner": s["owner"], "p_version": s["version"], "p_hungry_at": proj["hungry_at"],
            "p_dies_at": proj["dies_at"], "p_cared": cared, "p_gifts": s["gift_ids"], "p_journal": s["journal"][-12:],
            "p_nudge": nudge,
        }, "Ton Zicou n'a pas pu être enregistré. Réessaie dans un instant.")

    def _answer(self, s: dict, effect: dict | None = None) -> dict:
        today = pet.day_of(s["now"])
        shown = pet.view(s["life"], s["owner"], s["now"]) | {
            "daily": pet_loop.view(s["life"], s["owner"], s["now"], pet_coll_store.ctx(s)),
            "coll": pet_coll_store.summary(s),
            "xp": pet_xp.view(s["owner"], s["now"], pet_feast.xp_factor(s["life"], s["now"])),
            "feast": pet_feast.view(s["life"], s["owner"], s["now"], today),
            "bar": pet_bar.view(s["life"], s["owner"], s["now"])}
        out = {"adopted": True, "pet": shown, "news": s["news"], "effect": effect}
        if s.get("want_full"):
            out["collection"] = pet_coll_store.full(self, s)
        return out

    def _after_save(self, token: str, s: dict) -> None:
        """Cadeaux d'événement rangés dans la collection (déjà enregistrée) : marqués en base, une fois."""
        if s.get("awards_applied"):
            try:
                self._rpc(token, "pet_awards_claim", {"p_ids": s["awards_applied"]}, "Cadeaux pas encore rangés.")
            except pet.PetError:
                pass   # ils restent dans owner["coll"]["awards"] : jamais rangés deux fois, marqués au prochain passage
        if s.get("coins_applied"):
            try:
                self._rpc(token, "pet_event_coins_claim", {"p_ids": s["coins_applied"]}, "Pièces pas encore rangées.")
            except pet.PetError:
                pass   # gardées dans owner["claimed"]["event_coins"] : jamais versées deux fois, marquées plus tard

    def _retry(self, token: str, work, src: str | None = None, cared: bool = False, adopt: bool = False):
        """Charge, applique `work(s)` (qui renvoie l'effet, ou None s'il n'y a rien à enregistrer), enregistre ; un
        conflit (autre appareil) : on relit et on rejoue une fois. Sans Zicou enregistré : PetNotAdopted, rien n'est
        créé, sauf pour l'adoption explicite (`adopt`)."""
        for attempt in range(SAVE_ATTEMPTS):
            s = self._live(token, src)
            if s["fresh"] and not adopt:
                raise PetNotAdopted(NOT_ADOPTED_TEXT)
            effect = work(s)
            if effect is None and not s["changed"]:
                return self._answer(s)
            try:
                self._save(token, s, cared=cared)
                self._after_save(token, s)
                self.party.mark_pet(self.accounts.gid(s["seed"]), s["life"]["name"],
                                    s["life"]["stage"] not in ("egg", "dead"))   # adopté (œuf) : plus d'offre d'adoption
                return self._answer(s, effect)
            except PetConflict:
                if attempt == SAVE_ATTEMPTS - 1:
                    raise
        raise PetConflict("Ton Zicou a changé sur un autre appareil.")

    def me(self, token: str, src: str | None = "tab") -> dict:
        """Mon compagnon. `src` : d'où vient l'ouverture (mesure) ; « none » : simple relecture, pas comptée."""
        try:
            return self._retry(token, lambda s: None, src=None if src == "none" else SRC_ALIASES.get(src or "", "tab"))
        except PetNotAdopted:
            return dict(NOT_ADOPTED)   # « pas encore adopté » : l'onglet montre l'adoption, rien n'est pondu

    def adopt(self, token: str, name: str = "") -> dict:
        """Adoption explicite (accueil : choix du nom → « Faire éclore ») : l'œuf est pondu maintenant, avec son nom
        (3 min d'éclosion). Déjà adopté (deuxième toucher, autre appareil) : le Zicou tel quel, rien n'est changé."""
        clean = moderation.require_clean(pet.clean_name(name), "name") if name.strip() else ""

        def work(s: dict):
            if not s["fresh"]:
                return None
            if clean:
                s["life"]["name"] = clean
            return {"action": "adopt", "unlocked": [], "found": None, "text": None}
        return self._retry(token, work, adopt=True)

    def status(self, token: str) -> dict:
        """Pastille de l'en-tête et de l'onglet Zicou : humeur, besoin, éclosion. Ne pond jamais d'œuf, n'enregistre
        rien et ne compte pas d'ouverture (relu toutes les quelques minutes) ; sans compagnon : {"adopted": False}."""
        s = self._live(token, None)
        if s["fresh"]:
            return {"adopted": False}
        view = pet.view(s["life"], s["owner"], s["now"])
        daily = pet_loop.view(s["life"], s["owner"], s["now"], pet_coll_store.ctx(s))
        # Petit anneau de la pastille : la barre « petit cadeau » (sans les chances, montrées dans l'onglet).
        return pet_welcome.status(s, view, daily) | {"bar": pet_bar.view(s["life"], s["owner"], s["now"], with_odds=False)}

    def collection(self, token: str) -> dict:
        """Écran Collection (Zicoudex, boutique, atelier, vitrine, certificats) : simple relecture, pas une ouverture."""
        def work(s: dict):
            s["want_full"] = True
        return self._retry(token, work)

    def act(self, token: str, action: str, score: int = 0, name: str = "", outfit: str = "", item: str = "",
            game: str = "", hits: int = 0) -> dict:
        """`score` (envoyé par d'anciens téléphones) est ignoré : le score du jeu vient du jeton de partie (`game`) et des
        notes attrapées (`hits`), vérifiés ici ; sans jeton, jouer reste un soin, avec un score de 0."""
        del score
        if action == "outfit":   # ancienne tenue unique : un accessoire porté sur son emplacement
            return pet_coll_store.act(self, token, "equip", item=outfit)
        if action == "adopt":
            try:
                return self.adopt(token, name)
            except moderation.ContentRefused as e:
                raise pet.PetError(str(e)) from None
        if action == "bar":
            return self._retry(token, self._claim_bar)
        if action == "rename":
            try:
                name = moderation.require_clean(pet.clean_name(name), "name")
            except moderation.ContentRefused as e:
                raise pet.PetError(str(e)) from None

        def work(s: dict) -> dict:
            played = self._game_score(s["seed"], game, hits, s["now"], s["owner"]) if action == "play" and game else 0
            if action in pet_loop.LOOP_ACTIONS:
                rng = self._rng(s["seed"], s["now"], action)
                life, owner, effect = pet_loop.act(s["life"], s["owner"], action, s["now"], rng, item=item,
                                                   ctx=pet_coll_store.ctx(s))
                s["life"], s["owner"] = life, owner
                effect["found"] = pet_coll_store.settle_found(self, token, s, action, effect.get("found"))
                pet_coll_store.finish(s)
                more = effect["loop"]
                if action == "treat":
                    s["news"] += xp_gain(life, owner, "care", s["now"])
            else:
                life, owner, effect = pet.act(s["life"], s["owner"], action, s["now"], score=played, name=name, outfit=outfit)
                if action in pet.CARE_ACTIONS:
                    s["news"] += xp_gain(life, owner, "care", s["now"])
                streak = effect.get("streak", [])
                more = pet_loop.after_care(owner, action, played, s["now"]) + pet_loop.streak_rewards(owner, streak) + streak
                if action == "wake":
                    more += pet_loop.woke(owner, s["now"])
                effect["unlocked"] = effect["unlocked"] + [u for u in pet.unlock(owner) if u not in effect["unlocked"]]
            if action in pet_loop.LOOP_ACTIONS:
                more = more + effect.get("streak", [])
            s["news"] += news_lines(life["name"], effect["events"], [], [], effect["unlocked"]) + loop_lines(life["name"], more)
            s["life"], s["owner"] = life, owner
            detail = {"score": played, "hits": int(hits)} if action == "play" else {"kind": effect["found"]["kind"]} if effect.get("found") else {}
            s["journal"] += [{"kind": action, "detail": detail}]
            s["journal"] += [{"kind": e["kind"], "detail": {k: v for k, v in e.items() if k != "kind"}} for e in effect["events"]]
            out = {"action": action, "unlocked": effect["unlocked"], "found": effect.get("found"), "text": effect.get("text")}
            if action == "play":   # écran de fin du mini-jeu : le score calculé par le serveur
                out.update(score=played, hits=int(hits) if game else 0, notes=GAME_NOTES)
            return out
        return self._retry(token, work, cared=action in ("feed", "play", "cuddle", "heal", "sleep", "wake", "tuck", "treat"))

    def _claim_bar(self, s: dict) -> dict:
        """Barre « petit cadeau » pleine → récompense tirée ici (jet HMAC : compte, jour, numéro de la récupération du
        jour). Rejouée après un conflit : même jet ; déjà récupérée sur un autre appareil : refus doux (jamais deux fois)."""
        rng = self._rng(s["seed"], s["now"], f"bar{pet_bar.claimed_today(s['owner'], s['now'])}")
        s["owner"], found, events = pet_bar.claim(s["life"], s["owner"], s["now"], rng)
        if found["kind"] == "xp":
            s["life"]["lvl"] = pet_xp.badge(s["owner"])   # badge vu des amis
        s["news"] += [{"kind": "level", "text": f"⭐ {s['life']['name']} passe au niveau {e['level']}"
                       + (f" ★{e['stars']}" if e["stars"] else "") + " !"} for e in events if e.get("level_up")]
        s["journal"] += [{"kind": "bar", "detail": {"kind": found["kind"], "roll": found["roll"]}}]
        return {"action": "bar", "unlocked": [], "found": found, "text": None}

    def _note(self, token: str, what: str) -> None:
        """Visite ou cadeau à un ami : missions sociales. Un échec ici ne gâche pas la visite (déjà réussie). La visite
        n'est notée (et enregistrée) qu'une fois par jour : rouvrir la liste d'amis n'écrit plus rien (playtest)."""
        def work(s: dict):
            loop = pet_loop.loop_of(s["owner"])
            if what == "visit" and loop["day"] == pet.day_of(s["now"]) and loop["c"].get("visit"):
                return None
            events = pet_loop.note(s["owner"], what, s["now"])
            if s["life"]["stage"] not in ("egg", "dead"):
                s["news"] += xp_gain(s["life"], s["owner"], "social", s["now"])
            if what == "gift" and s["life"]["stage"] not in ("egg", "dead"):
                # Un cadeau à un ami est un vrai passage : la journée compte pour la série (playtest « Léa » : venue le
                # vendredi, cadeau offert, coffre ouvert… et 🔥 0 le dimanche). Pas la simple visite (un toucher).
                streak = pet.note_streak(s["owner"], s["now"], care=False)
                events += pet_loop.streak_rewards(s["owner"], streak) + streak
            s["news"] += loop_lines(s["life"]["name"], events)
            return {"note": what}   # compteurs du jour changés : toujours enregistré
        try:
            self._retry(token, work)
        except pet.PetError:
            pass

    # ── Amis ──

    def _card(self, row: dict, now: datetime) -> dict | None:
        life = row.get("life")
        if not isinstance(life, dict):
            return None
        try:
            shown = pet.friend_view(life, now) | pet_coll_store.friend_extras(life)
        except (KeyError, TypeError, ValueError):
            return None   # état illisible : cet ami n'apparaît pas plutôt que de tout casser
        return {"id": str(row.get("id")), "member": " ".join(str(row.get("name") or "?").split())[:40],
                "avatar_url": row.get("avatar_url") or None, "gifted": bool(row.get("gifted")), "pet": shown}

    def friends(self, token: str) -> dict:
        rows = self._rpc(token, "pet_friends", {}, "Les Zicou de tes amis n'ont pas pu être chargés.")
        now = self.clock()
        cards = [c for c in (self._card(r, now) for r in rows or [] if isinstance(r, dict)) if c]
        if cards:
            self._note(token, "visit")
        return {"friends": cards}

    def friend(self, token: str, friend_id: str) -> dict:
        row = self._rpc(token, "pet_friend", {"p_friend": friend_id}, "Ce Zicou n'a pas pu être chargé.")
        card = self._card(row, self.clock()) if isinstance(row, dict) else None
        if not card:
            raise pet.PetError("Ce Zicou n'a pas pu être chargé.")
        return card

    def profile(self, token: str, member: str) -> dict | None:
        """Fiche profil d'un membre : l'apparence publique de son Zicou (app/pet_profile.py). None : membre introuvable,
        inactif ou bloqué (dans un sens ou l'autre) — la route répond alors 404, sans dire lequel. Rien n'est écrit."""
        row = self._rpc(token, "pet_profile", {"p_member": member}, "Son Zicou n'a pas pu être chargé.")
        return pet_profile.card(row, member, self.clock()) if isinstance(row, dict) else None

    def gift(self, token: str, friend_id: str, kind: str) -> dict:
        if kind not in pet.GIFTS:
            raise pet.PetError("Cadeau inconnu.")
        if kind in pet_feast.GIFT_KINDS:
            return self._gift_feast(token, friend_id, kind)
        self._rpc(token, "pet_gift", {"p_friend": friend_id, "p_kind": kind}, "Le cadeau n'a pas pu être offert.")
        self._note(token, "gift")
        return self.friend(token, friend_id)

    def _gift_feast(self, token: str, friend_id: str, kind: str) -> dict:
        """Offrir un festin au Zicou d'un ami (économie du 4.11.2026, usage n° 2) : payé en pièces par CELUI QUI OFFRE,
        l'ami reçoit un EFFET (jamais des pièces : aucun transfert de monnaie). Même règle que les cadeaux gratuits :
        un cadeau par ami et par jour (la base le garantit). Pièces débitées d'abord ; si la base refuse le cadeau,
        elles sont rendues."""
        feast = pet_feast.FEASTS[pet_feast.GIFT_KINDS[kind]]
        card = self.friend(token, friend_id)
        if card.get("gifted"):
            raise pet.PetError("Tu lui as déjà fait un cadeau aujourd'hui. Reviens demain 💜")
        if card["pet"].get("stage") in ("egg", "dead"):
            raise pet.PetError("Son Zicou ne peut pas recevoir de cadeau pour l'instant.")

        def pay(s: dict) -> dict:
            if s["life"]["stage"] in ("egg", "dead"):
                raise pet.PetError("Les cadeaux s'offrent de Zicou à Zicou : il faut que le tien soit là 🥚")
            try:
                pet_collection._spend(s["owner"], feast["price"])
            except pet_collection.CollectionError as e:
                raise pet.PetError(str(e)) from None
            s["journal"] += [{"kind": "feast_gift", "detail": {"kind": kind, "price": feast["price"]}}]
            return {"paid": feast["price"]}

        def refund(s: dict) -> dict:
            s["owner"].setdefault("loop", {})["coins"] = int(s["owner"]["loop"].get("coins") or 0) + feast["price"]
            s["journal"] += [{"kind": "feast_refund", "detail": {"kind": kind, "price": feast["price"]}}]
            s["news"].append({"kind": "refund", "text": f"🪙 {feast['price']} pièces rendues : le cadeau n'est pas parti"})
            return {"refund": feast["price"]}

        self._retry(token, pay)
        try:
            self._rpc(token, "pet_gift", {"p_friend": friend_id, "p_kind": kind}, "Le cadeau n'a pas pu être offert.")
        except pet.PetError:
            try:
                self._retry(token, refund)
            except pet.PetError:
                log.error("Zicou : festin offert refusé ET pièces pas rendues (compte %s)", self.accounts._uid(token))
            raise
        self._note(token, "gift")
        return self.friend(token, friend_id)
