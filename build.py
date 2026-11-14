#!/usr/bin/env python3
"""Builds build/<NAME>.gtr, a 2 MB GameTank cartridge image, with llvm-mos from every .c and .s
file in sdk/ and src/. Runs on Windows and Linux.

  build.py          release build, optimized for size (-Os), into build/
  build.py debug    debug build into build-debug/: -Og -fno-inline, so every function stays its
                    own routine and the code follows the source closely; its assembly.s leaves
                    out the instruction bytes

Next to the image it writes:
  out.map, sourcemap.dbg   the GameTank emulator's symbols and its debugger's source view
  variables.dbg            GameTank Emulator Plus's variable hovers (types, scopes, locations)
  <NAME>.lbl               every label, VICE-style
  <NAME>.map               lld's map (sections, symbols, sizes)
  assembly.s               the linked program disassembled, with the C source between
  <NAME>.gtr.elf           the ELF, with DWARF debug info
  assets/<name>.h, .c      graphics from each assets/*.toml (see tools/tile_palettes), with
                           <name>_preview.png to check their colours
and it lists the branches of C code the optimizer compiled to nothing (see
tools/no_code_lines.py).

The whole program is compiled at once, with link-time optimization: the compiler sees every
function, so it inlines across files and puts locals and globals in zero page itself.

The compiler runs from the project folder with relative source paths, because the emulator
looks up the source files named in sourcemap.dbg relative to the project folder.

Python 3.8 or later, standard library only (as are the scripts in tools/).
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
from typing import NamedTuple

# The name of the cartridge image (build/<NAME>.gtr) and the other build files.
NAME = "game"

ROOT = os.path.dirname(os.path.abspath(__file__))
LLVM_BIN = os.path.join(ROOT, "dev", "llvm-mos", "bin")

# -mcpu=mosw65c02: the GameTank's CPU, a W65C02S.
# -mlto-zp=200: how much of zero page link-time optimization may give out: $00-$DF (the
#   compiler's imaginary registers are $E0-$FF), less what sdk/*.s declares there. The linker
#   fails if it overflows.
# -std=gnu23: C23 (constexpr, typeof, nullptr, #embed, enums with a fixed underlying type...)
#   with GNU extensions. Clang's default is gnu17.
# -Werror=return-type: a function that can end without returning its value lets the optimizer
#   assume that path never runs, and delete code that depends on it.
# -L sdk: finds sdk/link.ld, which the driver passes as -Tlink.ld.
COMPILE_FLAGS = ["--config", "mos-common.cfg", "-mcpu=mosw65c02", "-mlto-zp=200", "-std=gnu23", "-g",
                 "-Werror=return-type", "-I", "sdk", "-L", "sdk"]
# llvm-mos's startup pieces: setting up the C stack, copying initialised data and zeroing BSS.
STARTUP_LIBRARIES = ["-linit-stack", "-lcopy-data", "-lzero-bss"]
SOURCE_PATTERNS = ["sdk/*.c", "sdk/*.s", "src/*.c", "src/*.s"]


class Build(NamedTuple):
    folder: str
    compile_flags: list
    dump_flags: list
    debug_file_flags: list


# The debug build has no static stack (-fno-static-stack): with one, functions keep their locals
# at fixed zero-page addresses the debug info doesn't describe, so the emulator's variable hovers
# couldn't show them (see tools/variables.py). GT_DEBUG_BUILD turns on GT_DEBUG_FUNCTION
# (sdk/gametank.h).
BUILDS = {
    "release": Build("build", ["-Os"], [], []),
    "debug": Build("build-debug", ["-Og", "-fno-inline", "-fno-static-stack", "-DGT_DEBUG_BUILD"],
                   ["--no-show-raw-insn"], ["--no-static-stack"]),
}


class BuildError(Exception):
    pass


def llvm_tool(name):
    return os.path.join(LLVM_BIN, name + (".exe" if os.name == "nt" else ""))


def run(command, stdout=None):
    if subprocess.run(command, cwd=ROOT, stdout=stdout).returncode != 0:
        raise BuildError(f"{os.path.basename(command[0])} failed")


def project_files(pattern):
    """The files matching a pattern, relative to the project folder, in order."""
    return sorted(os.path.relpath(path, ROOT) for path in glob.glob(os.path.join(ROOT, pattern)))


def build_assets(build):
    """Runs tools/tile_palettes on every assets/*.toml, if there are any. cargo builds the tool the
    first time, and again when its source changes; otherwise it only checks, in well under a
    second."""
    configs = project_files("assets/*.toml")
    if not configs:
        return
    if shutil.which("cargo") is None:
        raise BuildError("cargo not found: the asset tool is Rust, see README.md, \"Setting up\"")
    run(["cargo", "run", "--release", "--quiet", "--manifest-path", os.path.join("tools", "tile_palettes", "Cargo.toml"),
         "--", os.path.join(build.folder, "assets"), *configs])


def compile_program(build, image):
    sources = [path for pattern in SOURCE_PATTERNS for path in project_files(pattern)]
    sources += project_files(os.path.join(build.folder, "assets", "*.c"))
    run([llvm_tool("clang"), *COMPILE_FLAGS, *build.compile_flags, "-I", os.path.join(build.folder, "assets"),
         f"-Wl,-Map,{os.path.join(build.folder, NAME + '.map')}", *STARTUP_LIBRARIES, "-o", image, *sources])


def write_build_files(build, image):
    with open(os.path.join(ROOT, build.folder, "assembly.s"), "wb") as assembly:
        run([llvm_tool("llvm-objdump"), "-d", "-S", "--print-imm-hex", *build.dump_flags, image + ".elf"],
            stdout=assembly)
    tools = os.path.join(ROOT, "tools")
    run([sys.executable, os.path.join(tools, "debug_files.py"), build.folder, NAME, *build.debug_file_flags])
    run([sys.executable, os.path.join(tools, "emulator_map.py"), build.folder, NAME])
    # Branches the optimizer deleted outright (the compiler doesn't warn about those): a report,
    # not an error.
    run([sys.executable, os.path.join(tools, "no_code_lines.py"), build.folder, NAME])


def main():
    parser = argparse.ArgumentParser(description="Builds the GameTank cartridge image.")
    parser.add_argument("build", nargs="?", choices=BUILDS, default="release")
    build = BUILDS[parser.parse_args().build]
    try:
        if not os.path.exists(llvm_tool("clang")):
            raise BuildError(f"llvm-mos not found in {LLVM_BIN}: see README.md, \"Setting up\"")
        os.makedirs(os.path.join(ROOT, build.folder), exist_ok=True)
        image = os.path.join(build.folder, NAME + ".gtr")
        build_assets(build)
        compile_program(build, image)
        write_build_files(build, image)
    except BuildError as error:
        sys.exit(f"{error}\nBuild failed.")
    print(f"Built {os.path.join(ROOT, image)}")


if __name__ == "__main__":
    main()
