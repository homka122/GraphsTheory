#!/usr/bin/env bash
# Сильная масштабируемость PageRank push (Galois без изменений): только время Timer_N и число раундов.
# usage: [RUNS=5] pagerank-scaling.sh "<graph list>" "<P list>"
# пример: RUNS=5 pagerank-scaling.sh soc-LiveJournal1 "1 2 3 4 5 6"
source "$(dirname "$0")/common.sh"
export PRINT_PER_HOST_STATS=1
runs=${RUNS:-5}
dir=$(out_dir pagerank-scaling)
cd "$dir"
for name in $1; do
  for p in $2; do
    tag=${name}_p$p
    timeout 3600 mpirun -n $p --map-by core --bind-to core $BIN/pagerank-push-dist \
      "$(graph_path "$name")" -t=1 --exec=Sync --maxIterations=100000000 --runs=$runs \
      --statFile=$tag.stats > $tag.out 2>&1
    rc=$?
    t=$(grep -E 'Timer_[0-9]+, HMAX' $tag.stats | awk -F', ' '{print $NF}' | sort -n | sed -n "$(( (runs + 1) / 2 ))p")
    echo "$name P=$p rc=$rc time_med=$t rounds=$(grep -h 'NumIterations_0' $tag.stats | awk -F', ' '{print $NF}' | head -1)"
    nice -n 19 python3 "$ROOT/analysis/pr_scaling_plot.py" "$dir" "$name" > /dev/null
  done
done
