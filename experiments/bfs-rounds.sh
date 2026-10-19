#!/usr/bin/env bash
# Число раундов BFS push при delta=1 не зависит от P и числа потоков: проверка профилировщиком.
# usage: bfs-rounds.sh "<graph list>" "<P:t list>"
# пример: bfs-rounds.sh "soc-LiveJournal1 roadNet-PA" "1:1 2:1 3:1 6:1 3:2 1:6"
source "$(dirname "$0")/common.sh"
cd "$(out_dir bfs-rounds)"
for cfg in $2; do
  p=${cfg%:*}; t=${cfg#*:}
  for name in $1; do
    start=$(start_of "$name") || exit 1
    tag=${name}_p${p}_t${t}
    mpirun -n $p --map-by slot:PE=$t --bind-to core $BIN/bfs-push-prof-dist \
      "$(graph_path "$name")" --exec=Sync --delta=1 --startNode=$start -t=$t --runs=1 \
      --phaseLog=$tag --statFile=$tag.stats > $tag.out 2>&1
    d=$(grep -o 'Max distance from source [0-9]* is [0-9]*' $tag.out | awk '{print $NF}')
    echo "$name P=$p t=$t rounds=$(stat $tag.stats NumIterations_0 HMAX) maxdist=$d"
  done
done
