import pytest

from app import links


class Cat:
    def __init__(self):
        self.queries = []

    def track(self, tid):
        return {"id": tid, "title": "Exact"}

    def search(self, q, limit=10):
        self.queries.append(q)
        return [{"id": "x" * 22, "title": q}]


class Resp:
    def __init__(self, data=None, status=200, headers=None, text=""):
        self._d, self.status_code, self.headers, self.text = data, status, headers or {}, text

    def json(self):
        return self._d


class Http:
    def __init__(self, routes):
        self.routes = routes

    def get(self, url, params=None, follow_redirects=None):
        for key, resp in self.routes.items():
            if key in url:
                return resp
        raise AssertionError(url)


def test_not_a_link_is_a_normal_search():
    assert links.resolve("daft punk", Cat()) is None


def test_spotify_link_with_tracking_params():
    r = links.resolve("https://open.spotify.com/intl-fr/track/4uLU6hMCjMI75M1A2tKUQC?si=abc", Cat(), Http({}))
    assert r["via"] == "Spotify" and r["tracks"][0]["id"] == "4uLU6hMCjMI75M1A2tKUQC"


def test_deezer_link_uses_isrc():
    cat = Cat()
    r = links.resolve("https://www.deezer.com/fr/track/3135556", cat, Http({"api.deezer.com/track/3135556": Resp({"isrc": "GBDUW0000059", "title": "X"})}))
    assert r["via"] == "Deezer" and cat.queries == ["isrc:GBDUW0000059"]


def test_youtube_title_is_cleaned():
    cat = Cat()
    http = Http({"youtube.com/oembed": Resp({"title": "Daft Punk - One More Time (Official Video) [HD]", "author_name": "Daft Punk"})})
    r = links.resolve("https://youtu.be/FGBhQbmPwH8", cat, http)
    assert r["via"] == "YouTube" and cat.queries == ["Daft Punk One More Time"]


def test_unknown_hosts_are_never_fetched():
    with pytest.raises(links.LinkError):
        links.resolve("http://192.168.50.1/admin", Cat(), Http({}))
