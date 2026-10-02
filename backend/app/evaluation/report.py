"""Aggregate evaluation reporting across simulated games."""

from __future__ import annotations


def build_report(results: list[dict]) -> dict:
    total = len(results)
    if total == 0:
        return {"total_games": 0}

    village_wins = sum(1 for r in results if r["winner"] == "village")
    decisions = sum(r["decisions"] for r in results)
    fail_closed = sum(r["fail_closed"] for r in results)

    # win rate per role: a player "wins" when their team wins
    role_games: dict[str, int] = {}
    role_wins: dict[str, int] = {}
    for r in results:
        for p in r["players"]:
            role = p["role"]
            team = "wolves" if role == "werewolf" else "village"
            role_games[role] = role_games.get(role, 0) + 1
            if r["winner"] == team:
                role_wins[role] = role_wins.get(role, 0) + 1

    return {
        "total_games": total,
        "village_wins": village_wins,
        "wolf_wins": total - village_wins,
        "village_win_rate": round(village_wins / total, 3),
        "avg_rounds": round(sum(r["rounds"] for r in results) / total, 2),
        "decisions_total": decisions,
        "fail_closed_total": fail_closed,
        "fail_closed_rate": round(fail_closed / decisions, 4) if decisions else 0.0,
        "avg_decision_latency_ms": round(
            sum(r["avg_latency_ms"] for r in results) / total, 1
        ),
        "role_win_rates": {
            role: round(role_wins.get(role, 0) / games, 3)
            for role, games in sorted(role_games.items())
        },
    }
