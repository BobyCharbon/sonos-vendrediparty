"""Limitation des essais de code PIN (page exposée sur Internet)."""

import threading
import time


class Limiter:
    """Verrouille une IP après trop d'échecs, et tout le monde si les échecs explosent.

    Un PIN à 4 chiffres n'a que 10 000 combinaisons : le verrou global empêche
    une attaque répartie sur beaucoup d'IP.
    """

    def __init__(self, per_ip: int, ip_lock: int, global_max: int, global_window: int, global_lock: int,
                 cooldown: bool = False):
        # cooldown=False : après per_ip échecs, l'IP est bloquée ip_lock secondes puis repart à zéro.
        # cooldown=True  : après per_ip échecs, chaque nouvel échec impose ip_lock secondes d'attente.
        self.per_ip, self.ip_lock, self.cooldown = per_ip, ip_lock, cooldown
        self.global_max, self.global_window, self.global_lock = global_max, global_window, global_lock
        self._ips: dict[str, tuple[int, float]] = {}  # ip -> (échecs, verrouillé jusqu'à)
        self._recent: list[float] = []
        self._global_until = 0.0
        self._lock = threading.Lock()

    def blocked(self, ip: str) -> str | None:
        now = time.time()
        with self._lock:
            if now < self._global_until:
                return f"Trop d'essais au total, réessaie dans {self._minutes(self._global_until)}"
            _, until = self._ips.get(ip, (0, 0))
            if now < until:
                return f"Trop d'essais, réessaie dans {self._minutes(until)}"
        return None

    def fail(self, ip: str):
        now = time.time()
        with self._lock:
            count, until = self._ips.get(ip, (0, 0))
            if until and now >= until and not self.cooldown:
                count = 0
            count += 1
            self._ips[ip] = (count, now + self.ip_lock if count >= self.per_ip else 0)
            self._recent = [t for t in self._recent if now - t < self.global_window] + [now]
            if len(self._recent) >= self.global_max:
                self._global_until = now + self.global_lock
                self._recent = []

    def success(self, ip: str):
        with self._lock:
            self._ips.pop(ip, None)

    @staticmethod
    def _minutes(until: float) -> str:
        left = until - time.time()
        return f"{max(1, round(left))} s" if left < 60 else f"{max(1, round(left / 60))} min"
