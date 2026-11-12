# -*- coding: utf-8 -*-
"""Печатает правила и выплаты последних тиражей двух разных игр."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lotto645_app import fetch_recent

for game in ("6x45", "6x45plus"):
    draws = fetch_recent(game, 100)
    print("\nGAME", game, "draws:", draws[-1].get("number"), "...", draws[0].get("number"))
    seen = set()
    for draw in draws:
        categories = json.loads(draw["winningCategories"])
        for cat in categories["categories"]:
            desc = cat["description"]
            payout = cat.get("dividend_per_column", 0) / 100
            winners = cat.get("win_columns_number", 0)
            if desc not in seen and payout and winners:
                seen.add(desc)
                print(desc, "->", payout, "RUB; draw", draw["number"],
                      "winners", winners)
    print("categories with observed payouts:", sorted(seen))
