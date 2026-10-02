"""Deterministic mock LLM.

Parses the machine-readable prompt header (TASK / SELF / ROUND / CANDIDATES /
ALIVE / WOLF TEAMMATES / INSPECTION RESULTS) and produces schema-valid JSON via
seeded hashing. This gives the project:

* a zero-dependency offline demo mode,
* deterministic CI with no API keys,
* a reproducible baseline for the evaluation harness.

It plays with simple heuristics: werewolves avoid accusing teammates, the seer
votes known werewolves, everyone else follows seeded pseudo-random suspicion.
"""

from __future__ import annotations

import json
import re
import zlib

from .base import ChatMessage, LLMResponse, Stopwatch, estimate_tokens

_SPEECH_TEMPLATES = [
    "I have been watching {name}. Their voting pattern does not line up with their claims.",
    "Before we rush to judgment, review who pushed the last vote. I still have questions about {name}.",
    "{name} has been deflecting every accusation since round one. That is wolf behaviour.",
    "I have no hard proof yet, but {name}'s story keeps changing. Write it down.",
    "Quiet players survive too long in this village. {name}, explain yourself.",
    "The kills are surgical. Someone is guiding them, and my eyes are on {name}.",
]

_VOTE_REASONS = [
    "The evidence points their way.",
    "Their defence did not convince me.",
    "Someone has to answer for the pattern of kills.",
    "Following the strongest thread of suspicion.",
]

_FIELD = lambda name, text: (  # noqa: E731
    (m.group(1).strip()) if (m := re.search(rf"^{name}:\s*(.*)$", text, re.M)) else ""
)


class DeterministicMockLLM:
    name = "mock"

    def __init__(self, seed: int = 0) -> None:
        self.seed = seed

    async def complete(
        self,
        messages: list[ChatMessage],
        *,
        max_tokens: int = 400,
        temperature: float = 0.0,
    ) -> LLMResponse:
        sw = Stopwatch()
        content = messages[-1].content

        task = _FIELD("TASK", content) or "speak"
        self_id = _FIELD("SELF", content)
        round_no = _FIELD("ROUND", content) or "0"
        candidates = [c.strip() for c in _FIELD("CANDIDATES", content).split(",") if c.strip()]
        alive = {
            pair.split("=", 1)[0].strip(): pair.split("=", 1)[1].strip()
            for pair in _FIELD("ALIVE", content).split(",")
            if "=" in pair
        }
        teammate_ids = [
            p.split("=", 1)[0].strip()
            for p in (_FIELD("WOLF TEAMMATES", content) or "").split(",")
            if "=" in p
        ]
        known_wolves = re.findall(r"-\s*(\w+)=[^\n]* is a werewolf", content)

        pool = [c for c in candidates if c != self_id and c not in teammate_ids] or candidates or [self_id]

        def pick(options: list[str], salt: str = "") -> str:
            h = zlib.crc32(f"{self.seed}|{task}|{self_id}|{round_no}|{salt}|{','.join(options)}".encode())
            return options[h % len(options)]

        h = zlib.crc32(f"{self.seed}|{task}|{self_id}|{round_no}".encode())

        if task == "speak":
            suspect = pick(pool) if pool and h % 10 < 7 else None
            name = alive.get(suspect, "someone") if suspect else "no one yet"
            statement = _SPEECH_TEMPLATES[h % len(_SPEECH_TEMPLATES)].format(name=name)
            payload = {"kind": "speech", "statement": statement, "suspicion": suspect}
        elif task == "vote":
            wolf_pool = [w for w in known_wolves if w in pool]
            target = pick(wolf_pool, "known") if wolf_pool else pick(pool)
            payload = {
                "kind": "vote",
                "target": target,
                "reason": _VOTE_REASONS[h % len(_VOTE_REASONS)],
            }
        elif task == "night_kill":
            payload = {"kind": "kill", "target": pick(pool)}
        elif task == "night_inspect":
            payload = {"kind": "inspect", "target": pick(pool)}
        else:
            payload = {"kind": "speech", "statement": "I pass.", "suspicion": None}

        text = json.dumps(payload)
        return LLMResponse(
            text=text,
            model="deterministic-mock",
            latency_ms=sw.elapsed_ms(),
            prompt_tokens=estimate_tokens(content),
            completion_tokens=estimate_tokens(text),
        )
