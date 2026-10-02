import asyncio

from app.game.engine import WerewolfEngine, role_composition
from app.game.models import Phase, Role, Team
from app.llm.mock import DeterministicMockLLM
from app.observability.tracing import DecisionTracer

from .conftest import make_settings


def make_engine(seed: int = 1, num_players: int = 7) -> WerewolfEngine:
    settings = make_settings()
    return WerewolfEngine.new_game(
        game_id=f"test-{seed}",
        provider=DeterministicMockLLM(seed=seed),
        tracer=DecisionTracer(),
        settings=settings,
        num_players=num_players,
        seed=seed,
    )


def test_role_composition_default():
    roles = role_composition(7)
    assert roles.count(Role.WEREWOLF) == 2
    assert roles.count(Role.SEER) == 1
    assert roles.count(Role.VILLAGER) == 4


def test_role_composition_large_game():
    assert role_composition(9).count(Role.WEREWOLF) == 3


def test_new_game_setup():
    engine = make_engine()
    assert len(engine.state.players) == 7
    assert len({p.id for p in engine.state.players}) == 7
    assert len(engine.agents) == 7
    assert len(engine.memories) == 7


def test_full_game_completes_with_mock():
    engine = make_engine(seed=3)
    state = asyncio.run(engine.play())

    assert state.phase == Phase.GAME_OVER
    assert state.winner in (Team.VILLAGE, Team.WOLVES)
    assert 1 <= state.round <= 20

    types = {e.type for e in state.events}
    assert {"kill", "speech", "vote", "win"} <= types

    # information asymmetry: seer inspections never become public events
    assert all(e.type != "inspect" or not e.public for e in state.events)

    # public events were written into every agent's episodic memory
    public_count = sum(1 for e in state.events if e.public)
    for memory in engine.memories.values():
        assert len(memory) >= 1
    assert any(len(m) >= public_count for m in engine.memories.values())


def test_games_are_deterministic_per_seed():
    a = asyncio.run(make_engine(seed=42).play())
    b = asyncio.run(make_engine(seed=42).play())
    assert a.winner == b.winner
    assert a.round == b.round
    assert [e.content for e in a.events] == [e.content for e in b.events]


def test_win_condition_village():
    engine = make_engine()
    for wolf in engine.state.alive_wolves():
        wolf.alive = False
    assert engine._check_win()
    assert engine.state.winner == Team.VILLAGE


def test_win_condition_wolves():
    engine = make_engine()
    wolves = len(engine.state.alive_wolves())
    villagers = engine.state.alive_villagers()
    for villager in villagers[wolves:]:  # leave exactly as many villagers as wolves
        villager.alive = False
    assert engine._check_win()
    assert engine.state.winner == Team.WOLVES
