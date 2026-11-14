#!/bin/sh
# Builds this project with its CMake preset: ./build.sh (release, into build/) or ./build.sh debug
# (into build-debug/). GAMETANK_LLVM_MOS, the gametank-llvm-mos folder, is the one above this one
# unless it's already set.
set -e
cd "$(dirname "$0")"
GAMETANK_LLVM_MOS="${GAMETANK_LLVM_MOS:-$(pwd)/..}"
export GAMETANK_LLVM_MOS
preset="${1:-release}"
cmake --preset "$preset"
cmake --build --preset "$preset"
