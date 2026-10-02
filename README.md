# AI Werewolf Arena — Multi-Agent LLM Social Deduction

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.11%2B-blue.svg)](backend/pyproject.toml)
[![React](https://img.shields.io/badge/frontend-React%2018%20%2B%20TS-61dafb.svg)](frontend/package.json)

AI Werewolf Arena is a production-oriented playground where **seven autonomous LLM agents play Werewolf** — the classic social-deduction game of hidden roles, deception and debate. Agents kill in secret at night, inspect each other, argue in public, and vote to eliminate suspects. A human can spectate any match or take a seat and try to out-reason the agents.

The game is the surface. Underneath it is a rigorous applied-AI system: multi-agent orchestration with strict information asymmetry, retrieval-augmented episodic memory, fail-closed structured-output guardrails, complete decision tracing, and a batch evaluation harness with ELO ratings.

## Why this project exists

Most LLM demos show one prompt producing one answer. Real systems are loops: agents with private knowledge, memory, adversarial incentives and invalid outputs that must be contained. Werewolf is a compact, fully observable environment that exercises exactly those properties — which makes it an honest benchmark for agent engineering rather than a toy.

## System Architecture

```text
                 ┌───────────────────────────────────────────┐
                 │         React + TypeScript frontend        │
                 │  lobby · live village feed · player seats  │
                 │  decision inspector (traces, latencies)    │
                 └───────────────┬───────────────────────────┘
                        REST /api│· WS /ws (live events)
                 ┌───────────────┴───────────────────────────┐
                 │              FastAPI control plane         │
                 │  game sessions · human actions · metrics   │
                 └───────────────┬───────────────────────────┘
                                 │
                 ┌───────────────▼───────────────────────────┐
                 │        WerewolfEngine (async state machine)│
                 │  NIGHT → DISCUSSION → VOTE → GAME_OVER     │
                 │  enforces information asymmetry per seat   │
                 └───┬───────────────┬───────────────┬───────┘
                     │ per decision  │ per event     │ per decision
                     ▼               ▼               ▼
           ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐
           │    Agents    │ │   Episodic   │ │    Guardrails     │
           │  perceive →  │ │    Memory    │ │  extract → schema │
           │  remember →  │ │  (TF-IDF     │ │  validate → retry │
           │  reason → act│ │  retrieval)  │ │  → fail closed    │
           └──────┬───────┘ └──────────────┘ └────────┬─────────┘
                  │ provider abstraction               │ every attempt
                  ▼                                    ▼
        ┌────────────────────┐              ┌────────────────────┐
        │ mock · Ollama ·    │              │  DecisionTracer +  │
        │ OpenAI-compatible  │              │  metrics registry  │
        └────────────────────┘              └────────────────────┘

   Batch path: evaluation/simulate.py runs N headless games → ELO table,
   role win-rates, guardrail statistics → JSON report.
```

## Game rules implemented

- 5–10 players. Default 7: **2 Werewolves**, **1 Seer**, **4 Villagers** (9+ players adds a third wolf).
- **Night:** wolves secretly agree on a kill; the seer secretly inspects one player and learns their true role.
- **Day:** every living player speaks once (with optional accusation), then all players vote; a strict plurality is eliminated, ties eliminate nobody.
- **Information asymmetry is enforced at the view layer:** agents only ever see public events plus their own private knowledge (role, teammates, inspection results). Roles of the dead are revealed publicly.
- **Win:** the village wins when all wolves are dead; wolves win when they equal or outnumber the villagers.

## Repository Layout

```text
backend/
  app/
    game/         engine (async state machine), domain models, prompt builder
    agents/       Agent protocol, LLM agent, human seat, persona registry
    llm/          provider protocol: mock (offline/CI) · Ollama · OpenAI-compatible
    memory/       episodic memory with TF-IDF retrieval (RAG loop)
    guardrails/   structured-output validation with retries + safety filters
    observability/  decision tracing + in-process metrics registry
    evaluation/   batch simulator, ELO ratings, aggregate reporting
    main.py       FastAPI control plane, WebSocket streaming, static hosting
  tests/          27 deterministic tests — no API keys required
frontend/         React 18 + TypeScript + Vite single-page app
Dockerfile        multi-stage: frontend build → non-root Python runtime serving API+UI
docker-compose.yml         app (+ optional local Ollama profile)
```

## Quickstart

### Fully offline (no API keys, deterministic mock agents)

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173 (proxies API + WS to :8000)
```

### With a real local model via Ollama

```bash
ollama pull llama3.1:8b
export ARENA_LLM_PROVIDER=ollama
cd backend && uvicorn app.main:app --reload
```

### One command with Docker (UI + API on :8000)

```bash
docker compose up --build          # mock provider
docker compose --profile local-llm up --build   # app + Ollama sidecar
```

### Run the evaluation harness

```bash
cd backend
python -m app.evaluation.simulate --games 20 --provider mock --seed 7
```

Example output:

```text
=== Simulation report (mock, 8 games) ===
village win rate : 0.125
avg rounds       : 2.25
decisions        : 189 (fail-closed rate 0.0)
role win rates   : {'seer': 0.125, 'villager': 0.125, 'werewolf': 0.875}

ELO leaderboard:
   1216.9  mock/Cleo                    4/7 wins
   1215.6  mock/Hank                    5/8 wins
   ...
```

## API Contract

| Endpoint | Description |
|---|---|
| `POST /api/games` | Create a game (`num_players`, optional `human_name`, `provider`, `seed`, `autoplay`) |
| `POST /api/games/{id}/run` | Run an AI-only game to completion synchronously (demo/CI helper) |
| `GET /api/games/{id}` | Current state; roles hidden while a human seat is alive |
| `POST /api/games/{id}/actions` | Submit the human seat's speech / vote / night action |
| `WS /ws/games/{id}` | Live event stream with embedded state snapshots |
| `GET /api/games/{id}/traces` | Per-decision traces + aggregate summary |
| `GET /api/metrics` | Process-wide counters and latency stats |
| `GET /health` | Liveness |

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ARENA_LLM_PROVIDER` | `mock` | `mock` · `ollama` · `openai` |
| `ARENA_OLLAMA_BASE_URL` / `ARENA_OLLAMA_MODEL` | `http://localhost:11434` / `llama3.1:8b` | local inference |
| `ARENA_OPENAI_BASE_URL` / `ARENA_OPENAI_API_KEY` / `ARENA_OPENAI_MODEL` | — | any OpenAI-compatible endpoint (secret via env only) |
| `ARENA_GUARDRAIL_MAX_RETRIES` | `2` | bounded retry budget per decision |
| `ARENA_MEMORY_TOP_K` | `5` | retrieved memories injected per decision |
| `ARENA_MAX_ROUNDS` | `20` | game-length safety bound |
| `ARENA_HUMAN_ACTION_TIMEOUT_SECONDS` | `600` | fail-safe timeout for the human seat |

## Advanced AI Engineering Patterns Implemented

### 1. Multi-agent orchestration under information asymmetry

Each seat runs the same perceive → remember → reason → act loop, but receives a **player view**, not the game state. The engine is the only component that knows all roles; agents' prompts are built exclusively from public events plus their own private knowledge. This mirrors real agent systems where a broker enforces data boundaries between tools and tenants.

### 2. Episodic memory as a RAG loop

Every game event is written into each agent's memory at emission time (private events only reach their recipients). Before every decision, the agent retrieves the top-k most relevant items via TF-IDF cosine similarity and injects them into the prompt. The retrieval boundary (`EpisodicMemory`) is deliberately swappable for an embedding model + vector store without touching the agent loop.

### 3. Fail-closed structured-output guardrails

LLM output is treated as untrusted: JSON is extracted from prose/markdown, validated against Pydantic schemas *and* a domain validator (e.g. "vote target must be a living candidate"), and retried with the validation error fed back to the model. When the retry budget is exhausted, the system **fails closed** to a safe default (pass / abstain / first legal candidate) and records the failure — invalid model behaviour can never corrupt game state.

### 4. Decision tracing and observability

Every decision produces a trace: prompt hash, retrieved memory ids, raw output, parsed output, guardrail attempts, token usage and latency. The frontend's decision inspector renders these live, and the evaluation harness aggregates them into fail-closed rates and latency profiles — the same audit trail you would want around any production agent.

### 5. Evaluation harness with ELO ratings

`evaluation/simulate.py` runs N headless games with bounded concurrency and produces role win-rates, guardrail statistics and an ELO leaderboard keyed by `provider/persona`. The same harness compares personas, prompt variants or models (e.g. `llama3.1:8b` vs `gpt-4o-mini`) on an equal footing.

### 6. Deterministic offline provider for CI

The `mock` provider parses the machine-readable prompt header and plays simple heuristics (wolves don't accuse teammates, the seer votes known wolves). It makes the entire system — engine, guardrails, memory, tracing, API — testable with **zero network access and zero API keys**, and gives the evaluation harness a reproducible baseline.

### 7. Responsible-AI boundary

Agent utterances pass through a safety layer (bounded length, blocklist redaction) before entering the public record. Agents can only produce game actions — there is no tool surface for prompt injection to reach. Secrets arrive exclusively via environment variables; the default path needs none.

## Engineering Trade-offs

- **TF-IDF retrieval instead of embeddings.** Keeps the arena self-contained, deterministic and fast in CI. The `EpisodicMemory` interface is the documented swap point for a real vector store.
- **In-memory session state.** Games are ephemeral by design; a production deployment would persist `GameState` (already a pure Pydantic model) in Redis/Postgres and move traces to a proper observability backend.
- **Single round of discussion per day.** Keeps games short and watchable; the engine's phase loop generalises to multi-round debates.
- **The mock provider is a heuristic baseline, not a benchmark of reasoning.** Meaningful agent-quality numbers require a real model (`ollama` / `openai` providers) and larger simulation batches.
- **The safety blocklist is a screening signal, not a moderation system.** Production use should route utterances through a dedicated content-safety endpoint.

## Testing & CI

```bash
cd backend && pip install -r requirements-dev.txt && python -m pytest
```

27 deterministic tests cover the engine (setup, win conditions, full games, determinism per seed, memory fan-out), guardrails (extraction, retries, fail-closed, domain validation, safety), memory retrieval, ELO mechanics, the simulation harness, and the HTTP API.

## License

MIT — see [LICENSE](LICENSE).
