# -*- coding: utf-8 -*-
"""Инкрементальная докачка архивов тиражей Столото (новые игры).

Использование:
  python download_new_games.py <игра> <файл.json> [старт_стр] [число_стр]
игра: ruslotto | gzhl | 4x20 | rapido
Дедупликация по номеру тиража; дописывает только новые тиражи.
Лимиты API: 50 тиражей/стр, глубже ~100 страниц не отдаёт.
"""
import json, os, sys, time, urllib.request

API = ("https://www.stoloto.ru/p/api/mobile/api/v35/service/draws/archive"
       "?game={game}&count=50&page={page}")
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                   "AppleWebKit/537.36 Chrome/150.0 Safari/537.36"),
    "Gosloto-Partner": "bXMjXFRXZ3coWXh6R3s1NTdUX3dnWlBMLUxmdg",
}


def fetch(game, page, attempts=4):
    last = None
    for a in range(attempts):
        try:
            req = urllib.request.Request(API.format(game=game, page=page),
                                         headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            time.sleep(1.0 * (a + 1))
    raise RuntimeError("%s стр.%d: %s" % (game, page, last))


def parse(game, d):
    n = d.get("number")
    dt = d.get("date", "")[:16].replace("T", " ")
    sp = d.get("superPrize") or 0
    if game in ("ruslotto", "gzhl"):
        st = (d.get("combination") or {}).get("structured") or {}
        np_ = [int(x) for x in (st.get("notPlayed") or [])] \
            if isinstance(st, dict) else []
        rounds, meta = [], []
        try:
            wc = json.loads(d.get("winningCategories") or "{}")
            cats = wc.get("main") or wc.get("categories") or []
            for c in sorted(cats, key=lambda c: c.get("winCat", 0)):
                nums = [int(x) for x in str(c.get("numbers") or "").split(",")
                        if x.strip().isdigit()]
                rounds.append(nums)
                meta.append([c.get("amount") or 0, c.get("countWins") or 0])
        except Exception:
            pass
        return {"n": n, "d": dt, "sp": sp, "np": np_, "r": rounds, "wm": meta}
    if game == "4x20":
        comb = (d.get("combination") or {}).get("structured") or []
        return {"n": n, "d": dt, "sp": sp,
                "a": sorted(int(x) for x in comb[:4]),
                "b": sorted(int(x) for x in comb[4:8])}
    if game == "rapido":
        st = (d.get("combination") or {}).get("structured") or {}
        played = [int(x) for x in (st.get("played") or [])]
        return {"n": n, "d": dt, "sp": sp, "p": played,
                "par": st.get("parity") or ""}
    raise ValueError(game)




if __name__ == "__main__":
    game, out = sys.argv[1], sys.argv[2]
    start = int(sys.argv[3]) if len(sys.argv) > 3 else 0
    npages = int(sys.argv[4]) if len(sys.argv) > 4 else 100
    recs = {}
    if os.path.exists(out):
        recs = {r["n"]: r for r in json.load(open(out, encoding="utf-8"))}
    page, done = start, False
    for _ in range(npages):
        page += 1
        try:
            payload = fetch(game, page)
        except Exception as e:
            print("ОШИБКА", e, flush=True)
            break
        draws = payload.get("draws") or []
        if not draws:
            done = True
            break
        new = 0
        for d in draws:
            r = parse(game, d)
            if r["n"] is not None and r["n"] not in recs:
                recs[r["n"]] = r
                new += 1
        if new == 0 or any(r["n"] == 1 for r in recs.values()):
            done = True
        time.sleep(0.4)
    out_list = [recs[k] for k in sorted(recs)]
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_list, f, ensure_ascii=False, separators=(",", ":"))
    print("ИТОГ %s: тиражей %d, №%s..№%s, исчерпан=%s"
          % (game, len(out_list), out_list[0]["n"], out_list[-1]["n"], done))
