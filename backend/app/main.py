"""FastAPI control plane for the arena.

Serves the game API, live WebSocket event streaming, decision traces, metrics,
and (when built) the static frontend. State is held in memory per process —
a deliberate, documented trade-off documented in the README.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from dataclasses import dataclass, field

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .agents.human_agent import HumanAgent
from .config import settings
from .game.engine import WerewolfEngine
from .game.models import GameEvent, GameState, NightAction, Phase, SpeechAction, VoteAction
from .llm.factory import create_provider
from .observability.metrics import metrics
from .observability.tracing import DecisionTracer

tracer = DecisionTracer()

app = FastAPI(title=settings.app_name, version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins.split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


# ------------------------------------------------------------------ sessions

@dataclass
class GameSession:
    engine: WerewolfEngine
    provider_name: str
    subscribers: set[WebSocket] = field(default_factory=set)
    task: asyncio.Task | None = None


sessions: dict[str, GameSession] = {}


def _has_human(state: GameState) -> bool:
    return any(p.is_human for p in state.players)


def public_state(state: GameState, reveal: bool) -> dict:
    """Serialise state; hide living players' roles unless reveal is allowed."""
    players = []
    for p in state.players:
        show_role = reveal or not p.alive or p.is_human
        players.append(
            {
                "id": p.id,
                "name": p.name,
                "persona": p.persona,
                "alive": p.alive,
                "is_human": p.is_human,
                "role": p.role.value if show_role else None,
            }
        )
    return {
        "id": state.id,
        "round": state.round,
        "phase": state.phase.value,
        "winner": state.winner.value if state.winner else None,
        "pending_human": state.pending_human,
        "players": players,
        "events": [e.model_dump(mode="json") for e in state.events if e.public or reveal],
    }


def _reveal_for(state: GameState) -> bool:
    return not _has_human(state) or state.phase == Phase.GAME_OVER


async def _broadcast(session: GameSession, event: GameEvent, state: GameState) -> None:
    message = json.dumps(
        {
            "type": "event",
            "event": event.model_dump(mode="json"),
            "state": public_state(state, reveal=_reveal_for(state)),
        }
    )
    dead: list[WebSocket] = []
    for ws in list(session.subscribers):
        try:
            await ws.send_text(message)
        except Exception:
            dead.append(ws)
    for ws in dead:
        session.subscribers.discard(ws)


# ------------------------------------------------------------------ requests

class CreateGameRequest(BaseModel):
    num_players: int = Field(default=7, ge=5, le=10)
    human_name: str | None = Field(default=None, max_length=24)
    provider: str | None = None  # mock | ollama | openai (default: configured)
    autoplay: bool = True
    seed: int | None = None


class HumanActionRequest(BaseModel):
    kind: str  # speech | vote | kill | inspect
    statement: str | None = Field(default=None, max_length=1200)
    suspicion: str | None = None
    target: str | None = None
    reason: str = ""


# ------------------------------------------------------------------ endpoints

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/api/config")
def config() -> dict:
    return {
        "provider": settings.llm_provider,
        "ollama_model": settings.ollama_model,
        "openai_model": settings.openai_model,
        "features": [
            "multi-agent-orchestration",
            "episodic-memory-rag",
            "structured-output-guardrails",
            "decision-tracing",
            "elo-evaluation-harness",
        ],
    }


@app.post("/api/games", status_code=201)
def create_game(req: CreateGameRequest) -> dict:
    try:
        provider = create_provider(settings, req.provider, seed=req.seed)
        game_id = uuid.uuid4().hex[:8]
        engine = WerewolfEngine.new_game(
            game_id=game_id,
            provider=provider,
            tracer=tracer,
            settings=settings,
            num_players=req.num_players,
            human_name=req.human_name,
            seed=req.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    session = GameSession(engine=engine, provider_name=provider.name)
    sessions[game_id] = session

    async def on_event(event: GameEvent, state: GameState) -> None:
        await _broadcast(session, event, state)

    engine.on_event = on_event

    if req.autoplay:
        session.task = asyncio.create_task(engine.play())

    return {"id": game_id, "provider": provider.name, "autoplay": req.autoplay}


@app.get("/api/games")
def list_games() -> dict:
    return {
        "games": [
            {
                "id": gid,
                "provider": s.provider_name,
                "phase": s.engine.state.phase.value,
                "round": s.engine.state.round,
                "winner": s.engine.state.winner.value if s.engine.state.winner else None,
                "players": len(s.engine.state.players),
            }
            for gid, s in sessions.items()
        ]
    }


@app.get("/api/games/{game_id}")
def get_game(game_id: str) -> dict:
    session = sessions.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="game not found")
    return public_state(session.engine.state, reveal=_reveal_for(session.engine.state))


@app.post("/api/games/{game_id}/run")
async def run_game(game_id: str) -> dict:
    """Run an AI-only game to completion synchronously (demo + CI helper)."""
    session = sessions.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="game not found")
    if _has_human(session.engine.state):
        raise HTTPException(status_code=400, detail="games with a human seat cannot run synchronously")
    if session.engine.running:
        raise HTTPException(status_code=409, detail="game already running")
    await session.engine.play()
    return public_state(session.engine.state, reveal=True)


@app.post("/api/games/{game_id}/actions")
async def submit_action(game_id: str, req: HumanActionRequest) -> dict:
    session = sessions.get(game_id)
    if not session:
        raise HTTPException(status_code=404, detail="game not found")
    pending = session.engine.state.pending_human
    if pending is None:
        raise HTTPException(status_code=409, detail="no human action is currently expected")

    expected = {"speech": "speech", "vote": "vote", "night_kill": "kill", "night_inspect": "inspect"}[pending]
    if req.kind != expected:
        raise HTTPException(status_code=422, detail=f"expected action kind {expected!r} right now")

    human = next((a for a in session.engine.agents.values() if isinstance(a, HumanAgent)), None)
    if human is None:
        raise HTTPException(status_code=400, detail="game has no human seat")

    if expected == "speech":
        action = SpeechAction(statement=req.statement or "", suspicion=req.suspicion)
    elif expected == "vote":
        action = VoteAction(target=req.target or "abstain", reason=req.reason)
    else:
        action = NightAction(kind=expected, target=req.target or "")

    await human.submit(action)
    return {"accepted": True}


@app.get("/api/games/{game_id}/traces")
def get_traces(game_id: str) -> dict:
    if game_id not in sessions:
        raise HTTPException(status_code=404, detail="game not found")
    return {
        "summary": tracer.summary(game_id),
        "traces": [t.to_dict() for t in tracer.for_game(game_id)],
    }


@app.get("/api/metrics")
def get_metrics() -> dict:
    return metrics.snapshot()


# ------------------------------------------------------------------ websocket

@app.websocket("/ws/games/{game_id}")
async def game_socket(websocket: WebSocket, game_id: str) -> None:
    session = sessions.get(game_id)
    if not session:
        await websocket.close(code=4404)
        return
    await websocket.accept()
    session.subscribers.add(websocket)
    state = session.engine.state
    await websocket.send_text(
        json.dumps({"type": "state", "state": public_state(state, reveal=_reveal_for(state))})
    )
    try:
        while True:
            await websocket.receive_text()  # keepalive; client sends nothing meaningful
    except WebSocketDisconnect:
        session.subscribers.discard(websocket)


# ------------------------------------------------------------------ frontend

_static_dir = os.environ.get("ARENA_STATIC_DIR", settings.static_dir)
if os.path.isdir(_static_dir):
    app.mount("/", StaticFiles(directory=_static_dir, html=True), name="frontend")
