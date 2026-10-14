from fastapi.testclient import TestClient

from app.main import app


def test_qr_is_standalone_svg():
    client = TestClient(app)
    client.post("/api/admin/login", json={"pin": "9999"})
    r = client.get("/qr.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert b'xmlns="http://www.w3.org/2000/svg"' in r.content


def test_pages_are_not_cached():
    client = TestClient(app)
    for path in ["/", "/admin", "/static/style.css"]:
        assert client.get(path).headers["cache-control"] == "no-cache"


def test_home_screen_names():
    client = TestClient(app)
    assert client.get("/static/manifest.json").json()["name"] == "Party !"
    admin = client.get("/static/manifest-admin.json").json()
    assert admin["start_url"] == "/admin"
    assert 'content="Party !"' in client.get("/").text
