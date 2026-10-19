# Профилировщик фаз SSSP push: sssp_push.cpp из Galois с замерами времени по фазам раунда.
# Флаги, include и define берём у каталога, где собирается sssp-push-dist,
# чтобы оба бинарника отличались только кодом профилировщика.
set(GALOIS_SSSP_DIR ${GALOIS_DIR}/lonestar/analytics/distributed/sssp)
get_directory_property(SSSP_OPTIONS DIRECTORY ${GALOIS_SSSP_DIR} COMPILE_OPTIONS)
get_directory_property(SSSP_DEFINITIONS DIRECTORY ${GALOIS_SSSP_DIR} COMPILE_DEFINITIONS)
get_directory_property(SSSP_INCLUDES DIRECTORY ${GALOIS_SSSP_DIR} INCLUDE_DIRECTORIES)
get_directory_property(SSSP_LINK_OPTIONS DIRECTORY ${GALOIS_SSSP_DIR} LINK_OPTIONS)

add_executable(sssp-push-prof-dist sssp_push_prof.cpp)
target_compile_options(sssp-push-prof-dist PRIVATE ${SSSP_OPTIONS})
target_link_options(sssp-push-prof-dist PRIVATE ${SSSP_LINK_OPTIONS})
target_compile_definitions(sssp-push-prof-dist PRIVATE ${SSSP_DEFINITIONS})
target_include_directories(sssp-push-prof-dist PRIVATE ${SSSP_INCLUDES} ${GALOIS_SSSP_DIR})
target_link_libraries(sssp-push-prof-dist Galois::shmem LLVMSupport distbench)
