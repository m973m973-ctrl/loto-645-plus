# -*- coding: utf-8 -*-
"""Быстрая проверка Windows-интерфейса без сетевого обновления."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lotto645_app as app_module

app = app_module.App()
app.withdraw()
try:
    assert len(app.nb.tabs()) == 8
    assert app.nb.tab(0, "text") == "6 из 45 Плюс"

    app.bet_n.delete(0, "end")
    app.bet_n.insert(0, "7")
    app.bet_price.delete(0, "end")
    app.bet_price.insert(0, "100")
    app._calc_bet()
    bet_text = app.bet_out.cget("text")
    assert "7 комбинаций" in bet_text
    assert "6+1" in bet_text
    assert "4 654 320" in bet_text  # 4 × C(45,6) / C(7,6)

    app.cmp_min.delete(0, "end")
    app.cmp_min.insert(0, "100")
    app._calc_games()
    rating = app.cmp_out.get("1.0", "end")
    assert "6 из 45 Плюс" in rating
    assert "32 580 240" in rating
    assert "6+0" in rating

    log = app_module.update_log(app_module.all_6x45plus([]))
    assert len(log) == 100
    assert all(e["game"] == "6x45plus" for e in log)
    app._render_log(log)
    assert app.log_summary.cget("text")

    print("OK: 8 вкладок, калькулятор, рейтинг и журнал Плюс")
    print("Журнал пересоздан:", log[0]["n"], "...", log[-1]["n"])
finally:
    app.destroy()
