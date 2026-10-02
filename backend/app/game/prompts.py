"""Prompt construction.

Prompts are built from a *player view*, never from global game state, so hidden
information cannot leak across the information-asymmetry boundary.

The user prompt carries a small machine-readable header (TASK / SELF / ROUND /
CANDIDATES / ALIVE). Real LLMs ignore it as context; the deterministic mock
provider parses it, which keeps the whole arena testable in CI without keys.
"""

from __future__ import annotations

from .models import Player, PlayerView, Role

ROLE_BRIEFS: dict[Role, str] = {
    Role.VILLAGER: (
        "You are a VILLAGER. You have no night action. Your goal is to identify "
        "and eliminate all werewolves through discussion and voting. Reason from "
        "evidence: voting patterns, contradictions, and who benefits from each death."
    ),
    Role.SEER: (
        "You are the SEER. Each night you secretly inspect one player and learn "
        "their true role. Use this knowledge to guide the village, but revealing "
        "yourself makes you the wolves' next target. Choose when and how to "
        "disclose what you know."
    ),
    Role.WEREWOLF: (
        "You are a WEREWOLF. Each night you and your teammates secretly kill one "
        "villager. By day you must blend in: deflect suspicion, misdirect votes, "
        "and never reveal yourself or your teammates. Subtle deception beats lying "
        "loudly."
    ),
}

SCHEMA_HINTS: dict[str, str] = {
    "speak": '{"kind": "speech", "statement": "<1-3 sentences you say out loud>", "suspicion": "<one candidate id or null>"}',
    "vote": '{"kind": "vote", "target": "<one candidate id>", "reason": "<one short sentence>"}',
    "night_kill": '{"kind": "kill", "target": "<one candidate id>"}',
    "night_inspect": '{"kind": "inspect", "target": "<one candidate id>"}',
}

TASK_INSTRUCTIONS: dict[str, str] = {
    "speak": (
        "It is your turn to speak in the village discussion. Make a statement that "
        "serves your secret goal. You may name one suspect, or none."
    ),
    "vote": "Cast your vote to eliminate one player. You must choose from the candidates.",
    "night_kill": "The pack hunts. Choose one villager to kill tonight.",
    "night_inspect": "Choose one player to inspect. You will learn their true role.",
}


def system_prompt(player: Player) -> str:
    return (
        "You are playing Werewolf, a social deduction game of hidden roles.\n"
        f"Your name is {player.name}. Your persona: {player.persona}. Stay in character.\n"
        f"{ROLE_BRIEFS[player.role]}\n"
        "Rules: werewolves win when they equal or outnumber the villagers; the "
        "village wins when all werewolves are eliminated. Eliminated players' roles "
        "are revealed publicly. Never break character, never mention being an AI, "
        "and respond ONLY with the requested JSON object."
    )


def task_prompt(
    task: str,
    view: PlayerView,
    candidates: list[str],
    memories: list[str],
) -> str:
    lines: list[str] = [
        f"ROUND: {view.round}",
        f"PHASE: {view.phase.value}",
        f"TASK: {task}",
        f"SELF: {view.me.id}",
        "ALIVE: " + ", ".join(f"{p['id']}={p['name']}" for p in view.alive),
        "CANDIDATES: " + ",".join(candidates),
        "",
        TASK_INSTRUCTIONS[task],
        "",
        "RECENT EVENTS:",
    ]
    if view.recent_events:
        lines += [f"- [r{e.round} {e.phase.value}] {e.content}" for e in view.recent_events]
    else:
        lines.append("- (none yet)")

    lines.append("")
    lines.append("PRIVATE NOTES:")
    lines += [f"- {n}" for n in view.private_notes]

    if view.inspections:
        lines.append("")
        lines.append("INSPECTION RESULTS (only you know these):")
        lines += [
            f"- {i['target']}={i['target_name']} is a {i['role']} (round {i['round']})"
            for i in view.inspections
        ]

    lines.append("")
    lines.append("RETRIEVED MEMORIES (most relevant past events):")
    lines += [f"- {m}" for m in memories] if memories else ["- (none)"]

    lines.append("")
    lines.append("Respond with ONLY a JSON object matching this schema:")
    lines.append(SCHEMA_HINTS[task])
    lines.append(f'The "target"/"suspicion" field must be one of: {", ".join(candidates)} (or null where allowed).')
    return "\n".join(lines)
