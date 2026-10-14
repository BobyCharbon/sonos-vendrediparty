from fastapi.testclient import TestClient

from app.main import app


def test_qr_is_standalone_svg():
    r = TestClient(app).get("/qr.svg")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("image/svg+xml")
    assert b'xmlns="http://www.w3.org/2000/svg"' in r.content
