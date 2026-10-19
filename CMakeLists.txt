cmake_minimum_required(VERSION 3.13)

project(dgalois-lab C CXX)

# Galois выбирает Release только в своей области видимости, нашим целям нужен тот же режим.
if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)
endif()
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)
set(CMAKE_RUNTIME_OUTPUT_DIRECTORY ${PROJECT_BINARY_DIR}/bin)

set(GALOIS_DIR ${PROJECT_SOURCE_DIR}/deps/Galois)
set(GALOIS_ENABLE_DIST ON CACHE BOOL "Enable distributed features")

# Правки апстрима лежат в patches/ и накатываются на deps/Galois, если ещё не накатаны.
file(GLOB GALOIS_PATCHES ${PROJECT_SOURCE_DIR}/patches/*.patch)
foreach(patch ${GALOIS_PATCHES})
  execute_process(COMMAND git apply --reverse --check ${patch}
    WORKING_DIRECTORY ${GALOIS_DIR} RESULT_VARIABLE not_applied OUTPUT_QUIET ERROR_QUIET)
  if(not_applied)
    execute_process(COMMAND git apply ${patch}
      WORKING_DIRECTORY ${GALOIS_DIR} RESULT_VARIABLE failed)
    if(failed)
      message(FATAL_ERROR "Cannot apply ${patch} to ${GALOIS_DIR}")
    endif()
    message(STATUS "Applied ${patch}")
  endif()
endforeach()

add_subdirectory(deps/Galois EXCLUDE_FROM_ALL)

add_subdirectory(src)

# Немодифицированные приложения Galois: по ним меряем время «чёрным ящиком».
add_custom_target(galois-apps ALL)
add_dependencies(galois-apps
  bfs-push-dist bfs-pull-dist sssp-push-dist sssp-pull-dist triangle-counting-dist
  pagerank-push-dist pagerank-pull-dist graph-convert)
