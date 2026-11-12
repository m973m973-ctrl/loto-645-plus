# -*- coding: utf-8 -*-
"""Регрессионные проверки разделения «6 из 45» и «6 из 45 Плюс»."""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import lotto645_app as app


def load(name):
    with open(os.path.join(ROOT, "analysis", name), encoding="utf-8") as f:
        return json.load(f)


plus = load("archive_full.json")
classic = load("archive_6x45.json")
assert plus and classic
assert all(len(d["main"]) == 6 and d.get("plus") in (1, 2, 3, 4) for d in plus)
assert all(len(d["main"]) == 6 and d.get("plus", 0) == 0 for d in classic)

# Бэктест и объединённая история содержат только Плюс.
app._HISTORY = None
assert len(app.history()) == len(plus)
merged = app.all_6x45plus([])
assert len(merged) == len(plus)
assert [d["n"] for d in merged] == [d["n"] for d in plus]
assert all(d.get("plus") in (1, 2, 3, 4) for d in merged)

# В рейтинге у игр разные цены и шансы суперприза.
rating = {row[0]: row for row in app.games_rating(100)}
assert rating["6 из 45"][1] == 70
assert rating["6 из 45"][3] == 8_145_060
assert rating["6 из 45 Плюс"][1] == 100
assert rating["6 из 45 Плюс"][3] == 32_580_240
assert "6+0" in rating["6 из 45 Плюс"][4]

# Старый смешанный журнал отбрасывается; новый содержит только Плюс.
test_log = os.path.join(ROOT, "analysis", ".test_predictions_log.json")
original_log_path = app.log_path
try:
    with open(test_log, "w", encoding="utf-8") as f:
        json.dump([{"n": 999999, "draw": [1, 2, 3, 4, 5, 6]}], f)
    app.log_path = lambda: test_log
    draws = []
    for i in range(170):
        draws.append({
            "n": i + 1,
            "date": "test",
            "main": sorted(((i * 7 + j * 11) % 45) + 1 for j in range(6)),
            "plus": i % 4 + 1,
            "w4": 0,
            "cols": 0,
        })
    log = app.update_log(draws)
    assert len(log) == 100
    assert log[0]["n"] == 71 and log[-1]["n"] == 170
    assert all(e["game"] == "6x45plus" for e in log)
    assert all(e["n"] != 999999 for e in log)
    assert all(e["plus"] in (1, 2, 3, 4) for e in log)
finally:
    app.log_path = original_log_path
    if os.path.exists(test_log):
        os.remove(test_log)

print("OK: архивы, рейтинг и журнал двух игр разделены")
print("Архив Плюс:", len(plus), "тиражей; классическая 6 из 45:", len(classic))
