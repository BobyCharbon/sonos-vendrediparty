"""Accès local aux enceintes Sonos via SoCo."""

import re
import threading
import time

import soco
from soco.exceptions import SoCoUPnPException
from soco.plugins.sharelink import ShareLinkPlugin

TRACK_ID_RE = re.compile(r"spotify(?:%3a|:)track(?:%3a|:)([A-Za-z0-9]{22})", re.I)


def spotify_track_id(uri: str) -> str | None:
    m = TRACK_ID_RE.search(uri or "")
    return m.group(1) if m else None


class Sonos:
    def __init__(self, seed_ip: str | None = None):
        self.seed_ip = seed_ip
        self._zones: dict[str, soco.SoCo] = {}
        self._zones_at = 0.0
        self._lock = threading.Lock()

    def _all_zones(self) -> dict[str, soco.SoCo]:
        with self._lock:
            if time.time() - self._zones_at > 60 or not self._zones:
                if self.seed_ip:
                    zones = soco.SoCo(self.seed_ip).all_zones
                else:
                    zones = soco.discover(timeout=3, include_invisible=False) or set()
                self._zones = {z.uid: z for z in zones}
                self._zones_at = time.time()
            return self._zones

    def rooms(self) -> list[dict]:
        """Un élément par groupe Sonos (identifié par son coordinateur)."""
        groups = {}
        for z in self._all_zones().values():
            coord = z.group.coordinator
            visible = {m.player_name for m in z.group.members if m.is_visible}
            groups[coord.uid] = {
                "uid": coord.uid,
                "name": " + ".join(sorted(visible)) or coord.player_name,
            }
        return sorted(groups.values(), key=lambda g: g["name"])

    def coordinator(self, uid: str) -> soco.SoCo:
        zone = self._all_zones().get(uid)
        if zone is None:
            self._zones_at = 0
            zone = self._all_zones().get(uid)
        if zone is None:
            raise LookupError("Enceinte Sonos introuvable")
        # Le groupe peut avoir changé depuis le démarrage de la session.
        return zone.group.coordinator

    def snapshot(self, uid: str, max_upcoming: int = 300) -> dict:
        coord = self.coordinator(uid)
        info = coord.get_current_track_info()
        state = coord.get_current_transport_info()["current_transport_state"]
        media_uri = coord.get_current_media_info().get("uri", "")
        current_pos = int(info.get("playlist_position") or 0)
        from_queue = media_uri.startswith("x-rincon-queue:")

        items = []
        if from_queue and current_pos > 0:
            queue = coord.get_queue(start=current_pos - 1, max_items=max_upcoming + 1)
            for offset, item in enumerate(queue):
                uri = item.resources[0].uri if item.resources else ""
                items.append(
                    {
                        "pos": current_pos + offset,
                        "track_id": spotify_track_id(uri),
                        "title": item.title,
                        "artist": getattr(item, "creator", "") or "",
                        "art": getattr(item, "album_art_uri", "") or "",
                    }
                )

        return {
            "coordinator_ip": coord.ip_address,
            # Volume du groupe : toutes les enceintes de la pièce suivent ensemble.
            "volume": coord.group.volume,
            "room": coord.player_name,
            "state": state,
            "from_queue": from_queue,
            "current_pos": current_pos if from_queue else 0,
            "current": items[0] if items else None,
            "upcoming": items[1:],
            "now": {
                "title": info.get("title", ""),
                "artist": info.get("artist", ""),
                "art": info.get("album_art", ""),
                "position": info.get("position", ""),
                "duration": info.get("duration", ""),
            },
        }

    def add_spotify_track(self, uid: str, track_id: str, title: str, position: int) -> int:
        coord = self.coordinator(uid)
        return ShareLinkPlugin(coord).add_share_link_to_queue(
            f"spotify:track:{track_id}", position=position, dc_title=title
        )

    def remove_at(self, uid: str, position: int):
        self.coordinator(uid).remove_from_queue(position - 1)

    def move(self, uid: str, from_pos: int, to_pos: int):
        """Déplace le titre en position from_pos (1-based) pour qu'il arrive en to_pos."""
        if from_pos == to_pos:
            return
        # InsertBefore s'exprime dans la numérotation d'avant le déplacement.
        insert_before = to_pos if to_pos < from_pos else to_pos + 1
        self.coordinator(uid).avTransport.ReorderTracksInQueue(
            [
                ("InstanceID", 0),
                ("StartingIndex", from_pos),
                ("NumberOfTracks", 1),
                ("InsertBefore", insert_before),
                ("UpdateID", 0),
            ]
        )

    def play_at(self, uid: str, position: int):
        self.coordinator(uid).play_from_queue(position - 1)

    def speakers(self, uid: str) -> list[dict]:
        """Toutes les enceintes visibles, avec leur volume et leur appartenance au groupe de la soirée."""
        coord = self.coordinator(uid)
        result = []
        for z in self._all_zones().values():
            # On masque caissons, surrounds et 2e enceinte d'une paire stéréo ; mais si aucune
            # enceinte d'un groupe n'est « visible » (cas de certaines paires), on garde la principale.
            lone_master = z.uid == z.group.coordinator.uid and not any(m.is_visible for m in z.group.members)
            if not (z.is_visible or lone_master):
                continue
            result.append({
                "uid": z.uid,
                "name": z.player_name,
                "volume": z.volume,
                "in_group": z.group.coordinator.uid == coord.uid,
                "coordinator": z.uid == coord.uid,
            })
        return sorted(result, key=lambda sp: (not sp["in_group"], sp["name"].lower()))

    def group_speaker(self, uid: str, speaker_uid: str, join: bool):
        coord = self.coordinator(uid)
        speaker = self._all_zones()[speaker_uid]
        if join:
            speaker.join(coord)
        elif speaker.uid != coord.uid:
            speaker.unjoin()
        self._zones_at = 0  # la composition des groupes a changé

    def set_speaker_volume(self, speaker_uid: str, volume: int):
        self._all_zones()[speaker_uid].volume = volume

    def play(self, uid: str):
        self.coordinator(uid).play()

    def pause(self, uid: str):
        self.coordinator(uid).pause()

    def set_volume(self, uid: str, volume: int):
        group = self.coordinator(uid).group
        try:
            group.volume = volume
        except SoCoUPnPException:
            # Erreur 801 intermittente : Sonos veut un « snapshot » du volume de groupe avant de le régler.
            if len(group.members) == 1:
                group.coordinator.volume = volume
                return
            group.coordinator.groupRenderingControl.SnapshotGroupVolume([("InstanceID", 0)])
            group.volume = volume

    def skip(self, uid: str):
        self.coordinator(uid).next()
