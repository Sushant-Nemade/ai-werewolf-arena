"""Werewolf game engine — an explicit async state machine.

Phases per round: NIGHT -> DAY_DISCUSSION -> DAY_VOTE -> (repeat) -> GAME_OVER.

The engine owns game rules and information asymmetry. It never talks to an LLM
directly: all cognition is delegated to agents behind the ``Agent`` protocol,
and every public/private event is fanned out to agent memories at emission time.
"""

from __future__ import annotations

import random
from collections import Counter
from typing import Awaitable, Callable

from ..agents.base import Agent
from ..agents.human_agent import HumanAgent
from ..agents.llm_agent import LLMAgent
from ..agents.personas import PERSONAS
from ..config import Settings
from ..llm.base import LLMProvider
from ..memory.store import EpisodicMemory, MemoryItem
from ..observability.metrics import metrics
from ..observability.tracing import DecisionTracer
from .models import GameEvent, GameState, Phase, Player, PlayerView, Role, Team

OnEvent = Callable[[GameEvent, GameState], Awaitable[None]]


def role_composition(num_players: int) -> list[Role]:
    wolves = 3 if num_players >= 9 else 2
    return [Role.WEREWOLF] * wolves + [Role.SEER] + [Role.VILLAGER] * (num_players - wolves - 1)


class WerewolfEngine:
    def __init__(
        self,
        state: GameState,
        agents: dict[str, Agent],
        memories: dict[str, EpisodicMemory],
        tracer: DecisionTracer,
        settings: Settings,
        provider_name: str = "mock",
    ) -> None:
        self.state = state
        self.agents = agents
        self.memories = memories
        self.tracer = tracer
        self.settings = settings
        self.provider_name = provider_name
        self.on_event: OnEvent | None = None
        self.inspections: list[dict] = []
        self.running = False
        self._event_seq = 0

    # ------------------------------------------------------------ construction

    @classmethod
    def new_game(
        cls,
        *,
        game_id: str,
        provider: LLMProvider,
        tracer: DecisionTracer,
        settings: Settings,
        num_players: int = 7,
        human_name: str | None = None,
        seed: int | None = None,
    ) -> "WerewolfEngine":
        if not 5 <= num_players <= len(PERSONAS):
            raise ValueError(f"num_players must be between 5 and {len(PERSONAS)}")

        rng = random.Random(seed)
        roles = role_composition(num_players)
        rng.shuffle(roles)
        personas = rng.sample(PERSONAS, num_players)

        players: list[Player] = []
        agents: dict[str, Agent] = {}
        memories: dict[str, EpisodicMemory] = {}

        for i in range(num_players):
            pid = f"p{i + 1}"
            is_human = human_name is not None and i == 0
            player = Player(
                id=pid,
                name=human_name if is_human else personas[i].name,
                role=roles[i],
                persona="human player" if is_human else personas[i].style,
                is_human=is_human,
            )
            players.append(player)
            memories[pid] = EpisodicMemory()
            if is_human:
                agents[pid] = HumanAgent(player, timeout_seconds=settings.human_action_timeout_seconds)
            else:
                agents[pid] = LLMAgent(player, provider, memories[pid], tracer, settings, game_id)

        state = GameState(id=game_id, players=players)
        return cls(state, agents, memories, tracer, settings, provider_name=provider.name)

    # ------------------------------------------------------------- event fanout

    async def _emit(
        self,
        type: str,
        content: str,
        *,
        actor: str | None = None,
        public: bool = True,
        metadata: dict | None = None,
        memory_for: list[str] | None = None,
    ) -> GameEvent:
        self._event_seq += 1
        event = GameEvent(
            id=self._event_seq,
            round=self.state.round,
            phase=self.state.phase,
            type=type,
            actor=actor,
            content=content,
            public=public,
            metadata=metadata or {},
        )
        self.state.events.append(event)

        recipients = memory_for if memory_for is not None else (list(self.memories) if public else [])
        for pid in recipients:
            self.memories[pid].add(
                MemoryItem(
                    id=f"{self.state.id}-e{event.id}",
                    round=event.round,
                    kind=event.type,
                    text=f"[r{event.round} {event.phase.value}] {content}",
                )
            )

        if self.on_event is not None:
            await self.on_event(event, self.state)
        return event

    # -------------------------------------------------------------- viewpoints

    def _view_for(self, player: Player) -> PlayerView:
        notes = [f"You are {player.name} ({player.id}). Your secret role is {player.role.value}."]
        if player.role == Role.WEREWOLF:
            teammates = [w for w in self.state.alive_wolves() if w.id != player.id]
            notes.append(
                "WOLF TEAMMATES: "
                + (", ".join(f"{w.id}={w.name}" for w in teammates) if teammates else "none — you are the last wolf")
            )
        inspections = [i for i in self.inspections if i["seer"] == player.id]
        recent = [e for e in self.state.events if e.public][-12:]
        return PlayerView(
            me=player,
            round=self.state.round,
            phase=self.state.phase,
            alive=[{"id": p.id, "name": p.name} for p in self.state.alive_players()],
            recent_events=recent,
            private_notes=notes,
            inspections=inspections,
        )

    async def _maybe_await_human(self, player: Player, pending: str | None) -> None:
        self.state.pending_human = pending if player.is_human else None

    # ------------------------------------------------------------------ phases

    async def _night(self) -> None:
        self.state.phase = Phase.NIGHT
        await self._emit("system", f"Night {self.state.round} falls. The village sleeps.")

        wolves = self.state.alive_wolves()
        villagers = self.state.alive_villagers()

        kill_target: str | None = None
        if wolves and villagers:
            candidate_ids = [p.id for p in villagers]
            proposals: list[str] = []
            for wolf in wolves:
                await self._maybe_await_human(wolf, "night_kill")
                try:
                    action = await self.agents[wolf.id].night_action(
                        self._view_for(wolf), "kill", candidate_ids
                    )
                    if action.target in candidate_ids:
                        proposals.append(action.target)
                finally:
                    await self._maybe_await_human(wolf, None)
            if proposals:
                kill_target = Counter(proposals).most_common(1)[0][0]

        # Seer investigations resolve before deaths are applied.
        seer_results: list[tuple[Player, Player]] = []
        for seer in [p for p in self.state.alive_players() if p.role == Role.SEER]:
            seen = {i["target"] for i in self.inspections if i["seer"] == seer.id}
            candidates = [p for p in self.state.alive_players() if p.id != seer.id and p.id not in seen]
            if not candidates:
                continue
            await self._maybe_await_human(seer, "night_inspect")
            try:
                action = await self.agents[seer.id].night_action(
                    self._view_for(seer), "inspect", [p.id for p in candidates]
                )
            finally:
                await self._maybe_await_human(seer, None)
            target = self.state.player(action.target)
            self.inspections.append(
                {
                    "seer": seer.id,
                    "target": target.id,
                    "target_name": target.name,
                    "role": target.role.value,
                    "round": self.state.round,
                }
            )
            seer_results.append((seer, target))

        if kill_target:
            victim = self.state.player(kill_target)
            victim.alive = False
            await self._emit(
                "kill",
                f"{victim.name} was found dead at dawn. They were a {victim.role.value}.",
                metadata={"victim": victim.id, "role": victim.role.value},
            )
        else:
            await self._emit("system", "Dawn breaks. Miraculously, nobody was killed.")

        for seer, target in seer_results:
            await self._emit(
                "inspect",
                f"You inspected {target.name}: they are a {target.role.value}.",
                actor=seer.id,
                public=False,
                memory_for=[seer.id],
                metadata={"target": target.id, "role": target.role.value},
            )

    async def _discussion(self) -> None:
        self.state.phase = Phase.DAY_DISCUSSION
        await self._emit("system", "The village gathers to discuss the night's events.")

        alive = self.state.alive_players()
        offset = self.state.round % len(alive)
        order = alive[offset:] + alive[:offset]

        for player in order:
            if not player.alive:
                continue
            candidates = [p.id for p in self.state.alive_players() if p.id != player.id]
            await self._maybe_await_human(player, "speech")
            try:
                action = await self.agents[player.id].speak(self._view_for(player), candidates)
            finally:
                await self._maybe_await_human(player, None)
            content = action.statement
            if action.suspicion:
                try:
                    content += f" (suspects {self.state.player(action.suspicion).name})"
                except KeyError:
                    pass
            await self._emit("speech", content, actor=player.id, metadata={"suspicion": action.suspicion})

    async def _vote(self) -> None:
        self.state.phase = Phase.DAY_VOTE
        await self._emit("system", "The village votes.")

        votes: dict[str, str] = {}
        alive_ids = {p.id for p in self.state.alive_players()}
        for player in self.state.alive_players():
            candidates = [p.id for p in self.state.alive_players() if p.id != player.id]
            await self._maybe_await_human(player, "vote")
            try:
                action = await self.agents[player.id].vote(self._view_for(player), candidates)
            finally:
                await self._maybe_await_human(player, None)
            if action.target in alive_ids and action.target != player.id:
                votes[player.id] = action.target
                await self._emit(
                    "vote",
                    f"{player.name} votes to eliminate {self.state.player(action.target).name}.",
                    actor=player.id,
                    metadata={"target": action.target},
                )
            else:
                await self._emit("vote", f"{player.name} abstains.", actor=player.id, metadata={"target": None})

        tally = Counter(votes.values())
        if not tally:
            await self._emit("system", "Everyone abstained. Nobody is eliminated.")
            return
        top = tally.most_common()
        if len(top) > 1 and top[0][1] == top[1][1]:
            await self._emit("system", "The vote is tied. Nobody is eliminated.")
            return

        eliminated = self.state.player(top[0][0])
        eliminated.alive = False
        await self._emit(
            "elimination",
            f"{eliminated.name} is eliminated by the village. They were a {eliminated.role.value}.",
            metadata={"eliminated": eliminated.id, "role": eliminated.role.value},
        )

    # --------------------------------------------------------------- game loop

    def _check_win(self) -> bool:
        wolves = len(self.state.alive_wolves())
        villagers = len(self.state.alive_villagers())
        if wolves == 0:
            self.state.winner = Team.VILLAGE
        elif wolves >= villagers:
            self.state.winner = Team.WOLVES
        return self.state.winner is not None

    async def play(self) -> GameState:
        if self.running or self.state.phase == Phase.GAME_OVER:
            return self.state
        self.running = True
        try:
            metrics.inc("games.started")
            await self._emit(
                "system",
                "A new game begins. "
                + ", ".join(p.name for p in self.state.players)
                + " take their seats. Roles are dealt in secret.",
            )
            while not self._check_win() and self.state.round < self.settings.max_rounds:
                self.state.round += 1
                await self._night()
                if self._check_win():
                    break
                await self._discussion()
                await self._vote()
                if self._check_win():
                    break

            if self.state.winner is None:  # round limit reached
                self.state.winner = Team.WOLVES if self.state.alive_wolves() else Team.VILLAGE

            self.state.phase = Phase.GAME_OVER
            self.state.pending_human = None
            metrics.inc("games.completed")
            metrics.inc(f"games.won.{self.state.winner.value}")
            survivors = ", ".join(p.name for p in self.state.alive_players())
            await self._emit(
                "win",
                f"Game over. The {self.state.winner.value} win. Survivors: {survivors or 'none'}.",
                metadata={"winner": self.state.winner.value},
            )
            return self.state
        finally:
            self.running = False

    # ----------------------------------------------------------------- results

    def agent_label(self, player: Player) -> str:
        return f"human/{player.name}" if player.is_human else f"{self.provider_name}/{player.name}"

    def build_result(self) -> dict:
        summary = self.tracer.summary(self.state.id)
        return {
            "game_id": self.state.id,
            "winner": self.state.winner.value if self.state.winner else None,
            "rounds": self.state.round,
            "players": [
                {
                    "id": p.id,
                    "name": p.name,
                    "role": p.role.value,
                    "label": self.agent_label(p),
                    "alive": p.alive,
                }
                for p in self.state.players
            ],
            "decisions": summary["decisions"],
            "fail_closed": summary.get("fail_closed", 0),
            "avg_latency_ms": summary.get("avg_latency_ms", 0.0),
        }
