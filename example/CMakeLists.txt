cmake_minimum_required(VERSION 3.21)

# GAMETANK_LLVM_MOS is the gametank-llvm-mos folder (build.sh and build.bat set it if it isn't).
# Found before project(): it picks the compiler.
find_package(gametank-llvm-mos REQUIRED HINTS "$ENV{GAMETANK_LLVM_MOS}")

# Your game's name: the image is build/<name>.gtr.
project(example_project_name_here C ASM)

# Every source file (.c, and .S for assembly). Headers aren't listed: the build finds them as
# they're included.
gametank_add_rom(${PROJECT_NAME}
    main.c
    player.c)
gametank_add_tiles(${PROJECT_NAME} assets/tiles.toml)
