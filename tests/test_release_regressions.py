"""Régressions de la salle et de la persistance avant fusion en production."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from app import games, main
from app.party import PartyStore


def test_parallel_session_saves_are_serialized_and_valid(tmp_path):
    store = PartyStore(tmp_path / "session.json")
    initial_version = store.version
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(lambda _: store.save(), range(80)))
    assert store.version == initial_version + 80
    assert json.loads(store.path.read_text())["guest_pin"] == store.session.guest_pin


def test_ios_installed_app_page_height_follows_the_physical_screen():
    """Barre d'onglets iPhone (app installée, iOS 26) : la page doit dépasser l'écran PHYSIQUE (screen.height),
    pas 100vh / 100lvh qui suivent la hauteur erronée d'iOS. Vérifié en vrai navigateur par
    tests/e2e/test_ios_tab_bar.py ; ici, le câblage des deux pages installables."""
    static = Path(main.__file__).parent / "static"
    css = (static / "style.css").read_text(encoding="utf-8")
    assert "html.ios-app body { min-height: calc(var(--ios-screen-h, 100lvh) + 1px); }" in css
    for page in ("index.html", "admin.html"):
        html = (static / page).read_text(encoding="utf-8")
        head = html[:html.index("</head>")]
        assert head.index("/static/ios-app.js") < head.index("/static/style.css"), page  # avant tout affichage
    js = (static / "ios-app.js").read_text(encoding="utf-8")
    assert "screen.height" in js and "navigator.standalone" in js


def test_manual_identity_scores_and_removal_survive_child_games(monkeypatch, tmp_path):
    store = PartyStore(tmp_path / "session.json")
    monkeypatch.setattr(main, "store", store)
    room = games.new_game("room", host="host-release1", name="Hôte", code="6743")
    manual = games.add_guest(room, "Mamie")
    store.session.games[room["code"]] = room
    main.room_launch(room, "host-release1", {"type": "never"})
    first = main.room_child(room)
    assert games.player(first, manual["id"])["manual"]
    first.setdefault("tally", {})[manual["id"]] = {"drink": 2, "give": 1}
    games.room_merge(room, first)
    main.room_launch(room, "host-release1", {"type": "never"})
    second = main.room_child(room)
    assert games.player(second, manual["id"])["manual"]
    second.setdefault("tally", {})[manual["id"]] = {"drink": 3, "give": 0}
    games.room_merge(room, second)
    board = games.room_view(room, "host-release1", None)["board"]
    assert [row["drink"] for row in board if row["name"] == "Mamie"] == [5]
    main.room_launch(room, "host-release1", {"type": "never"})
    client = TestClient(main.app)
    response = client.post(f"/api/games/{room['code']}", json={
        "guest_id": "host-release1", "action": "remove", "target": manual["pid"],
    })
    assert response.status_code == 200
    assert games.player(main.room_child(room), manual["id"]) is None


def test_manual_added_during_child_game_has_same_identity(monkeypatch, tmp_path):
    store = PartyStore(tmp_path / "session.json")
    monkeypatch.setattr(main, "store", store)
    room = games.new_game("room", host="host-release2", name="Hôte", code="6744")
    store.session.games[room["code"]] = room
    main.room_launch(room, "host-release2", {"type": "never"})
    response = TestClient(main.app).post(f"/api/games/{room['code']}", json={
        "guest_id": "host-release2", "action": "addguest", "guess": "Mamie",
    })
    assert response.status_code == 200
    manual = next(p for p in room["players"] if p.get("manual"))
    assert games.player(main.room_child(room), manual["id"])["manual"]
