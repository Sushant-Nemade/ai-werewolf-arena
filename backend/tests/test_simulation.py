import asyncio

from app.evaluation.simulate import run_simulation


def test_simulation_report_shape():
    report = asyncio.run(run_simulation(games=2, provider_name="mock", seed=5, concurrency=2))

    assert report["total_games"] == 2
    assert report["village_wins"] + report["wolf_wins"] == 2
    assert report["decisions_total"] > 0
    assert 0.0 <= report["fail_closed_rate"] <= 1.0
    assert set(report["role_win_rates"]) <= {"werewolf", "seer", "villager"}

    labels = [row["label"] for row in report["elo"]]
    assert len(labels) > 0
    ratings = [row["rating"] for row in report["elo"]]
    assert ratings == sorted(ratings, reverse=True)
