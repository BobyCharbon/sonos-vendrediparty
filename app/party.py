"""État de la soirée (persisté en JSON) et logique d'insertion dans la file."""

import json
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from .game_lock import LOCK as GAMES_LOCK

MODES = ("next", "fair")
HOST_ID = "host"
INACTIVE_AFTER = 3 * 3600  # un invité sans activité depuis 3 h est déconnecté  # les ajouts de l'hôte sont des demandes comme les autres, signées « Hôte »


@dataclass
class Request:
    id: str
    track_id: str
    title: str
    artist: str
    image: str
    guest_id: str
    guest_name: str
    added_at: float
    status: str = "queued"  # queued | played | removed
    ip: str = ""
    duration_ms: int = 0


@dataclass
class Session:
    active: bool = False
    room_uid: str = ""
    room_name: str = ""
    # Source : spotify_sonos (maison), spotify (extérieur), sonos (ancienne file native).
    source: str = "sonos"
    spotify_device_id: str = ""  # Sonos sélectionné via Spotify Connect (mode maison).
    spotify_device_name: str = ""
    # Ancienne file extérieure : migration vers l'envoi immédiat lors de la prochaine lecture de l'état.
    vqueue: list[str] = field(default_factory=list)
    vpushed: str = ""
    vpushed_during: str = ""  # titre qui jouait quand la demande a été envoyée (une seule par titre)
    spotify_transfer_issues: list[str] = field(default_factory=list)
    mode: str = "next"
    started_at: float = 0
    requests: list[Request] = field(default_factory=list)
    # guest_id -> {"name", "ips", "until"} ; until = 0 : banni sans limite.
    bans: dict[str, dict] = field(default_factory=dict)
    # Code d'accès invités (4 chiffres), conservé d'une soirée à l'autre.
    guest_pin: str = ""
    # guest_id -> {"name", "ips", "joined_at"} : invités entrés pendant la soirée.
    guests: dict[str, dict] = field(default_factory=dict)
    # Messages des invités pour l'hôte : {"id", "guest_id", "name", "text", "at", "read"}.
    messages: list[dict] = field(default_factory=list)
    # Jetons d'accès révoqués (invités déconnectés par l'hôte : ils doivent ressaisir le code).
    revoked: list[str] = field(default_factory=list)
    # Titres déjà joués pendant la soirée : {"track_id", "title", "artist", "art", "by", "at"}.
    played: list[dict] = field(default_factory=list)
    # Abonnements aux notifications push : guest_id -> [abonnement Web Push] ; l'hôte à part.
    push: dict[str, list[dict]] = field(default_factory=dict)
    admin_push: list[dict] = field(default_factory=list)
    # Ce dont l'hôte veut être prévenu : nouveaux messages, nouvelles parties de jeu.
    admin_notify: dict = field(default_factory=lambda: {"messages": True, "games": False})
    # Playlists favorites de l'hôte (Réglages) : {"id": "spotify:playlist:…" ou "fav:…"/"sq:…", "title"}.
    top_playlists: list[dict] = field(default_factory=list)
    # Parties de jeu en cours (voir games.py), par code ; indépendantes de la soirée musique.
    games: dict[str, dict] = field(default_factory=dict)
    # Événement lié à la soirée (module Événements) : ses comptes notés « Présent » entrent sans le code.
    event_id: str = ""
    event_title: str = ""
    # Compte (identifiant Supabase) -> jeton d'accès donné sans code, révoqué s'il n'est plus « Présent ».
    event_passes: dict[str, str] = field(default_factory=dict)


class PartyStore:
    def __init__(self, path: Path, ignored_ips: set[str] | None = None):
        self.path = path
        # IP du reverse proxy : partagée par tous les invités externes, jamais utilisée pour un ban.
        self.ignored_ips = ignored_ips or set()
        self.lock = threading.RLock()
        self.session = self._load()
        self.last_seen: dict[str, float] = {}  # en mémoire : rafraîchi à chaque appel des invités
        self.version = 0  # incrémenté à chaque modification : les pages ouvertes se rafraîchissent
        if not self.session.guest_pin:
            self.regenerate_pin()
        # Invités d'avant le suivi d'activité : le délai de 3 h part du démarrage du serveur.
        for g in self.session.guests.values():
            g.setdefault("active_at", time.time())
        # Données d'avant la propagation des prénoms : on aligne sur le dernier prénom connu.
        for r in self.session.requests:
            name = self.session.guests.get(r.guest_id, {}).get("name")
            if name and r.guest_name != name:
                r.guest_name = name

    def _load(self) -> Session:
        try:
            raw = json.loads(self.path.read_text())
            raw["requests"] = [Request(**r) for r in raw.get("requests", [])]
            # Ignore les champs d'anciennes versions plutôt que de tout perdre (code, bans…).
            known = Session.__dataclass_fields__
            return Session(**{k: v for k, v in raw.items() if k in known})
        except (FileNotFoundError, ValueError, TypeError):
            return Session()

    def _serialize(self) -> str:
        # Les parties sont protégées par GAMES_LOCK (pris par save), mais d'autres données de la
        # soirée (invités, demandes…) peuvent encore changer pendant la copie : on réessaie
        # brièvement sur « dictionary changed size during iteration » plutôt que d'échouer.
        for attempt in range(5):
            try:
                return json.dumps(asdict(self.session), ensure_ascii=False, indent=2)
            except RuntimeError:
                if attempt == 4:
                    raise
                time.sleep(0.01)
        raise RuntimeError("sérialisation impossible")  # inatteignable, pour le typage

    def save(self, notify: bool = True):
        # Le suivi des invités et les actions de jeu peuvent enregistrer en parallèle.
        # Toujours le verrou des parties d'abord, puis celui-ci (même ordre partout : pas d'interblocage),
        # pour ne jamais copier une partie à moitié modifiée.
        with GAMES_LOCK, self.lock:
            if notify:
                self.version += 1
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = self._serialize()
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(payload)
            tmp.replace(self.path)

    def start(self, room_uid: str, room_name: str, mode: str, source: str = "sonos",
              spotify_device_id: str = "", spotify_device_name: str = ""):
        # Les bannissements et le code d'accès survivent d'une soirée à l'autre.
        self.session = Session(
            active=True, room_uid=room_uid, room_name=room_name, mode=mode, started_at=time.time(), source=source,
            spotify_device_id=spotify_device_id, spotify_device_name=spotify_device_name,
            bans=self.session.bans, guest_pin=self.session.guest_pin, revoked=self.session.revoked,
            push=self.session.push, admin_push=self.session.admin_push, admin_notify=self.session.admin_notify, top_playlists=self.session.top_playlists,
            games=self.session.games, event_id=self.session.event_id, event_title=self.session.event_title,
        )
        self.save()

    def regenerate_pin(self, pin: str | None = None) -> str:
        """Nouveau code d'accès : tiré au hasard, ou choisi par l'hôte (4 chiffres)."""
        old = self.session.guest_pin
        if pin is None:
            while (pin := f"{secrets.randbelow(10000):04d}") == old:
                pass
        self.session.guest_pin = pin
        self.session.revoked = []  # le nouveau code invalide déjà tous les anciens jetons
        self.save()
        return pin

    def stop(self):
        self.session.active = False
        self.save()

    def pending(self) -> list[Request]:
        return [r for r in self.session.requests if r.status == "queued"]

    def add(self, track: dict, guest_id: str, guest_name: str, ip: str = "") -> Request:
        req = Request(
            id=uuid.uuid4().hex[:12],
            track_id=track["id"],
            title=track["title"],
            artist=track["artist"],
            image=track.get("image", ""),
            guest_id=guest_id,
            guest_name=guest_name,
            added_at=time.time(),
            ip=ip,
            duration_ms=track.get("duration_ms", 0),
        )
        self.session.requests.append(req)
        self.save()
        return req

    def register_guest(self, guest_id: str, name: str, ip: str, via: str = "music"):
        """Un invité entre (ou change de prénom) : il apparaît tout de suite dans l'admin.
        via : « music » (code de la soirée saisi) ou « games » (jeux, sans le code)."""
        g = self.session.guests.get(guest_id)
        if g and g["name"] == name and via in g.get("via", ["music"]) and (not ip or ip in self.ignored_ips or ip in g["ips"]):
            self.seen(guest_id)
            return
        if g is None:
            if len(self.session.guests) >= 300:
                return  # garde-fou : la page des jeux est publique
            g = self.session.guests[guest_id] = {"name": name, "ips": [], "joined_at": time.time(), "via": []}
        if via not in g.setdefault("via", ["music"]):
            g["via"].append(via)
        g["active_at"] = time.time()
        if g["name"] != name:
            self.rename_guest(guest_id, name)
        if ip and ip not in self.ignored_ips and ip not in g["ips"]:
            g["ips"].append(ip)
        self.save()

    def rename_guest(self, guest_id: str, name: str):
        """Nouveau prénom partout : file d'attente, historique, messages, bannissements."""
        if guest_id in self.session.guests:
            self.session.guests[guest_id]["name"] = name
        for r in self.session.requests:
            if r.guest_id == guest_id:
                r.guest_name = name
        for m in self.session.messages:
            if m["guest_id"] == guest_id:
                m["name"] = name
        if guest_id in self.session.bans:
            self.session.bans[guest_id]["name"] = name
        self.save()

    def link_token(self, guest_id: str, token: str | None):
        """Associe le jeton d'accès (cookie) à l'invité, pour pouvoir le déconnecter."""
        g = self.session.guests.get(guest_id)
        if g is None or not token or token in g.setdefault("tokens", []):
            return
        g["tokens"] = g["tokens"][-9:] + [token]
        self.save()

    def event_pass(self, account: str, present: bool) -> str | None:
        """Jeton d'accès sans code d'un compte de l'événement lié : le même tant qu'il reste « Présent »,
        révoqué dès qu'il ne l'est plus (il lui faudra alors le code)."""
        with GAMES_LOCK, self.lock:
            nonce = self.session.event_passes.get(account)
            if present and nonce and nonce not in self.session.revoked:
                return nonce
            if not present and not nonce:
                return None
            passes = {k: v for k, v in self.session.event_passes.items() if k != account}
            if nonce:
                self.session.revoked = (self.session.revoked + [nonce])[-500:]
            if present:
                nonce = secrets.token_hex(8)
                passes[account] = nonce
            self.session.event_passes = passes
            self.save()
            return nonce if present else None

    def kick(self, guest_id: str):
        """Déconnecte un invité : jetons révoqués, il disparaît de la liste jusqu'à ce qu'il ressaisisse le code."""
        g = self.session.guests.pop(guest_id, {})
        self.session.revoked = (self.session.revoked + g.get("tokens", []))[-500:]
        # Garde ses IP pour qu'un ban ultérieur reste possible via ses demandes.
        for r in self.session.requests:
            if r.guest_id == guest_id and not r.ip and g.get("ips"):
                r.ip = g["ips"][-1]
        self.last_seen.pop(guest_id, None)
        self.save()

    def seen(self, guest_id: str):
        g = self.session.guests.get(guest_id)
        if g is None:
            return
        now = time.time()
        self.last_seen[guest_id] = now
        # Dernière activité enregistrée (au plus toutes les 5 min) : elle survit à un redémarrage du serveur.
        if now - g.get("active_at", 0) > 300:
            g["active_at"] = now
            self.save(notify=False)

    def prune_inactive(self) -> list[str]:
        """Déconnecte les invités sans activité depuis 3 h (ils devront ressaisir le code)."""
        now = time.time()
        idle = [gid for gid, g in self.session.guests.items()
                if gid != HOST_ID and now - max(g.get("active_at") or g["joined_at"], self.last_seen.get(gid, 0)) > INACTIVE_AFTER]
        for gid in idle:
            self.kick(gid)
        return idle

    def guest_ips(self, guest_id: str) -> set[str]:
        ips = set(self.session.guests.get(guest_id, {}).get("ips", []))
        ips |= {r.ip for r in self.session.requests if r.guest_id == guest_id and r.ip}
        return ips - self.ignored_ips - {""}

    def guests(self) -> list[dict]:
        """Invités entrés pendant la soirée, avec leurs titres et leur statut de blocage."""
        guests = {
            gid: {"guest_id": gid, "name": g["name"], "joined_at": g["joined_at"], "total": 0, "queued": 0,
                  "via": g.get("via", ["music"]), "active_at": max(g.get("active_at") or g["joined_at"], self.last_seen.get(gid, 0))}
            for gid, g in self.session.guests.items()
        }
        for r in self.session.requests:
            g = guests.get(r.guest_id)  # seulement les invités présents (pas ceux déconnectés)
            if g is not None:
                g["total"] += 1
                g["queued"] += r.status == "queued"
        guests.pop(HOST_ID, None)  # l'hôte n'est pas un invité (pas de ban, pas de déconnexion)
        for g in guests.values():
            g["ban"] = self.ban_status(g["guest_id"], *self.guest_ips(g["guest_id"]))
            g["last_seen"] = self.last_seen.get(g["guest_id"], 0)
        return sorted(guests.values(), key=lambda g: g["name"].lower())

    def add_message(self, guest_id: str, name: str, text: str) -> dict:
        msg = {"id": uuid.uuid4().hex[:12], "guest_id": guest_id, "name": name, "text": text, "at": time.time(), "read": False}
        self.session.messages.append(msg)
        self.save()
        return msg

    def reply(self, message_id: str, text: str) -> dict | None:
        msg = next((m for m in self.session.messages if m["id"] == message_id), None)
        if msg is not None:
            msg.update(reply=text, reply_at=time.time(), read=True)
            self.save()
        return msg

    def messages_of(self, guest_id: str) -> list[dict]:
        return [m for m in self.session.messages if m["guest_id"] == guest_id]

    def update_messages(self, ids: set[str] | None, *, read: bool = False, delete: bool = False):
        """Marque comme lus ou supprime des messages (ids=None : tous)."""
        hit = lambda m: ids is None or m["id"] in ids
        if delete:
            self.session.messages = [m for m in self.session.messages if not hit(m)]
        else:
            for m in self.session.messages:
                if hit(m):
                    m["read"] = read
        self.save()

    def ban(self, guest_id: str, minutes: int | None):
        """Bloque un invité par son identifiant (jamais par IP partagée) ; minutes=None : sans limite."""
        reqs = [r for r in self.session.requests if r.guest_id == guest_id]
        name = self.session.guests.get(guest_id, {}).get("name") or (reqs[-1].guest_name if reqs else "")
        self.session.bans[guest_id] = {
            "name": name,
            "ips": sorted(self.guest_ips(guest_id)),
            "until": time.time() + minutes * 60 if minutes else 0,
        }
        self.save()

    def unban(self, guest_id: str):
        self.session.bans.pop(guest_id, None)
        self.save()

    def active_bans(self) -> dict[str, dict]:
        now = time.time()
        expired = [g for g, b in self.session.bans.items() if b["until"] and b["until"] <= now]
        for g in expired:
            del self.session.bans[g]
        if expired:
            self.save()
        return self.session.bans

    def ban_status(self, guest_id: str, *ips: str) -> dict | None:
        """{"until": timestamp ou 0} si cet invité (son identifiant) est bloqué.
        Jamais par adresse IP : en soirée tout le monde partage la même box (Wi-Fi de l'hôte, iPhone et ordinateur
        de l'hôte…) ; bloquer l'IP d'un invité bloquait les autres. Les IP gardées dans le ban ne servent qu'à l'info.
        (ips reste accepté pour ne pas changer les appelants.)"""
        found = [b for g, b in self.active_bans().items() if g == guest_id]
        if not found:
            return None
        # Un bannissement sans limite l'emporte sur un blocage temporaire.
        return {"until": 0 if any(b["until"] == 0 for b in found) else max(b["until"] for b in found)}

    def reconcile(self, upcoming_ids: set[str]) -> list[Request]:
        """Marque comme jouées les demandes qui ne sont plus à venir dans la file ; les renvoie."""
        done = [r for r in self.pending() if r.track_id not in upcoming_ids]
        for r in done:
            r.status = "played"
        if done:
            self.save()
        return done

    def track_started(self, entry: dict):
        """Nouveau titre en cours : ajouté à l'historique de la soirée."""
        self.session.played = self.session.played[-199:] + [{**entry, "at": time.time()}]
        self.save()

    def add_push(self, guest_id: str | None, sub: dict):
        """Abonne un invité (ou l'hôte si guest_id est None) ; un appareil n'est abonné qu'une fois."""
        self.remove_push(sub["endpoint"], save=False)
        sub = {"endpoint": sub["endpoint"], "keys": {k: sub["keys"][k] for k in ("p256dh", "auth")}}
        if guest_id is None:
            self.session.admin_push = self.session.admin_push[-4:] + [sub]
        else:
            self.session.push[guest_id] = self.session.push.get(guest_id, [])[-2:] + [sub]
        self.save()

    def remove_push(self, endpoint: str, save: bool = True):
        self.session.admin_push = [s for s in self.session.admin_push if s["endpoint"] != endpoint]
        for gid in list(self.session.push):
            self.session.push[gid] = [s for s in self.session.push[gid] if s["endpoint"] != endpoint]
            if not self.session.push[gid]:
                del self.session.push[gid]
        if save:
            self.save()


def insert_position(
    mode: str,
    current_pos: int,
    upcoming: list[tuple[int, str]],
    pending: list[Request],
    guest_id: str,
) -> int:
    """Position (1-based) où insérer un nouveau titre ; 0 = fin de file.

    current_pos : position 1-based du titre en cours (0 si aucun).
    upcoming    : (position 1-based, track_id) des titres après le titre en cours.

    - "next" : à la suite des demandes déjà en attente (premier arrivé, premier servi ; celles de l'hôte comprises),
      donc jamais devant une demande plus ancienne, et toujours avant la suite de la playlist.
    - "fair" : tour par tour entre invités. La k-ième demande en attente d'un
      invité appartient au tour k ; un nouveau titre se place après le dernier
      titre invité d'un tour <= au sien, donc avant la suite de la playlist.
    """
    if current_pos <= 0:
        return 0
    if mode != "fair":
        return end_of_requests(current_pos, upcoming, pending)

    pending_by_track = {r.track_id: r for r in pending}
    rounds: dict[str, int] = {}
    placed: list[tuple[int, int]] = []  # (position, tour)
    for pos, track_id in upcoming:
        req = pending_by_track.pop(track_id, None)
        if req is None:
            continue
        rounds[req.guest_id] = rounds.get(req.guest_id, 0) + 1
        placed.append((pos, rounds[req.guest_id]))

    my_round = rounds.get(guest_id, 0) + 1
    before = [pos for pos, rnd in placed if rnd <= my_round]
    return (max(before) if before else current_pos) + 1


def fair_moves(current_pos: int, upcoming: list[tuple[int, str]], pending: list[Request]) -> list[tuple[int, int]]:
    """Déplacements (de, vers) à appliquer dans l'ordre pour remettre la file au tour par tour.

    Les titres d'invités en attente sont regroupés juste après le titre en cours :
    1er titre de chaque invité, puis 2e, etc. (invités dans l'ordre de leur première demande,
    titres d'un même invité dans l'ordre d'ajout). Le reste de la file garde son ordre.
    """
    if current_pos <= 0:
        return []
    queue = [track_id for _, track_id in upcoming]
    by_guest: dict[str, list[Request]] = {}
    for r in sorted(pending, key=lambda r: r.added_at):
        if r.track_id in queue:
            by_guest.setdefault(r.guest_id, []).append(r)
    rounds = max((len(v) for v in by_guest.values()), default=0)
    target = [reqs[k].track_id for k in range(rounds) for reqs in by_guest.values() if k < len(reqs)]

    moves = []
    for i, track_id in enumerate(target):
        src = queue.index(track_id)
        if src != i:
            queue.insert(i, queue.pop(src))
            moves.append((current_pos + 1 + src, current_pos + 1 + i))
    return moves


def end_of_requests(current_pos: int, upcoming: list[tuple[int, str]], pending: list[Request]) -> int:
    """Position (1-based) juste après la dernière demande en attente : la fin de « notre » file,
    avant la suite de la playlist de l'hôte. 0 = fin de la file Sonos (rien ne joue)."""
    if current_pos <= 0:
        return 0
    requested = {r.track_id for r in pending}
    last = max((pos for pos, track_id in upcoming if track_id in requested), default=current_pos)
    return last + 1
