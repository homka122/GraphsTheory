#!/usr/bin/env python3
"""Сводка по фазам BSP для bfs-push-prof-dist.

Читает <prefix>.host<ID>.csv всех процессов и печатает, на что каждый процесс
тратил время в раундах BFS.

Фазы раунда:
  полезная работа      compute минус пустые проверки;
  пустые проверки      do_all пробегает все вершины, холостой проход стоит
                       scan_us (замерен перед BFS, когда ни одна вершина не
                       активна); раунд 0 (FirstItr) целиком полезная работа;
  ожидание compute     процесс уже в sync, а кто-то ещё считает;
  обмен (sync)         остаток sync после того, как все закончили compute;
  ожидание sync        процесс в Allreduce, а кто-то ещё в sync;
  Allreduce            остаток проверки завершения.

Ожидания выводятся из абсолютных меток времени (общие часы всех процессов на
одной машине): TC = самый поздний конец compute в раунде, TS = самый поздний
конец sync. Запуск с --explicitBarrier (или старые CSV без меток) меряет
ожидание compute явным барьером, а ожидание sync не выделяет.

Пример:
    python3 phase_report.py phases            # медианный запуск
    python3 phase_report.py phases --run 2 --rounds
"""
import argparse
import csv
import glob
import statistics

PHASES = [
    ("useful", "полезная работа"),
    ("scan", "пустые проверки"),
    ("barrier", "ожидание compute"),
    ("sync", "обмен (sync)"),
    ("syncwait", "ожидание sync"),
    ("term", "Allreduce"),
]


def load(prefix):
    hosts = {}
    for path in glob.glob(f"{prefix}.host*.csv"):
        with open(path) as f:
            meta_line = f.readline().lstrip("# ").strip()
            meta = dict(kv.split("=", 1) for kv in meta_line.split())
            rows = list(csv.DictReader(f))
        hosts[int(meta["host"])] = {"meta": meta, "rows": rows}
    if not hosts:
        raise SystemExit(f"нет файлов {prefix}.host*.csv")
    return dict(sorted(hosts.items()))


def runs_of(hosts):
    return sorted({int(r["run"]) for r in hosts[0]["rows"]})


def run_rows(hosts, h, run):
    return [r for r in hosts[h]["rows"] if int(r["run"]) == run]


def round_phases(hosts, run):
    """{host: [ {фаза: мкс} по раундам ]} для одного запуска."""
    per = {h: run_rows(hosts, h, run) for h in hosts}
    n = min(len(v) for v in per.values())
    timestamps = all("t_compute_end_us" in rows[0] for rows in per.values() if rows)
    explicit = any(d["meta"].get("explicit_barrier", "1") == "1" for d in hosts.values())
    out = {h: [] for h in hosts}
    for i in range(n):
        rs = {h: per[h][i] for h in hosts}
        if timestamps and not explicit:
            tc_max = max(float(r["t_compute_end_us"]) for r in rs.values())
            ts_max = max(float(r["t_sync_end_us"]) for r in rs.values())
        for h, r in rs.items():
            scan_us = float(hosts[h]["meta"]["scan_us"])
            compute = float(r["compute_us"])
            scan = 0.0 if int(r["round"]) == 0 else min(compute, scan_us)
            sync, term = float(r["sync_us"]), float(r["term_us"])
            if timestamps and not explicit:
                wait_c = min(max(0.0, tc_max - float(r["t_compute_end_us"])), sync)
                wait_s = min(max(0.0, ts_max - float(r["t_sync_end_us"])), term)
            else:
                wait_c, wait_s = None, 0.0
            out[h].append({
                "useful": compute - scan,
                "scan": scan,
                "barrier": float(r["barrier_us"]) if wait_c is None else wait_c,
                "sync": sync if wait_c is None else sync - wait_c,
                "syncwait": wait_s,
                "term": term - wait_s,
            })
    return out


def host_totals(hosts, run):
    """{host: {фаза: мкс}} — суммы по раундам одного запуска."""
    return {h: {k: sum(p[k] for p in ps) for k, _ in PHASES}
            for h, ps in round_phases(hosts, run).items()}


def median_run(hosts):
    runs = runs_of(hosts)
    wall = {run: statistics.mean(sum(t.values()) for t in host_totals(hosts, run).values())
            for run in runs}
    order = sorted(runs, key=lambda r: wall[r])
    return order[len(order) // 2]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("prefix", help="префикс, переданный в --phaseLog")
    ap.add_argument("--run", type=int, help="номер запуска (по умолчанию медианный по времени)")
    ap.add_argument("--rounds", action="store_true", help="напечатать таблицу по раундам")
    args = ap.parse_args()

    hosts = load(args.prefix)
    run = median_run(hosts) if args.run is None else args.run
    m = hosts[0]["meta"]
    nrounds = len(run_rows(hosts, 0, run))
    mode = "явный барьер" if m.get("explicit_barrier", "1") == "1" else "метки времени, без барьера"
    print(f"Процессов: {m['hosts']}, потоков на процесс: {m['threads']}, "
          f"старт: {m['start_node']}, delta: {m['delta']}, ожидание: {mode}")
    print(f"Запуск {run} из {runs_of(hosts)}, раундов: {nrounds} (включая раунд 0 = FirstItr)\n")

    print(f"{'процесс':>8} {'мастера':>10} {'зеркала':>10} {'рёбер':>12} {'холостой проход, мс':>20}")
    for h, d in hosts.items():
        mm = d["meta"]
        print(f"{h:>8} {int(mm['masters']):>10} {int(mm['mirrors']):>10} "
              f"{int(mm['local_edges']):>12} {float(mm['scan_us']) / 1000:>20.3f}")
    print()

    tot = host_totals(hosts, run)
    print("Время по фазам, мс (доля от времени процесса):")
    print(f"{'процесс':>8}" + "".join(f"{name:>20}" for _, name in PHASES) + f"{'всего':>10}")
    for h, t in tot.items():
        total = sum(t.values())
        print(f"{h:>8}" + "".join(f"{t[k] / 1000:>12.1f} ({100 * t[k] / total:4.1f}%)" for k, _ in PHASES)
              + f"{total / 1000:>10.1f}")
    mean = {k: statistics.mean(t[k] for t in tot.values()) for k, _ in PHASES}
    total_mean = sum(mean.values())
    print(f"{'среднее':>8}" + "".join(f"{mean[k] / 1000:>12.1f} ({100 * mean[k] / total_mean:4.1f}%)"
                                     for k, _ in PHASES) + f"{total_mean / 1000:>10.1f}\n")

    comp = [t["useful"] + t["scan"] for t in tot.values()]
    if len(comp) > 1 and statistics.mean(comp) > 0:
        print(f"Дисбаланс compute: max/среднее = {max(comp) / statistics.mean(comp):.2f}")
    edges = [sum(int(r["edges"]) for r in run_rows(hosts, h, run)) for h in hosts]
    print(f"Обработано рёбер по процессам: {edges} (всего {sum(edges)})")

    if args.rounds:
        rp = round_phases(hosts, run)
        print("\nПо раундам, мс (max по процессам, ожидания — сумма по процессам):")
        print(f"{'раунд':>6} {'активных':>10} {'рёбер':>11} {'compute':>9} {'ожид.compute':>13} "
              f"{'обмен':>8} {'ожид.sync':>10} {'Allreduce':>10}")
        for i in range(nrounds):
            rows = [run_rows(hosts, h, run)[i] for h in hosts]
            ph = [rp[h][i] for h in hosts]
            print(f"{int(rows[0]['round']):>6} {sum(int(r['active']) for r in rows):>10} "
                  f"{sum(int(r['edges']) for r in rows):>11} "
                  f"{max(p['useful'] + p['scan'] for p in ph) / 1000:>9.3f} "
                  f"{sum(p['barrier'] for p in ph) / 1000:>13.3f} {max(p['sync'] for p in ph) / 1000:>8.3f} "
                  f"{sum(p['syncwait'] for p in ph) / 1000:>10.3f} {max(p['term'] for p in ph) / 1000:>10.3f}")


if __name__ == "__main__":
    main()
