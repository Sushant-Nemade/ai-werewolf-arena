"""ELO rating for agents.

Each game is treated as a team match: every winning-team member scores against
the average rating of the losing team and vice versa. Ratings are keyed by
agent label (``provider/persona``), so the same harness can compare personas,
models, or prompt variants against each other.
"""

from __future__ import annotations


class EloTable:
    def __init__(self, k: float = 32.0, base: float = 1200.0) -> None:
        self.k = k
        self.base = base
        self.ratings: dict[str, float] = {}
        self.games: dict[str, int] = {}
        self.wins: dict[str, int] = {}

    @staticmethod
    def expected(a: float, b: float) -> float:
        return 1.0 / (1.0 + 10 ** ((b - a) / 400.0))

    def _rating(self, label: str) -> float:
        return self.ratings.get(label, self.base)

    def record_game(self, winners: list[str], losers: list[str]) -> None:
        if not winners or not losers:
            return
        avg_winner = sum(self._rating(w) for w in winners) / len(winners)
        avg_loser = sum(self._rating(l) for l in losers) / len(losers)

        for w in winners:
            self.ratings[w] = self._rating(w) + self.k * (1.0 - self.expected(self._rating(w), avg_loser))
            self.games[w] = self.games.get(w, 0) + 1
            self.wins[w] = self.wins.get(w, 0) + 1
        for l in losers:
            self.ratings[l] = self._rating(l) + self.k * (0.0 - self.expected(self._rating(l), avg_winner))
            self.games[l] = self.games.get(l, 0) + 1

    def table(self) -> list[dict]:
        return sorted(
            (
                {
                    "label": label,
                    "rating": round(rating, 1),
                    "games": self.games.get(label, 0),
                    "wins": self.wins.get(label, 0),
                    "win_rate": round(self.wins.get(label, 0) / self.games[label], 3) if self.games.get(label) else 0.0,
                }
                for label, rating in self.ratings.items()
            ),
            key=lambda row: row["rating"],
            reverse=True,
        )
