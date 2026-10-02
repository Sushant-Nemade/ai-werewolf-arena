"""Batch simulation harness.

Runs N headless games with bounded concurrency, feeds results into the ELO
table, and emits a JSON report. This is the benchmarking entry point:

    python -m app.evaluation.simulate --games 20 --provider mock --seed 7
    python -m app.evaluation.simulate --games 10 --provider ollama
"""

from __future__ import annotations

import argparse
import asyncio
import json

from ..config import Settings
from ..game.engine import WerewolfEngine
from ..llm.factory import create_provider
from ..observability.tracing import DecisionTracer
from .elo import EloTable
from .report import build_report


async def run_simulation(
    games: int,
    provider_name: str = "mock",
    seed: int = 0,
    concurrency: int = 4,
    settings: Settings | None = None,
) -> dict:
    settings = settings or Settings()
    tracer = DecisionTracer()
    elo = EloTable()
    semaphore = asyncio.Semaphore(concurrency)
    results: list[dict] = []

    async def run_one(index: int) -> None:
        async with semaphore:
            provider = create_provider(settings, provider_name, seed=seed + index)
            engine = WerewolfEngine.new_game(
                game_id=f"sim-{seed}-{index}",
                provider=provider,
                tracer=tracer,
                settings=settings,
                num_players=7,
                seed=seed + index,
            )
            await engine.play()
            result = engine.build_result()
            results.append(result)
            winners = [p["label"] for p in result["players"] if (p["role"] == "werewolf") == (result["winner"] == "wolves")]
            losers = [p["label"] for p in result["players"] if p["label"] not in winners]
            elo.record_game(winners, losers)

    await asyncio.gather(*(run_one(i) for i in range(games)))

    report = build_report(results)
    report["elo"] = elo.table()
    report["provider"] = provider_name
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Run headless Werewolf simulations and print an evaluation report.")
    parser.add_argument("--games", type=int, default=20)
    parser.add_argument("--provider", type=str, default="mock", choices=["mock", "ollama", "openai"])
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--out", type=str, default="simulation-report.json")
    args = parser.parse_args()

    report = asyncio.run(run_simulation(args.games, args.provider, args.seed, args.concurrency))

    print(f"\n=== Simulation report ({report['provider']}, {report['total_games']} games) ===")
    print(f"village win rate : {report['village_win_rate']}")
    print(f"avg rounds       : {report['avg_rounds']}")
    print(f"decisions        : {report['decisions_total']} (fail-closed rate {report['fail_closed_rate']})")
    print(f"role win rates   : {report['role_win_rates']}")
    print("\nELO leaderboard:")
    for row in report["elo"]:
        print(f"  {row['rating']:>7}  {row['label']:<28} {row['wins']}/{row['games']} wins")

    with open(args.out, "w") as fh:
        json.dump(report, fh, indent=2)
    print(f"\nFull report written to {args.out}")


if __name__ == "__main__":
    main()
