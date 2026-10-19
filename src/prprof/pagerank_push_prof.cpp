/*
 * This file belongs to the Galois project, a C++ library for exploiting
 * parallelism. The code is being released under the terms of the 3-Clause BSD
 * License (a copy is located in LICENSE.txt at the top-level directory).
 *
 * Copyright (C) 2018, The University of Texas at Austin. All rights reserved.
 * UNIVERSITY EXPRESSLY DISCLAIMS ANY AND ALL WARRANTIES CONCERNING THIS
 * SOFTWARE AND DOCUMENTATION, INCLUDING ANY WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR ANY PARTICULAR PURPOSE, NON-INFRINGEMENT AND WARRANTIES OF
 * PERFORMANCE, AND ANY WARRANTY THAT MIGHT OTHERWISE ARISE FROM COURSE OF
 * DEALING OR USAGE OF TRADE.  NO WARRANTY IS EITHER EXPRESS OR IMPLIED WITH
 * RESPECT TO THE USE OF THE SOFTWARE OR DOCUMENTATION. Under no circumstances
 * shall University be liable for incidental, special, indirect, direct or
 * consequential damages or loss of profits, interruption of business, or
 * related expenses which may arise from use of Software or Documentation,
 * including but not limited to those resulting from defects in Software and/or
 * Documentation, or loss or inaccuracy of data of any kind.
 */

#include "DistBench/Output.h"
#include "DistBench/Start.h"
#include "galois/DistGalois.h"
#include "galois/gstl.h"
#include "galois/DReducible.h"
#include "galois/DTerminationDetector.h"
#include "galois/runtime/Tracer.h"

#include <algorithm>
#include <chrono>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <limits>
#include <vector>

#ifdef GALOIS_ENABLE_GPU
#include "pagerank_push_cuda.h"
struct CUDA_Context* cuda_ctx;
#else
enum { CPU, GPU_CUDA };
int personality = CPU;
#endif

constexpr static const char* const REGION_NAME = "PageRank";

/******************************************************************************/
/* Declaration of command line arguments */
/******************************************************************************/
namespace cll = llvm::cl;

static cll::opt<float> tolerance("tolerance",
                                 cll::desc("tolerance for residual"),
                                 cll::init(0.000001));
static cll::opt<unsigned int>
    maxIterations("maxIterations",
                  cll::desc("Maximum iterations: Default 1000"),
                  cll::init(1000));

static cll::opt<std::string>
    phaseLog("phaseLog",
             cll::desc("Prefix of per-host phase timing CSV files "
                       "(<prefix>.host<ID>.csv), default \"phases\""),
             cll::init("phases"));

static cll::opt<unsigned>
    scanReps("scanReps",
             cll::desc("Idle passes used to calibrate the cost of scanning "
                       "all masters without work (default 5)"),
             cll::init(5));

static cll::list<uint64_t> pushBlocks(
    "pushBlocks", cll::CommaSeparated,
    cll::desc("Global IDs where the PageRank (push) loop is split into "
              "separately timed blocks of masters; one host only. Each block "
              "is written to <phaseLog>.blocks.host0.csv"));

enum Exec { Sync, Async };

static cll::opt<Exec> execution(
    "exec", cll::desc("Distributed Execution Model (default value Async):"),
    cll::values(clEnumVal(Sync, "Bulk-synchronous Parallel (BSP)"),
                clEnumVal(Async, "Bulk-asynchronous Parallel (BASP)")),
    cll::init(Async));

/******************************************************************************/
/* Graph structure declarations + other initialization */
/******************************************************************************/

static const float alpha = (1.0 - 0.85);
struct NodeData {
  float value;
  std::atomic<uint32_t> nout;
  float delta;
  std::atomic<float> residual;
};

galois::DynamicBitSet bitset_residual;
galois::DynamicBitSet bitset_nout;

typedef galois::graphs::DistGraph<NodeData, void> Graph;
typedef typename Graph::GraphNode GNode;
typedef GNode WorkItem;

std::unique_ptr<galois::graphs::GluonSubstrate<Graph>> syncSubstrate;

#include "pagerank_push_sync.hh"

/******************************************************************************/
/* Phase profiling */
/******************************************************************************/

// One record per BSP round on this host.
// delta: PageRank_delta do_all (residual -> value, delta);
// reset: reset_mirrorField; push: PageRank do_all (delta -> residual of
// neighbours); sync: Gluon sync of residual; term: global reduce of the
// active-vertex counter.
// got: masters with residual > 0 in PageRank_delta; active: masters that sent
// delta in PageRank; edges: edges they sent along.
// The t_* fields are absolute steady_clock times in microseconds: all hosts on
// one machine share this clock, so waiting for the slowest host can be derived
// afterwards without an extra barrier.
struct RoundRecord {
  unsigned run;
  unsigned round;
  double delta_us;
  double reset_us;
  double push_us;
  double sync_us;
  double term_us;
  uint64_t got;
  uint64_t active;
  uint64_t edges;
  double t_start_us;
  double t_compute_end_us;
  double t_sync_end_us;
  double t_term_end_us;
};

std::vector<RoundRecord> roundLog;

// --pushBlocks: push time of each block of masters per round.
struct BlockRecord {
  unsigned run;
  unsigned round;
  unsigned block;
  double push_us;
  uint64_t active;
  uint64_t edges;
};

std::vector<BlockRecord> blockLog;
// Plain counters: the profiler runs one thread per host (checked in main);
// GAccumulator costs ~10% of the run time on road graphs.
uint64_t gotCount  = 0;
uint64_t edgeCount = 0;

using Clock = std::chrono::steady_clock;

static double usBetween(Clock::time_point a, Clock::time_point b) {
  return std::chrono::duration<double, std::micro>(b - a).count();
}

static double absUs(Clock::time_point t) {
  return std::chrono::duration<double, std::micro>(t.time_since_epoch()).count();
}

/******************************************************************************/
/* Algorithm structures */
/******************************************************************************/

// Reset all fields of all nodes to 0
struct ResetGraph {
  Graph* graph;

  ResetGraph(Graph* _graph) : graph(_graph) {}
  void static go(Graph& _graph) {
    const auto& allNodes = _graph.allNodesRange();
    if (personality == GPU_CUDA) {
#ifdef GALOIS_ENABLE_GPU
      std::string impl_str("ResetGraph_" +
                           (syncSubstrate->get_run_identifier()));
      galois::StatTimer StatTimer_cuda(impl_str.c_str(), REGION_NAME);
      StatTimer_cuda.start();
      ResetGraph_allNodes_cuda(cuda_ctx);
      StatTimer_cuda.stop();
#else
      abort();
#endif
    } else if (personality == CPU) {
      galois::do_all(
          galois::iterate(allNodes.begin(), allNodes.end()),
          ResetGraph{&_graph}, galois::no_stats(),
          galois::loopname(
              syncSubstrate->get_run_identifier("ResetGraph").c_str()));
    }
  }

  void operator()(GNode src) const {
    NodeData& sdata = graph->getData(src);
    sdata.value     = 0;
    sdata.nout      = 0;
    sdata.residual  = 0;
    sdata.delta     = 0;
  }
};

// Initialize residual at nodes with outgoing edges + find nout for
// nodes with outgoing edges
struct InitializeGraph {
  const float& local_alpha;
  Graph* graph;

  InitializeGraph(const float& _alpha, Graph* _graph)
      : local_alpha(_alpha), graph(_graph) {}

  void static go(Graph& _graph) {
    // first initialize all fields to 0 via ResetGraph (can't assume all zero
    // at start)
    ResetGraph::go(_graph);

    const auto& nodesWithEdges = _graph.allNodesWithEdgesRange();

    if (personality == GPU_CUDA) {
#ifdef GALOIS_ENABLE_GPU
      std::string impl_str("InitializeGraph_" +
                           (syncSubstrate->get_run_identifier()));
      galois::StatTimer StatTimer_cuda(impl_str.c_str(), REGION_NAME);
      StatTimer_cuda.start();
      InitializeGraph_nodesWithEdges_cuda(alpha, cuda_ctx);
      StatTimer_cuda.stop();
#else
      abort();
#endif
    } else if (personality == CPU) {
      // regular do all without stealing; just initialization of nodes with
      // outgoing edges
      galois::do_all(
          galois::iterate(nodesWithEdges.begin(), nodesWithEdges.end()),
          InitializeGraph{alpha, &_graph}, galois::steal(), galois::no_stats(),
          galois::loopname(
              syncSubstrate->get_run_identifier("InitializeGraph").c_str()));
    }

    syncSubstrate->sync<writeSource, readSource, Reduce_add_nout, Bitset_nout>(
        "InitializeGraphNout");
  }

  void operator()(GNode src) const {
    NodeData& sdata = graph->getData(src);
    sdata.residual  = local_alpha;
    uint32_t num_edges =
        std::distance(graph->edge_begin(src), graph->edge_end(src));
    galois::atomicAdd(sdata.nout, num_edges);
    bitset_nout.set(src);
  }
};

struct PageRank_delta {
  const float& local_alpha;
  cll::opt<float>& local_tolerance;
  Graph* graph;

  PageRank_delta(const float& _local_alpha, cll::opt<float>& _local_tolerance,
                 Graph* _graph)
      : local_alpha(_local_alpha), local_tolerance(_local_tolerance),
        graph(_graph) {}

  void static go(Graph& _graph) {
    const auto& nodesWithEdges = _graph.allNodesWithEdgesRange();

    if (personality == GPU_CUDA) {
#ifdef GALOIS_ENABLE_GPU
      std::string impl_str("PageRank_" + (syncSubstrate->get_run_identifier()));
      galois::StatTimer StatTimer_cuda(impl_str.c_str(), REGION_NAME);
      StatTimer_cuda.start();
      PageRank_delta_nodesWithEdges_cuda(alpha, tolerance, cuda_ctx);
      StatTimer_cuda.stop();
#else
      abort();
#endif
    } else if (personality == CPU) {
      galois::do_all(
          galois::iterate(nodesWithEdges.begin(), nodesWithEdges.end()),
          PageRank_delta{alpha, tolerance, &_graph}, galois::no_stats(),
          galois::loopname(
              syncSubstrate->get_run_identifier("PageRank_delta").c_str()));
    }
  }

  void operator()(WorkItem src) const {
    NodeData& sdata = graph->getData(src);

    if (sdata.residual > 0) {
      ++gotCount;
      float residual_old = sdata.residual;
      sdata.residual     = 0;
      sdata.value += residual_old;
      if (residual_old > this->local_tolerance) {
        if (sdata.nout > 0) {
          sdata.delta = residual_old * (1 - local_alpha) / sdata.nout;
        }
      }
    }
  }
};

template <bool async>
struct PageRank {
  Graph* graph;
  using DGTerminatorDetector =
      typename std::conditional<async, galois::DGTerminator<unsigned int>,
                                galois::DGAccumulator<unsigned int>>::type;

  DGTerminatorDetector& active_vertices;

  PageRank(Graph* _g, DGTerminatorDetector& _dga)
      : graph(_g), active_vertices(_dga) {}

  void static go(Graph& _graph) {
    unsigned _num_iterations   = 0;
    const auto& nodesWithEdges = _graph.allNodesWithEdgesRange();
    DGTerminatorDetector dga;

    bool more = false;

    do {
      syncSubstrate->set_num_round(_num_iterations);
      gotCount = 0;
      edgeCount = 0;
      auto tStart = Clock::now();
      PageRank_delta::go(_graph);
      auto tDelta = Clock::now();
      dga.reset();
      // reset residual on mirrors
      syncSubstrate->reset_mirrorField<Reduce_add_residual>();
      auto tReset = Clock::now();

      if (personality == GPU_CUDA) {
#ifdef GALOIS_ENABLE_GPU
        std::string impl_str("PageRank_" +
                             (syncSubstrate->get_run_identifier()));
        galois::StatTimer StatTimer_cuda(impl_str.c_str(), REGION_NAME);
        StatTimer_cuda.start();
        unsigned int __retval = 0;
        PageRank_nodesWithEdges_cuda(__retval, cuda_ctx);
        dga += __retval;
        StatTimer_cuda.stop();
#else
        abort();
#endif
      } else if (personality == CPU && pushBlocks.empty()) {
        galois::do_all(
            galois::iterate(nodesWithEdges), PageRank{&_graph, dga},
            galois::no_stats(), galois::steal(),
            galois::loopname(
                syncSubstrate->get_run_identifier("PageRank").c_str()));
      } else if (personality == CPU) {
        // one host: local ID == global ID, masters are [0, numMasters)
        std::vector<uint64_t> bounds{0};
        for (uint64_t b : pushBlocks)
          bounds.push_back(b);
        bounds.push_back(_graph.numMasters());
        for (unsigned b = 0; b + 1 < bounds.size(); ++b) {
          uint64_t activeBefore = dga.read_local();
          uint64_t edgesBefore  = edgeCount;
          auto t0               = Clock::now();
          galois::do_all(
              galois::iterate((GNode)bounds[b], (GNode)bounds[b + 1]),
              PageRank{&_graph, dga}, galois::no_stats(), galois::steal(),
              galois::loopname(
                  syncSubstrate->get_run_identifier("PageRank").c_str()));
          blockLog.push_back({syncSubstrate->get_run_num(), _num_iterations, b,
                              usBetween(t0, Clock::now()),
                              dga.read_local() - activeBefore,
                              edgeCount - edgesBefore});
        }
      }

      auto tCompute = Clock::now();

      syncSubstrate->sync<writeDestination, readSource, Reduce_add_residual,
                          Bitset_residual, async>("PageRank");
      auto tSync = Clock::now();

      uint64_t localActive = dga.read_local();
      galois::runtime::reportStat_Tsum(
          REGION_NAME, "NumWorkItems_" + (syncSubstrate->get_run_identifier()),
          (unsigned long)localActive);

      unsigned round = _num_iterations;
      ++_num_iterations;

      auto tTermStart = Clock::now();
      more = (async || (_num_iterations < maxIterations)) &&
             dga.reduce(syncSubstrate->get_run_identifier());
      auto tTerm = Clock::now();

      roundLog.push_back({syncSubstrate->get_run_num(), round,
                          usBetween(tStart, tDelta), usBetween(tDelta, tReset),
                          usBetween(tReset, tCompute), usBetween(tCompute, tSync),
                          usBetween(tTermStart, tTerm), gotCount,
                          localActive, edgeCount, absUs(tStart),
                          absUs(tCompute), absUs(tSync), absUs(tTerm)});
    } while (more);

    if (galois::runtime::getSystemNetworkInterface().ID == 0) {
      galois::runtime::reportStat_Single(
          REGION_NAME,
          "NumIterations_" + std::to_string(syncSubstrate->get_run_num()),
          (unsigned long)_num_iterations);
    }
  }

  void operator()(WorkItem src) const {
    NodeData& sdata = graph->getData(src);
    if (sdata.delta > 0) {
      float _delta = sdata.delta;
      sdata.delta  = 0;

      active_vertices += 1; // this should be moved to Pagerank_delta operator
      edgeCount += *graph->edge_end(src) - *graph->edge_begin(src);

      for (auto nbr : graph->edges(src)) {
        GNode dst       = graph->getEdgeDst(nbr);
        NodeData& ddata = graph->getData(dst);

        galois::atomicAdd(ddata.residual, _delta);

        bitset_residual.set(dst);
      }
    }
  }
};

/******************************************************************************/
/* Sanity check operators */
/******************************************************************************/

// Gets various values from the pageranks values/residuals of the graph
struct PageRankSanity {
  cll::opt<float>& local_tolerance;
  Graph* graph;

  galois::DGAccumulator<float>& DGAccumulator_sum;
  galois::DGAccumulator<float>& DGAccumulator_sum_residual;
  galois::DGAccumulator<uint64_t>& DGAccumulator_residual_over_tolerance;

  galois::DGReduceMax<float>& max_value;
  galois::DGReduceMin<float>& min_value;
  galois::DGReduceMax<float>& max_residual;
  galois::DGReduceMin<float>& min_residual;

  PageRankSanity(
      cll::opt<float>& _local_tolerance, Graph* _graph,
      galois::DGAccumulator<float>& _DGAccumulator_sum,
      galois::DGAccumulator<float>& _DGAccumulator_sum_residual,
      galois::DGAccumulator<uint64_t>& _DGAccumulator_residual_over_tolerance,
      galois::DGReduceMax<float>& _max_value,
      galois::DGReduceMin<float>& _min_value,
      galois::DGReduceMax<float>& _max_residual,
      galois::DGReduceMin<float>& _min_residual)
      : local_tolerance(_local_tolerance), graph(_graph),
        DGAccumulator_sum(_DGAccumulator_sum),
        DGAccumulator_sum_residual(_DGAccumulator_sum_residual),
        DGAccumulator_residual_over_tolerance(
            _DGAccumulator_residual_over_tolerance),
        max_value(_max_value), min_value(_min_value),
        max_residual(_max_residual), min_residual(_min_residual) {}

  void static go(Graph& _graph, galois::DGAccumulator<float>& DGA_sum,
                 galois::DGAccumulator<float>& DGA_sum_residual,
                 galois::DGAccumulator<uint64_t>& DGA_residual_over_tolerance,
                 galois::DGReduceMax<float>& max_value,
                 galois::DGReduceMin<float>& min_value,
                 galois::DGReduceMax<float>& max_residual,
                 galois::DGReduceMin<float>& min_residual) {
    DGA_sum.reset();
    DGA_sum_residual.reset();
    max_value.reset();
    max_residual.reset();
    min_value.reset();
    min_residual.reset();
    DGA_residual_over_tolerance.reset();

    if (personality == GPU_CUDA) {
#ifdef GALOIS_ENABLE_GPU
      float _max_value;
      float _min_value;
      float _sum_value;
      float _sum_residual;
      uint64_t num_residual_over_tolerance;
      float _max_residual;
      float _min_residual;
      PageRankSanity_masterNodes_cuda(
          num_residual_over_tolerance, _sum_value, _sum_residual, _max_residual,
          _max_value, _min_residual, _min_value, tolerance, cuda_ctx);
      DGA_sum += _sum_value;
      DGA_sum_residual += _sum_residual;
      DGA_residual_over_tolerance += num_residual_over_tolerance;
      max_value.update(_max_value);
      max_residual.update(_max_residual);
      min_value.update(_min_value);
      min_residual.update(_min_residual);
#else
      abort();
#endif
    } else {
      galois::do_all(galois::iterate(_graph.masterNodesRange().begin(),
                                     _graph.masterNodesRange().end()),
                     PageRankSanity(tolerance, &_graph, DGA_sum,
                                    DGA_sum_residual,
                                    DGA_residual_over_tolerance, max_value,
                                    min_value, max_residual, min_residual),
                     galois::no_stats(), galois::loopname("PageRankSanity"));
    }

    float max_rank          = max_value.reduce();
    float min_rank          = min_value.reduce();
    float rank_sum          = DGA_sum.reduce();
    float residual_sum      = DGA_sum_residual.reduce();
    uint64_t over_tolerance = DGA_residual_over_tolerance.reduce();
    float max_res           = max_residual.reduce();
    float min_res           = min_residual.reduce();

    // Only node 0 will print data
    if (galois::runtime::getSystemNetworkInterface().ID == 0) {
      galois::gPrint("Max rank is ", max_rank, "\n");
      galois::gPrint("Min rank is ", min_rank, "\n");
      galois::gPrint("Rank sum is ", rank_sum, "\n");
      galois::gPrint("Residual sum is ", residual_sum, "\n");
      galois::gPrint("# nodes with residual over ", tolerance,
                     " (tolerance) is ", over_tolerance, "\n");
      galois::gPrint("Max residual is ", max_res, "\n");
      galois::gPrint("Min residual is ", min_res, "\n");
    }
  }

  /* Gets the max, min rank from all owned nodes and
   * also the sum of ranks */
  void operator()(GNode src) const {
    NodeData& sdata = graph->getData(src);

    max_value.update(sdata.value);
    min_value.update(sdata.value);
    max_residual.update(sdata.residual);
    min_residual.update(sdata.residual);

    DGAccumulator_sum += sdata.value;
    DGAccumulator_sum_residual += sdata.residual;

    if (sdata.residual > local_tolerance) {
      DGAccumulator_residual_over_tolerance += 1;
    }
  }
};

/******************************************************************************/
/* Profiling helpers */
/******************************************************************************/

struct ScanCost {
  double delta_us; // median idle PageRank_delta pass, -1 if not idle
  double push_us;  // median idle PageRank pass, -1 if not idle
};

std::vector<ScanCost> scanCosts; // one per run

// Runs both do_alls of a round right after convergence, when residual and
// delta are 0 at every master: each call only evaluates the empty checks.
// The median of these idle passes is the cost of scanning all masters.
// If the run stopped at maxIterations the state is not idle and the
// calibration is skipped (-1).
ScanCost calibrateScanCost(Graph& _graph) {
  const auto& nodesWithEdges = _graph.allNodesWithEdgesRange();
  galois::DGAccumulator<unsigned int> dga;
  std::vector<double> d, p;
  dga.reset();

  for (unsigned rep = 0; rep < std::max(1u, (unsigned)scanReps); ++rep) {
    gotCount = 0;
    auto t0 = Clock::now();
    galois::do_all(
        galois::iterate(nodesWithEdges.begin(), nodesWithEdges.end()),
        PageRank_delta{alpha, tolerance, &_graph}, galois::no_stats(),
        galois::loopname("PageRank_delta_scan_calibration"));
    auto t1 = Clock::now();
    galois::do_all(galois::iterate(nodesWithEdges),
                   PageRank<false>{&_graph, dga}, galois::no_stats(),
                   galois::steal(),
                   galois::loopname("PageRank_scan_calibration"));
    auto t2 = Clock::now();
    if (gotCount != 0 || dga.read_local() != 0) {
      return {-1, -1};
    }
    d.push_back(usBetween(t0, t1));
    p.push_back(usBetween(t1, t2));
  }
  std::sort(d.begin(), d.end());
  std::sort(p.begin(), p.end());
  return {d[d.size() / 2], p[p.size() / 2]};
}

void writeBlockLog() {
  std::ofstream out(std::string(phaseLog) + ".blocks.host0.csv");
  out << "# bounds=0";
  for (uint64_t b : pushBlocks)
    out << ";" << b;
  out << "\nrun,round,block,push_us,active,edges\n";
  out << std::fixed << std::setprecision(3);
  for (const auto& r : blockLog) {
    out << r.run << "," << r.round << "," << r.block << "," << r.push_us << ","
        << r.active << "," << r.edges << "\n";
  }
}

void writePhaseLog(Graph& _graph) {
  const auto& net = galois::runtime::getSystemNetworkInterface();
  std::string fname =
      std::string(phaseLog) + ".host" + std::to_string(net.ID) + ".csv";
  std::ofstream out(fname);
  out << "# host=" << net.ID << " hosts=" << net.Num
      << " threads=" << galois::getActiveThreads()
      << " masters=" << _graph.numMasters()
      << " mirrors=" << (_graph.size() - _graph.numMasters())
      << " nodes_with_edges=" << _graph.getNumNodesWithEdges()
      << " local_edges=" << _graph.sizeEdges() << " tolerance=" << tolerance
      << "\n";
  out << "run,round,delta_us,reset_us,push_us,sync_us,term_us,got,active,edges,"
         "t_start_us,t_compute_end_us,t_sync_end_us,t_term_end_us,"
         "scan_delta_us,scan_push_us\n";
  out << std::fixed << std::setprecision(3);
  for (const auto& r : roundLog) {
    const ScanCost& sc = scanCosts.at(r.run);
    out << r.run << "," << r.round << "," << r.delta_us << "," << r.reset_us
        << "," << r.push_us << "," << r.sync_us << "," << r.term_us << ","
        << r.got << "," << r.active << "," << r.edges << "," << r.t_start_us
        << "," << r.t_compute_end_us << "," << r.t_sync_end_us << ","
        << r.t_term_end_us << "," << sc.delta_us << "," << sc.push_us << "\n";
  }
}

/******************************************************************************/
/* Make results */
/******************************************************************************/

std::vector<float> makeResultsCPU(std::unique_ptr<Graph>& hg) {
  std::vector<float> values;

  values.reserve(hg->numMasters());
  for (auto node : hg->masterNodesRange()) {
    values.push_back(hg->getData(node).value);
  }

  return values;
}

#ifdef GALOIS_ENABLE_GPU
std::vector<float> makeResultsGPU(std::unique_ptr<Graph>& hg) {
  std::vector<float> values;

  values.reserve(hg->numMasters());
  for (auto node : hg->masterNodesRange()) {
    values.push_back(get_node_value_cuda(cuda_ctx, node));
  }

  return values;
}
#else
std::vector<float> makeResultsGPU(std::unique_ptr<Graph>& /*unused*/) {
  abort();
}
#endif

std::vector<float> makeResults(std::unique_ptr<Graph>& hg) {
  switch (personality) {
  case CPU:
    return makeResultsCPU(hg);
  case GPU_CUDA:
    return makeResultsGPU(hg);
  default:
    abort();
  }
}

/******************************************************************************/
/* Main */
/******************************************************************************/

constexpr static const char* const name = "PageRank - Compiler Generated "
                                          "Distributed Heterogeneous, "
                                          "per-round phase profiling";
constexpr static const char* const desc =
    "Residual PageRank on Distributed Galois; writes per-round phase times and "
    "useful/empty master counts per host to <phaseLog>.host<ID>.csv.";
constexpr static const char* const url = 0;

int main(int argc, char** argv) {
  galois::DistMemSys G;
  DistBenchStart(argc, argv, name, desc, url);

  auto& net = galois::runtime::getSystemNetworkInterface();

  if (net.ID == 0) {
    galois::runtime::reportParam(REGION_NAME, "Max Iterations", maxIterations);
    std::ostringstream ss;
    ss << tolerance;
    galois::runtime::reportParam(REGION_NAME, "Tolerance", ss.str());
  }
  galois::StatTimer StatTimer_total("TimerTotal", REGION_NAME);

  if (galois::getActiveThreads() != 1) {
    GALOIS_DIE("phase profiling counts work in plain variables: run with -t=1");
  }

  if (!pushBlocks.empty() && net.Num != 1) {
    GALOIS_DIE("--pushBlocks needs one host: blocks are global ID ranges");
  }

  if (execution != Sync) {
    GALOIS_DIE("phase profiling needs --exec=Sync: rounds of BASP are not "
               "aligned across hosts");
  }

  StatTimer_total.start();

  std::unique_ptr<Graph> hg;
#ifdef GALOIS_ENABLE_GPU
  std::tie(hg, syncSubstrate) =
      distGraphInitialization<NodeData, void>(&cuda_ctx);
#else
  std::tie(hg, syncSubstrate) = distGraphInitialization<NodeData, void>();
#endif

  bitset_residual.resize(hg->size());
  bitset_nout.resize(hg->size());

  galois::gPrint("[", net.ID, "] InitializeGraph::go called\n");

  InitializeGraph::go((*hg));
  galois::runtime::getHostBarrier().wait();

  galois::DGAccumulator<float> DGA_sum;
  galois::DGAccumulator<float> DGA_sum_residual;
  galois::DGAccumulator<uint64_t> DGA_residual_over_tolerance;
  galois::DGReduceMax<float> max_value;
  galois::DGReduceMin<float> min_value;
  galois::DGReduceMax<float> max_residual;
  galois::DGReduceMin<float> min_residual;

  for (auto run = 0; run < numRuns; ++run) {
    galois::gPrint("[", net.ID, "] PageRank::go run ", run, " called\n");
    std::string timer_str("Timer_" + std::to_string(run));
    galois::StatTimer StatTimer_main(timer_str.c_str(), REGION_NAME);

    StatTimer_main.start();
    if (execution == Async) {
      PageRank<true>::go(*hg);
    } else {
      PageRank<false>::go(*hg);
    }
    StatTimer_main.stop();

    // outside the timer: idle passes after convergence
    galois::runtime::getHostBarrier().wait();
    scanCosts.push_back(calibrateScanCost(*hg));
    galois::runtime::getHostBarrier().wait();

    // sanity check
    PageRankSanity::go(*hg, DGA_sum, DGA_sum_residual,
                       DGA_residual_over_tolerance, max_value, min_value,
                       max_residual, min_residual);

    if ((run + 1) != numRuns) {
      if (personality == GPU_CUDA) {
#ifdef GALOIS_ENABLE_GPU
        bitset_residual_reset_cuda(cuda_ctx);
        bitset_nout_reset_cuda(cuda_ctx);
#else
        abort();
#endif
      } else {
        bitset_residual.reset();
        bitset_nout.reset();
      }

      (*syncSubstrate).set_num_run(run + 1);
      InitializeGraph::go(*hg);
      galois::runtime::getHostBarrier().wait();
    }
  }

  StatTimer_total.stop();

  writePhaseLog(*hg);
  if (!pushBlocks.empty()) {
    writeBlockLog();
  }

  if (output) {
    std::vector<float> results = makeResults(hg);
    auto globalIDs             = hg->getMasterGlobalIDs();
    assert(results.size() == globalIDs.size());

    writeOutput(outputLocation, "pagerank", results.data(), results.size(),
                globalIDs.data());
  }

  return 0;
}
