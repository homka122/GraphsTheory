# Профилировщик фаз BFS push: bfs_push.cpp из Galois с замерами времени по фазам раунда.
# Флаги, include и define берём у каталога, где собирается bfs-push-dist,
# чтобы оба бинарника отличались только кодом профилировщика.
set(GALOIS_BFS_DIR ${GALOIS_DIR}/lonestar/analytics/distributed/bfs)
get_directory_property(BFS_OPTIONS DIRECTORY ${GALOIS_BFS_DIR} COMPILE_OPTIONS)
get_directory_property(BFS_DEFINITIONS DIRECTORY ${GALOIS_BFS_DIR} COMPILE_DEFINITIONS)
get_directory_property(BFS_INCLUDES DIRECTORY ${GALOIS_BFS_DIR} INCLUDE_DIRECTORIES)
get_directory_property(BFS_LINK_OPTIONS DIRECTORY ${GALOIS_BFS_DIR} LINK_OPTIONS)

add_executable(bfs-push-prof-dist bfsprof_push.cpp)
target_compile_options(bfs-push-prof-dist PRIVATE ${BFS_OPTIONS})
target_link_options(bfs-push-prof-dist PRIVATE ${BFS_LINK_OPTIONS})
target_compile_definitions(bfs-push-prof-dist PRIVATE ${BFS_DEFINITIONS})
target_include_directories(bfs-push-prof-dist PRIVATE ${BFS_INCLUDES} ${GALOIS_BFS_DIR})
target_link_libraries(bfs-push-prof-dist Galois::shmem LLVMSupport distbench)
