#!/usr/bin/env python3
"""Отчёт по прогонам pagerank-push-prof-dist (experiments/pagerank-prof.sh).

usage: pr_report.py <dir> <graph>

Читает <dir>/<graph>_p<P>_r<run>.host<ID>.csv и .stats, рисует PNG, сводную
картинку <dir>/<graph>_live.png (для imv, он перечитывает файл сам) и таблицу
<dir>/<graph>.txt.

Время раунда на каждом процессе делится на:
  полезная работа   PageRank_delta + PageRank минус пустые проверки;
  обнуление зеркал  reset_mirrorField: residual всех зеркал = 0 в начале раунда;
  пустые вершины    мастер пройден, но работы нет: в PageRank_delta нет residual,
                    в PageRank нет delta. Цена — холостой проход по всем мастерам
                    (замерен после сходимости, scan_*_us) × доля пустых;
  ожидание счёта    процесс уже в sync, а кто-то ещё считает;
  обмен (sync)      остаток sync после того, как все досчитали;
  ожидание sync     процесс в Allreduce, а кто-то ещё в sync;
  Allreduce         остаток проверки завершения.
Ожидания выводятся из абсолютных меток времени: все процессы на одной машине
видят одни часы.
"""
import csv
import glob
import os
import re
import statistics
import sys
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

CATS = [
    ("useful", "полезная работа", "#2ca02c"),
    ("empty", "пустые проверки", "#bcbd22"),
    ("reset", "обнуление зеркал", "#8c564b"),
    ("wait_c", "ожидание счёта", "#d62728"),
    ("sync", "обмен (sync)", "#1f77b4"),
    ("wait_s", "ожидание sync", "#ff7f0e"),
    ("term", "Allreduce", "#9467bd"),
]


def read_host(path):
    meta = {}
    with open(path) as f:
        head = f.readline()
        for kv in head[1:].split():
            k, v = kv.split("=")
            meta[k] = float(v)
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in r:
            r[k] = float(r[k])
    return meta, rows


def timer(stats):
    for line in open(stats):
        m = re.search(r"Timer_0, HMAX, (\d+)", line)
        if m:
            return int(m.group(1))
    return None


def analyse(prefix):
    """Раунды одного прогона: по каждому раунду и процессу — счётчики и время по категориям, мкс."""
    files = sorted(glob.glob(prefix + ".host*.csv"), key=lambda s: int(re.search(r"host(\d+)", s).group(1)))
    hosts = [read_host(f) for f in files]
    nr = min(len(rows) for _, rows in hosts)
    rounds = []
    for k in range(nr):
        rs = [rows[k] for _, rows in hosts]
        tc = max(r["t_compute_end_us"] for r in rs)
        ts = max(r["t_sync_end_us"] for r in rs)
        per = []
        for (meta, _), r in zip(hosts, rs):
            m = meta["masters"] or 1
            compute = r["delta_us"] + r["push_us"]
            empty = 0.0
            if r["scan_delta_us"] >= 0:
                empty = (r["scan_delta_us"] * (m - r["got"]) / m +
                         r["scan_push_us"] * (m - r["active"]) / m)
            empty = min(empty, compute)
            wait_c = min(max(tc - r["t_compute_end_us"], 0.0), r["sync_us"])
            wait_s = min(max(ts - r["t_sync_end_us"], 0.0), r["term_us"])
            per.append({
                "useful": compute - empty, "empty": empty, "reset": r["reset_us"], "wait_c": wait_c,
                "sync": r["sync_us"] - wait_c, "wait_s": wait_s, "term": r["term_us"] - wait_s,
                "masters": m, "got": r["got"], "active": r["active"], "edges": r["edges"],
            })
        rounds.append(per)
    return [meta for meta, _ in hosts], rounds


def collect(d, graph):
    runs = {}
    for stats in glob.glob(os.path.join(d, f"{graph}_p*_r*.stats")):
        m = re.search(r"_p(\d+)_r(\d+)\.stats$", stats)
        prefix = stats[:-len(".stats")]
        t = timer(stats)
        if t is None or not glob.glob(prefix + ".host*.csv"):
            continue
        runs.setdefault(int(m.group(1)), []).append((t, prefix))
    return runs


def median_run(lst):
    lst = sorted(lst)
    return lst[(len(lst) - 1) // 2]


def totals(rounds, host=None):
    acc = {c: 0.0 for c, _, _ in CATS}
    for per in rounds:
        hs = per if host is None else [per[host]]
        for h in hs:
            for c, _, _ in CATS:
                acc[c] += h[c] / len(hs)
    return acc


def plot_scaling(runs, graph, out):
    ps = sorted(runs)
    med = {p: median_run(runs[p])[0] for p in ps}
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(18, 5))

    for p in ps:
        ts = [t for t, _ in runs[p]]
        a.errorbar(p, med[p] / 1000, yerr=[[(med[p] - min(ts)) / 1000], [(max(ts) - med[p]) / 1000]],
                   fmt="o", color="k", capsize=4)
    a.plot(ps, [med[p] / 1000 for p in ps], "k-")
    a.set_xlabel("P (процессов)")
    a.set_ylabel("время, с (медиана, min–max)")
    a.set_title("Время PageRank (Timer_0)")
    a.grid(alpha=0.3)
    a.set_ylim(bottom=0)

    if 1 in med:
        b.plot(ps, ps, "k--", label="идеал")
        b.plot(ps, [med[1] / med[p] for p in ps], "o-", label="ускорение")
        b.set_xlabel("P (процессов)")
        b.set_ylabel("T(1) / T(P)")
        b.set_title("Ускорение")
        b.grid(alpha=0.3)
        b.legend()

    bottom = [0.0] * len(ps)
    tot = {p: totals(analyse(median_run(runs[p])[1])[1]) for p in ps}
    for cat, label, color in CATS:
        vals = [tot[p][cat] / 1e6 for p in ps]
        c.bar(ps, vals, bottom=bottom, color=color, label=label)
        bottom = [x + y for x, y in zip(bottom, vals)]
    c.set_xlabel("P (процессов)")
    c.set_ylabel("с, среднее по процессам")
    c.set_title("На что уходит время (медианный прогон)")
    c.legend(fontsize=8)
    c.grid(axis="y", alpha=0.3)

    fig.suptitle(f"{graph}: PageRank push, --exec=Sync, 1 поток на процесс")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    plt.close(fig)


def plot_rounds(prefix, p, graph, out):
    metas, rounds = analyse(prefix)
    ks = range(len(rounds))
    fig, (a, b, c) = plt.subplots(1, 3, figsize=(20, 5.5))

    masters = [sum(h["masters"] for h in per) for per in rounds]
    got = [sum(h["got"] for h in per) for per in rounds]
    act = [sum(h["active"] for h in per) for per in rounds]
    a.plot(ks, masters, "k-", label="пройдено мастеров (все)")
    a.plot(ks, got, "-", color="#1f77b4", label="пришла вода (residual > 0)")
    a.plot(ks, act, "-", color="#2ca02c", label="рассылают (delta > 0)")
    a.plot(ks, [m - g for m, g in zip(masters, got)], "--", color="#bcbd22", label="пустые: residual = 0")
    a.set_yscale("log")
    a.set_xlabel("раунд")
    a.set_ylabel("вершин, сумма по процессам")
    a.set_title("Вершины по раундам")
    a.grid(alpha=0.3, which="both")
    a.legend(fontsize=8)

    bottom = [0.0] * len(rounds)
    for cat, label, color in CATS:
        vals = [sum(h[cat] for h in per) / len(per) / 1000 for per in rounds]
        b.bar(ks, vals, bottom=bottom, color=color, label=label, width=1.0)
        bottom = [x + y for x, y in zip(bottom, vals)]
    b.set_yscale("log")
    b.set_ylim(bottom=0.1)
    b.set_xlabel("раунд")
    b.set_ylabel("мс, среднее по процессам")
    b.set_title("Время раунда по фазам (лог. шкала)")
    b.legend(fontsize=8)
    b.grid(alpha=0.3, axis="y", which="both")

    hs = range(len(metas))
    bottom = [0.0] * len(metas)
    for cat, label, color in CATS:
        vals = [totals(rounds, h)[cat] / 1e6 for h in hs]
        c.bar(hs, vals, bottom=bottom, color=color, label=label)
        bottom = [x + y for x, y in zip(bottom, vals)]
    edges = [sum(per[h]["edges"] for per in rounds) for h in hs]
    for h in hs:
        c.text(h, bottom[h], f"{edges[h] / 1e9:.2f} млрд\nрёбер", ha="center", va="bottom", fontsize=8)
    c.set_xticks(list(hs), [f"процесс {h}\n{int(metas[h]['masters']) / 1e6:.2f} млн мастеров" for h in hs],
                 fontsize=8)
    c.set_ylabel("с за прогон")
    c.set_title("Кто чем занят (над столбцом — разослано по рёбрам)")
    c.set_ylim(top=max(bottom) * 1.15)
    c.legend(fontsize=8)
    c.grid(alpha=0.3, axis="y")

    fig.suptitle(f"{graph}, P={p}: медианный прогон {os.path.basename(prefix)}, {len(rounds)} раундов")
    fig.tight_layout()
    fig.savefig(out, dpi=100)
    plt.close(fig)


def main():
    d, graph = sys.argv[1], sys.argv[2]
    runs = collect(d, graph)
    if not runs:
        return
    stamp = int(time.time())
    ps = sorted(runs)
    plot_scaling(runs, graph, os.path.join(d, f"{graph}_scaling.png"))
    for p in ps:
        plot_rounds(median_run(runs[p])[1], p, graph, os.path.join(d, f"{graph}_rounds_p{p}.png"))

    t1 = median_run(runs[1])[0] if 1 in runs else None
    names = ["P", "прогонов", "время,с", "ускор.", "раундов", "рёбер,млрд", "пустых"] + [l for _, l, _ in CATS]
    table = []
    for p in ps:
        t, prefix = median_run(runs[p])
        metas, rounds = analyse(prefix)
        tot = totals(rounds)
        s = sum(tot.values()) or 1
        scanned = sum(h["masters"] for per in rounds for h in per)
        empty_v = sum(h["masters"] - h["got"] for per in rounds for h in per)
        edges = sum(h["edges"] for per in rounds for h in per)
        table.append([str(p), str(len(runs[p])), f"{t / 1000:.2f}",
                      f"{t1 / t:.2f}" if t1 else "-", str(len(rounds)), f"{edges / 1e9:.2f}",
                      f"{100 * empty_v / scanned:.0f}%"] + [f"{100 * tot[c] / s:.0f}%" for c, _, _ in CATS])
    widths = [max(len(r[i]) for r in [names] + table) for i in range(len(names))]
    lines = [f"{graph}: PageRank push, Sync, 1 поток на процесс; обновлено {time.strftime('%H:%M:%S')}",
             "доли времени — среднее по процессам в медианном по Timer_0 прогоне", ""]
    lines += ["  ".join(c.rjust(w) for c, w in zip(r, widths)) for r in [names] + table]
    txt = "\n".join(lines) + "\n"
    open(os.path.join(d, f"{graph}.txt"), "w").write(txt)
    print(txt)

    # одна картинка для просмотрщика: масштабируемость и раунды всех P друг под другом
    imgs = [plt.imread(os.path.join(d, f"{graph}_scaling.png"))]
    imgs += [plt.imread(os.path.join(d, f"{graph}_rounds_p{p}.png")) for p in ps]
    w = max(i.shape[1] for i in imgs)
    padded = [np.pad(i, ((0, 0), (0, w - i.shape[1]), (0, 0)), constant_values=1.0) for i in imgs]
    tmp = os.path.join(d, f"{graph}_live.tmp.png")
    plt.imsave(tmp, np.concatenate(padded, axis=0))
    os.replace(tmp, os.path.join(d, f"{graph}_live.png"))


if __name__ == "__main__":
    main()
