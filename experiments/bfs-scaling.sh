#!/usr/bin/env bash
# Сильная масштабируемость BFS push (Galois без изменений, --delta=1, Sync): время Timer_N и число раундов.
# usage: [RUNS=5] bfs-scaling.sh "<graph list>" "<P list>"
# пример: RUNS=5 bfs-scaling.sh "soc-LiveJournal1 roadNet-PA rgg_n_2_21_s0" "1 2 3 4 5 6"
source "$(dirname "$0")/common.sh"
export PRINT_PER_HOST_STATS=1
runs=${RUNS:-5}
cd "$(out_dir bfs-scaling)"
for name in $1; do
  start=$(start_of "$name") || exit 1
  for p in $2; do
    tag=${name}_p$p
    timeout 1800 mpirun -n $p --map-by core --bind-to core $BIN/bfs-push-dist \
      "$(graph_path "$name")" --exec=Sync --delta=1 --startNode=$start -t=1 --runs=$runs \
      --statFile=$tag.stats > $tag.out 2>&1
    rc=$?
    t=$(grep -E 'Timer_[0-9]+, HMAX' $tag.stats | awk -F', ' '{print $NF}' | sort -n | sed -n "$(( (runs + 1) / 2 ))p")
    echo "$name P=$p rc=$rc time_med=$t rounds=$(grep -h 'NumIterations_0' $tag.stats | awk -F', ' '{print $NF}' | head -1)" \
      "rf=$(stat $tag.stats ReplicationFactor HOST_0)"
  done
done
