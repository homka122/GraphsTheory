# Профилировщик фаз PageRank push: pagerank_push.cpp из Galois с замерами времени по фазам раунда
# и счётчиками полезных и пустых вершин. Флаги, include и define берём у каталога, где собирается
# pagerank-push-dist, чтобы оба бинарника отличались только кодом профилировщика.
set(GALOIS_PR_DIR ${GALOIS_DIR}/lonestar/analytics/distributed/pagerank)
get_directory_property(PR_OPTIONS DIRECTORY ${GALOIS_PR_DIR} COMPILE_OPTIONS)
get_directory_property(PR_DEFINITIONS DIRECTORY ${GALOIS_PR_DIR} COMPILE_DEFINITIONS)
get_directory_property(PR_INCLUDES DIRECTORY ${GALOIS_PR_DIR} INCLUDE_DIRECTORIES)
get_directory_property(PR_LINK_OPTIONS DIRECTORY ${GALOIS_PR_DIR} LINK_OPTIONS)

add_executable(pagerank-push-prof-dist pagerank_push_prof.cpp)
target_compile_options(pagerank-push-prof-dist PRIVATE ${PR_OPTIONS})
target_link_options(pagerank-push-prof-dist PRIVATE ${PR_LINK_OPTIONS})
target_compile_definitions(pagerank-push-prof-dist PRIVATE ${PR_DEFINITIONS})
target_include_directories(pagerank-push-prof-dist PRIVATE ${PR_INCLUDES} ${GALOIS_PR_DIR})
target_link_libraries(pagerank-push-prof-dist Galois::shmem LLVMSupport distbench)
