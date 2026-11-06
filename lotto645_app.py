# -*- coding: utf-8 -*-
"""Лото 6/45 Плюс — настольное приложение статистики тиражей.

Показывает последний тираж, частоты чисел, горячие и давно не выпадавшие
числа, статистику плюс-шара, три варианта комбинации (статистическая,
запасная, «антитолпа») и бэктест каждой по всей истории обеих игр
(более 28 тысяч тиражей, архив встроен в программу).
Данные: публичный архив stoloto.ru.
"""
import json
import os
import sys
import threading
import time
import urllib.request
import tkinter as tk
from datetime import datetime, timezone, timedelta

API = ("https://www.stoloto.ru/p/api/mobile/api/v35/service/draws/archive"
       "?game=6x45plus&count=100&page={}")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 Chrome/150.0 Safari/537.36"),
    "Gosloto-Partner": "bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg",
}
PAGES = 6  # ~300 последних тиражей
MSK = timezone(timedelta(hours=3))

BG = "#1e1f24"
PANEL = "#26272e"
FG = "#f2f2f2"
FG2 = "#9a9aa3"
BLUE = "#4c7dff"
RED = "#d24a43"
GOLD = "#e8b23f"
GREEN = "#3fae6a"

LOG_NAME = "predictions_log.json"
MY_NAME = "my_combos.json"


def resource_path(name):
    """Файл данных: рядом со скриптом или внутри exe."""
    base = getattr(sys, "_MEIPASS", None)
    if base:
        p = os.path.join(base, name)
        if os.path.exists(p):
            return p
    for p in (os.path.join("analysis", name), name):
        if os.path.exists(p):
            return p
    return None


_HISTORY = None

def history():
    """Все тиражи обеих игр: [(множество чисел), ...]."""
    global _HISTORY
    if _HISTORY is None:
        _HISTORY = []
        for name in ("archive_full.json", "archive_6x45.json"):
            p = resource_path(name)
            if p:
                try:
                    for d in json.load(open(p, encoding="utf-8")):
                        _HISTORY.append(set(d["main"]))
                except Exception:
                    pass
    return _HISTORY


def backtest(combo):
    """Совпадения комбинации со всей историей обеих игр."""
    t = set(combo)
    res = {3: 0, 4: 0, 5: 0, 6: 0}
    for s in history():
        k = len(t & s)
        if k >= 3:
            res[k] += 1
    return res


def log_path():
    """Журнал прогнозов: рядом с программой (или в analysis у скрипта)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    p = os.path.join(base, "analysis", LOG_NAME)
    if os.path.isdir(os.path.dirname(p)):
        return p
    return os.path.join(base, LOG_NAME)


def my_path():
    """Файл любимых комбинаций рядом с программой."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, MY_NAME)


def load_my():
    try:
        with open(my_path(), encoding="utf-8") as f:
            data = json.load(f)
        return [sorted(set(int(x) for x in c)) for c in data
                if len(set(c)) == 6 and all(1 <= int(x) <= 45 for x in c)]
    except Exception:
        return []


def save_my(combos):
    with open(my_path(), "w", encoding="utf-8") as f:
        json.dump(combos, f)


def combos_for(prior):
    """Прогноз (main/alt/crowd) по истории prior. Терпимо к неполным полям."""
    if len(prior) < 50:
        return None
    total = len(prior)
    freq = {n: 0 for n in range(1, 46)}
    f100 = {n: 0 for n in range(1, 46)}
    plus = {1: 0, 2: 0, 3: 0, 4: 0}
    for d in prior:
        for n in d["main"]:
            freq[n] += 1
        p = d.get("plus", 0)
        if p in plus:
            plus[p] += 1
    for d in prior[-100:]:
        for n in d["main"]:
            f100[n] += 1
    last_seen = {}
    for i, d in enumerate(prior):
        for n in d["main"]:
            last_seen[n] = i
    overdue = sorted(({"n": n, "since": total - 1 - last_seen.get(n, -1)}
                      for n in range(1, 46)), key=lambda x: -x["since"])[:10]
    hot100 = sorted(({"n": n, "c": f100[n]} for n in range(1, 46)),
                    key=lambda x: (-x["c"], x["n"]))[:10]
    top_all = sorted(freq, key=lambda n: (-freq[n], n))
    hot = [x["n"] for x in hot100]
    ovd = [x["n"] for x in overdue]
    main, seen = [], set()
    for pool, take in ((hot, 3), (ovd, 2), (top_all, 1)):
        added = 0
        for n in pool:
            if n not in seen:
                main.append(n); seen.add(n); added += 1
            if added == take:
                break
    alt, seen2 = [], set()
    for pool, take in ((ovd, 3), (hot, 3)):
        added = 0
        for n in pool:
            if n not in seen2 and n not in seen:
                alt.append(n); seen2.add(n); added += 1
            if added == take:
                break
    # «антитолпа» — только если хватает данных о победителях
    crowd = None
    wd = [d for d in prior if d.get("cols")]
    if len(wd) >= 100:
        pop = {}
        for n in range(1, 46):
            a = [d["w4"] / d["cols"] for d in wd if n in d["main"]]
            b = [d["w4"] / d["cols"] for d in wd if n not in d["main"]]
            pop[n] = (sum(a) / len(a) - sum(b) / len(b)) if a and b else 0
        crowd = sorted(sorted(range(1, 46), key=lambda n: pop[n])[:6])
    ps = sorted(plus, key=lambda k: plus[k])
    return {"main": sorted(main), "alt": sorted(alt), "crowd": crowd,
            "plus_main": max(plus, key=lambda k: plus[k]),
            "plus_alt": ps[0],
            "plus_crowd": ps[1] if len(ps) > 1 else 1}


def update_log(all_draws, keep=100):
    """Журнал: для каждого тиража прогноз, посчитанный ДО него.
    Добавляет только новые тиражи, хранит последние keep записей."""
    try:
        log = json.load(open(log_path(), encoding="utf-8"))
    except Exception:
        log = []
    known = {e["n"] for e in log}
    all_draws = [d for d in all_draws if d.get("main")]
    start = max(50, len(all_draws) - keep)
    todo = [i for i in range(start, len(all_draws))
            if all_draws[i]["n"] not in known]
    for i in todo:
        pred = combos_for(all_draws[:i])
        if not pred:
            continue
        d = all_draws[i]
        log.append({"n": d["n"], "date": d.get("date", ""),
                    "draw": d["main"], "plus": d.get("plus", 0),
                    "main": pred["main"], "alt": pred["alt"],
                    "crowd": pred["crowd"],
                    "plus_main": pred["plus_main"],
                    "plus_alt": pred["plus_alt"],
                    "plus_crowd": pred["plus_crowd"]})
    log = sorted({e["n"]: e for e in log}.values(),
                 key=lambda e: e["n"])[-keep:]
    try:
        json.dump(log, open(log_path(), "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    except Exception:
        pass
    return log


def fetch_page(p, attempts=4):
    last = None
    for a in range(attempts):
        try:
            req = urllib.request.Request(API.format(p), headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (a + 1))
    raise RuntimeError("страница %d: %s" % (p, last))


def fetch_draws():
    draws = []
    for p in range(1, PAGES + 1):
        payload = fetch_page(p)
        if payload.get("requestStatus") != "success":
            raise RuntimeError("Ошибка API: %s" % payload.get("errors"))
        for d in payload.get("draws", []):
            comb = (d.get("combination") or {}).get("structured") or []
            if len(comb) >= 6:
                w4, cols = 0, 0
                try:
                    wc = json.loads(d["winningCategories"])
                    cols = wc.get("columns") or 0
                    for c in wc.get("categories", []):
                        if c.get("lotos_wcnumber") == 4:  # категория «4»
                            w4 = c.get("win_columns_number", 0)
                except Exception:
                    pass
                draws.append({
                    "n": d["number"],
                    "date": d.get("date", "")[:16].replace("T", " "),
                    "main": sorted(int(x) for x in comb[:6]),
                    "plus": int(comb[6]) if len(comb) > 6 else 0,
                    "w4": w4, "cols": cols,
                })
        time.sleep(0.25)
    uniq = {d["n"]: d for d in draws}
    return [uniq[k] for k in sorted(uniq)]


def all_6x45(fetched):
    """Полная история 6x45: встроенный архив + свежие тиражи из сети."""
    out = {}
    p = resource_path("archive_6x45.json")
    if p:
        try:
            for d in json.load(open(p, encoding="utf-8")):
                d.setdefault("plus", 0)
                d.setdefault("w4", 0)
                d.setdefault("cols", 0)
                d["date"] = d.get("date", "")[:16].replace("T", " ")
                out[d["n"]] = d
        except Exception:
            pass
    for d in fetched:
        out[d["n"]] = d
    return [out[k] for k in sorted(out)]


def analyze(draws):
    total = len(draws)
    freq = {n: 0 for n in range(1, 46)}
    f100 = {n: 0 for n in range(1, 46)}
    plus = {1: 0, 2: 0, 3: 0, 4: 0}
    for d in draws:
        for n in d["main"]:
            freq[n] += 1
        if d["plus"] in plus:
            plus[d["plus"]] += 1
    for d in draws[-100:]:
        for n in d["main"]:
            f100[n] += 1
    last_seen = {}
    for i, d in enumerate(draws):
        for n in d["main"]:
            last_seen[n] = i
    overdue = sorted(({"n": n, "since": total - 1 - last_seen.get(n, -1)}
                      for n in range(1, 46)), key=lambda x: -x["since"])[:10]
    hot100 = sorted(({"n": n, "c": f100[n]} for n in range(1, 46)),
                    key=lambda x: (-x["c"], x["n"]))[:10]
    freq_all = [{"n": n, "c": freq[n]} for n in range(1, 46)]

    # популярность числа у игроков: доля победителей «4 из 6»,
    # когда число выпадает, минус когда не выпадает
    pop = {}
    wd = [d for d in draws if d["cols"]]
    for n in range(1, 46):
        a = [d["w4"] / d["cols"] for d in wd if n in d["main"]]
        b = [d["w4"] / d["cols"] for d in wd if n not in d["main"]]
        pop[n] = (sum(a) / len(a) - sum(b) / len(b)) if a and b else 0
    crowd = sorted(range(1, 46), key=lambda n: pop[n])[:6]
    crowd = sorted(crowd)

    hot = [x["n"] for x in hot100]
    ovd = [x["n"] for x in overdue]
    top_all = [x["n"] for x in sorted(freq_all, key=lambda x: (-x["c"], x["n"]))]
    main, seen = [], set()
    for pool, take in ((hot, 3), (ovd, 2), (top_all, 1)):
        added = 0
        for n in pool:
            if n not in seen:
                main.append(n); seen.add(n); added += 1
            if added == take:
                break
    alt, seen2 = [], set()
    for pool, take in ((ovd, 3), (hot, 3)):
        added = 0
        for n in pool:
            if n not in seen2 and n not in seen:
                alt.append(n); seen2.add(n); added += 1
            if added == take:
                break
    plus_sorted = sorted(plus, key=lambda k: plus[k])
    return {
        "freq": freq_all, "hot": hot100, "overdue": overdue, "plus": plus,
        "main": sorted(main), "plus_main": max(plus, key=lambda k: plus[k]),
        "alt": sorted(alt), "plus_alt": plus_sorted[0],
        "crowd": crowd, "plus_crowd": plus_sorted[1] if len(plus_sorted) > 1 else 1,
        "pop": pop,
    }


class Ball(tk.Canvas):
    def __init__(self, master, n, size=36, outline=FG, fill=PANEL, fg=FG):
        super().__init__(master, width=size, height=size, bg=BG,
                         highlightthickness=0)
        self.create_oval(2, 2, size - 2, size - 2, outline=outline,
                         fill=fill, width=2)
        self.create_text(size / 2, size / 2, text=str(n), fill=fg,
                         font=("Segoe UI", int(size * 0.38), "bold"))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("6 из 45 Плюс — статистика")
        self.configure(bg=BG)
        self.geometry("780x1180")
        self.minsize(720, 1120)
        self._build()
        self.after(200, self.refresh)

    AUTO_MS = 15 * 60 * 1000  # автообновление каждые 15 минут

    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 4))
        tk.Label(top, text="6 из 45 Плюс — статистика тиражей", bg=BG, fg=FG,
                 font=("Segoe UI", 15, "bold")).pack(side="left")
        self.btn = tk.Button(top, text="Обновить", command=self.refresh,
                             bg=BLUE, fg="white", relief="flat",
                             font=("Segoe UI", 10), padx=14, pady=4,
                             cursor="hand2")
        self.btn.pack(side="right")

        self.meta = tk.Label(self, text="Загрузка…", bg=BG, fg=FG2,
                             font=("Segoe UI", 9))
        self.meta.pack(anchor="w", padx=16)

        self.last = tk.Label(self, text="", bg=BG, fg=FG,
                             font=("Segoe UI", 11))
        self.last.pack(anchor="w", padx=16, pady=(6, 0))

        fr = tk.Frame(self, bg=BG); fr.pack(fill="x", padx=16, pady=(10, 0))
        self.rows = {}
        for key, label in (("main", "Предлагаемая комбинация"),
                           ("alt", "Запасная"),
                           ("crowd", "«Антитолпа» — реже всего отмечают игроки")):
            tk.Label(fr, text=label, bg=BG, fg=FG2,
                     font=("Segoe UI", 10)).pack(anchor="w")
            row = tk.Frame(fr, bg=BG); row.pack(anchor="w", pady=2)
            bt = tk.Label(fr, text="", bg=BG, fg=FG2, font=("Segoe UI", 9))
            bt.pack(anchor="w", pady=(0, 6))
            self.rows[key] = (row, bt)

        self.chart_lbl = tk.Label(self, text="", bg=BG, fg=FG2,
                                  font=("Segoe UI", 10))
        self.chart_lbl.pack(anchor="w", padx=16, pady=(6, 0))
        self.chart = tk.Canvas(self, bg=PANEL, highlightthickness=0,
                               height=190)
        self.chart.pack(fill="x", padx=16, pady=4)

        lists = tk.Frame(self, bg=BG); lists.pack(fill="x", padx=16, pady=8)
        left = tk.Frame(lists, bg=BG); left.pack(side="left", anchor="n")
        tk.Label(left, text="Горячие (последние 100 тиражей)", bg=BG, fg=FG2,
                 font=("Segoe UI", 10)).pack(anchor="w")
        self.hot = tk.Frame(left, bg=BG); self.hot.pack(anchor="w", pady=2)
        right = tk.Frame(lists, bg=BG); right.pack(side="left", anchor="n",
                                                   padx=(40, 0))
        tk.Label(right, text="Давно не выпадали", bg=BG, fg=FG2,
                 font=("Segoe UI", 10)).pack(anchor="w")
        self.cold = tk.Frame(right, bg=BG); self.cold.pack(anchor="w", pady=2)

        self.plus_lbl = tk.Label(self, text="", bg=BG, fg=FG2,
                                 font=("Segoe UI", 10))
        self.plus_lbl.pack(anchor="w", padx=16)

        # --- калькулятор развёрнутой ставки ---
        bet = tk.Frame(self, bg=BG)
        bet.pack(fill="x", padx=16, pady=(10, 0))
        tk.Label(bet, text="Развёрнутая ставка — чисел:", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(side="left")
        self.bet_n = tk.Spinbox(bet, from_=7, to=19, width=3, bg=PANEL, fg=FG,
                                buttonbackground=PANEL, relief="flat",
                                font=("Segoe UI", 10), insertbackground=FG,
                                command=self._calc_bet)
        self.bet_n.pack(side="left", padx=(6, 14))
        tk.Label(bet, text="цена комбинации, ₽:", bg=BG, fg=FG2,
                 font=("Segoe UI", 10)).pack(side="left")
        self.bet_price = tk.Entry(bet, width=6, bg=PANEL, fg=FG, relief="flat",
                                  font=("Segoe UI", 10), insertbackground=FG)
        self.bet_price.insert(0, "100")
        self.bet_price.pack(side="left", padx=6)
        tk.Label(bet, text="человек:", bg=BG, fg=FG2,
                 font=("Segoe UI", 10)).pack(side="left")
        self.bet_ppl = tk.Entry(bet, width=4, bg=PANEL, fg=FG, relief="flat",
                                font=("Segoe UI", 10), insertbackground=FG)
        self.bet_ppl.insert(0, "1")
        self.bet_ppl.pack(side="left", padx=6)
        tk.Button(bet, text="Посчитать", command=self._calc_bet,
                  bg=BLUE, fg="white", relief="flat", font=("Segoe UI", 9),
                  padx=10, cursor="hand2").pack(side="left", padx=8)
        self.bet_out = tk.Label(self, text="", bg=BG, fg=FG,
                                font=("Segoe UI", 9), justify="left")
        self.bet_out.pack(anchor="w", padx=16, pady=(2, 0))

        # --- мои комбинации ---
        tk.Label(self, text="Мои комбинации — программа сама проверит их "
                            "по каждому новому тиражу", bg=BG, fg=FG,
                 font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=16,
                                                    pady=(10, 0))
        myfr = tk.Frame(self, bg=BG)
        myfr.pack(fill="x", padx=16, pady=(2, 0))
        tk.Label(myfr, text="6 чисел через пробел:", bg=BG, fg=FG2,
                 font=("Segoe UI", 9)).pack(side="left")
        self.my_entry = tk.Entry(myfr, bg=PANEL, fg=FG, relief="flat",
                                 font=("Segoe UI", 10), insertbackground=FG,
                                 width=16)
        self.my_entry.pack(side="left", padx=6)
        tk.Button(myfr, text="Добавить", command=self._add_my, bg=BLUE,
                  fg="white", relief="flat", font=("Segoe UI", 9), padx=10,
                  cursor="hand2").pack(side="left")
        tk.Button(myfr, text="🎲 Антитолпа", command=self._gen_crowd,
                  bg=PANEL, fg=GREEN, relief="flat", font=("Segoe UI", 9),
                  padx=10, cursor="hand2").pack(side="left", padx=8)
        self.my_list = tk.Frame(self, bg=BG)
        self.my_list.pack(fill="x", padx=16, pady=(2, 0))
        self._my_last_draw = None
        self._render_my_list()

        tk.Label(self, text="Проверка прогнозов на последних 100 тиражах "
                            "(цветные — совпали: синий — прогноз, "
                            "золотой — запасной, зелёный — антитолпа)",
                 bg=BG, fg=FG2, font=("Segoe UI", 9),
                 justify="left").pack(anchor="w", padx=16, pady=(8, 0))
        self.log_summary = tk.Label(self, text="", bg=BG, fg=FG,
                                    font=("Segoe UI", 9, "bold"),
                                    justify="left")
        self.log_summary.pack(anchor="w", padx=16)
        self.log_filter = tk.IntVar(value=1)
        tk.Checkbutton(self, text="Показывать только тиражи с 2 и более "
                                  "совпадениями", variable=self.log_filter,
                       bg=BG, fg=FG2, selectcolor=PANEL,
                       activebackground=BG, activeforeground=FG,
                       font=("Segoe UI", 9),
                       command=self._rerender_log).pack(anchor="w", padx=16)
        log_fr = tk.Frame(self, bg=PANEL)
        log_fr.pack(fill="both", expand=True, padx=16, pady=(2, 4))
        sb = tk.Scrollbar(log_fr)
        sb.pack(side="right", fill="y")
        self.log_text = tk.Text(log_fr, bg=PANEL, fg=FG, relief="flat",
                                font=("Consolas", 9), height=11,
                                yscrollcommand=sb.set, wrap="none",
                                cursor="arrow")
        self.log_text.pack(side="left", fill="both", expand=True)
        sb.config(command=self.log_text.yview)
        self.log_text.tag_config("draw", foreground=FG, font=("Consolas", 9, "bold"))
        self.log_text.tag_config("hit_main", foreground=BLUE,
                                 font=("Consolas", 9, "bold"))
        self.log_text.tag_config("hit_alt", foreground=GOLD,
                                 font=("Consolas", 9, "bold"))
        self.log_text.tag_config("hit_crowd", foreground=GREEN,
                                 font=("Consolas", 9, "bold"))
        self.log_text.tag_config("miss", foreground=FG2)
        self.log_text.tag_config("hdr", foreground=FG2)
        self.log_text.config(state="disabled")

        tk.Label(self,
                 text="Все комбинации равновероятны (1 : 8 145 060) — "
                      "статистика не повышает шансы.\n«Антитолпа» лишь "
                      "уменьшает риск делить приз с другими игроками.",
                 bg=BG, fg=FG2, font=("Segoe UI", 9), justify="left"
                 ).pack(anchor="w", padx=16, pady=(8, 12))

    def refresh(self):
        self.btn.config(state="disabled", text="Обновление…")
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self):
        try:
            draws = fetch_draws()
            stats = analyze(draws)
            bt = {k: backtest(stats[k]) for k in ("main", "alt", "crowd")}
            log = update_log(all_6x45(draws))
            self.after(0, lambda: self._render(draws, stats, bt, None, log))
        except Exception as e:
            self.after(0, lambda: self._render(None, None, None, e, None))

    @staticmethod
    def _bt_text(bt):
        if not history():
            return "архив истории не найден — бэктест недоступен"
        rep = "полный повтор был!" if bt[6] else "полного повтора не было"
        return ("по истории %d тиражей: 5 чисел — %d, 4 — %d, 3 — %d; %s"
                % (len(history()), bt[5], bt[4], bt[3], rep))

    def _render(self, draws, st, bt, err, log=None):
        self.btn.config(state="normal", text="Обновить")
        # автообновление каждые 15 минут (тиражи выходят каждые 15 мин)
        self.after(self.AUTO_MS, self.refresh)
        if err:
            self.meta.config(text="Ошибка загрузки: %s" % err)
            return
        now = datetime.now(MSK).strftime("%d.%m.%Y %H:%M МСК")
        self.meta.config(text="Обновлено %s · тиражи №%d–%d (окно %d) · "
                         "автообновление каждые 15 мин" %
                         (now, draws[0]["n"], draws[-1]["n"], len(draws)))
        ld = draws[-1]
        self._my_last_draw = ld["main"]
        self._recent_draws = [d["main"] for d in draws[-100:]]
        self._render_my_list()
        self.last.config(text="Последний тираж №%d (%s): %s + плюс %s" %
                         (ld["n"], ld["date"],
                          " ".join(map(str, ld["main"])), ld["plus"]))

        conf = {"main": (st["main"], st["plus_main"], 36, FG, 3),
                "alt": (st["alt"], st["plus_alt"], 30, FG, 2),
                "crowd": (st["crowd"], st["plus_crowd"], 30, GREEN, 2)}
        for key, (combo, pl, size, color, pad) in conf.items():
            row, btlbl = self.rows[key]
            for w in row.winfo_children():
                w.destroy()
            for n in combo:
                Ball(row, n, size=size,
                     outline=color if key == "crowd" else FG,
                     fg=color if key == "crowd" else FG).pack(side="left",
                                                              padx=pad)
            Ball(row, pl, size=size, outline=GOLD,
                 fg=GOLD).pack(side="left", padx=(10, pad))
            btlbl.config(text=self._bt_text(bt[key]))

        self.chart_lbl.config(text="Частота выпадения чисел за %d тиражей "
                              "(синие — горячие, красная точка — давно не было)"
                              % len(draws))
        self._draw_chart(st)

        for w in self.hot.winfo_children():
            w.destroy()
        for x in st["hot"]:
            tk.Label(self.hot, text="%d (%d)" % (x["n"], x["c"]), bg=PANEL,
                     fg=BLUE, font=("Segoe UI", 10, "bold"), padx=6,
                     pady=1).pack(side="left", padx=2, pady=1)
        for w in self.cold.winfo_children():
            w.destroy()
        for x in st["overdue"]:
            tk.Label(self.cold, text="%d (%d тир.)" % (x["n"], x["since"]),
                     bg=PANEL, fg=RED, font=("Segoe UI", 10, "bold"),
                     padx=6, pady=1).pack(side="left", padx=2, pady=1)
        ps = st["plus"]
        self.plus_lbl.config(text="Плюс-шар: 1 — %d · 2 — %d · 3 — %d · 4 — %d"
                             % (ps[1], ps[2], ps[3], ps[4]))
        if log:
            self._render_log(log)

    # ---------- Мои комбинации ----------

    def _add_my(self):
        import re
        nums = [int(x) for x in re.findall(r"\d+", self.my_entry.get())]
        if len(set(nums)) != 6 or not all(1 <= x <= 45 for x in nums):
            self.meta.config(text="Нужно ровно 6 разных чисел от 1 до 45")
            return
        combo = sorted(set(nums))
        combos = load_my()
        if combo not in combos:
            combos.append(combo)
            save_my(combos)
        self.my_entry.delete(0, "end")
        self._render_my_list()

    def _del_my(self, combo):
        save_my([c for c in load_my() if c != combo])
        self._render_my_list()

    def _gen_crowd(self):
        """Случайный «антитолпа»-билет: упор на числа >31 и редко
        отмечаемые, без троек подряд — чтобы не делить приз с толпой."""
        import random
        unpop_low = {12, 24}
        weights = {x: (3.0 if x > 31 or x in unpop_low else 1.0)
                   for x in range(1, 46)}
        for _ in range(300):
            pool = list(range(1, 46))
            chosen = []
            for _ in range(6):
                tot = sum(weights[x] for x in pool)
                r = random.random() * tot
                for i, x in enumerate(pool):
                    r -= weights[x]
                    if r <= 0:
                        chosen.append(pool.pop(i))
                        break
            chosen.sort()
            if sum(1 for x in chosen if x > 31) < 3:
                continue
            if any(chosen[i + 1] == chosen[i] + 1 and
                   chosen[i + 2] == chosen[i] + 2 for i in range(4)):
                continue
            combos = load_my()
            if chosen not in combos:
                combos.append(chosen)
                save_my(combos)
            self._render_my_list()
            return

    def _render_my_list(self):
        for w in self.my_list.winfo_children():
            w.destroy()
        last = self._my_last_draw
        combos = load_my()
        if not combos:
            tk.Label(self.my_list, text="пока пусто — добавьте свои числа",
                     bg=BG, fg=FG2, font=("Segoe UI", 9)).pack(anchor="w")
            return
        for c in combos:
            row = tk.Frame(self.my_list, bg=BG)
            row.pack(anchor="w", pady=1)
            hits = set(c) & set(last) if last else set()
            for n in c:
                hit = n in hits
                tk.Label(row, text=str(n), bg=PANEL,
                         fg=GREEN if hit else FG2,
                         font=("Segoe UI", 10,
                               "bold" if hit else "normal"),
                         padx=6, pady=1).pack(side="left", padx=2)
            if last:
                k = len(hits)
                tk.Label(row,
                         text="совпало: %d%s" % (k, " — призовое! 🎉"
                                                 if k >= 3 else ""),
                         bg=BG, fg=GREEN if k >= 3 else FG2,
                         font=("Segoe UI", 9, "bold" if k >= 3
                               else "normal")).pack(side="left", padx=8)
            recent = getattr(self, "_recent_draws", None)
            if recent:
                n3 = sum(1 for m in recent if len(set(c) & set(m)) >= 3)
                tk.Label(row, text="3+ за 100 тир.: %d" % n3,
                         bg=BG, fg=FG2, font=("Segoe UI", 8)
                         ).pack(side="left")
            tk.Button(row, text="✕", command=lambda cc=list(c): self._del_my(cc),
                      bg=BG, fg=RED, relief="flat", font=("Segoe UI", 8),
                      cursor="hand2").pack(side="left")

    # ---------- Развёрнутые ставки ----------

    def _calc_bet(self):
        try:
            n = int(self.bet_n.get())
            price = float(self.bet_price.get().replace(",", "."))
            ppl = max(1, int(self.bet_ppl.get()))
        except ValueError:
            self.bet_out.config(text="Введите число от 7 до 19, цену и число "
                                     "участников цифрами")
            return
        n = max(7, min(19, n))
        from math import comb
        combos = comb(n, 6)
        total = combos * price
        full = comb(45, 6)
        # вероятность, что среди выбранных n чисел окажется ровно j выигрышных
        def p(j):
            return comb(n, j) * comb(45 - n, 6 - j) / full
        p6 = p(6)
        p5 = p(5) + p6
        p4 = p(4) + p5
        p3 = p(3) + p4
        one_in = round(full / combos)
        lines = [
            "%d чисел = %d комбинаций · стоимость %s ₽" %
            (n, combos, ("%s" % total).rstrip("0").rstrip(".")),
            "Шанс суперприза (6 из 6): 1 к %s (%.4f%%)" %
            (f"{one_in:,}".replace(",", " "), p6 * 100),
            "Поймать 5+ чисел тиража: %.2f%% · 4+: %.1f%% · 3+: %.1f%%" %
            (p5 * 100, p4 * 100, p3 * 100),
        ]
        if ppl > 1:
            lines.append("Синдикат из %d чел.: по %s ₽ с человека, "
                         "выигрыш делится на %d" %
                         (ppl, ("%s" % (total / ppl)).rstrip("0").rstrip("."),
                          ppl))
        lines.append("Честно: цена растёт ровно пропорционально шансу — "
                     "ожидание выигрыша то же, что и у обычных билетов.")
        self.bet_out.config(text="\n".join(lines))

    def _render_log(self, log):
        self._log = log
        t = self.log_text
        t.config(state="normal")
        t.delete("1.0", "end")
        names = (("main", "Прогноз", "hit_main"),
                 ("alt", "Запасной", "hit_alt"),
                 ("crowd", "Антитолпа", "hit_crowd"))
        # сводка: сколько раз было 3+ совпадений за журнал
        summ = {}
        for key, _, _ in names:
            c3 = c4 = c5 = 0
            for e in log:
                combo = e.get(key)
                if not combo:
                    continue
                k = len(set(combo) & set(e["draw"]))
                c3 += k >= 3; c4 += k >= 4; c5 += k >= 5
            summ[key] = (c3, c4, c5)
        self.log_summary.config(
            text="за %d тиражей — 3+ совпадения: прогноз %d, запасной %d, "
                 "антитолпа %d (из них 4+: %d / %d / %d; 5+: %d / %d / %d)"
                 % (len(log), summ["main"][0], summ["alt"][0],
                    summ["crowd"][0], summ["main"][1], summ["alt"][1],
                    summ["crowd"][1], summ["main"][2], summ["alt"][2],
                    summ["crowd"][2]))
        min_hits = 2 if self.log_filter.get() else 0
        shown = 0
        for e in reversed(log):
            hits = [len(set(e[k]) & set(e["draw"])) for k, _, _ in names
                    if e.get(k)]
            if min_hits and (not hits or max(hits) < min_hits):
                continue
            shown += 1
            t.insert("end", "№%d %s  выпало: " % (e["n"], e["date"]), "hdr")
            t.insert("end", " ".join("%2d" % x for x in e["draw"]), "draw")
            if e.get("plus"):
                t.insert("end", " +%d" % e["plus"], "draw")
            for key, label, tag in names:
                combo = e.get(key)
                t.insert("end", "   %s: " % label, "hdr")
                if not combo:
                    t.insert("end", "—", "miss")
                    continue
                hit = set(e["draw"])
                parts = []
                for n in combo:
                    parts.append(("%2d" % n, tag if n in hit else "miss"))
                k = len(set(combo) & hit)
                for j, (s, tg) in enumerate(parts):
                    if j:
                        t.insert("end", " ", "miss")
                    t.insert("end", s, tg)
                t.insert("end", " (%d)" % k,
                         tag if k >= 3 else "miss")
            t.insert("end", "\n")
        if min_hits:
            t.insert("end", "— показано %d из %d тиражей (фильтр 2+) —\n"
                     % (shown, len(log)), "hdr")
        t.config(state="disabled")

    def _rerender_log(self):
        if getattr(self, "_log", None):
            self._render_log(self._log)

    def _draw_chart(self, st):
        c = self.chart
        c.delete("all")
        freq = st["freq"]
        hot = {x["n"] for x in st["hot"]}
        ovd = {x["n"] for x in st["overdue"]}
        c.update_idletasks()
        W = max(c.winfo_width(), 680)
        H = 190
        pad_b, pad_t = 22, 12
        maxv = max(x["c"] for x in freq) or 1
        bw = (W - 16) / 45.0
        for i, x in enumerate(freq):
            h = (H - pad_t - pad_b) * x["c"] / maxv
            x0 = 8 + i * bw
            color = BLUE if x["n"] in hot else "#565864"
            c.create_rectangle(x0 + 1, H - pad_b - h, x0 + bw - 1, H - pad_b,
                               fill=color, outline="")
            if x["n"] in ovd:
                cx = x0 + bw / 2
                c.create_oval(cx - 2.5, H - pad_b - h - 8, cx + 2.5,
                              H - pad_b - h - 3, fill=RED, outline="")
            if x["n"] % 5 == 0 or x["n"] == 1:
                c.create_text(x0 + bw / 2, H - 10, text=str(x["n"]),
                              fill=FG2, font=("Segoe UI", 8))


if __name__ == "__main__":
    App().mainloop()
