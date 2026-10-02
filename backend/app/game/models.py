"""Domain model for the Werewolf arena.

The game state is a pure Pydantic model: serialisable, auditable, and easy to
persist later (the in-memory store is a deliberate, documented trade-off).
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, Field


class Role(str, enum.Enum):
    WEREWOLF = "werewolf"
    SEER = "seer"
    VILLAGER = "villager"


class Team(str, enum.Enum):
    VILLAGE = "village"
    WOLVES = "wolves"


ROLE_TEAM: dict[Role, Team] = {
    Role.WEREWOLF: Team.WOLVES,
    Role.SEER: Team.VILLAGE,
    Role.VILLAGER: Team.VILLAGE,
}


class Phase(str, enum.Enum):
    SETUP = "setup"
    NIGHT = "night"
    DAY_DISCUSSION = "day_discussion"
    DAY_VOTE = "day_vote"
    GAME_OVER = "game_over"


class Player(BaseModel):
    id: str
    name: str
    role: Role
    persona: str
    is_human: bool = False
    alive: bool = True

    @property
    def team(self) -> Team:
        return ROLE_TEAM[self.role]


class SpeechAction(BaseModel):
    kind: str = "speech"
    statement: str
    suspicion: str | None = None  # player id, or None


class VoteAction(BaseModel):
    kind: str = "vote"
    target: str  # player id, or "abstain"
    reason: str = ""


class NightAction(BaseModel):
    kind: str  # "kill" | "inspect"
    target: str  # player id


class GameEvent(BaseModel):
    id: int
    round: int
    phase: Phase
    type: str  # system | speech | vote | kill | inspect | elimination | win
    actor: str | None = None
    content: str
    public: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class PlayerView(BaseModel):
    """Everything one player is allowed to see when making a decision.

    Enforcing information asymmetry at this boundary is what prevents hidden
    knowledge (roles, seer results) from leaking into other agents' prompts.
    """

    me: Player
    round: int
    phase: Phase
    alive: list[dict[str, str]]  # [{"id": ..., "name": ...}]
    recent_events: list[GameEvent] = Field(default_factory=list)
    private_notes: list[str] = Field(default_factory=list)
    inspections: list[dict[str, Any]] = Field(default_factory=list)  # seer only


class GameState(BaseModel):
    id: str
    round: int = 0
    phase: Phase = Phase.SETUP
    players: list[Player]
    events: list[GameEvent] = Field(default_factory=list)
    winner: Team | None = None
    # Which action kind the human seat must provide, if any:
    # "speech" | "vote" | "night_kill" | "night_inspect" | None
    pending_human: str | None = None

    def alive_players(self) -> list[Player]:
        return [p for p in self.players if p.alive]

    def alive_wolves(self) -> list[Player]:
        return [p for p in self.alive_players() if p.role == Role.WEREWOLF]

    def alive_villagers(self) -> list[Player]:
        return [p for p in self.alive_players() if p.role != Role.WEREWOLF]

    def player(self, player_id: str) -> Player:
        for p in self.players:
            if p.id == player_id:
                return p
        raise KeyError(f"unknown player id: {player_id}")
