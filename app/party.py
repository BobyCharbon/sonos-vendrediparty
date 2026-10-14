"""État de la soirée (persisté en JSON) et logique d'insertion dans la file."""

import json
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

MODES = ("next", "fair")
HOST_ID = "host"  # les ajouts de l'hôte sont des demandes comme les autres, signées « Hôte »


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


@dataclass
class Session:
    active: bool = False
    room_uid: str = ""
    room_name: str = ""
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

    def save(self):
        self.version += 1
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self.session), ensure_ascii=False, indent=2))
        tmp.replace(self.path)

    def start(self, room_uid: str, room_name: str, mode: str):
        # Les bannissements et le code d'accès survivent d'une soirée à l'autre.
        self.session = Session(
            active=True, room_uid=room_uid, room_name=room_name, mode=mode, started_at=time.time(),
            bans=self.session.bans, guest_pin=self.session.guest_pin, revoked=self.session.revoked,
        )
        self.save()

    def regenerate_pin(self) -> str:
        old = self.session.guest_pin
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
        )
        self.session.requests.append(req)
        self.save()
        return req

    def register_guest(self, guest_id: str, name: str, ip: str):
        """Un invité entre (ou change de prénom) : il apparaît tout de suite dans l'admin."""
        g = self.session.guests.get(guest_id)
        if g and g["name"] == name and (not ip or ip in self.ignored_ips or ip in g["ips"]):
            return
        if g is None:
            g = self.session.guests[guest_id] = {"name": name, "ips": [], "joined_at": time.time()}
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

    def kick(self, guest_id: str):
        """Déconnecte un invité : ses jetons sont révoqués, il devra ressaisir le code."""
        g = self.session.guests.get(guest_id, {})
        self.session.revoked = (self.session.revoked + g.get("tokens", []))[-500:]
        g["tokens"] = []
        self.last_seen.pop(guest_id, None)
        self.save()

    def seen(self, guest_id: str):
        if guest_id in self.session.guests:
            self.last_seen[guest_id] = time.time()

    def guest_ips(self, guest_id: str) -> set[str]:
        ips = set(self.session.guests.get(guest_id, {}).get("ips", []))
        ips |= {r.ip for r in self.session.requests if r.guest_id == guest_id and r.ip}
        return ips - self.ignored_ips - {""}

    def guests(self) -> list[dict]:
        """Invités entrés pendant la soirée, avec leurs titres et leur statut de blocage."""
        guests = {
            gid: {"guest_id": gid, "name": g["name"], "joined_at": g["joined_at"], "total": 0, "queued": 0}
            for gid, g in self.session.guests.items()
        }
        for r in self.session.requests:
            g = guests.setdefault(r.guest_id, {"guest_id": r.guest_id, "name": r.guest_name, "joined_at": r.added_at, "total": 0, "queued": 0})
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
        """Bloque un invité (par identifiant et par IP) ; minutes=None : sans limite."""
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
        """{"until": timestamp ou 0} si l'invité ou l'une de ses IP est bloqué."""
        ips = {ip for ip in ips if ip} - self.ignored_ips
        found = [b for g, b in self.active_bans().items() if g == guest_id or ips & (set(b["ips"]) - self.ignored_ips)]
        if not found:
            return None
        # Un bannissement sans limite l'emporte sur un blocage temporaire.
        return {"until": 0 if any(b["until"] == 0 for b in found) else max(b["until"] for b in found)}

    def reconcile(self, upcoming_ids: set[str]):
        """Marque comme jouées les demandes qui ne sont plus à venir dans la file."""
        changed = False
        for r in self.pending():
            if r.track_id not in upcoming_ids:
                r.status = "played"
                changed = True
        if changed:
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

    - "next" : juste après le titre en cours.
    - "fair" : tour par tour entre invités. La k-ième demande en attente d'un
      invité appartient au tour k ; un nouveau titre se place après le dernier
      titre invité d'un tour <= au sien, donc avant la suite de la playlist.
    """
    if current_pos <= 0:
        return 0
    if mode != "fair":
        return current_pos + 1

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
