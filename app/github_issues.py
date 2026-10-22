"""Retours envoyés à Claude : une issue GitHub étiquetée « claude-fix », que le workflow
.github/workflows/claude-fix.yml corrige (commit sur develop) puis ferme. L'état de l'issue revient dans l'admin."""
import threading
import time

import httpx

API = "https://api.github.com"
LABEL = "claude-fix"
FAILED_LABEL = "claude-failed"  # posée par le workflow quand la correction échoue
CACHE_TTL = 60                  # s : l'admin ouvert ne relit pas GitHub à chaque rafraîchissement


# Causes fréquentes d'un refus, dites en clair dans l'admin.
REFUSALS = {
    401: "jeton GitHub invalide ou expiré : régénère-le et mets-le dans GITHUB_TOKEN",
    403: "le jeton n'a pas le droit d'écrire les issues : donne-lui « Issues : Read and write » sur ce dépôt",
    404: "dépôt introuvable pour ce jeton : vérifie « Repository access » du jeton et GITHUB_REPO",
    410: "les issues sont désactivées sur ce dépôt : active-les dans Settings → Features",
}


class GitHubError(Exception):
    pass


class Issues:
    def __init__(self, token: str, repo: str, client: httpx.Client | None = None):
        self.token, self.repo = token, repo
        self.client = client or httpx.Client(timeout=10)
        self.lock = threading.Lock()
        self.cache: dict[int, tuple[float, dict]] = {}

    @property
    def configured(self) -> bool:
        return bool(self.token and self.repo)

    def _call(self, method: str, path: str, **kw) -> dict:
        if not self.configured:
            raise GitHubError("GITHUB_TOKEN n'est pas configuré sur le serveur")
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}
        try:
            r = self.client.request(method, f"{API}/repos/{self.repo}{path}", headers=headers, **kw)
        except httpx.HTTPError as e:
            raise GitHubError("GitHub ne répond pas, réessaie dans un instant") from e
        if r.status_code >= 300:
            try:
                detail = r.json().get("message", "")
            except ValueError:
                detail = ""
            reason = REFUSALS.get(r.status_code) or detail or "raison inconnue"
            raise GitHubError(f"GitHub a refusé la demande ({r.status_code}) : {reason}")
        return r.json()

    def create(self, title: str, body: str) -> dict:
        issue = self._call("POST", "/issues", json={"title": title, "body": body, "labels": [LABEL]})
        return {"number": issue["number"], "url": issue["html_url"]}

    def state(self, number: int) -> str:
        """« pending » (Claude y travaille), « fixed » (issue fermée) ou « failed » (étiquette d'échec)."""
        now = time.time()
        with self.lock:
            hit = self.cache.get(number)
        if hit and now - hit[0] < CACHE_TTL:
            issue = hit[1]
        else:
            issue = self._call("GET", f"/issues/{number}")
            with self.lock:
                self.cache[number] = (now, issue)
        if issue.get("state") == "closed":
            return "fixed"
        return "failed" if any(lb.get("name") == FAILED_LABEL for lb in issue.get("labels", [])) else "pending"
