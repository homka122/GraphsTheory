#!/usr/bin/env bash
# Быстрая проверка сборки: решётка 20×20, BFS и PageRank при P=2, сверка ответа BFS.
# usage: smoke-test.sh   (нужен собранный build/bin)
set -euo pipefail
source "$(dirname "$0")/common.sh"
dir=$(mktemp -d)
trap 'rm -rf "$dir"' EXIT

# решётка n×n, рёбра в обе стороны; кратчайший путь от угла до угла — 2(n-1)
n=20
awk -v n=$n 'BEGIN {
  for (i = 0; i < n; i++) for (j = 0; j < n; j++) {
    v = i * n + j
    if (j + 1 < n) { print v, v + 1; print v + 1, v }
    if (i + 1 < n) { print v, v + n; print v + n, v }
  }
}' > "$dir/grid.el"
$BIN/graph-convert --edgelist2gr "$dir/grid.el" "$dir/grid.gr" > /dev/null

mpirun -n 2 --oversubscribe $BIN/bfs-push-dist "$dir/grid.gr" --exec=Sync --delta=1 --startNode=0 -t=1 \
  > "$dir/bfs.out" 2>&1
d=$(grep -h 'Max distance' "$dir/bfs.out" | sort -u | awk '{print $NF}')
if [ "$d" != $((2 * (n - 1))) ]; then
  echo "BFS: максимальное расстояние $d, ожидалось $((2 * (n - 1)))"; cat "$dir/bfs.out"; exit 1
fi

mpirun -n 2 --oversubscribe $BIN/pagerank-push-dist "$dir/grid.gr" --exec=Sync -t=1 \
  --maxIterations=100000000 > "$dir/pr.out" 2>&1
grep -q 'Residual sum is 0' "$dir/pr.out" || { echo "PageRank не сошёлся"; cat "$dir/pr.out"; exit 1; }

echo "ok: BFS max distance $d, PageRank сошёлся"
