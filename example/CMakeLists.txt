cmake_minimum_required(VERSION 3.21)

# gametank-llvm-mos is the folder above this one. Included before project(): it picks the compiler.
include("${CMAKE_CURRENT_LIST_DIR}/../cmake/gametank.cmake")

project(example C ASM)

gametank_add_rom(example main.c)
