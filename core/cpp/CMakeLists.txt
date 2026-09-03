cmake_minimum_required(VERSION 3.16)
project(sih26168_nav LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(nav_core STATIC
  src/math.cpp
  src/leansolver.cpp
  src/preprocess.cpp
  src/inference.cpp
  src/inekf.cpp
  src/graphpf.cpp
  src/aiding.cpp
  src/metrics.cpp
  src/engine.cpp
)
target_include_directories(nav_core PUBLIC ${CMAKE_CURRENT_SOURCE_DIR}/include)

add_executable(nav_golden tests/golden.cpp)
target_link_libraries(nav_golden PRIVATE nav_core)
target_include_directories(nav_golden PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/include)

enable_testing()
add_test(NAME golden COMMAND nav_golden)
