# Residual core (C++): pure RPT2 PFS/session keying + wire helpers.
# Build (from monorepo root or this dir):
#   cmake -S residual_core -B residual_core/build && cmake --build residual_core/build
#   residual_core/build/residual_core_tests

cmake_minimum_required(VERSION 3.16)
project(residual_core LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# OpenSSL 3 (Homebrew on Apple Silicon: /opt/homebrew/opt/openssl@3)
if(APPLE AND EXISTS "/opt/homebrew/opt/openssl@3")
  set(OPENSSL_ROOT_DIR "/opt/homebrew/opt/openssl@3")
endif()
find_package(OpenSSL REQUIRED)

add_library(residual_core STATIC
  src/protocol.cpp
  src/pfs.cpp
  src/c_api.cpp
  src/x25519.cpp
  src/aead.cpp
)
target_include_directories(residual_core
  PUBLIC
    ${CMAKE_CURRENT_SOURCE_DIR}/include
  PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/src
    ${OPENSSL_INCLUDE_DIR}
)
target_link_libraries(residual_core PUBLIC OpenSSL::Crypto)

# Warnings on Clang/AppleClang
if(CMAKE_CXX_COMPILER_ID MATCHES "Clang|AppleClang|GNU")
  target_compile_options(residual_core PRIVATE -Wall -Wextra -Wpedantic)
endif()

add_executable(residual_core_tests tests/test_main.cpp)
target_link_libraries(residual_core_tests PRIVATE residual_core)
target_include_directories(residual_core_tests PRIVATE
  ${CMAKE_CURRENT_SOURCE_DIR}/include
)

enable_testing()
add_test(NAME residual_core_tests COMMAND residual_core_tests)
