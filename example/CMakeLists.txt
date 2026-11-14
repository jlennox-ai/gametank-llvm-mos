cmake_minimum_required(VERSION 3.21)

# GAMETANK_LLVM_MOS is the gametank-llvm-mos folder (build.sh and build.bat set it if it isn't).
# Found before project(): it picks the compiler.
find_package(gametank-llvm-mos REQUIRED HINTS "$ENV{GAMETANK_LLVM_MOS}")

project(example C ASM)

gametank_add_rom(example main.c)
