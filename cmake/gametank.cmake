# GameTank programs with llvm-mos. A project's CMakeLists.txt includes this before project(),
# since it picks the compiler (gametank-toolchain.cmake), then adds its cartridge image:
#
#   cmake_minimum_required(VERSION 3.21)
#   include(path/to/gametank-llvm-mos/cmake/gametank.cmake)
#   project(mygame C ASM)
#   gametank_add_rom(mygame main.c player.c)
#
# gametank_add_rom(<name> <source>... [ZERO_PAGE <bytes>] [LINKER_SCRIPT <file>])
#   Builds <name>.gtr, a 2 MB cartridge image, from the sources and the SDK (sdk/), and writes its
#   debug files next to it (tools/debug_files.py). <name> is an ordinary executable target, so
#   target_compile_options, target_compile_definitions and the rest work on it.
#   ZERO_PAGE: how much of zero page link-time optimization may give out, 200 by default. Zero
#     page for variables is $00-$DF (the compiler's imaginary registers are $E0-$FF), less what
#     the SDK's assembly declares there (7 bytes) and what yours does. The link fails if it
#     overflows.
#   LINKER_SCRIPT: a linker script to use instead of sdk/link.ld.
#
# gametank_add_tiles(<name> <config.toml>...)
#   Converts tile sheets into C for <name> with tools/tile_palettes (README.md, "Graphics"):
#   tiles.toml makes tiles.h, which <name>'s sources can include, and tiles.c.
#
# The programs the build runs are in dev/. One that isn't there is downloaded the first time it's
# needed (into the temp folder) and unpacked there:
#   dev/llvm-mos        the compiler: the llvm-mos SDK release below, checked against its SHA-256
#   dev/tile_palettes   the tile tool, for gametank_add_tiles: from this repository's latest
#                       release (whose bundles come with it already in dev/)
# To use another build of either, put it there yourself first.
include_guard(GLOBAL)
cmake_minimum_required(VERSION 3.21)

get_filename_component(GAMETANK_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
if(CMAKE_HOST_WIN32)
  set(GAMETANK_EXECUTABLE_SUFFIX ".exe")
else()
  set(GAMETANK_EXECUTABLE_SUFFIX "")
endif()

# Per system (windows, linux): the file to download, then for llvm-mos its SHA-256.
set(GAMETANK_LLVM_MOS_URL "https://github.com/llvm-mos/llvm-mos-sdk/releases/download/v23.3.0")
set(GAMETANK_LLVM_MOS_windows llvm-mos-windows.7z 77ced2b04c2802a3c92bec8f99dc59110916af6cfe5fff2442bbeadde8de5be2)
set(GAMETANK_LLVM_MOS_linux llvm-mos-linux.tar.xz 9f694497bc93a7c876d8c62325c7d74e7860346d80fbcd0555e19ba6856658c8)
set(GAMETANK_TILE_PALETTES_URL "https://github.com/jlennox-ai/gametank-llvm-mos/releases/latest/download")
set(GAMETANK_TILE_PALETTES_windows tile_palettes-windows-x86_64.zip)
set(GAMETANK_TILE_PALETTES_linux tile_palettes-linux-x86_64.tar.gz)

# Makes sure dev/<folder>/<program> exists. If dev/<folder> doesn't, downloads <url>/<file>, with
# <file> (and its SHA-256, if given) from the list <downloads>_<system>, and unpacks the <folder>
# folder in it to dev/<folder>.
function(_gametank_fetch folder program url downloads)
  set(destination "${GAMETANK_ROOT}/dev/${folder}")
  if(EXISTS "${destination}/${program}")
    return()
  endif()
  if(EXISTS "${destination}")
    message(FATAL_ERROR "${destination} has no ${program}: delete it to have it downloaded again")
  endif()

  cmake_host_system_information(RESULT platform QUERY OS_PLATFORM)
  if(CMAKE_HOST_WIN32 AND platform MATCHES "^(AMD64|x86_64)$")
    set(download ${${downloads}_windows})
  elseif(CMAKE_HOST_UNIX AND NOT CMAKE_HOST_APPLE AND platform STREQUAL "x86_64")
    set(download ${${downloads}_linux})
  else()
    message(FATAL_ERROR "There's no ${folder} download for this system (${platform}): put one in ${destination}")
  endif()
  list(GET download 0 file)
  set(expected_hash "")
  list(LENGTH download download_length)
  if(download_length GREATER 1)
    list(GET download 1 hash)
    set(expected_hash EXPECTED_HASH "SHA256=${hash}")
  endif()

  # Another configure (another build folder) may be fetching it at the same time.
  file(MAKE_DIRECTORY "${GAMETANK_ROOT}/dev")
  file(LOCK "${destination}.lock" GUARD FUNCTION TIMEOUT 1800 RESULT_VARIABLE lock_result)
  if(lock_result)
    message(FATAL_ERROR "Couldn't lock ${destination}.lock: ${lock_result}")
  endif()
  if(EXISTS "${destination}/${program}")
    return()
  endif()

  if(DEFINED ENV{TEMP})
    set(temp "$ENV{TEMP}")
  elseif(DEFINED ENV{TMPDIR})
    set(temp "$ENV{TMPDIR}")
  else()
    set(temp "/tmp")
  endif()
  set(archive "${temp}/gametank-${file}")
  message(STATUS "Downloading ${url}/${file}")
  file(DOWNLOAD "${url}/${file}" "${archive}" ${expected_hash} SHOW_PROGRESS STATUS status)
  list(GET status 0 status_code)
  if(NOT status_code EQUAL 0)
    list(GET status 1 status_message)
    file(REMOVE "${archive}")
    message(FATAL_ERROR "Downloading ${url}/${file} failed: ${status_message}")
  endif()

  # Unpacked beside dev/<folder> and then moved there, so an unpacking cut short never leaves a
  # dev/<folder> that looks complete.
  set(unpacking "${destination}.unpacking")
  file(REMOVE_RECURSE "${unpacking}")
  message(STATUS "Unpacking it into ${destination}")
  file(ARCHIVE_EXTRACT INPUT "${archive}" DESTINATION "${unpacking}")
  if(NOT EXISTS "${unpacking}/${folder}/${program}")
    message(FATAL_ERROR "${file} has no ${folder}/${program}")
  endif()
  file(RENAME "${unpacking}/${folder}" "${destination}")
  file(REMOVE_RECURSE "${unpacking}")
  file(REMOVE "${archive}")
endfunction()

_gametank_fetch(llvm-mos "bin/mos-clang${GAMETANK_EXECUTABLE_SUFFIX}" "${GAMETANK_LLVM_MOS_URL}" GAMETANK_LLVM_MOS)
set(CMAKE_TOOLCHAIN_FILE "${CMAKE_CURRENT_LIST_DIR}/gametank-toolchain.cmake")

function(gametank_add_rom name)
  # The emulator wants the debug files next to the image, and finds the sources from the folder
  # above it, so a build type has a build folder of its own: build/ and build-debug/, as the
  # presets have it, not one per build type inside it.
  get_property(multi_config GLOBAL PROPERTY GENERATOR_IS_MULTI_CONFIG)
  if(multi_config)
    message(FATAL_ERROR "gametank_add_rom needs a single-configuration generator, like Ninja (the presets')")
  endif()
  cmake_parse_arguments(PARSE_ARGV 1 rom "" "ZERO_PAGE;LINKER_SCRIPT" "")
  if(NOT rom_UNPARSED_ARGUMENTS)
    message(FATAL_ERROR "gametank_add_rom(${name}): no sources")
  endif()
  if(NOT DEFINED rom_ZERO_PAGE)
    set(rom_ZERO_PAGE 200)
  endif()
  if(DEFINED rom_LINKER_SCRIPT)
    get_filename_component(linker_script "${rom_LINKER_SCRIPT}" ABSOLUTE)
  else()
    set(linker_script "${GAMETANK_ROOT}/sdk/link.ld")
  endif()

  file(GLOB sdk_sources CONFIGURE_DEPENDS "${GAMETANK_ROOT}/sdk/*.c" "${GAMETANK_ROOT}/sdk/*.S")
  add_executable(${name} ${rom_UNPARSED_ARGUMENTS} ${sdk_sources})
  # The image is <name>.gtr; lld writes the ELF, with its debug info, next to it as <name>.gtr.elf.
  set_target_properties(${name} PROPERTIES SUFFIX ".gtr" LINK_DEPENDS "${linker_script}")
  target_include_directories(${name} PRIVATE "${GAMETANK_ROOT}/sdk")
  # -std=gnu23: C23 with GNU extensions; Clang's default is gnu17.
  # -Werror=return-type: a function that can end without returning its value lets the optimizer
  #   assume that path never runs, and delete code that depends on it.
  target_compile_options(${name} PRIVATE "$<$<COMPILE_LANGUAGE:C>:-std=gnu23;-Werror=return-type>")
  target_link_options(${name} PRIVATE
    "-mlto-zp=${rom_ZERO_PAGE}"
    "-T${linker_script}"
    "-Wl,-Map,${CMAKE_CURRENT_BINARY_DIR}/${name}.map")
  # llvm-mos's startup pieces: setting up the C stack, copying initialised data and zeroing BSS.
  target_link_libraries(${name} PRIVATE init-stack copy-data zero-bss)

  # The debug files: rewritten when the image or the tools that write them change.
  find_package(Python3 3.8 REQUIRED COMPONENTS Interpreter)
  set(build_folder "${CMAKE_CURRENT_BINARY_DIR}")
  set(debug_files "${build_folder}/${name}.lbl" "${build_folder}/sourcemap.dbg" "${build_folder}/variables.dbg"
    "${build_folder}/out.map" "${build_folder}/assembly.s")
  file(GLOB tools CONFIGURE_DEPENDS "${GAMETANK_ROOT}/tools/*.py")
  if(CMAKE_BUILD_TYPE STREQUAL "Debug")
    set(debug_build --debug)
  else()
    set(debug_build "")
  endif()
  add_custom_command(OUTPUT ${debug_files}
    COMMAND "${Python3_EXECUTABLE}" "${GAMETANK_ROOT}/tools/debug_files.py" "${build_folder}" "${name}" ${debug_build}
    DEPENDS ${name} ${tools}
    COMMENT "Writing ${name}'s debug files"
    VERBATIM)
  add_custom_target(${name}_debug_files ALL DEPENDS ${debug_files})
endfunction()

function(gametank_add_tiles name)
  if(NOT ARGN)
    message(FATAL_ERROR "gametank_add_tiles(${name}): no configs")
  endif()
  set(program "tile_palettes${GAMETANK_EXECUTABLE_SUFFIX}")
  _gametank_fetch(tile_palettes "${program}" "${GAMETANK_TILE_PALETTES_URL}" GAMETANK_TILE_PALETTES)
  set(tool "${GAMETANK_ROOT}/dev/tile_palettes/${program}")

  set(output_folder "${CMAKE_CURRENT_BINARY_DIR}/assets")
  foreach(config IN LISTS ARGN)
    get_filename_component(config "${config}" ABSOLUTE)
    get_filename_component(asset "${config}" NAME_WE)
    get_filename_component(config_folder "${config}" DIRECTORY)
    # A config's image is a file in its folder (the tool checks).
    file(GLOB images CONFIGURE_DEPENDS "${config_folder}/*.png")
    add_custom_command(
      OUTPUT "${output_folder}/${asset}.c" "${output_folder}/${asset}.h" "${output_folder}/${asset}_preview.png"
      COMMAND "${tool}" "${output_folder}" "${config}"
      DEPENDS "${config}" ${images} "${tool}"
      COMMENT "Converting ${asset}.toml"
      VERBATIM)
    target_sources(${name} PRIVATE "${output_folder}/${asset}.c" "${output_folder}/${asset}.h")
  endforeach()
  target_include_directories(${name} PRIVATE "${output_folder}")
endfunction()
