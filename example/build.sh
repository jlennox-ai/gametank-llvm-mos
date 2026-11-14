#!/bin/sh
# Builds this project with its CMake preset: ./build.sh (release, into build/) or ./build.sh debug
# (into build-debug/).
set -e
cd "$(dirname "$0")"
preset="${1:-release}"
cmake --preset "$preset"
cmake --build --preset "$preset"
