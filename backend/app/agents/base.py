"""Agent protocol.

An agent maps a restricted ``PlayerView`` to a structured action. The engine
never calls the LLM directly — all cognition goes through this boundary, which
keeps the game engine independent of any model or provider.
"""

from __future__ import annotations

from typing import Protocol

from ..game.models import NightAction, Player, PlayerView, SpeechAction, VoteAction


class Agent(Protocol):
    player: Player

    async def speak(self, view: PlayerView, candidates: list[str]) -> SpeechAction: ...

    async def vote(self, view: PlayerView, candidates: list[str]) -> VoteAction: ...

    async def night_action(self, view: PlayerView, kind: str, candidates: list[str]) -> NightAction: ...
