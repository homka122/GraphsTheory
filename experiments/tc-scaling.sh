#!/usr/bin/env bash
# Сильная масштабируемость подсчёта треугольников: время подсчёта и построения графа при разных P.
# Нужны симметричные графы из tc-prepare-graphs.sh.
# usage: [RUNS=3] tc-scaling.sh "<graph list>" "<P list>"
# пример: RUNS=20 tc-scaling.sh "roadNet-PA soc-LiveJournal1" "1 2 3 4 5 6"
source "$(dirname "$0")/common.sh"
export PRINT_PER_HOST_STATS=1
runs=${RUNS:-3}
cd "$(out_dir tc-scaling)"
for name in $1; do
  for p in $2; do
    tag=${name}_p$p
    timeout 3600 mpirun -n $p --map-by core --bind-to core $BIN/triangle-counting-dist \
      "$(sym_graph_path "$name")" -symmetricGraph -t=1 --runs=$runs --statFile=$tag.stats > $tag.out 2>&1
    rc=$?
    t=$(grep -E 'Timer_[0-9]+, HMAX' $tag.stats | awk -F', ' '{print $NF}' | sort -n | sed -n "$(( (runs + 1) / 2 ))p")
    echo "$name P=$p rc=$rc time_med=$t construct=$(stat $tag.stats GraphConstructTime HMAX)" \
      "triangles=$(grep -h 'Total number of triangles' $tag.out | sort -u | awk '{print $NF}' | tr '\n' ' ')"
  done
done
