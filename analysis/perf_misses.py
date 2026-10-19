#!/usr/bin/env python3
"""Промахи кэша на ребро по логам experiments/perf-misses.sh.

usage: perf_misses.py <dir> <alg> <graph> <P> <edges_per_run> [load_from_alg]

Счётчики одного прогона = (runs=2) − (runs=1) по каждому процессу. Если передан load_from_alg,
а прогона с runs=2 нет, то из runs=1 вычитается загрузка графа, оценённая по другому алгоритму
на том же графе и P: загрузка = 2·(runs=1) − (runs=2).
Печатает по процессам и в сумме: такты, заполнения строк L1 из L2, из L3 и из памяти (DRAM)
на одно обработанное ребро.
"""
import glob
import os
import sys

EVENTS = {"cycles:u": "cycles", "ls_dmnd_fills_from_sys.lcl_l2:u": "L2",
          "ls_dmnd_fills_from_sys.int_cache:u": "L3", "ls_dmnd_fills_from_sys.mem_io_local:u": "DRAM"}


def read(path):
    out = {}
    for line in open(path):
        parts = line.strip().split(",")
        if len(parts) > 2 and parts[2] in EVENTS:
            out[EVENTS[parts[2]]] = int(parts[0])
    return out


def ranks(d, alg, graph, p, runs):
    files = sorted(glob.glob(os.path.join(d, f"{alg}_{graph}_p{p}_runs{runs}.rank*.perf")),
                   key=lambda s: int(s.split(".rank")[1].split(".")[0]))
    return [read(f) for f in files]


def main():
    d, alg, graph, p, edges = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), float(sys.argv[5])
    r1 = ranks(d, alg, graph, p, 1)
    r2 = ranks(d, alg, graph, p, 2)
    if r2:
        one = [{k: b[k] - a[k] for k in a} for a, b in zip(r1, r2)]
    else:
        l1, l2 = ranks(d, sys.argv[6], graph, p, 1), ranks(d, sys.argv[6], graph, p, 2)
        load = [{k: 2 * a[k] - b[k] for k in a} for a, b in zip(l1, l2)]
        one = [{k: a[k] - c[k] for k in a} for a, c in zip(r1, load)]
    tot = {k: sum(x[k] for x in one) for k in EVENTS.values()}
    print(f"{alg} {graph} P={p}: на ребро (сумма по процессам) "
          + " ".join(f"{k}={tot[k] / edges:.2f}" for k in EVENTS.values()))
    for i, x in enumerate(one):
        print(f"  процесс {i}: " + " ".join(f"{k}={x[k] / 1e6:.0f}М" for k in EVENTS.values()))


if __name__ == "__main__":
    main()
