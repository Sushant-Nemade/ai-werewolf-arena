from app.evaluation.elo import EloTable


def test_winners_gain_losers_drop():
    elo = EloTable()
    elo.record_game(winners=["a", "b"], losers=["c", "d"])
    assert elo.ratings["a"] > elo.base
    assert elo.ratings["c"] < elo.base


def test_expected_score_bounds():
    assert 0.0 < EloTable.expected(1200, 1200) < 1.0
    assert EloTable.expected(1200, 1200) == 0.5
    assert EloTable.expected(1600, 1200) > 0.9


def test_underdog_win_moves_more_rating():
    elo = EloTable()
    elo.ratings["strong"] = 1600.0
    elo.ratings["weak"] = 1000.0
    before = elo.ratings["weak"]
    elo.record_game(winners=["weak"], losers=["strong"])
    assert elo.ratings["weak"] - before > 16  # more than half of K for an upset


def test_table_sorted_with_stats():
    elo = EloTable()
    elo.record_game(winners=["a"], losers=["b"])
    table = elo.table()
    assert table[0]["label"] == "a"
    assert table[0]["wins"] == 1 and table[0]["games"] == 1
    assert table[1]["win_rate"] == 0.0
