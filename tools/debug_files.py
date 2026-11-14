"""Writes a label file and the emulator's source map and variables for a build, from the
linked ELF <build>/<name>.gtr.elf: <build>/<name>.lbl, <build>/sourcemap.dbg and
<build>/variables.dbg (see variables.py). tools/emulator_map.py then makes out.map from the
label file. The build directory is in the project folder (<project>/build), and the emulator
looks source files up relative to the project folder.

The label file has a VICE-style line per symbol ("al 008000 .main"), from llvm-nm.

The source map is in ld65's debug info format, which is what the emulator reads: its code
stepper (F7) shows the source line at the PC. It comes from the ELF's DWARF line table (via
llvm-dwarfdump): each row's address range becomes a span, and each span gets a line. The
emulator finds an address's segment by cartridge bank, so there's a segment per bank of the
program: 126 at $8000-$BFFF and 127 at $C000-$FFFF.

usage: debug_files.py <build directory> <name> [--no-static-stack]"""
import os
import re
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LLVM_BIN = os.path.join(ROOT, "dev", "llvm-mos", "bin")
SEGMENTS = (  # (name, start, size, cartridge bank)
    ("BANK126", 0x8000, 0x4000, 126),
    ("BANK127", 0xC000, 0x4000, 127),
)

NM_LINE = re.compile(r"^([0-9a-f]+) (\w) (\S+)$")
INCLUDE_DIRECTORY = re.compile(r'^include_directories\[\s*(\d+)\] = "(.*)"$')
FILE_NAME_START = re.compile(r"^file_names\[\s*(\d+)\]:$")
FILE_NAME = re.compile(r'^name: "(.*)"$')
DIRECTORY_INDEX = re.compile(r"^dir_index: (\d+)$")
ROW = re.compile(r"^0x([0-9a-f]+)\s+(\d+)\s+\d+\s+(\d+)\s+\d+\s+\d+\s+\d+\s*(.*)$")


def elf_path(build, name):
    """The linked ELF of the build of <name> in the build directory, as build.py names it."""
    return os.path.join(build, f"{name}.gtr.elf")


def project_folder(build):
    """The project folder a build directory is in."""
    return os.path.dirname(os.path.abspath(build))


def run_tool(name, *arguments):
    """Runs llvm-mos's tool name (llvm-nm, ...) and returns its output."""
    executable = os.path.join(LLVM_BIN, name + (".exe" if os.name == "nt" else ""))
    result = subprocess.run([executable, *arguments], capture_output=True, encoding="utf-8")
    if result.returncode != 0:
        sys.exit(f"{name} failed: {result.stderr.strip()}")
    return result.stdout


def unescape(text):
    """llvm-dwarfdump prints strings C-escaped (backslashes doubled)."""
    return text.replace("\\\\", "\\")


def project_path(path, project):
    """A source path as the emulator wants it: relative to the project folder."""
    return os.path.relpath(os.path.normpath(os.path.join(project, path)), project)


def write_labels(elf_path, labels_path):
    lines = []
    for line in run_tool("llvm-nm", "--defined-only", elf_path).splitlines():
        match = NM_LINE.match(line.strip())
        if match is None:
            sys.exit(f"unexpected llvm-nm line: {line}")
        address, kind, name = match.groups()
        # Absolute local symbols are assembler constants (DMA_FLAGS = 0x2007), not variables.
        if kind == "a":
            continue
        lines.append(f"al {int(address, 16):06X} .{name}")
    with open(labels_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def read_line_rows(elf_path, project):
    """Returns [(start, end, source path, line)]: the address range each line's code covers, with
    the source path relative to the project folder."""
    rows = []
    directories = {}
    files = {}
    file_index = None
    sequence = []
    for raw_line in run_tool("llvm-dwarfdump", "--debug-line", elf_path).splitlines():
        line = raw_line.strip()
        if line.startswith("debug_line["):
            directories = {}
            files = {}
            continue
        match = INCLUDE_DIRECTORY.match(line)
        if match:
            directories[int(match.group(1))] = unescape(match.group(2))
            continue
        match = FILE_NAME_START.match(line)
        if match:
            file_index = int(match.group(1))
            files[file_index] = {}
            continue
        match = FILE_NAME.match(line)
        if match and file_index is not None:
            files[file_index]["name"] = unescape(match.group(1))
            continue
        match = DIRECTORY_INDEX.match(line)
        if match and file_index is not None:
            files[file_index]["directory"] = int(match.group(1))
            continue
        match = ROW.match(line)
        if match is None:
            continue
        address = int(match.group(1), 16)
        source_line = int(match.group(2))
        flags = match.group(4).split()
        if sequence:
            previous_address, previous_file, previous_line = sequence[-1]
            if address > previous_address and previous_line != 0:
                entry = files[previous_file]
                # A relative directory is relative to directory 0, the compiler's working folder.
                directory = os.path.join(directories[0], directories[entry["directory"]])
                rows.append((previous_address, address,
                             project_path(os.path.join(directory, entry["name"]), project), previous_line))
        if "end_sequence" in flags:
            sequence = []
        else:
            sequence.append((address, int(match.group(3)), source_line))
    return rows


def segment_index(address):
    for index, (_, start, size, _) in enumerate(SEGMENTS):
        if start <= address < start + size:
            return index
    return None


def write_source_map(elf_path, project, source_map_path):
    file_ids = {}
    spans = []
    lines = []
    for start, end, path, source_line in read_line_rows(elf_path, project):
        segment = segment_index(start)
        # Code outside the program's two banks (none, today) can't be looked up by the emulator.
        if segment is None:
            continue
        if segment_index(end - 1) != segment:
            sys.exit(f"line {path}:{source_line} at ${start:04X}-${end:04X} crosses a bank boundary")
        file_id = file_ids.setdefault(path, len(file_ids))
        span_id = len(spans)
        spans.append(f"span\tid={span_id},seg={segment},start={start - SEGMENTS[segment][1]},size={end - start}")
        lines.append(f"line\tid={len(lines)},file={file_id},line={source_line},type=1,span={span_id}")
    output = [f'file\tid={file_id},name="{path}",size=0,mtime=0x00000000,mod=0' for path, file_id in file_ids.items()]
    for index, (name, start, size, bank) in enumerate(SEGMENTS):
        output.append(f'seg\tid={index},name="{name}",start=0x{start:06X},size=0x{size:04X},'
                      f"addrsize=absolute,type=ro,bank={bank}")
    output += spans + lines
    with open(source_map_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(output) + "\n")


def main():
    # --no-static-stack: the build was compiled with -fno-static-stack (see variables.py).
    arguments = sys.argv[1:]
    if len(arguments) not in (2, 3) or (len(arguments) == 3 and arguments[2] != "--no-static-stack"):
        sys.exit("usage: debug_files.py <build directory> <name> [--no-static-stack]")
    build, name = arguments[0], arguments[1]
    elf = elf_path(build, name)
    if not os.path.exists(elf):
        sys.exit(f"{elf} not found: run build.py")
    write_labels(elf, os.path.join(build, f"{name}.lbl"))
    write_source_map(elf, project_folder(build), os.path.join(build, "sourcemap.dbg"))
    # Imported here: variables uses this module's helpers.
    import variables
    variables.write_variables(elf, os.path.join(build, "variables.dbg"), static_stack=len(arguments) == 2)


if __name__ == "__main__":
    main()
