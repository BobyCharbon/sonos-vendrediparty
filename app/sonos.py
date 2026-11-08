"""Accès local aux enceintes Sonos via SoCo."""

import logging
import random
import re
import threading
from xml.sax.saxutils import escape as xml_escape
import time

import soco
from soco.data_structures import DidlPlaylistContainer
from soco.exceptions import SoCoUPnPException
from soco.plugins.sharelink import ShareLinkPlugin

# SoCo attend 20 s par défaut une enceinte qui ne répond pas (une enceinte qui décroche du Wi-Fi bloquait tout) ;
# sur le réseau local, une réponse prend moins d'une seconde (mesuré le 05.11.2026 : file de 220 titres en 0,35 s).
soco.config.REQUEST_TIMEOUT = 5.0
# Réglage et lecture d'un volume : délai court, l'app renvoie de toute façon la valeur suivante.
VOLUME_TIMEOUT = 2.5
ZONES_TTL = 60

log = logging.getLogger(__name__)

TRACK_ID_RE = re.compile(r"spotify(?:%3a|:)track(?:%3a|:)([A-Za-z0-9]{22})", re.I)


# Services musicaux Sonos (paramètre « sid » de l'adresse du titre) : on affiche d'où vient un titre non Spotify.
SERVICES = {"9": "Spotify", "284": "YouTube Music", "204": "Apple Music", "2": "Deezer", "160": "SoundCloud",
            "303": "Sonos Radio", "254": "TuneIn", "201": "Amazon Music", "31": "Qobuz", "174": "Tidal"}


def service_name(uri: str) -> str:
    m = re.search(r"[?&]sid=(\d+)", uri or "")
    if m:
        return SERVICES.get(m.group(1), "Sonos")
    return "Bibliothèque" if (uri or "").startswith(("x-file-cifs:", "x-smb:")) else "Sonos"


def spotify_track_id(uri: str) -> str | None:
    m = TRACK_ID_RE.search(uri or "")
    return m.group(1) if m else None


def seconds(hms: str | None) -> int | None:
    """« 0:03:45 » -> 225 ; None si inconnu (radio, NOT_IMPLEMENTED…)."""
    try:
        parts = [int(float(x)) for x in (hms or "").split(":")]
    except ValueError:
        return None
    if not parts or len(parts) > 3:
        return None
    total = 0
    for x in parts:
        total = total * 60 + x
    return total


def _read_volume(zone) -> int:
    result = zone.renderingControl.GetVolume([("InstanceID", 0), ("Channel", "Master")], timeout=VOLUME_TIMEOUT)
    return int(result["CurrentVolume"])


def _playing(zone) -> bool:
    """L'enceinte joue (ou se met à jouer) ; illisible : on considère qu'elle ne joue pas."""
    try:
        return zone.get_current_transport_info().get("current_transport_state") in ("PLAYING", "TRANSITIONING")
    except Exception:
        return False


def _reachable(zone) -> bool:
    """L'enceinte répond-elle ? (son nom est lu une fois puis gardé en cache par SoCo.)"""
    try:
        return bool(zone.player_name)
    except Exception:
        return False


class Sonos:
    def __init__(self, seed_ip: str | None = None):
        self.seed_ip = seed_ip
        self._zones: dict[str, soco.SoCo] = {}
        self._zones_at = 0.0
        self._lock = threading.Lock()
        self._refresher: threading.Thread | None = None
        # Dernier groupe vu pour chaque enceinte de soirée : si elle en sort, la soirée suit ceux qui continuent.
        self._last_members: dict[str, set[str]] = {}

    def _refresh_zones(self):
        if self.seed_ip:
            zones = soco.SoCo(self.seed_ip).all_zones
        else:
            zones = soco.discover(timeout=3, include_invisible=False) or set()
        # Une enceinte éteinte reste annoncée par les autres : on l'ignore au lieu de tout bloquer.
        self._zones = {z.uid: z for z in zones if _reachable(z)}
        self._zones_at = time.time()

    def _refresh_in_background(self):
        try:
            with self._lock:
                self._refresh_zones()
        except Exception:
            log.exception("Sonos : rafraîchissement des enceintes impossible")

    def _all_zones(self) -> dict[str, soco.SoCo]:
        """Les enceintes connues. Périmées, elles servent encore pendant leur relecture en arrière-plan : une enceinte
        lente à répondre ne bloque plus le volume ni la liste (seule la toute première lecture attend)."""
        if not self._zones:
            with self._lock:
                if not self._zones:
                    self._refresh_zones()
            return self._zones
        if time.time() - self._zones_at > ZONES_TTL and not (self._refresher and self._refresher.is_alive()):
            self._refresher = threading.Thread(target=self._refresh_in_background, daemon=True)
            self._refresher.start()
        return self._zones

    def rooms(self) -> list[dict]:
        """Un élément par groupe Sonos (identifié par son coordinateur)."""
        groups = {}
        for z in self._all_zones().values():
            try:
                coord = z.group.coordinator
                members = list(z.group.members)
            except Exception:  # groupe illisible (membre éteint) : l'enceinte seule
                coord, members = z, [z]
            visible = {m.player_name for m in members if _reachable(m) and m.is_visible}
            groups[coord.uid] = {
                "uid": coord.uid,
                "name": " + ".join(sorted(visible)) or coord.player_name,
                "spotify_name": coord.player_name,
            }
        return sorted(groups.values(), key=lambda g: g["name"])

    def coordinator(self, uid: str) -> soco.SoCo:
        zone = self._all_zones().get(uid)
        if zone is None:
            with self._lock:
                self._refresh_zones()
            zone = self._zones.get(uid)
        if zone is None:
            raise LookupError("Enceinte Sonos introuvable")
        # Le groupe peut avoir changé depuis le démarrage de la session.
        return self._follow_group(uid, zone.group.coordinator)

    def _follow_group(self, uid: str, coord: soco.SoCo) -> soco.SoCo:
        """L'enceinte de la soirée retirée de son groupe (app Sonos) : Sonos continue la musique sur les autres, la
        soirée les suit au lieu d'afficher « en pause » (retour de l'admin, 08.11). Revenue dans un groupe : normal."""
        try:
            members = {m.uid for m in coord.group.members}
        except Exception:  # groupe illisible : on garde l'enceinte telle quelle
            return coord
        before = self._last_members.get(uid, set())
        if members == {uid} and len(before) > 1 and not _playing(coord):
            zones = self._all_zones()
            for other in sorted(before - {uid}):
                zone = zones.get(other)
                try:
                    moved = zone.group.coordinator if zone is not None else None
                except Exception:
                    moved = None
                # Seulement un groupe qui continue (encore groupé, ou qui joue) : jamais une enceinte retirée à l'arrêt.
                if moved is not None and moved.uid != uid and (len(moved.group.members) > 1 or _playing(moved)):
                    # L'enceinte de la soirée reste dans le groupe retenu : la lecture suivante suit encore.
                    self._last_members[uid] = {uid} | {m.uid for m in moved.group.members}
                    return moved
        self._last_members[uid] = members
        return coord

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
                duration = seconds(item.resources[0].duration) if item.resources else None
                items.append(
                    {
                        "pos": current_pos + offset,
                        "track_id": spotify_track_id(uri),
                        "title": item.title,
                        "artist": getattr(item, "creator", "") or "",
                        "art": getattr(item, "album_art_uri", "") or "",
                        "duration": duration or None,
                        "service": service_name(uri),
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
        share = ShareLinkPlugin(coord)
        # Le titre entre tel quel dans les métadonnées XML envoyées au Sonos : un « & » (« HAINE&SEX ») les rendait
        # invalides et Sonos refusait l'ajout (erreur UPnP 800).
        title = xml_escape(title)
        # En lecture aléatoire, Sonos refuse un titre inséré à une position (erreur UPnP 800) :
        # on le lui donne « à jouer ensuite », la seule insertion qu'il accepte dans ce mode.
        if "SHUFFLE" in (coord.play_mode or ""):
            return share.add_share_link_to_queue(f"spotify:track:{track_id}", position=0, as_next=True, dc_title=title)
        return share.add_share_link_to_queue(f"spotify:track:{track_id}", position=position, dc_title=title)

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
        for z in list(self._all_zones().values()):
            try:
                # On masque caissons, surrounds et 2e enceinte d'une paire stéréo ; mais si aucune
                # enceinte d'un groupe n'est « visible » (cas de certaines paires), on garde la principale.
                lone_master = z.uid == z.group.coordinator.uid and not any(m.is_visible for m in z.group.members)
                if not (z.is_visible or lone_master):
                    continue
                result.append({
                    "uid": z.uid,
                    "name": z.player_name,
                    "volume": _read_volume(z),
                    "in_group": z.group.coordinator.uid == coord.uid,
                    "coordinator": z.uid == coord.uid,
                })
            except Exception as e:  # enceinte qui a décroché du Wi-Fi : on liste les autres
                log.warning("Sonos : %s ne répond pas (%s)", getattr(z, "ip_address", "?"), e)
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
        self._all_zones()[speaker_uid].renderingControl.SetVolume(
            [("InstanceID", 0), ("Channel", "Master"), ("DesiredVolume", volume)], timeout=VOLUME_TIMEOUT)

    def play(self, uid: str):
        self.coordinator(uid).play()

    def pause(self, uid: str):
        self.coordinator(uid).pause()

    def set_volume(self, uid: str, volume: int):
        group = self.coordinator(uid).group
        rendering = group.coordinator.groupRenderingControl

        def set_group():
            rendering.SetGroupVolume([("InstanceID", 0), ("DesiredVolume", volume)], timeout=VOLUME_TIMEOUT)

        try:
            set_group()
        except SoCoUPnPException:
            # Erreur 801 intermittente : Sonos veut un « snapshot » du volume de groupe avant de le régler.
            if len(group.members) == 1:
                group.coordinator.renderingControl.SetVolume(
                    [("InstanceID", 0), ("Channel", "Master"), ("DesiredVolume", volume)], timeout=VOLUME_TIMEOUT)
                return
            rendering.SnapshotGroupVolume([("InstanceID", 0)], timeout=VOLUME_TIMEOUT)
            set_group()

    def skip(self, uid: str):
        self.coordinator(uid).next()

    def playlists(self) -> list[dict]:
        """Playlists Sonos, puis favoris qui sont des playlists (Spotify…)."""
        # Une enceinte principale : les caissons et surrounds refusent ces requêtes.
        zones = sorted(self._all_zones().values(), key=lambda z: (z.ip_address != self.seed_ip, not z.is_visible))
        error = None
        for zone in zones[:4]:
            try:
                playlists, favorites = zone.get_sonos_playlists(), zone.music_library.get_sonos_favorites()
                break
            except Exception as e:
                error = e
        else:
            raise error or LookupError("Aucune enceinte Sonos")
        items = {}
        for p in playlists:
            items["sq:" + p.item_id] = ("sonos", p)
        for f in favorites:
            ref = f.reference
            # Les playlists Sonos mises en favori (SQ:…) sont déjà listées au-dessus.
            if isinstance(ref, DidlPlaylistContainer) and not ref.item_id.startswith("SQ:"):
                items["fav:" + ref.item_id] = ("favorite", ref)
        self._playlists = items
        return [{"id": k, "title": item.title, "kind": kind} for k, (kind, item) in items.items()]

    def launch_playlist(self, uid: str, playlist_id: str, keep: list[tuple[str, str]]):
        """Remplace la file par la playlist, en aléatoire (avec répétition) et fondu enchaîné.
        keep : (track_id, titre) des demandes à garder ; elles passent en premier."""
        coord = self.coordinator(uid)
        if playlist_id.startswith("spotify:playlist:"):
            # Playlist Spotify (même hors des favoris) : Sonos la lit avec le compte Spotify lié.
            coord.clear_queue()
            ShareLinkPlugin(coord).add_share_link_to_queue(playlist_id)
        else:
            if playlist_id not in getattr(self, "_playlists", {}):
                self.playlists()
            if playlist_id not in self._playlists:
                raise LookupError("Playlist introuvable")
            coord.clear_queue()
            coord.add_to_queue(self._playlists[playlist_id][1])
        # La file Sonos devient la source d'abord : si Spotify Connect ou la TV jouait, Sonos refuse sinon le mode
        # aléatoire (UPnP 712 « Play mode not supported »).
        coord.avTransport.SetAVTransportURI([("InstanceID", 0), ("CurrentURI", f"x-rincon-queue:{coord.uid}#0"),
                                             ("CurrentURIMetaData", "")])
        # Sonos mélange réellement la file : l'ordre de la file reste l'ordre de lecture.
        coord.play_mode = "SHUFFLE"
        coord.cross_fade = True
        size = coord.queue_size
        if not size:
            raise LookupError("Cette playlist est vide")
        # Le 1er titre de la file reste le même après mélange : on démarre ailleurs, au hasard.
        start = random.randint(1, size)
        for i, (track_id, title) in enumerate(keep):
            ShareLinkPlugin(coord).add_share_link_to_queue(f"spotify:track:{track_id}", position=start + i, dc_title=title)
        coord.play_from_queue(start - 1)
