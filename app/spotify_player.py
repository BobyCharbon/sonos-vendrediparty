"""Mode « Party extérieur » : la musique sort du téléphone de l'hôte (app Spotify → enceinte Bluetooth).

Ce lecteur a la même interface que Sonos pour le reste de l'app. La file des demandes reste sur le
serveur (store.session.vqueue) : l'API Spotify ne sait qu'ajouter à la fin de sa file, sans retirer ni
déplacer. On pousse donc une seule demande à la fois, ~25 s avant la fin du titre en cours ; elle passe
juste après, puis la playlist lancée sur le téléphone reprend. Positions : 1 = titre en cours, 2… = demandes.
"""

import threading

from .spotify import Spotify, SpotifyError, SpotifyUser

PUSH_BEFORE_END_MS = 25_000


def hms(ms: int | None) -> str:
    if not ms:
        return ""
    s = ms // 1000
    return f"{s // 3600}:{s // 60 % 60:02d}:{s % 60:02d}"


class SpotifyPlayer:
    def __init__(self, user: SpotifyUser, catalog: Spotify, store):
        self.user, self.catalog, self.store = user, catalog, store
        self._lock = threading.RLock()

    # --- File virtuelle (sur le serveur) ---

    @property
    def q(self) -> list[str]:
        return self.store.session.vqueue

    def _save(self):
        self.store.save(notify=False)

    def _item(self, pos: int, track_id: str) -> dict:
        t = self.catalog.track(track_id)
        return {"pos": pos, "track_id": track_id, "title": t["title"], "artist": t["artist"], "art": t.get("image", ""),
                "duration": (t.get("duration_ms") or 0) // 1000 or None}

    def snapshot(self, uid: str = "", max_upcoming: int = 300) -> dict:
        with self._lock:
            pb = self.user.playback()
            item = (pb or {}).get("item") or {}
            cur_id = item.get("id")
            s = self.store.session
            # La demande poussée vers Spotify a démarré : elle quitte notre file.
            if s.vpushed and cur_id == s.vpushed:
                if s.vpushed in self.q:
                    self.q.remove(s.vpushed)
                s.vpushed = ""
                self._save()
            # Fin du titre en cours proche : on glisse la prochaine demande dans la file Spotify.
            playing = bool(pb and pb.get("is_playing"))
            left = (item.get("duration_ms") or 0) - ((pb or {}).get("progress_ms") or 0)
            if playing and not s.vpushed and self.q and cur_id and left < PUSH_BEFORE_END_MS:
                self._push()
            images = (item.get("album") or {}).get("images") or []
            art = images[0]["url"] if images else ""
            current = {"pos": 1, "track_id": cur_id, "title": item.get("name", ""),
                       "artist": ", ".join(a["name"] for a in item.get("artists", [])), "art": art,
                       "duration": (item.get("duration_ms") or 0) // 1000 or None} if cur_id else None
            device = (pb or {}).get("device") or {}
            return {
                "coordinator_ip": None,
                "volume": device.get("volume_percent"),
                "room": device.get("name", "Spotify"),
                "state": "PLAYING" if playing else ("PAUSED_PLAYBACK" if pb else "STOPPED"),
                "from_queue": True,  # les demandes sont gardées ici : on peut toujours en ajouter
                "current_pos": 1,
                "current": current,
                "upcoming": [self._item(i + 2, tid) for i, tid in enumerate(self.q[:max_upcoming])],
                "now": {"title": current["title"] if current else "", "artist": current["artist"] if current else "",
                        "art": art, "position": hms((pb or {}).get("progress_ms")), "duration": hms(item.get("duration_ms"))},
                "device": device.get("name", ""),
            }

    def _push(self):
        """Envoie la première demande dans la file Spotify (elle passera juste après le titre en cours)."""
        s = self.store.session
        self.user.queue(self.q[0])
        s.vpushed = self.q[0]
        self._save()

    def add_spotify_track(self, uid: str, track_id: str, title: str, position: int) -> int:
        with self._lock:
            idx = len(self.q) if position <= 0 else max(0, min(len(self.q), position - 2))
            # La demande déjà glissée chez Spotify reste en tête : on n'insère jamais devant elle.
            if self.store.session.vpushed and self.q and self.q[0] == self.store.session.vpushed:
                idx = max(idx, 1)
            self.q.insert(idx, track_id)
            self._save()
            return idx + 2

    def remove_at(self, uid: str, position: int):
        with self._lock:
            i = position - 2
            if 0 <= i < len(self.q):
                # Déjà glissé chez Spotify : il passera quand même (Spotify ne permet pas de le retirer).
                self.q.pop(i)
                self._save()

    def move(self, uid: str, from_pos: int, to_pos: int):
        with self._lock:
            a, b = from_pos - 2, to_pos - 2
            if 0 <= a < len(self.q) and 0 <= b < len(self.q):
                pushed = self.store.session.vpushed
                if pushed and self.q[0] == pushed and (a == 0 or b == 0):
                    raise SpotifyError("Ce titre est déjà envoyé à Spotify : il passe juste après")
                self.q.insert(b, self.q.pop(a))
                self._save()

    def play_at(self, uid: str, position: int):
        """Jouer maintenant : la demande passe en tête, part chez Spotify, et on passe au titre suivant."""
        with self._lock:
            i = position - 2
            if not 0 <= i < len(self.q):
                return
            s = self.store.session
            if not (s.vpushed and self.q[0] == s.vpushed):
                self.q.insert(0, self.q.pop(i))
                self._push()
            self.user.next()

    def skip(self, uid: str = ""):
        with self._lock:
            s = self.store.session
            if self.q and not s.vpushed:
                self._push()  # la prochaine demande passe tout de suite
            self.user.next()

    def play(self, uid: str = ""):
        self.user.play()

    def pause(self, uid: str = ""):
        self.user.pause()

    def set_volume(self, uid: str, volume: int):
        self.user.volume(volume)

    def launch_playlist(self, uid: str, playlist_id: str, keep):
        """Lance une playlist Spotify sur le téléphone, en aléatoire. Les demandes restent dans notre file."""
        if not playlist_id.startswith("spotify:playlist:"):
            raise LookupError("En mode extérieur, seules les playlists Spotify peuvent être lancées")
        self.user.play(playlist_id)
        try:
            self.user.shuffle(True)
        except SpotifyError:
            pass

    def speakers(self, uid: str = "") -> list:
        return []
