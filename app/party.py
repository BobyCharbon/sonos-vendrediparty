"""État de la soirée (persisté en JSON) et logique d'insertion dans la file."""

import json
import secrets
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

MODES = ("next", "fair")


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


class PartyStore:
    def __init__(self, path: Path):
        self.path = path
        self.lock = threading.RLock()
        self.session = self._load()
        if not self.session.guest_pin:
            self.regenerate_pin()

    def _load(self) -> Session:
        try:
            raw = json.loads(self.path.read_text())
            raw["requests"] = [Request(**r) for r in raw.get("requests", [])]
            return Session(**raw)
        except (FileNotFoundError, ValueError, TypeError):
            return Session()

    def save(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(asdict(self.session), ensure_ascii=False, indent=2))
        tmp.replace(self.path)

    def start(self, room_uid: str, room_name: str, mode: str):
        # Les bannissements et le code d'accès survivent d'une soirée à l'autre.
        self.session = Session(
            active=True, room_uid=room_uid, room_name=room_name, mode=mode, started_at=time.time(),
            bans=self.session.bans, guest_pin=self.session.guest_pin,
        )
        self.save()

    def regenerate_pin(self) -> str:
        old = self.session.guest_pin
        while (pin := f"{secrets.randbelow(10000):04d}") == old:
            pass
        self.session.guest_pin = pin
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

    def guests(self) -> list[dict]:
        """Invités ayant ajouté au moins un titre, avec leur statut de blocage."""
        guests: dict[str, dict] = {}
        for r in self.session.requests:
            g = guests.setdefault(r.guest_id, {"guest_id": r.guest_id, "name": r.guest_name, "ips": set(), "total": 0, "queued": 0})
            g["name"] = r.guest_name
            g["total"] += 1
            g["queued"] += r.status == "queued"
            if r.ip:
                g["ips"].add(r.ip)
        result = []
        for g in guests.values():
            g["ban"] = self.ban_status(g["guest_id"], *g.pop("ips"))
            result.append(g)
        return sorted(result, key=lambda g: g["name"].lower())

    def ban(self, guest_id: str, minutes: int | None):
        """Bloque un invité (par identifiant et par IP) ; minutes=None : sans limite."""
        reqs = [r for r in self.session.requests if r.guest_id == guest_id]
        self.session.bans[guest_id] = {
            "name": reqs[-1].guest_name if reqs else "",
            "ips": sorted({r.ip for r in reqs if r.ip}),
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
        ips = {ip for ip in ips if ip}
        found = [b for g, b in self.active_bans().items() if g == guest_id or ips & set(b["ips"])]
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
