#!/usr/bin/env python3
"""Builds a project into a 2 MB GameTank cartridge image with llvm-mos: every .c and .s file in
the project folder and in sdk/. Runs on Windows and Linux.

  build.py <project folder>          release build, optimized for size (-Os), into <project>/build/
  build.py <project folder> debug    debug build into <project>/build-debug/: -Og -fno-inline, so
                                     every function stays its own routine and the code follows the
                                     source closely; its assembly.s leaves out the instruction bytes

The image is named after the project folder: example/build/example.gtr. Next to it, the build
writes:
  out.map, sourcemap.dbg   the GameTank emulator's symbols and its debugger's source view
  variables.dbg            GameTank Emulator Plus's variable hovers (types, scopes, locations)
  <name>.lbl               every label, VICE-style
  <name>.map               lld's map (sections, symbols, sizes)
  assembly.s               the linked program disassembled, with the C source between
  <name>.gtr.elf           the ELF, with DWARF debug info
  assets/<asset>.h, .c     graphics from each <project>/assets/*.toml (see tools/tile_palettes),
                           with <asset>_preview.png to check their colours
and it lists the branches of C code the optimizer compiled to nothing (see
tools/no_code_lines.py).

The whole program is compiled at once, with link-time optimization: the compiler sees every
function, so it inlines across files and puts locals and globals in zero page itself.

The compiler runs from the project folder with source paths relative to it, because the emulator
looks up the source files named in sourcemap.dbg relative to the folder above sourcemap.dbg's.

Python 3.8 or later, standard library only (as are the scripts in tools/).
"""
import argparse
import glob
import os
import shutil
import subprocess
import sys
from typing import NamedTuple

ROOT = os.path.dirname(os.path.abspath(__file__))
SDK = os.path.join(ROOT, "sdk")
TOOLS = os.path.join(ROOT, "tools")
LLVM_BIN = os.path.join(ROOT, "dev", "llvm-mos", "bin")

# -mcpu=mosw65c02: the GameTank's CPU, a W65C02S.
# -mlto-zp=200: how much of zero page link-time optimization may give out: $00-$DF (the
#   compiler's imaginary registers are $E0-$FF), less what sdk/*.s declares there. The linker
#   fails if it overflows.
# -std=gnu23: C23 (constexpr, typeof, nullptr, #embed, enums with a fixed underlying type...)
#   with GNU extensions. Clang's default is gnu17.
# -Werror=return-type: a function that can end without returning its value lets the optimizer
#   assume that path never runs, and delete code that depends on it.
COMPILE_FLAGS = ["--config", "mos-common.cfg", "-mcpu=mosw65c02", "-mlto-zp=200", "-std=gnu23", "-g",
                 "-Werror=return-type"]
# llvm-mos's startup pieces: setting up the C stack, copying initialised data and zeroing BSS.
STARTUP_LIBRARIES = ["-linit-stack", "-lcopy-data", "-lzero-bss"]
SOURCE_PATTERNS = ["*.c", "*.s"]


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


class Project(NamedTuple):
    folder: str  # absolute
    name: str
    output: str  # absolute: <folder>/build or <folder>/build-debug

    def relative(self, path):
        """path relative to the project folder, as the compiler is given it."""
        try:
            return os.path.relpath(path, self.folder)
        except ValueError:
            raise BuildError(f"{path} must be on the same drive as the project, {self.folder}")

    def files(self, folder, pattern):
        """The files in folder matching pattern, relative to the project folder, in order."""
        return sorted(self.relative(path) for path in glob.glob(os.path.join(folder, pattern)))


def llvm_tool(name):
    return os.path.join(LLVM_BIN, name + (".exe" if os.name == "nt" else ""))


def run(command, project, stdout=None):
    if subprocess.run(command, cwd=project.folder, stdout=stdout).returncode != 0:
        raise BuildError(f"{os.path.basename(command[0])} failed")


def build_assets(project):
    """Runs tools/tile_palettes on every <project>/assets/*.toml, if there are any. cargo builds the
    tool the first time, and again when its source changes; otherwise it only checks, in well
    under a second."""
    configs = project.files(os.path.join(project.folder, "assets"), "*.toml")
    if not configs:
        return
    if shutil.which("cargo") is None:
        raise BuildError("cargo not found: the asset tool is Rust, see README.md, \"Setting up\"")
    run(["cargo", "run", "--release", "--quiet", "--manifest-path", os.path.join(TOOLS, "tile_palettes", "Cargo.toml"),
         "--", os.path.join(project.output, "assets"), *configs], project)


def compile_program(project, build, image):
    sources = [path for folder in (SDK, project.folder) for pattern in SOURCE_PATTERNS
               for path in project.files(folder, pattern)]
    sources += project.files(os.path.join(project.output, "assets"), "*.c")
    sdk = project.relative(SDK)
    # -L sdk finds sdk/link.ld, which the driver passes as -Tlink.ld.
    run([llvm_tool("clang"), *COMPILE_FLAGS, *build.compile_flags, "-I", sdk, "-L", sdk,
         "-I", project.relative(os.path.join(project.output, "assets")),
         f"-Wl,-Map,{os.path.join(project.output, project.name + '.map')}", *STARTUP_LIBRARIES, "-o", image,
         *sources], project)


def write_build_files(project, build, image):
    with open(os.path.join(project.output, "assembly.s"), "wb") as assembly:
        run([llvm_tool("llvm-objdump"), "-d", "-S", "--print-imm-hex", *build.dump_flags, image + ".elf"], project,
            stdout=assembly)
    run([sys.executable, os.path.join(TOOLS, "debug_files.py"), project.output, project.name, *build.debug_file_flags],
        project)
    run([sys.executable, os.path.join(TOOLS, "emulator_map.py"), project.output, project.name], project)
    # Branches the optimizer deleted outright (the compiler doesn't warn about those): a report,
    # not an error.
    run([sys.executable, os.path.join(TOOLS, "no_code_lines.py"), project.output, project.name], project)


def main():
    parser = argparse.ArgumentParser(description="Builds a project into a GameTank cartridge image.")
    parser.add_argument("project", help="the folder with the project's .c and .s files")
    parser.add_argument("build", nargs="?", choices=BUILDS, default="release")
    arguments = parser.parse_args()
    build = BUILDS[arguments.build]
    folder = os.path.abspath(arguments.project)
    project = Project(folder, os.path.basename(folder), os.path.join(folder, build.folder))
    try:
        if not os.path.isdir(project.folder):
            raise BuildError(f"{project.folder} isn't a folder")
        if not os.path.exists(llvm_tool("clang")):
            raise BuildError(f"llvm-mos not found in {LLVM_BIN}: see README.md, \"Setting up\"")
        os.makedirs(project.output, exist_ok=True)
        image = os.path.join(project.output, project.name + ".gtr")
        build_assets(project)
        compile_program(project, build, image)
        write_build_files(project, build, image)
    except BuildError as error:
        sys.exit(f"{error}\nBuild failed.")
    print(f"Built {image}")


if __name__ == "__main__":
    main()
