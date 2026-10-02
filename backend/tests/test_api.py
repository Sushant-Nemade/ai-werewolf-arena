from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health():
    assert client.get("/health").json() == {"status": "ok"}


def test_config_lists_features():
    body = client.get("/api/config").json()
    assert "episodic-memory-rag" in body["features"]


def test_create_run_and_inspect_game():
    created = client.post(
        "/api/games", json={"num_players": 7, "autoplay": False, "seed": 11}
    )
    assert created.status_code == 201
    game_id = created.json()["id"]

    state = client.post(f"/api/games/{game_id}/run").json()
    assert state["phase"] == "game_over"
    assert state["winner"] in ("village", "wolves")
    assert all(p["role"] for p in state["players"])  # roles revealed when over

    fetched = client.get(f"/api/games/{game_id}").json()
    assert fetched["id"] == game_id
    assert len(fetched["events"]) > 0

    traces = client.get(f"/api/games/{game_id}/traces").json()
    assert traces["summary"]["decisions"] > 0
    trace = traces["traces"][0]
    for key in ("task", "model", "prompt_hash", "retrieved_memory_ids", "latency_ms", "fail_closed"):
        assert key in trace

    listing = client.get("/api/games").json()
    assert any(g["id"] == game_id for g in listing["games"])


def test_unknown_game_404():
    assert client.get("/api/games/nope").status_code == 404


def test_invalid_player_count_rejected():
    assert client.post("/api/games", json={"num_players": 3}).status_code == 422
