#!/usr/bin/env python3
"""Проверка бинарного .gr Galois для подсчёта треугольников.

usage: gr_check.py <graph>.gr

Печатает число вершин и рёбер, петли, кратные рёбра, симметричность
и сортировку списков соседей. Код возврата 1, если граф не симметричный
или в нём есть петли или кратные рёбра.

Формат .gr (версия 1): 4 × uint64 (версия, размер данных ребра, вершины, рёбра),
uint64[вершины] — конец списка соседей каждой вершины, uint32[рёбра] — соседи.
"""
import sys

import numpy as np


def main():
    path = sys.argv[1]
    with open(path, "rb") as f:
        version, edge_size, n, m = np.fromfile(f, dtype=np.uint64, count=4)
        ends = np.fromfile(f, dtype=np.uint64, count=int(n))
        dst = np.fromfile(f, dtype=np.uint32, count=int(m)).astype(np.int64)
    assert version == 1, f"unsupported .gr version {version}"
    deg = np.diff(ends.astype(np.int64), prepend=0)
    src = np.repeat(np.arange(n, dtype=np.int64), deg)

    loops = int(np.count_nonzero(src == dst))
    key = src * n + dst
    keys = np.sort(key)
    dups = int(np.count_nonzero(keys[1:] == keys[:-1]))
    rev = np.sort(dst * n + src)
    symmetric = bool(np.array_equal(keys, rev))
    # соседи внутри каждого списка идут по возрастанию, если ключи уже отсортированы
    sorted_lists = bool(np.all(key[1:] >= key[:-1]))

    print(f"{path}: vertices={n} edges={m} edge_data={edge_size}B max_degree={deg.max()} "
          f"self_loops={loops} multi_edges={dups} symmetric={symmetric} sorted={sorted_lists}")
    sys.exit(0 if symmetric and loops == 0 and dups == 0 else 1)


if __name__ == "__main__":
    main()
