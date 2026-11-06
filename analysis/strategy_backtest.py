# -*- coding: utf-8 -*-
"""Бэктест стратегий 6/45 по полному архиву: каждая комбинация выбирается
только по тиражам ДО текущего (walk-forward), сравнение со случайным выбором."""
import json, random
from collections import Counter

with open('analysis/archive_6x45.json', encoding='utf-8') as f:
    draws = json.load(f)
draws = sorted(draws, key=lambda d: d['n'])
mains = [sorted(d['main']) for d in draws]
N = len(mains)
print('Тиражей:', N)

WARM = 200          # минимум истории перед первым прогнозом
WINDOW = 100

def freq_last(prior, w=WINDOW):
    c = Counter()
    for m in prior[-w:]:
        c.update(m)
    return c

def strat_hot(prior):
    return sorted(x for x, _ in freq_last(prior).most_common(6))

def strat_cold(prior):
    c = freq_last(prior)
    return sorted(sorted(range(1, 46), key=lambda x: (c[x], x))[:6])

def strat_mixed(prior):
    c = freq_last(prior)
    hot = [x for x, _ in c.most_common(45)]
    combo = hot[:3]
    for x in sorted(range(1, 46), key=lambda x: (c[x], x)):
        if len(combo) >= 6: break
        if x not in combo: combo.append(x)
    return sorted(combo)

def strat_freq_all(prior):
    c = Counter()
    for m in prior: c.update(m)
    return sorted(x for x, _ in c.most_common(6))

def strat_overdue(prior):
    last_seen = {x: -1 for x in range(1, 46)}
    for i, m in enumerate(prior):
        for x in m: last_seen[x] = i
    return sorted(sorted(range(1, 46), key=lambda x: (last_seen[x], x))[:6])

def strat_pairs(prior):
    """Числа, чаще других выпадающие в паре с самым частым числом окна."""
    c = freq_last(prior)
    top = c.most_common(1)[0][0]
    pc = Counter()
    for m in prior[-WINDOW:]:
        if top in m:
            pc.update(x for x in m if x != top)
    combo = [top] + [x for x, _ in pc.most_common(5)]
    return sorted(combo)

def strat_repeat_last(prior):
    """Числа прошлого тиража + добор самыми частыми."""
    last = prior[-1]
    c = freq_last(prior)
    combo = list(last)
    for x, _ in c.most_common(45):
        if len(combo) >= 6: break
        if x not in combo: combo.append(x)
    return sorted(combo)

def strat_even_spread(prior):
    """Равномерно по диапазону: 2 низких, 2 средних, 2 высоких — самые частые в группах."""
    c = freq_last(prior)
    groups = [range(1, 16), range(16, 31), range(31, 46)]
    combo = []
    for g in groups:
        combo += sorted(g, key=lambda x: (-c[x], x))[:2]
    return sorted(combo)

strategies = {
    'hot (6 самых частых за 100)': strat_hot,
    'cold (6 самых редких за 100)': strat_cold,
    'mixed 3+3': strat_mixed,
    'частые за всё время': strat_freq_all,
    'overdue (давно не были)': strat_overdue,
    'пары от топ-числа': strat_pairs,
    'повтор прошлого тиража+': strat_repeat_last,
    'равномерно 2-2-2': strat_even_spread,
}

# Теоретическое распределение совпадений для случайных 6 из 45
from math import comb
tot = comb(45, 6)
theory = {k: comb(6, k) * comb(39, 6 - k) / tot for k in range(7)}

def evaluate(fn):
    hits = Counter()
    for i in range(WARM, N):
        combo = fn(mains[:i])
        h = len(set(combo) & set(mains[i]))
        hits[h] += 1
    n = N - WARM
    avg = sum(k * v for k, v in hits.items()) / n
    p2 = sum(v for k, v in hits.items() if k >= 2) / n
    p3 = sum(v for k, v in hits.items() if k >= 3) / n
    return avg, p2, p3, hits, n

# Случайная базовая линия (3 прогона по 5000 тиражей вперемешку, детерминированно)
random.seed(42)
rh = Counter()
for i in range(WARM, N):
    combo = random.sample(range(1, 46), 6)
    rh[len(set(combo) & set(mains[i]))] += 1
n = N - WARM
ravg = sum(k * v for k, v in rh.items()) / n
rp2 = sum(v for k, v in rh.items() if k >= 2) / n
rp3 = sum(v for k, v in rh.items() if k >= 3) / n

print(f'\nТеория (случайный выбор): ср. совпадений 0.800, 2+ = {sum(v for k,v in theory.items() if k>=2):.3f}, 3+ = {sum(v for k,v in theory.items() if k>=3):.4f}')
print(f'Случай (прогон):          ср. {ravg:.3f}, 2+ = {rp2:.3f}, 3+ = {rp3:.4f}')
print('-' * 78)
print(f'{"стратегия":32s} ср.совп  2+      3+      4+     5+  6')
print('-' * 78)
for name, fn in strategies.items():
    avg, p2, p3, hits, n2 = evaluate(fn)
    print(f'{name:32s} {avg:.3f}   {p2:.3f}  {p3:.4f}  {hits[4]/n2:.5f} {hits[5]/n2:.5f} {hits[6]}')

# Дополнительно: есть ли автокорреляция — числа прошлого тиража в следующем?
ov = sum(len(set(mains[i-1]) & set(mains[i])) for i in range(1, N)) / (N - 1)
print(f'\nСреднее пересечение соседних тиражей: {ov:.3f} (теория 0.800)')

# Проверка «живучести» пар: пары, выпавшие >N раз
pc = Counter()
for m in mains:
    for a in range(6):
        for b in range(a+1, 6):
            pc[(m[a], m[b])] += 1
exp_pair = N * comb(6, 2) / comb(45, 2)
top_pairs = pc.most_common(5)
print(f'Ожидание выпадений пары: {exp_pair:.1f}; топ-5 пар: {top_pairs}')
