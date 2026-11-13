# -*- coding: utf-8 -*-
"""Обновляет архив классической «6 из 45» и строит прогноз только по нему."""
import csv
import json
import os
import sys
from collections import Counter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from lotto645_app import combos_for, fetch_recent

ARCHIVE = os.path.join(ROOT, "analysis", "archive_6x45.json")
SOURCE = os.path.join(ROOT, "analysis", "archive_6x45_source.csv")
FORECAST = os.path.join(ROOT, "analysis", "forecast_6x45_latest.json")

with open(ARCHIVE, encoding="utf-8") as f:
    archive = json.load(f)

by_number = {int(d["n"]): d for d in archive}
original_numbers = set(by_number)

# Присланный полный CSV — основной источник классической игры.
def as_int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0

if os.path.exists(SOURCE):
    with open(SOURCE, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f, delimiter=";"):
            main = sorted(int(x) for x in row["Числа (по порядку)"].split())
            number = int(row["Тираж"])
            if len(set(main)) != 6 or not all(1 <= x <= 45 for x in main):
                continue
            by_number[number] = {
                "n": number,
                "date": row["Дата"],
                "main": main,
                "w4": as_int(row.get("Угадано 4 — билетов")),
                "cols": as_int(row.get("Билетов в розыгрыше")),
            }

# Докачиваем тиражи, которые могли появиться уже после выгрузки CSV.
recent = fetch_recent("6x45", 100)
for raw in recent:
    combination = (raw.get("combination") or {}).get("structured") or []
    if len(combination) < 6:
        continue
    number = int(raw["number"])
    main = sorted(int(x) for x in combination[:6])
    if len(set(main)) != 6 or not all(1 <= x <= 45 for x in main):
        continue
    if number in by_number:
        continue
    by_number[number] = {
        "n": number,
        "date": raw.get("date", ""),
        "main": main,
        "w4": 0,
        "cols": 0,
    }

new_numbers = sorted(set(by_number) - original_numbers)
archive = [by_number[n] for n in sorted(by_number)]
assert archive and all(len(d["main"]) == 6 for d in archive)
assert all(d.get("plus", 0) == 0 for d in archive), "В архив попали данные Плюс"

with open(ARCHIVE, "w", encoding="utf-8") as f:
    json.dump(archive, f, ensure_ascii=False)

prediction = combos_for(archive)
assert prediction and len(prediction["main"]) == 6 and len(prediction["alt"]) == 6

# Сравнение только с прошлыми тиражами классической игры, без Плюс.
def static_backtest(combo):
    hits = Counter(len(set(combo) & set(d["main"])) for d in archive)
    return {str(k): hits[k] for k in range(2, 7)}

last100 = archive[-100:]
frequency = Counter(x for d in last100 for x in d["main"])
hot = [x for x, _ in sorted(frequency.items(), key=lambda p: (-p[1], p[0]))[:10]]
last_seen = {x: -1 for x in range(1, 46)}
for i, draw in enumerate(archive):
    for x in draw["main"]:
        last_seen[x] = i
overdue = sorted(range(1, 46), key=lambda x: (last_seen[x], x))[:10]

result = {
    "game": "6x45",
    "archive_draws": len(archive),
    "added_draws": sorted(new_numbers),
    "last_draw": archive[-1],
    "forecast_for_draw": archive[-1]["n"] + 1,
    "main": prediction["main"],
    "alternative": prediction["alt"],
    "hot_last_100": hot,
    "overdue": overdue,
    "main_static_backtest": static_backtest(prediction["main"]),
    "alternative_static_backtest": static_backtest(prediction["alt"]),
    "note": "Статистический выбор не увеличивает математическую вероятность выигрыша.",
}
with open(FORECAST, "w", encoding="utf-8") as f:
    json.dump(result, f, ensure_ascii=False, indent=2)

print(json.dumps(result, ensure_ascii=False, indent=2))
