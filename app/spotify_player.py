"""Spotify possède la file, à la maison sur Sonos comme à l'extérieur sur le téléphone.

L'aperçu vient de Spotify ; les suppressions et déplacements se font dans son application.
Les anciens champs vqueue/vpushed ne servent plus qu'à migrer une soirée déjà ouverte.
"""

import threading

from .spotify import Spotify, SpotifyError, SpotifyUser


QUEUE_MANAGED_IN_SPOTIFY = "Modifie la file directement dans l'app Spotify"


def hms(ms: int | None) -> str:
    if not ms:
        return ""
    s = ms // 1000
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


class SpotifyPlayer:
    def __init__(self, user: SpotifyUser, catalog: Spotify, store, sonos=None):
        self.user, self.catalog, self.store = user, catalog, store
        self.sonos = sonos
        self._lock = threading.RLock()

    def _target(self) -> dict:
        s = self.store.session
        return {"device_id": s.spotify_device_id} if s.source == "spotify_sonos" else {}

    def _check_device(self, playback: dict):
        s = self.store.session
        if s.source == "spotify_sonos" and (playback.get("device") or {}).get("id") != s.spotify_device_id:
            raise SpotifyError(f"Spotify a changé d'appareil. Sélectionne « {s.spotify_device_name} » dans Spotify, ou redémarre la soirée pour choisir une autre pièce")

    @staticmethod
    def _item(pos: int, item: dict) -> dict:
        images = (item.get("album") or {}).get("images") or item.get("images") or []
        # L'identifiant d'origine permet de retrouver une demande relinkée par Spotify.
        track_id = ((item.get("linked_from") or {}).get("id") or item.get("id")) if item.get("type", "track") == "track" else None
        return {"pos": pos, "track_id": track_id, "title": item.get("name") or "Titre indisponible",
                "artist": ", ".join(a["name"] for a in item.get("artists", [])) or (item.get("show") or {}).get("name", ""),
                "art": images[0]["url"] if images else "", "duration": (item.get("duration_ms") or 0) // 1000 or None}

    def _migrate_legacy_queue(self):
        """Transfère l'ancienne file une fois, sans renvoyer la demande déjà expédiée.

        Chaque tentative est persistée AVANT l'appel réseau. Un envoi incertain reste signalé
        à l'hôte, sans nouvelle tentative au prochain rafraîchissement ou redémarrage.
        """
        s = self.store.session
        if s.vpushed:
            if s.vpushed in s.vqueue:
                s.vqueue.remove(s.vpushed)
            s.vpushed = s.vpushed_during = ""
            self.store.save(notify=False)
        while s.vqueue:
            tid = s.vqueue.pop(0)
            s.spotify_transfer_issues.append(tid)
            self.store.save(notify=False)
            try:
                self.user.queue(tid)
            except Exception:
                continue
            s.spotify_transfer_issues.remove(tid)
            self.store.save(notify=False)

    def snapshot(self, uid: str = "", max_upcoming: int = 300) -> dict:
        with self._lock:
            pb = self.user.playback() or {}
            self._check_device(pb)
            queue = self.user.get_queue()
            # Ne migre pas vers un appareil absent ; les demandes restent conservées.
            if pb.get("device"):
                self._migrate_legacy_queue()
            item = pb.get("item") or queue.get("currently_playing") or {}
            current = self._item(1, item) if item else None
            device = pb.get("device") or {}
            volume = device.get("volume_percent")
            if self.store.session.source == "spotify_sonos" and self.sonos:
                try:
                    volume = self.sonos.coordinator(uid).group.volume
                except Exception:
                    volume = None  # La file Spotify reste accessible si le volume Sonos ne répond pas.
            return {
                "coordinator_ip": None, "volume": volume,
                "room": device.get("name", "Spotify"),
                "state": "PLAYING" if pb.get("is_playing") else ("PAUSED_PLAYBACK" if pb else "STOPPED"),
                "from_queue": True, "current_pos": 1, "current": current,
                "upcoming": [self._item(i + 2, t) for i, t in enumerate(queue.get("queue", [])[:max_upcoming]) if t],
                "now": {"title": current["title"] if current else "", "artist": current["artist"] if current else "",
                        "art": current["art"] if current else "", "position": hms(pb.get("progress_ms")), "duration": hms(item.get("duration_ms"))},
                "device": device.get("name", ""),
            }

    def add_spotify_track(self, uid: str, track_id: str, title: str, position: int) -> int:
        with self._lock:
            self.user.queue(track_id, **self._target())
            # L'API ne renvoie pas la position ; on ne prétend pas en connaître une.
            return 0

    def remove_at(self, uid: str, position: int):
        raise SpotifyError(QUEUE_MANAGED_IN_SPOTIFY)

    def move(self, uid: str, from_pos: int, to_pos: int):
        raise SpotifyError(QUEUE_MANAGED_IN_SPOTIFY)

    def play_at(self, uid: str, position: int):
        raise SpotifyError(QUEUE_MANAGED_IN_SPOTIFY)

    def skip(self, uid: str = ""):
        self.user.next(**self._target())

    def play(self, uid: str = ""):
        self.user.play(**self._target())

    def pause(self, uid: str = ""):
        self.user.pause(**self._target())

    def set_volume(self, uid: str, volume: int):
        if self.store.session.source == "spotify_sonos" and self.sonos:
            self.sonos.set_volume(uid, volume)
        else:
            self.user.volume(volume)

    def launch_playlist(self, uid: str, playlist_id: str, keep):
        if not playlist_id.startswith("spotify:playlist:"):
            raise LookupError("Seules les playlists Spotify peuvent être lancées dans ce mode")
        self.user.play(playlist_id, **self._target())
        try:
            self.user.shuffle(True, **self._target())
        except SpotifyError:
            pass

    def speakers(self, uid: str = "") -> list:
        if self.store.session.source == "spotify_sonos" and self.sonos:
            return self.sonos.speakers(uid)
        return []
