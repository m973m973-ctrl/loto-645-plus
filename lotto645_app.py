# -*- coding: utf-8 -*-
"""Лото 6/45 Плюс — настольное приложение статистики тиражей.

Версия с вкладками (закладками): каждый раздел — отдельная вкладка,
все длинные разделы прокручиваются (исправлено: окно рейтинга
не помещалось и не скроллилось).

Вкладки:
  «6 из 45 Плюс»   — последний тираж, прогнозы, частотный график;
  «Инструменты»    — развёрнутая ставка, синдикат, мои комбинации;
  «Рейтинг лотерей»— сравнение игр Столото (с прокруткой);
  «Проверка прогнозов» — журнал последних 100 тиражей;
  «Русское лото»   — правила, последний тираж, проверка билета;
  «4 из 20»        — правила, последний тираж, проверка комбинации;
  «Жилищная лотерея» — правила, последний тираж, проверка билета.

Данные: публичный архив stoloto.ru (коды игр: 6x45plus, ruslotto, 4x20, gzhl).
"""
import json
import os
import sys
import threading
import time
import urllib.request
import tkinter as tk
from tkinter import ttk
from datetime import datetime, timezone, timedelta

API = ("https://www.stoloto.ru/p/api/mobile/api/v35/service/draws/archive"
       "?game={game}&count={count}&page={page}")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 Chrome/150.0 Safari/537.36"),
    "Gosloto-Partner": "bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg",
}
PAGES = 6  # ~300 последних тиражей 6/45 Плюс
MSK = timezone(timedelta(hours=3))

BG = "#1e1f24"
PANEL = "#26272e"
PANEL2 = "#33343c"
FG = "#f2f2f2"
FG2 = "#9a9aa3"
BLUE = "#4c7dff"
RED = "#d24a43"
GOLD = "#e8b23f"
GREEN = "#3fae6a"

LOG_NAME = "predictions_log.json"
MY_NAME = "my_combos.json"


# ---------- Сравнение лотерей ----------

def _pmatch(n, k, d, j):
    """Вероятность угадать ровно j из d выпавших, отметив k из n."""
    from math import comb
    return comb(d, j) * comb(n - d, k - j) / comb(n, k)


def _p_ge(n, k, d, jmin):
    return sum(_pmatch(n, k, d, j) for j in range(jmin, min(k, d) + 1))


# (название, ставка ₽, [(приз ₽, вероятность)] | "bingo", суперприз 1 к N,
#  примечание)
# Призовые суммы — по опубликованным правилам, примерные (могут меняться).
def _games():
    from math import comb
    g = []
    # 5 из 36 (клава): 5 из 36 + 1 из 4
    p = lambda j: _pmatch(36, 5, 5, j)
    g.append(("5 из 36", 75, [(75, p(2)), (750, p(3)), (7500, p(4)),
                              (100000, p(5) * 3 / 4)], 1507968, ""))
    # 6 из 45
    p = lambda j: _pmatch(45, 6, 6, j)
    g.append(("6 из 45", 50, [(50, p(2)), (400, p(3)), (2000, p(4)),
                              (100000, p(5))], 8145060, ""))
    # 6 из 45 Плюс
    p = lambda j: _pmatch(45, 6, 6, j)
    g.append(("6 из 45 Плюс", 100, [(100, p(2)), (500, p(3)), (3000, p(4)),
                                    (100000, p(5))], 8145060, ""))
    # 7 из 49
    p = lambda j: _pmatch(49, 7, 7, j)
    g.append(("7 из 49", 40, [(150, p(3)), (1500, p(4)), (15000, p(5)),
                              (1500000, p(6))], 85900584, ""))
    # 4 из 20: выигрыш, если совпало >=2 чисел хотя бы в одном поле.
    # a — совпадения в поле 1, b — в поле 2 (независимы).
    p1 = {j: _pmatch(20, 4, 4, j) for j in range(5)}
    p_win = sum(pa * pb for a, pa in p1.items() for b, pb in p1.items()
                if (a >= 2 or b >= 2) and not (a == 4 and b == 4))
    p_big = sum(pa * pb for a, pa in p1.items() for b, pb in p1.items()
                if (a >= 3 or b >= 3) and not (a == 4 and b == 4))
    g.append(("4 из 20", 250, [(250, p_win), (1000, p_big)], 23474025,
              "призовой фонд 67% — самый высокий у Столото; 21 выигрышная "
              "категория (от «2+0» до «4+4»)"))
    # Рапидо: 8 из 20 + 1 из 4
    p = lambda j: _pmatch(20, 8, 8, j)
    g.append(("Рапидо", 60, [(60, p(4) * 3 / 4), (200, p(5) * 3 / 4),
                             (600, p(5) / 4), (1000, p(6) * 3 / 4),
                             (3000, p(6) / 4), (4000, p(7) * 3 / 4),
                             (15000, p(7) / 4), (60000, p(8) * 3 / 4)],
              503880, ""))
    # Всё или ничего (12 из 24): симметрия j и 12-j
    p = lambda j: _pmatch(24, 12, 12, j) + _pmatch(24, 12, 12, 12 - j)
    g.append(("Всё или ничего", 100, [(100, p(4)), (300, p(3)),
                                      (1500, p(2)), (15000, p(1))],
              1352078, ""))
    # Бинго-лотереи (90 бочонков, билет 2 поля x 15 чисел) — другая модель,
    # вероятности по статистике оператора, оценочно.
    jack_bingo = comb(90, 15) // 2  # закрыть одно из 2 полей за 15 ходов
    g.append(("Русское лото", 200, ("bingo", 1 / 2.5), jack_bingo,
              "тиражи по воскресеньям; любой приз ≈ 1 из 2,5 билетов "
              "(статистика оператора); суперприз сейчас 800 млн ₽"))
    g.append(("Жилищная лотерея", 150, ("bingo", 1 / 3), jack_bingo,
              "тиражи по воскресеньям; главные призы — квартиры и дома "
              "(разыграно 4500+); выигрывает ≈ каждый 3-й билет"))
    return g


def games_rating(min_prize):
    """Рейтинг: шанс выигрыша не меньше min_prize ₽ за одну ставку."""
    rows = []
    for name, price, cats, jack, note in _games():
        if isinstance(cats, tuple) and cats[0] == "bingo":
            # оценка по статистике оператора: шанс любого приза
            p_any = cats[1]
            p = (p_any if min_prize <= 150 else p_any / 6) + 1.0 / jack
            rows.append((name, price, p, jack, note))
        else:
            p = sum(prob for prize, prob in cats if prize >= min_prize)
            if jack:  # суперприз заведомо больше порога
                p += 1 / jack
            rows.append((name, price, p, jack, note))
    rows.sort(key=lambda r: -r[2])
    return rows


def games_text(min_prize):
    lines = ["Шанс выиграть ≥ %d ₽ за одну ставку (лучшие сверху):"
             % min_prize, ""]
    for i, (name, price, p, jack, note) in enumerate(games_rating(min_prize), 1):
        lines.append("%d. %s (ставка ~%d ₽) — 1 к %.1f, суперприз 1 к %s"
                     % (i, name, price, 1 / p,
                        f"{jack:,}".replace(",", " ")))
        if note:
            lines.append("     " + note)
    lines += ["",
              "Суммы призов и цены билетов примерные, по опубликованным "
              "правилам — уточняйте на stoloto.ru.",
              "Бинго-лотереи (Русское лото, Жилищная) оценены по статистике "
              "оператора, а не по комбинаторной модели."]
    return "\n".join(lines)


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


# ---------- Загрузка тиражей (любая игра) ----------

def fetch_page(game, p, count=100, attempts=4):
    last = None
    for a in range(attempts):
        try:
            url = API.format(game=game, count=count, page=p)
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.5 * (a + 1))
    raise RuntimeError("страница %d: %s" % (p, last))


def fetch_draws():
    draws = []
    for p in range(1, PAGES + 1):
        payload = fetch_page("6x45plus", p)
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


def fetch_recent(game, count=100):
    """Свежие тиражи любой игры (одна страница архива)."""
    payload = fetch_page(game, 1, count=count, attempts=2)
    if payload.get("requestStatus") != "success":
        raise RuntimeError("Ошибка API: %s" % payload.get("errors"))
    return payload.get("draws", [])


# ---------- Бинго-лотереи: Русское лото и Жилищная лотерея ----------
# Билет: 2 поля, в каждом 3 строки по 5 чисел (15 чисел, всего 30 из 90).
# Тур 1: закрыта любая строка (5 чисел) бочонками 1-го тура.
# Тур 2: закрыто поле (15 чисел) бочонками туров 1-2.
# Тур 3: закрыты все 30 чисел бочонками туров 1-3.
# Туры 4+: каждая категория = один ход; выигрывает билет, все 30 чисел
# которого закрыты к этому ходу. Билет выигрывает один раз — в младшем туре.
# Джекпот: поле (15 чисел) закрыто на 15-м ходу.

def parse_bingo_draw(d):
    """Тираж бинго-лотереи из API -> структура для проверки билетов."""
    info = {"n": d.get("number"), "date": d.get("date", "")[:16].replace("T", " "),
            "superPrize": d.get("superPrize") or 0, "rounds": [],
            "not_played": []}
    st = (d.get("combination") or {}).get("structured")
    if isinstance(st, dict):
        info["not_played"] = [int(x) for x in st.get("notPlayed") or []]
    try:
        wc = json.loads(d.get("winningCategories") or "{}")
        cats = wc.get("main") or wc.get("categories") or []
        for c in sorted(cats, key=lambda c: c.get("winCat", 0)):
            nums = [int(x) for x in str(c.get("numbers") or "").split(",")
                    if x.strip().isdigit()]
            info["rounds"].append({"cat": c.get("winCat"),
                                   "amount": c.get("amount") or 0,
                                   "count": c.get("countWins") or 0,
                                   "numbers": nums})
    except Exception:
        pass
    return info


def bingo_check(rows6, info):
    """Проверка билета: rows6 — 6 строк по 5 чисел (строки 0-2 — поле 1,
    3-5 — поле 2). Возвращает dict с результатом."""
    rows = [set(r) for r in rows6]
    fields = [rows[0] | rows[1] | rows[2], rows[3] | rows[4] | rows[5]]
    all30 = fields[0] | fields[1]
    rounds = [set(r["numbers"]) for r in info["rounds"] if r["numbers"]]
    seq = [b for r in info["rounds"] for b in r["numbers"]]
    res = {"win": False, "tour": None, "what": "", "jackpot": False,
           "closed": len(all30 & set(seq)), "total": len(all30)}
    # джекпот: одно из полей полностью в первых 15 бочонках
    if len(seq) >= 15:
        first15 = set(seq[:15])
        for i, f in enumerate(fields, 1):
            if f and f <= first15:
                res.update(win=True, jackpot=True, tour=0,
                           what="ДЖЕКПОТ: поле %d закрыто на 15-м ходу!" % i)
                return res
    if not rounds:
        return res
    # тур 1 — строка
    if any(row and row <= rounds[0] for row in rows):
        res.update(win=True, tour=1,
                   what="1-й тур: закрыта горизонтальная строка")
        return res
    cum = rounds[0]
    # тур 2 — поле
    if len(rounds) > 1:
        cum = cum | rounds[1]
        for i, f in enumerate(fields, 1):
            if f and f <= cum:
                res.update(win=True, tour=2,
                           what="2-й тур: закрыто поле %d (15 чисел)" % i)
                return res
    # тур 3 — весь билет
    if len(rounds) > 2:
        cum = cum | rounds[2]
        if all30 and all30 <= cum:
            res.update(win=True, tour=3,
                       what="3-й тур: закрыты все 30 чисел билета")
            return res
    # дальнейшие ходы
    for k in range(3, len(rounds)):
        cum = cum | rounds[k]
        if all30 and all30 <= cum:
            res.update(win=True, tour=k + 1,
                       what="Тур %d: закрыты все 30 чисел билета" % (k + 1))
            return res
    return res


# ---------- Спортлото «4 из 20» ----------
# Два поля по 20 чисел, в каждом отмечают 4. Тираж: 4 числа в поле 1 и
# 4 числа в поле 2. Выигрыш: совпало >= 2 чисел хотя бы в одном поле
# (21 выигрышная категория). Суперприз: 4 + 4 (1 к 23 474 025).

def parse_4x20_draw(d):
    comb = (d.get("combination") or {}).get("structured") or []
    return {"n": d.get("number"), "date": d.get("date", "")[:16].replace("T", " "),
            "superPrize": d.get("superPrize") or 0,
            "f1": sorted(int(x) for x in comb[:4]),
            "f2": sorted(int(x) for x in comb[4:8])}


def check_4x20(f1, f2, draw):
    """a совпадений в поле 1, b — в поле 2; выигрыш при a>=2 или b>=2."""
    a = len(set(f1) & set(draw["f1"]))
    b = len(set(f2) & set(draw["f2"]))
    win = a >= 2 or b >= 2
    sup = a == 4 and b == 4
    return {"a": a, "b": b, "win": win, "super": sup}


# ---------- Рапидо ----------
# Поле 1: 8 чисел из 20; поле 2: 1 число из 4. Тиражи каждые ~15 минут.
# Классическая таблица выигрышей: от 4 совпадений в поле 1 при угаданном
# числе поля 2 и от 5 совпадений без него; суперприз — 8 + 1.

def parse_rapido_draw(d):
    st = (d.get("combination") or {}).get("structured") or {}
    played = [int(x) for x in (st.get("played") or [])]
    return {"n": d.get("number"), "date": d.get("date", "")[:16].replace("T", " "),
            "superPrize": d.get("superPrize") or 0,
            "f1": sorted(played[:8]), "f2": played[8] if len(played) > 8 else None,
            "parity": st.get("parity") or ""}


def check_rapido(f1_8, f2_1, draw):
    """f1_8 — 8 чисел поля 1; f2_1 — число поля 2 (или None)."""
    a = len(set(f1_8) & set(draw["f1"]))
    b = 1 if (f2_1 is not None and f2_1 == draw["f2"]) else 0
    win = a >= 5 or (a == 4 and b == 1)
    sup = a == 8 and b == 1
    return {"a": a, "b": b, "win": win, "super": sup}


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


# ---------- Тексты вкладок ----------

RUSLOTO_INFO = """\
РУССКОЕ ЛОТО — классическая бинго-лотерея (90 бочонков).

• Тиражи: раз в неделю, по воскресеньям (трансляция на НТВ утром).
  Продажа билетов на тираж закрывается накануне вечером.
• Билет: 2 поля, в каждом 15 чисел от 1 до 90 (3 строки по 5 чисел).
• Призовой фонд: 50% от продаж. Суперприз: от 800 000 000 ₽.
• По статистике оператора выигрывает примерно каждый 2,5-й билет.

Как определяется выигрыш (по турам):
  1-й тур — совпали все 5 чисел любой горизонтальной строки;
  2-й тур — совпали все 15 чисел одного поля;
  3-й тур и далее — совпали все 30 чисел билета (каждый следующий
  тур = один ход ведущего). Игра идёт, пока не останется 3-4 бочонка.
  ДЖЕКПОТ: поле из 15 чисел закрыто уже на 15-м ходу.
"""

ZHILOTO_INFO = """\
ЖИЛИЩНАЯ ЛОТЕРЕЯ — бинго-лотерея с недвижимостью (90 шаров).

• Тиражи: раз в неделю, по воскресеньям (НТВ, утро).
• Билет: 2 поля по 15 чисел от 1 до 90 — механика как у Русского лото.
• Главные призы: квартиры, загородные дома, дачи (за историю лотереи
  разыграно 4 500+ объектов недвижимости) + денежные призы.
• Призовой фонд: 50% от продаж.

Выигрыш по турам — как в Русском лото:
  1-й тур — закрыта строка из 5 чисел; 2-й тур — поле (15 чисел);
  3-й и далее — все 30 чисел билета. Билет выигрывает один раз,
  в самом раннем туре.
"""

RAPIDO_INFO = """\
РАПИДО — самая частая лотерея Столото.

• Тиражи: каждые ~15 минут, ежедневно.
• Ставка: 8 чисел из 20 (поле 1) + 1 число из 4 (поле 2).
• По статистике оператора любой выигрыш — примерно 1 : 3,1,
  это лучший шанс вернуть деньги среди лотерей Столото.
• Суперприз: 8 + 1 (растёт от тиража к тиражу).

Как определяется выигрыш:
  считаются совпадения в поле 1 (a = 0..8) и поле 2 (b = 0..1);
  выигрышные категории — от «4+1» и «5+0» и выше, всего 9 категорий;
  суперприз — совпадение 8 + 1. Точные суммы — на stoloto.ru.
"""

X4_20_INFO = """\
СПОРТЛОТО «4 из 20» — рекордные суперпризы.

• Тиражи: ежедневно, несколько раз в день.
• Ставка: 4 числа из 20 (поле 1) + 4 числа из 20 (поле 2).
• Призовой фонд: 67% от продаж — самый высокий у Столото.
• Суперприз: сотни миллионов ₽ (совпадение 4 + 4, шанс 1 к 23 474 025).
  По статистике оператора лотерея чаще других делает миллионеров.

Как определяется выигрыш:
  a — совпадения в поле 1, b — в поле 2. Выигрыш при a >= 2 или b >= 2:
  всего 21 выигрышная категория («2+0», «2+1», «2+2», ..., «4+4»).
  Чем больше совпадений — тем крупнее приз; «4+4» — суперприз.
"""


class Ball(tk.Canvas):
    def __init__(self, master, n, size=36, outline=FG, fill=PANEL, fg=FG):
        super().__init__(master, width=size, height=size, bg=BG,
                         highlightthickness=0)
        self.create_oval(2, 2, size - 2, size - 2, outline=outline,
                         fill=fill, width=2)
        self.create_text(size / 2, size / 2, text=str(n), fill=fg,
                         font=("Segoe UI", int(size * 0.38), "bold"))


class ScrollFrame(tk.Frame):
    """Прокручиваемый контейнер: содержимое кладётся в .inner.
    Исправляет «раздел не помещается и не скроллится»."""

    def __init__(self, master, **kw):
        super().__init__(master, bg=BG, **kw)
        self.canvas = tk.Canvas(self, bg=BG, highlightthickness=0)
        self.sb = tk.Scrollbar(self, orient="vertical",
                               command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=self.sb.set)
        self.sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.inner,
                                              anchor="nw")
        self.inner.bind("<Configure>", self._on_inner)
        self.canvas.bind("<Configure>", self._on_canvas)

    def _on_inner(self, _=None):
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _on_canvas(self, e):
        self.canvas.itemconfigure(self._win, width=e.width)

    def wheel(self, e):
        if getattr(e, "num", None) == 4 or getattr(e, "delta", 0) > 0:
            self.canvas.yview_scroll(-2, "units")
        else:
            self.canvas.yview_scroll(2, "units")


def _lbl(parent, text, fg=FG2, size=10, bold=False, justify="left"):
    return tk.Label(parent, text=text, bg=BG, fg=fg, justify=justify,
                    font=("Segoe UI", size, "bold" if bold else "normal"))


def _entry(parent, width=24):
    return tk.Entry(parent, width=width, bg=PANEL, fg=FG, relief="flat",
                    font=("Segoe UI", 10), insertbackground=FG)


def _btn(parent, text, command, color=BLUE):
    return tk.Button(parent, text=text, command=command, bg=color, fg="white",
                     relief="flat", font=("Segoe UI", 9), padx=10,
                     cursor="hand2")


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Лотереи Столото — статистика и проверка билетов")
        self.configure(bg=BG)
        try:
            ic = resource_path("loto.ico")
            if ic:
                self.iconbitmap(ic)
        except Exception:
            pass
        self.geometry("820x900")
        self.minsize(680, 560)
        self._game_draws = {}   # код игры -> {номер тиража: разобранный тираж}
        self._build()
        self.after(200, self.refresh)

    AUTO_MS = 15 * 60 * 1000  # автообновление каждые 15 минут

    # ---------- каркас ----------

    def _build(self):
        top = tk.Frame(self, bg=BG)
        top.pack(fill="x", padx=16, pady=(14, 4))
        _lbl(top, "Лотереи Столото — статистика", fg=FG, size=15,
             bold=True).pack(side="left")
        self.btn = tk.Button(top, text="Обновить", command=self.refresh,
                             bg=BLUE, fg="white", relief="flat",
                             font=("Segoe UI", 10), padx=14, pady=4,
                             cursor="hand2")
        self.btn.pack(side="right")

        self.meta = _lbl(self, "Загрузка…", size=9)
        self.meta.pack(anchor="w", padx=16)

        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("TNotebook", background=BG, borderwidth=0)
        style.configure("TNotebook.Tab", background=PANEL, foreground=FG2,
                        padding=(12, 6), font=("Segoe UI", 10))
        style.map("TNotebook.Tab", background=[("selected", PANEL2)],
                  foreground=[("selected", FG)])

        self.nb = ttk.Notebook(self)
        self.nb.pack(fill="both", expand=True, padx=10, pady=(4, 10))

        self._build_tab_main()
        self._build_tab_tools()
        self._build_tab_rating()
        self._build_tab_log()
        self._build_tab_bingo("ruslotto", "Русское лото", RUSLOTO_INFO)
        self._build_tab_rapido()
        self._build_tab_4x20()
        self._build_tab_bingo("gzhl", "Жилищная лотерея", ZHILOTO_INFO)

        _lbl(self, "Все комбинации равновероятны — статистика не повышает "
                   "шансы. «Антитолпа» лишь уменьшает риск делить приз "
                   "с другими игроками.", size=9).pack(anchor="w", padx=16,
                                                       pady=(0, 8))
        # прокрутка колесом мыши — во всех вкладках со ScrollFrame
        self.bind_all("<MouseWheel>", self._global_wheel)
        self.bind_all("<Button-4>", self._global_wheel)
        self.bind_all("<Button-5>", self._global_wheel)

    def _global_wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        while w is not None:
            if isinstance(w, ScrollFrame):
                w.wheel(e)
                return
            w = getattr(w, "master", None)

    # ---------- вкладка «6 из 45 Плюс» ----------

    def _build_tab_main(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text="6 из 45 Плюс")
        f = sf.inner

        self.last = _lbl(f, "", fg=FG, size=11)
        self.last.pack(anchor="w", padx=16, pady=(6, 0))

        fr = tk.Frame(f, bg=BG); fr.pack(fill="x", padx=16, pady=(10, 0))
        self.rows = {}
        for key, label in (("main", "Предлагаемая комбинация"),
                           ("alt", "Запасная"),
                           ("crowd", "«Антитолпа» — реже всего отмечают игроки")):
            _lbl(fr, label).pack(anchor="w")
            row = tk.Frame(fr, bg=BG); row.pack(anchor="w", pady=2)
            bt = _lbl(fr, "", size=9)
            bt.pack(anchor="w", pady=(0, 6))
            self.rows[key] = (row, bt)

        self.chart_lbl = _lbl(f, "")
        self.chart_lbl.pack(anchor="w", padx=16, pady=(6, 0))
        self.chart = tk.Canvas(f, bg=PANEL, highlightthickness=0, height=190)
        self.chart.pack(fill="x", padx=16, pady=4)

        lists = tk.Frame(f, bg=BG); lists.pack(fill="x", padx=16, pady=8)
        left = tk.Frame(lists, bg=BG); left.pack(side="left", anchor="n")
        _lbl(left, "Горячие (последние 100 тиражей)").pack(anchor="w")
        self.hot = tk.Frame(left, bg=BG); self.hot.pack(anchor="w", pady=2)
        right = tk.Frame(lists, bg=BG); right.pack(side="left", anchor="n",
                                                   padx=(40, 0))
        _lbl(right, "Давно не выпадали").pack(anchor="w")
        self.cold = tk.Frame(right, bg=BG); self.cold.pack(anchor="w", pady=2)

        self.plus_lbl = _lbl(f, "")
        self.plus_lbl.pack(anchor="w", padx=16, pady=(0, 12))

    # ---------- вкладка «Инструменты» ----------

    def _build_tab_tools(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text="Инструменты")
        f = sf.inner

        # --- калькулятор развёрнутой ставки ---
        bet = tk.Frame(f, bg=BG)
        bet.pack(fill="x", padx=16, pady=(12, 0))
        _lbl(bet, "Развёрнутая ставка — чисел:", fg=FG, bold=True
             ).pack(side="left")
        self.bet_n = tk.Spinbox(bet, from_=7, to=19, width=3, bg=PANEL, fg=FG,
                                buttonbackground=PANEL, relief="flat",
                                font=("Segoe UI", 10), insertbackground=FG,
                                command=self._calc_bet)
        self.bet_n.pack(side="left", padx=(6, 14))
        _lbl(bet, "цена комбинации, ₽:").pack(side="left")
        self.bet_price = _entry(bet, 6)
        self.bet_price.insert(0, "100")
        self.bet_price.pack(side="left", padx=6)
        _lbl(bet, "человек:").pack(side="left")
        self.bet_ppl = _entry(bet, 4)
        self.bet_ppl.insert(0, "1")
        self.bet_ppl.pack(side="left", padx=6)
        _btn(bet, "Посчитать", self._calc_bet).pack(side="left", padx=8)
        self.bet_out = _lbl(f, "", fg=FG, size=9)
        self.bet_out.pack(anchor="w", padx=16, pady=(2, 0))

        # --- мои комбинации ---
        _lbl(f, "Мои комбинации — программа сама проверит их по каждому "
                "новому тиражу", fg=FG, bold=True).pack(anchor="w", padx=16,
                                                        pady=(16, 0))
        myfr = tk.Frame(f, bg=BG)
        myfr.pack(fill="x", padx=16, pady=(2, 0))
        _lbl(myfr, "6 чисел через пробел:", size=9).pack(side="left")
        self.my_entry = _entry(myfr, 16)
        self.my_entry.pack(side="left", padx=6)
        _btn(myfr, "Добавить", self._add_my).pack(side="left")
        _btn(myfr, "🎲 Антитолпа", self._gen_crowd, color=PANEL
             ).pack(side="left", padx=8)
        self.my_list = tk.Frame(f, bg=BG)
        self.my_list.pack(fill="x", padx=16, pady=(2, 12))
        self._my_last_draw = None
        self._render_my_list()

    # ---------- вкладка «Рейтинг лотерей» ----------

    def _build_tab_rating(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="Рейтинг лотерей")

        cmpf = tk.Frame(f, bg=BG)
        cmpf.pack(fill="x", padx=16, pady=(12, 4))
        _lbl(cmpf, "Сравнение лотерей — мин. выигрыш, ₽:", fg=FG, bold=True
             ).pack(side="left")
        self.cmp_min = _entry(cmpf, 6)
        self.cmp_min.insert(0, "100")
        self.cmp_min.pack(side="left", padx=6)
        _btn(cmpf, "Показать рейтинг", self._calc_games).pack(side="left")

        # рейтинг — прокручиваемое текстовое поле (раньше не влезало
        # в окно и не скроллилось)
        box = tk.Frame(f, bg=PANEL)
        box.pack(fill="both", expand=True, padx=16, pady=(4, 12))
        sb = tk.Scrollbar(box)
        sb.pack(side="right", fill="y")
        self.cmp_out = tk.Text(box, bg=PANEL, fg=FG, relief="flat",
                               font=("Consolas", 10), wrap="word",
                               yscrollcommand=sb.set, cursor="arrow")
        self.cmp_out.pack(side="left", fill="both", expand=True)
        sb.config(command=self.cmp_out.yview)
        self.cmp_out.config(state="disabled")

    # ---------- вкладка «Проверка прогнозов» ----------

    def _build_tab_log(self):
        f = tk.Frame(self.nb, bg=BG)
        self.nb.add(f, text="Проверка прогнозов")

        _lbl(f, "Проверка прогнозов на последних 100 тиражах (цветные — "
                "совпали: синий — прогноз, золотой — запасной, "
                "зелёный — антитолпа)", size=9).pack(anchor="w", padx=16,
                                                     pady=(12, 0))
        self.log_summary = _lbl(f, "", fg=FG, size=9, bold=True)
        self.log_summary.pack(anchor="w", padx=16)
        self.log_filter = tk.IntVar(value=1)
        tk.Checkbutton(f, text="Показывать только тиражи с 2 и более "
                               "совпадениями", variable=self.log_filter,
                       bg=BG, fg=FG2, selectcolor=PANEL,
                       activebackground=BG, activeforeground=FG,
                       font=("Segoe UI", 9),
                       command=self._rerender_log).pack(anchor="w", padx=16)
        log_fr = tk.Frame(f, bg=PANEL)
        log_fr.pack(fill="both", expand=True, padx=16, pady=(2, 12))
        sb = tk.Scrollbar(log_fr)
        sb.pack(side="right", fill="y")
        self.log_text = tk.Text(log_fr, bg=PANEL, fg=FG, relief="flat",
                                font=("Consolas", 9),
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


    # ---------- вкладки бинго-лотерей (Русское лото, Жилищная) ----------

    def _build_tab_bingo(self, game, title, info_text):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text=title)
        f = sf.inner

        _lbl(f, info_text, size=9).pack(anchor="w", padx=16, pady=(10, 0))

        ctrl = tk.Frame(f, bg=BG)
        ctrl.pack(fill="x", padx=16, pady=(8, 0))
        _lbl(ctrl, "Номер тиража:", fg=FG, bold=True).pack(side="left")
        num = _entry(ctrl, 8)
        num.pack(side="left", padx=6)
        out = _lbl(f, "Загрузите тираж — или оставьте номер пустым: "
                      "возьмётся последний.", size=9)
        out.pack(anchor="w", padx=16, pady=(4, 0))

        state = {"game": game, "num": num, "out": out, "draw": None}

        _btn(ctrl, "Загрузить тираж",
             lambda: self._load_game_draw(state)).pack(side="left", padx=4)

        _lbl(f, "Проверка билета — введите 6 строк по 5 чисел (1–90):",
             fg=FG, bold=True).pack(anchor="w", padx=16, pady=(12, 2))
        rows_e = []
        for i in range(6):
            rf = tk.Frame(f, bg=BG)
            rf.pack(anchor="w", padx=16, pady=1)
            _lbl(rf, "Поле %d, строка %d:" % (i // 3 + 1, i % 3 + 1),
                 size=9).pack(side="left")
            e = _entry(rf, 26)
            e.pack(side="left", padx=6)
            rows_e.append(e)
        res = _lbl(f, "", fg=GOLD, size=10, bold=True)
        res.pack(anchor="w", padx=16, pady=(6, 12))
        state["rows"] = rows_e
        state["res"] = res
        _btn(f, "Проверить билет", lambda: self._check_bingo(state),
             color=GREEN).pack(anchor="w", padx=16, pady=(0, 16))

    def _load_game_draw(self, state):
        state["out"].config(text="Загрузка…")
        threading.Thread(target=self._load_game_draw_bg, args=(state,),
                         daemon=True).start()

    def _load_game_draw_bg(self, state):
        try:
            draws = fetch_recent(state["game"], 100)
            parsed = {}
            for d in draws:
                if state["game"] in ("ruslotto", "gzhl"):
                    p = parse_bingo_draw(d)
                elif state["game"] == "4x20":
                    p = parse_4x20_draw(d)
                else:
                    p = parse_rapido_draw(d)
                if p.get("n") is not None:
                    parsed[p["n"]] = p
            self.after(0, lambda: self._show_game_draw(state, parsed, None))
        except Exception as e:
            self.after(0, lambda: self._show_game_draw(state, None, e))

    def _show_game_draw(self, state, parsed, err):
        if err:
            state["out"].config(text="Ошибка загрузки: %s" % err)
            return
        cache = self._game_draws.setdefault(state["game"], {})
        cache.update(parsed)
        want = state["num"].get().strip()
        if want.isdigit() and int(want) in cache:
            d = cache[int(want)]
        else:
            d = cache[max(cache)]  # последний тираж
            if want and not (want.isdigit() and int(want) in cache):
                state["out"].config(
                    text="Тираж №%s не найден среди последних 100 — "
                         "показан последний." % want)
                state["out"].after(4000, lambda: None)
        state["draw"] = d
        if state["game"] in ("ruslotto", "gzhl"):
            np_ = ", ".join(map(str, d["not_played"])) or "—"
            tours = []
            for r in d["rounds"][:8]:
                if r["count"]:
                    tours.append("тур %d: %d побед. по %s ₽"
                                 % (r["cat"], r["count"],
                                    f"{r['amount']:,}".replace(",", " ")))
            txt = ("Тираж №%s (%s). Не выпали бочонки: %s.\n"
                   "Суперприз: %s ₽.\n%s"
                   % (d["n"], d["date"], np_,
                      f"{d['superPrize']:,}".replace(",", " "),
                      "\n".join(tours) if tours else ""))
        elif state["game"] == "4x20":
            txt = ("Тираж №%s (%s): поле 1: %s · поле 2: %s · "
                   "суперприз %s ₽"
                   % (d["n"], d["date"], " ".join(map(str, d["f1"])),
                      " ".join(map(str, d["f2"])),
                      f"{d['superPrize']:,}".replace(",", " ")))
        else:  # rapido
            txt = ("Тираж №%s (%s): поле 1: %s · поле 2: %s · "
                   "суперприз %s ₽"
                   % (d["n"], d["date"], " ".join(map(str, d["f1"])),
                      d["f2"], f"{d['superPrize']:,}".replace(",", " ")))
        state["out"].config(text=txt)

    def _check_bingo(self, state):
        import re
        d = state.get("draw")
        if not d:
            state["res"].config(text="Сначала нажмите «Загрузить тираж»",
                                fg=RED)
            return
        rows = []
        for e in state["rows"]:
            nums = [int(x) for x in re.findall(r"\d+", e.get())]
            if len(nums) != 5 or len(set(nums)) != 5 or \
                    not all(1 <= x <= 90 for x in nums):
                state["res"].config(
                    text="В каждой строке должно быть ровно 5 разных "
                         "чисел от 1 до 90", fg=RED)
                return
            rows.append(nums)
        flat = [x for r in rows for x in r]
        if len(set(flat)) != 30:
            state["res"].config(text="Все 30 чисел билета должны быть "
                                     "разными", fg=RED)
            return
        r = bingo_check(rows, d)
        if r["jackpot"]:
            state["res"].config(text="🎉 " + r["what"], fg=GOLD)
        elif r["win"]:
            state["res"].config(text="✅ Билет выиграл! " + r["what"], fg=GREEN)
        else:
            state["res"].config(
                text="Без выигрыша: закрыто %d из %d чисел билета."
                     % (r["closed"], r["total"]), fg=FG2)

    # ---------- вкладка «Рапидо» ----------

    def _build_tab_rapido(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text="Рапидо")
        f = sf.inner

        _lbl(f, RAPIDO_INFO, size=9).pack(anchor="w", padx=16, pady=(10, 0))

        ctrl = tk.Frame(f, bg=BG)
        ctrl.pack(fill="x", padx=16, pady=(8, 0))
        _lbl(ctrl, "Номер тиража:", fg=FG, bold=True).pack(side="left")
        num = _entry(ctrl, 8)
        num.pack(side="left", padx=6)
        out = _lbl(f, "Загрузите тираж — или оставьте номер пустым: "
                      "возьмётся последний.", size=9)
        out.pack(anchor="w", padx=16, pady=(4, 0))
        state = {"game": "rapido", "num": num, "out": out, "draw": None}
        _btn(ctrl, "Загрузить тираж",
             lambda: self._load_game_draw(state)).pack(side="left", padx=4)

        ck = tk.Frame(f, bg=BG)
        ck.pack(anchor="w", padx=16, pady=(12, 0))
        _lbl(ck, "Поле 1 — 8 чисел (1–20):", fg=FG, bold=True
             ).pack(side="left")
        e1 = _entry(ck, 22)
        e1.pack(side="left", padx=6)
        _lbl(ck, "поле 2 (1–4):", fg=FG, bold=True).pack(side="left")
        e2 = _entry(ck, 4)
        e2.pack(side="left", padx=6)
        res = _lbl(f, "", fg=GOLD, size=10, bold=True)
        res.pack(anchor="w", padx=16, pady=(6, 12))
        state.update(e1=e1, e2=e2, res=res)
        _btn(f, "Проверить ставку",
             lambda: self._check_rapido(state),
             color=GREEN).pack(anchor="w", padx=16, pady=(0, 16))

    def _check_rapido(self, state):
        import re
        d = state.get("draw")
        if not d:
            state["res"].config(text="Сначала нажмите «Загрузить тираж»",
                                fg=RED)
            return
        f1 = [int(x) for x in re.findall(r"\d+", state["e1"].get())]
        f2s = [int(x) for x in re.findall(r"\d+", state["e2"].get())]
        if len(set(f1)) != 8 or not all(1 <= x <= 20 for x in f1):
            state["res"].config(text="Поле 1: ровно 8 разных чисел "
                                     "от 1 до 20", fg=RED)
            return
        f2 = f2s[0] if f2s else None
        if f2 is not None and not 1 <= f2 <= 4:
            state["res"].config(text="Поле 2: число от 1 до 4", fg=RED)
            return
        r = check_rapido(f1, f2, d)
        base = "Совпало: поле 1 — %d из 8, поле 2 — %s." % (
            r["a"], "да" if r["b"] else "нет")
        if r["super"]:
            state["res"].config(text="🎉 СУПЕРПРИЗ! 8 + 1. " + base, fg=GOLD)
        elif r["win"]:
            state["res"].config(text="✅ Выигрышная ставка! " + base,
                                fg=GREEN)
        else:
            state["res"].config(text="Без выигрыша. " + base, fg=FG2)

    # ---------- вкладка «4 из 20» ----------

    def _build_tab_4x20(self):
        sf = ScrollFrame(self.nb)
        self.nb.add(sf, text="4 из 20")
        f = sf.inner

        _lbl(f, X4_20_INFO, size=9).pack(anchor="w", padx=16, pady=(10, 0))

        ctrl = tk.Frame(f, bg=BG)
        ctrl.pack(fill="x", padx=16, pady=(8, 0))
        _lbl(ctrl, "Номер тиража:", fg=FG, bold=True).pack(side="left")
        num = _entry(ctrl, 8)
        num.pack(side="left", padx=6)
        out = _lbl(f, "Загрузите тираж — или оставьте номер пустым: "
                      "возьмётся последний.", size=9)
        out.pack(anchor="w", padx=16, pady=(4, 0))
        state = {"game": "4x20", "num": num, "out": out, "draw": None}
        _btn(ctrl, "Загрузить тираж",
             lambda: self._load_game_draw(state)).pack(side="left", padx=4)

        ck = tk.Frame(f, bg=BG)
        ck.pack(anchor="w", padx=16, pady=(12, 0))
        _lbl(ck, "Поле 1 — 4 числа (1–20):", fg=FG, bold=True
             ).pack(side="left")
        e1 = _entry(ck, 14)
        e1.pack(side="left", padx=6)
        _lbl(ck, "поле 2 — 4 числа:", fg=FG, bold=True).pack(side="left")
        e2 = _entry(ck, 14)
        e2.pack(side="left", padx=6)
        res = _lbl(f, "", fg=GOLD, size=10, bold=True)
        res.pack(anchor="w", padx=16, pady=(6, 12))
        state.update(e1=e1, e2=e2, res=res)
        _btn(f, "Проверить ставку",
             lambda: self._check_4x20(state),
             color=GREEN).pack(anchor="w", padx=16, pady=(0, 16))

    def _check_4x20(self, state):
        import re
        d = state.get("draw")
        if not d:
            state["res"].config(text="Сначала нажмите «Загрузить тираж»",
                                fg=RED)
            return
        f1 = [int(x) for x in re.findall(r"\d+", state["e1"].get())]
        f2 = [int(x) for x in re.findall(r"\d+", state["e2"].get())]
        if len(set(f1)) != 4 or not all(1 <= x <= 20 for x in f1) or \
                len(set(f2)) != 4 or not all(1 <= x <= 20 for x in f2):
            state["res"].config(text="В каждом поле ровно 4 разных числа "
                                     "от 1 до 20", fg=RED)
            return
        r = check_4x20(f1, f2, d)
        base = "Совпало: поле 1 — %d из 4, поле 2 — %d из 4." % (r["a"],
                                                                 r["b"])
        if r["super"]:
            state["res"].config(text="🎉 СУПЕРПРИЗ! 4 + 4. " + base, fg=GOLD)
        elif r["win"]:
            state["res"].config(
                text="✅ Выигрышная ставка (%d+%d из 21 выигрышной "
                     "категории)! %s" % (r["a"], r["b"], base), fg=GREEN)
        else:
            state["res"].config(text="Без выигрыша. " + base, fg=FG2)


    # ---------- данные 6/45 Плюс ----------

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
                     bg=BG, fg=RED, font=("Segoe UI", 10, "bold"),
                     padx=6, pady=1).pack(side="left", padx=2, pady=1)
        ps = st["plus"]
        self.plus_lbl.config(text="Плюс-шар: 1 — %d · 2 — %d · 3 — %d · 4 — %d"
                             % (ps[1], ps[2], ps[3], ps[4]))
        if log:
            self._render_log(log)

    # ---------- рейтинг лотерей ----------

    def _calc_games(self):
        try:
            mp = float(self.cmp_min.get().replace(",", "."))
            if mp <= 0:
                raise ValueError
        except ValueError:
            txt = "Введите сумму числом, например 100"
        else:
            txt = games_text(mp)
        self.cmp_out.config(state="normal")
        self.cmp_out.delete("1.0", "end")
        self.cmp_out.insert("1.0", txt)
        self.cmp_out.config(state="disabled")

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
            _lbl(self.my_list, "пока пусто — добавьте свои числа",
                 size=9).pack(anchor="w")
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

    # ---------- журнал прогнозов ----------

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
