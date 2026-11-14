# What find_package(gametank-llvm-mos) loads: cmake/gametank.cmake, which describes it all. A
# project finds it with GAMETANK_LLVM_MOS, the gametank-llvm-mos folder, before project():
#
#   find_package(gametank-llvm-mos REQUIRED HINTS "$ENV{GAMETANK_LLVM_MOS}")
include("${CMAKE_CURRENT_LIST_DIR}/gametank.cmake")
