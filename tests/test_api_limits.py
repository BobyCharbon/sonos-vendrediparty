"""Bornes de l'API publique (audit du 14.11) : liste des invités (/api/presence), flux en direct (/api/events),
pochettes relayées par le Sonos (/art). Une vraie soirée (~60 invités sur le même Wi-Fi, donc souvent la même
adresse) n'est jamais refusée."""
import asyncio
import socket
import threading
import time

import httpx
import pytest
import uvicorn
from fastapi.testclient import TestClient

from app import main, party

PARTY_IP, ATTACKER_IP = "10.0.0.2", "203.0.113.9"


@pytest.fixture
def no_guests():
    main.store.session.guests.clear()
    yield
    main.store.session.guests.clear()


def presence(ip: str, guest_id: str, name: str):
    r = TestClient(main.app, client=(ip, 50000)).post("/api/presence", json={"guest_id": guest_id, "name": name})
    assert r.status_code == 200


def test_presence_flood_never_pushes_out_a_real_guest(no_guests):
    for i in range(60):  # la soirée : 60 invités derrière la même box
        presence(PARTY_IP, f"vrai-invite-{i:03}", f"Invité {i}")
    for i in range(400):  # 400 faux invités envoyés depuis une autre adresse
        presence(ATTACKER_IP, f"faux-invite-{i:03}", "Spam")
    guests = main.store.session.guests
    assert all(f"vrai-invite-{i:03}" in guests for i in range(60))
    assert sum(gid.startswith("faux-") for gid in guests) <= party.GUESTS_PER_IP
    presence(PARTY_IP, "retardataire-01", "Zoé")  # un invité de plus arrive : jamais refusé
    assert "retardataire-01" in guests and len(guests) <= party.GUESTS_MAX


def test_presence_full_list_makes_room_for_a_new_real_guest(no_guests):
    for n in range(party.GUESTS_MAX):  # liste pleine, venue de nombreuses adresses
        presence(f"198.51.{n // 100}.{n % 100}", f"faux-invite-{n:03}", "Spam")
    presence(PARTY_IP, "vrai-invite-01", "Léa")
    assert "vrai-invite-01" in main.store.session.guests
    assert len(main.store.session.guests) <= party.GUESTS_MAX
    # Une personne entrée avec le code de la soirée n'est jamais retirée pour faire de la place.
    main.store.register_guest("musique-0001", "Max", PARTY_IP)
    for n in range(party.GUESTS_MAX):
        presence(f"192.0.{n // 100}.{n % 100}", f"autre-faux-{n:03}", "Spam")
    assert "musique-0001" in main.store.session.guests


def test_art_only_relays_covers_given_by_the_server(monkeypatch):
    fetched = []

    class Sonos:
        status_code, content, headers = 200, b"jpg", {"content-type": "image/jpeg"}

        def raise_for_status(self):
            pass

    monkeypatch.setattr(main.httpx, "get", lambda url, **kw: fetched.append(url) or Sonos())
    monkeypatch.setattr(main.store.session, "room_uid", "RINCON_TEST")
    monkeypatch.setattr(main, "_snap", {"data": {"coordinator_ip": "192.168.1.20"}})
    admin = TestClient(main.app)
    assert admin.post("/api/admin/login", json={"pin": "9999"}).status_code == 200
    # Pochette lue dans l'état du Sonos : la page la reçoit et /art la relaie.
    real = "http://192.168.1.20:1400/getaa?s=1&u=x-sonos-spotify%3aspotify%253atrack%253a1%3fsid%3d12"
    url = main.art_url(real)
    assert admin.get(url).status_code == 200
    assert fetched == ["http://192.168.1.20:1400/getaa?s=1&u=x-sonos-spotify%3aspotify%253atrack%253a1%3fsid%3d12"]
    # Une adresse inventée : l'enceinte n'irait pas la chercher sur le réseau local.
    for p in ("/getaa?s=1&u=http://192.168.1.1/admin", "/getaa?s=1&u=x-file-cifs://192.168.1.5/c$/x.jpg"):
        assert admin.get("/art", params={"p": p}).status_code == 404
    assert len(fetched) == 1


@pytest.fixture
def live_server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(main.app, host="127.0.0.1", port=port, lifespan="off", log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 20
    while not server.started:
        assert time.monotonic() < deadline, "le serveur de test ne démarre pas"
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(10)


def test_sse_streams_are_bounded_by_closing_the_oldest(live_server, monkeypatch):
    monkeypatch.setattr(main, "SSE_PER_IP", 3)

    async def scenario():
        async with httpx.AsyncClient(base_url=live_server, timeout=10) as client:
            async def open_stream():
                cm = client.stream("GET", "/api/events")
                r = await cm.__aenter__()
                assert r.status_code == 200  # jamais refusé
                lines = r.aiter_lines()
                assert (await anext(lines)).startswith("event: notice")
                return cm, lines

            streams = [await open_stream() for _ in range(3)]
            assert len(main.SSE_STREAMS) == 3
            streams.append(await open_stream())  # un onglet rouvert : accepté, le plus ancien flux se ferme
            rest = [line async for line in streams[0][1]]  # se termine au lieu d'attendre indéfiniment
            assert all(line.startswith(("data:", "event:", ":")) or not line for line in rest)
            await asyncio.sleep(0.5)
            assert len(main.SSE_STREAMS) == 3
            for cm, _ in streams:
                await cm.__aexit__(None, None, None)

    asyncio.run(asyncio.wait_for(scenario(), 20))


def test_sse_full_server_closes_a_stream_of_the_busiest_address(monkeypatch):
    monkeypatch.setattr(main, "SSE_MAX", 5)
    monkeypatch.setattr(main, "SSE_STREAMS", {})
    opened = [main.sse_open(ip) for ip in ("6.6.6.6",) * 4 + (PARTY_IP,)]
    main.sse_open("10.0.0.3")  # une nouvelle page, serveur plein : acceptée
    assert opened[0][1].is_set()  # le plus ancien flux de l'adresse qui en tient le plus
    assert not any(stop.is_set() for _, stop in opened[1:])
    assert len(main.SSE_STREAMS) == 5
