# CMake toolchain for GameTank programs: llvm-mos's clang, from dev/llvm-mos, with its
# target-independent mos-common configuration (link-time optimization, the C library), for the
# GameTank's CPU, a W65C02S. gametank.cmake selects it; gametank_add_rom adds the GameTank's own
# setup (the SDK and its linker script).
set(CMAKE_SYSTEM_NAME Generic)
set(CMAKE_SYSTEM_PROCESSOR mos)

get_filename_component(gametank_llvm_mos "${CMAKE_CURRENT_LIST_DIR}/../dev/llvm-mos" ABSOLUTE)
if(CMAKE_HOST_WIN32)
  set(gametank_executable_suffix ".exe")
else()
  set(gametank_executable_suffix "")
endif()
set(CMAKE_C_COMPILER "${gametank_llvm_mos}/bin/mos-clang${gametank_executable_suffix}")
if(NOT EXISTS "${CMAKE_C_COMPILER}")
  message(FATAL_ERROR "llvm-mos isn't in ${gametank_llvm_mos}: see README.md, \"Setting up\"")
endif()
set(CMAKE_ASM_COMPILER "${CMAKE_C_COMPILER}")
set(CMAKE_AR "${gametank_llvm_mos}/bin/llvm-ar${gametank_executable_suffix}")
set(CMAKE_RANLIB "${gametank_llvm_mos}/bin/llvm-ranlib${gametank_executable_suffix}")

# These go to both compiling and linking: with link-time optimization, the code is generated at
# the link. Always -g: the debug files are written from the debug info.
set(CMAKE_C_FLAGS_INIT "--config mos-common.cfg -mcpu=mosw65c02 -g")
set(CMAKE_ASM_FLAGS_INIT "--config mos-common.cfg -mcpu=mosw65c02 -g")
# The debug build: every function stays its own routine and the code follows the source closely,
# and no static stack (functions' locals at fixed zero-page addresses the debug info doesn't
# describe), so the emulator can show every variable. GT_DEBUG_BUILD turns on GT_DEBUG_FUNCTION
# (sdk/gametank.h).
set(CMAKE_C_FLAGS_DEBUG_INIT "-Og -fno-inline -fno-static-stack -DGT_DEBUG_BUILD")
set(CMAKE_C_FLAGS_MINSIZEREL_INIT "-Os")

# A program can't be linked without the SDK's linker script, so CMake's compiler checks build
# static libraries instead.
set(CMAKE_TRY_COMPILE_TARGET_TYPE STATIC_LIBRARY)

if(NOT CMAKE_BUILD_TYPE AND NOT CMAKE_CONFIGURATION_TYPES)
  set(CMAKE_BUILD_TYPE MinSizeRel CACHE STRING "MinSizeRel (the default) or Debug" FORCE)
endif()
