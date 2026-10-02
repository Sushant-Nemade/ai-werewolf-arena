"""Persona registry.

Personas give agents distinguishable voices and strategies, which makes
emergent social dynamics visible and gives the evaluation harness a stable
label to rate.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Persona:
    name: str
    style: str


PERSONAS: list[Persona] = [
    Persona("Ada", "an analytical logician who cites voting evidence and contradictions"),
    Persona("Boris", "an aggressive accuser who pressures quiet players"),
    Persona("Cleo", "a quiet observer who speaks rarely but precisely"),
    Persona("Dorian", "a charming deflector who uses humour under pressure"),
    Persona("Edda", "a cautious consensus-builder who dislikes rushed votes"),
    Persona("Flynn", "a chaotic wildcard who changes theories often"),
    Persona("Greta", "a methodical note-taker who references earlier rounds"),
    Persona("Hank", "a bold risk-taker who pushes for fast votes"),
    Persona("Iris", "an empathetic reader of tone and motive"),
    Persona("Joris", "a skeptical statistician who quotes base rates"),
]
