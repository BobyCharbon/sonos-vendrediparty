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

from . import moderation, pet, pet_coll_store, pet_loop, pet_streak
from .accounts import AccountError

PARTY_KEEP_SECONDS = 3 * 24 * 3600
PARTY_KEEP_PER_PLAYER = 20
SAVE_ATTEMPTS = 2   # un conflit (autre appareil) : on relit et on rejoue une fois

# Clé du serveur Party (playtest « Marc », 4.11) : variable d'environnement PET_SECRET = le secret « pet_server_key » du
# coffre de la base (migration 20261104170000). Elle seule permet d'écrire un personnage (pet_load / pet_save /
# pet_gift) et elle rend les tirages imprévisibles (HMAC). Jamais envoyée au navigateur, jamais dans le dépôt.
SECRET_ENV = "PET_SECRET"
KEYED_RPC = ("pet_load", "pet_save", "pet_gift", "pet_mint", "pet_cert_set", "pet_awards_claim")
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


class PartyLog:
    """Parties de Party terminées par un joueur relié à un compte (identifiant acct-…) : petit bonus pour son compagnon.
    Gardé dans un fichier (les parties vivent dans la mémoire du serveur, pas dans Supabase), 3 jours au plus."""

    def __init__(self, path: Path | None):
        self.path = path
        self.lock = threading.Lock()
        self.data: dict[str, list[list]] = {}
        if path and path.exists():
            try:
                raw = json.loads(path.read_text())
                self.data = {k: v for k, v in raw.items() if isinstance(v, list)} if isinstance(raw, dict) else {}
            except (OSError, ValueError):
                self.data = {}

    def note(self, gid: str, game_id: str, now: float | None = None) -> bool:
        """Une partie terminée (une fois par partie et par joueur). True si c'est nouveau."""
        if not gid.startswith("acct-") or not game_id:
            return False
        now = now or time.time()
        with self.lock:
            rows = [r for r in self.data.get(gid, []) if now - r[1] < PARTY_KEEP_SECONDS]
            if any(r[0] == game_id for r in rows):
                return False
            self.data[gid] = (rows + [[game_id, now]])[-PARTY_KEEP_PER_PLAYER:]
            self._write()
        return True

    def times(self, gid: str) -> list[str]:
        with self.lock:
            rows = list(self.data.get(gid, []))
        return [pet.iso(datetime.fromtimestamp(r[1], timezone.utc)) for r in rows]

    def _write(self) -> None:
        if not self.path:
            return
        try:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data))
            tmp.replace(self.path)
        except OSError:
            pass  # disque plein : le bonus de la partie est perdu, rien d'autre


def _now() -> datetime:
    return datetime.now(timezone.utc)


SRC_ALIASES = {"notif": "notification", "notification": "notification", "tab": "tab", "widget": "widget", "link": "link"}

REWARD_TEXT = {"brain": "🧠 Bonus Méninges : il est tout fier de toi", "party": "🎮 Bonus partie de Party : quelle ambiance !",
               "soiree": "🪩 Bonus soirée : il a dansé toute la nuit"}
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
    lines += [{"kind": "reward", "text": REWARD_TEXT[g["source"]]} for g in got]
    for a in applied:
        _, what, emoji = pet.GIFTS[a["kind"]]
        lines.append({"kind": "gift", "text": f"{emoji} {a['from']} lui a offert {what}"})
    labels = {o[0]: (o[1], o[2]) for o in pet.OUTFITS}
    lines += [{"kind": "unlocked", "text": f"{labels[u][1]} Nouvelle tenue : {labels[u][0]}"} for u in unlocked]
    return lines


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
            raise PetUnavailable("Ton compagnon ne répond pas. Réessaie dans un instant.")
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
        data = self._rpc(token, "pet_load", {"p_src": src}, "Ton compagnon n'a pas pu être chargé.")
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
        life, owner, got = pet.rewards(life, owner, now, data.get("brain") or [], self.party.times(gid), data.get("events") or [])
        loop_events += self._brain_played(owner, owner["stats"].get("brain", 0) - brain_before, now)
        received = [g for g in data.get("gifts") or [] if isinstance(g, dict)]
        life, owner, applied = pet.gifts(life, owner, now, received)
        unlocked = pet.unlock(owner)
        journal += [{"kind": e["kind"], "detail": {k: v for k, v in e.items() if k != "kind"}} for e in events]
        journal += [{"kind": "reward", "detail": {"source": g["source"]}} for g in got]
        journal += [{"kind": "gift_received", "detail": {"kind": a["kind"]}} for a in applied]
        s = {"now": now, "life": life, "owner": owner, "version": version, "journal": journal, "seed": str(uid),
             "gift_ids": [str(g.get("id")) for g in received if g.get("id")],
             "changed": not saved or bool(events or got or applied or unlocked or loop_events),
             "news": news_lines(life["name"], events, got, applied, unlocked) + loop_lines(life["name"], loop_events)}
        pet_coll_store.enrich(self, token, s, data, events)   # collection : shiny, cadeaux d'événement, certificats
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
        }, "Ton compagnon n'a pas pu être enregistré. Réessaie dans un instant.")

    def _answer(self, s: dict, effect: dict | None = None) -> dict:
        shown = pet.view(s["life"], s["owner"], s["now"]) | {
            "daily": pet_loop.view(s["life"], s["owner"], s["now"], pet_coll_store.ctx(s)),
            "coll": pet_coll_store.summary(s)}
        out = {"pet": shown, "news": s["news"], "effect": effect}
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

    def _retry(self, token: str, work, src: str | None = None, cared: bool = False):
        """Charge, applique `work(s)` (qui renvoie l'effet, ou None s'il n'y a rien à enregistrer), enregistre ; un
        conflit (autre appareil) : on relit et on rejoue une fois."""
        for attempt in range(SAVE_ATTEMPTS):
            s = self._live(token, src)
            effect = work(s)
            if effect is None and not s["changed"]:
                return self._answer(s)
            try:
                self._save(token, s, cared=cared)
                self._after_save(token, s)
                return self._answer(s, effect)
            except PetConflict:
                if attempt == SAVE_ATTEMPTS - 1:
                    raise
        raise PetConflict("Ton compagnon a changé sur un autre appareil.")

    def me(self, token: str, src: str | None = "tab") -> dict:
        """Mon compagnon. `src` : d'où vient l'ouverture (mesure) ; « none » : simple relecture, pas comptée."""
        return self._retry(token, lambda s: None, src=None if src == "none" else SRC_ALIASES.get(src or "", "tab"))

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
            else:
                life, owner, effect = pet.act(s["life"], s["owner"], action, s["now"], score=played, name=name, outfit=outfit)
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

    def _note(self, token: str, what: str) -> None:
        """Visite ou cadeau à un ami : missions sociales. Un échec ici ne gâche pas la visite (déjà réussie). La visite
        n'est notée (et enregistrée) qu'une fois par jour : rouvrir la liste d'amis n'écrit plus rien (playtest)."""
        def work(s: dict):
            loop = pet_loop.loop_of(s["owner"])
            if what == "visit" and loop["day"] == pet.day_of(s["now"]) and loop["c"].get("visit"):
                return None
            events = pet_loop.note(s["owner"], what, s["now"])
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
        rows = self._rpc(token, "pet_friends", {}, "Les compagnons de tes amis n'ont pas pu être chargés.")
        now = self.clock()
        cards = [c for c in (self._card(r, now) for r in rows or [] if isinstance(r, dict)) if c]
        if cards:
            self._note(token, "visit")
        return {"friends": cards}

    def friend(self, token: str, friend_id: str) -> dict:
        row = self._rpc(token, "pet_friend", {"p_friend": friend_id}, "Ce compagnon n'a pas pu être chargé.")
        card = self._card(row, self.clock()) if isinstance(row, dict) else None
        if not card:
            raise pet.PetError("Ce compagnon n'a pas pu être chargé.")
        return card

    def gift(self, token: str, friend_id: str, kind: str) -> dict:
        if kind not in pet.GIFTS:
            raise pet.PetError("Cadeau inconnu.")
        self._rpc(token, "pet_gift", {"p_friend": friend_id, "p_kind": kind}, "Le cadeau n'a pas pu être offert.")
        self._note(token, "gift")
        return self.friend(token, friend_id)
