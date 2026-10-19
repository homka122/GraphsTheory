#!/usr/bin/env bash
# Перебор Δ для SSSP push: раунды, раскрытые рёбра и время при разных P.
# usage: [RUNS=3] sssp-delta-sweep.sh <graph> "<P list>" "<delta list>"
# пример: sssp-delta-sweep.sh USA-road-d.NY "1 6" "0 100 300 1000 3000 10000"
source "$(dirname "$0")/common.sh"
export PRINT_PER_HOST_STATS=1
runs=${RUNS:-3}
name=$1; start=$(start_of "$name") || exit 1
cd "$(out_dir sssp-delta-sweep)"
for p in $2; do
  for dl in $3; do
    tag=${name}_p${p}_d${dl}
    # maxIterations по умолчанию 1000 и молча обрывает прогон, поэтому задаём с запасом.
    timeout 900 mpirun -n $p --map-by core --bind-to core $BIN/sssp-push-dist \
      "$(graph_path "$name")" --exec=Sync --delta=$dl --startNode=$start -t=1 --runs=$runs \
      --maxIterations=100000000 --statFile=$tag.stats > $tag.out 2>&1
    rc=$?
    t=$(grep -E 'Timer_[0-9], HMAX' $tag.stats | awk -F', ' '{print $NF}' | sort -n | sed -n "$(( (runs + 1) / 2 ))p")
    m=$(grep -h 'Max distance' $tag.out | sort -u | awk '{print $NF}' | tr '\n' ' ')
    echo "$name P=$p delta=$dl rc=$rc time_med=$t rounds=$(stat $tag.stats NumIterations_0 HMAX)" \
      "work=$(stat $tag.stats NumWorkItems_0 HSUM) maxdist=$m"
  done
done
