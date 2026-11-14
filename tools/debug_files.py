"""Writes a build's debug files, from its linked ELF <build>/<name>.gtr.elf, after
gametank_add_rom (cmake/gametank.cmake) links it:

  <name>.lbl      every label, VICE-style ("al 008000 .main"), from the symbol table
  sourcemap.dbg   the emulator's source view (see below)
  variables.dbg   GameTank Emulator Plus's variable hovers (see variables.py)
  out.map         the emulator's symbols, from the labels (see emulator_map.py)
  assembly.s      the linked program disassembled, with the C source between

The source map is in ld65's debug info format, which is what the emulator reads: its code
stepper (F7) shows the source line at the PC. It comes from the ELF's DWARF line table (via
llvm-dwarfdump): each row's address range becomes a span, and each span gets a line. The
emulator finds an address's segment by cartridge bank, so there's a segment per bank of the
program, as the linker script sets them (sdk/link.ld's __gt_program_bank at $8000-$BFFF and
__gt_fixed_bank at $C000-$FFFF). It names source files relative to the folder above the build
directory, which is where the emulator looks them up.

--debug: the debug build, which is compiled with -fno-static-stack (see variables.py) and whose
assembly.s leaves out the instruction bytes.

usage: debug_files.py <build directory> <name> [--debug]"""
import os
import re
import subprocess
import sys

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LLVM_BIN = os.path.join(ROOT, "dev", "llvm-mos", "bin")
BANK_SIZE = 0x4000
PROGRAM_BANK_START = 0x8000
FIXED_BANK_START = 0xC000
# Where lld puts the line table's rows for code it discarded.
DISCARDED_ADDRESS = 0

# "   78: 000080c4   252 FUNC    GLOBAL DEFAULT                  3 main", with sometimes a flag
# after the visibility ("[ZEROPAGE]"): the value, type, section index (ABS, UND, ...) and name.
SYMBOL_LINE = re.compile(r"^\s*\d+:\s+([0-9a-f]+)\s+\S+\s+(\w+)\s+\w+\s+\w+(?:\s+\[[^\]]*\])?\s+(\S+)\s+(\S+)$")
IMAGINARY_REGISTER = re.compile(r"^__rc\d+$")
INCLUDE_DIRECTORY = re.compile(r'^include_directories\[\s*(\d+)\] = "(.*)"$')
FILE_NAME_START = re.compile(r"^file_names\[\s*(\d+)\]:$")
FILE_NAME = re.compile(r'^name: "(.*)"$')
DIRECTORY_INDEX = re.compile(r"^dir_index: (\d+)$")
ROW = re.compile(r"^0x([0-9a-f]+)\s+(\d+)\s+\d+\s+(\d+)\s+\d+\s+\d+\s+\d+\s*(.*)$")


def elf_path(build, name):
    """The linked ELF of the build of <name> in the build directory."""
    return os.path.join(build, f"{name}.gtr.elf")


def project_folder(build):
    """The folder the emulator looks source files up in: the one the build directory is in."""
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


def read_symbols(elf_path):
    """[(address, absolute, name)] for the symbols the ELF defines, from llvm-readelf."""
    symbols = []
    for line in run_tool("llvm-readelf", "--symbols", "--wide", elf_path).splitlines():
        match = SYMBOL_LINE.match(line)
        if match is None:
            continue
        address, symbol_type, section, name = match.groups()
        if section == "UND" or symbol_type in ("FILE", "SECTION"):
            continue
        symbols.append((int(address, 16), section == "ABS", name))
    if not symbols:
        sys.exit(f"{elf_path} has no symbols")
    return symbols


def write_labels(symbols, labels_path):
    lines = []
    for address, absolute, name in symbols:
        # Absolute symbols are constants, not addresses: the assembler's (DMA_FLAGS = 0x2007) and
        # the linker script's and C library's (__stack_size, __gt_program_bank). The imaginary
        # registers are absolute too, but they are addresses.
        if absolute and not IMAGINARY_REGISTER.match(name):
            continue
        lines.append(f"al {address:06X} .{name}")
    with open(labels_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def program_segments(symbols):
    """[(name, start, size, cartridge bank)]: a segment per bank of the program, as the linker
    script sets them."""
    values = {name: address for address, absolute, name in symbols if absolute}
    banks = []
    for name in ("__gt_program_bank", "__gt_fixed_bank"):
        if name not in values:
            sys.exit(f"the linker script doesn't define {name}: see sdk/link.ld")
        banks.append(values[name])
    starts = (PROGRAM_BANK_START, FIXED_BANK_START)
    return [(f"BANK{bank}", start, BANK_SIZE, bank) for bank, start in zip(banks, starts)]


def read_line_rows(elf_path, project):
    """Returns [(start, end, source path, line)]: the address range each line's code covers, with
    the source path relative to the project folder. Code the linker discarded as unused (an
    assembly routine nothing calls) keeps its rows, as a sequence lld moved to address 0, where no
    code can be (it's zero page): those are left out."""
    rows = []
    directories = {}
    files = {}
    file_index = None
    sequence = []
    discarded = False
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
        if not sequence and not discarded and address == DISCARDED_ADDRESS:
            discarded = True
        if discarded:
            if "end_sequence" in flags:
                discarded = False
            continue
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


def segment_index(address, segments):
    for index, (_, start, size, _) in enumerate(segments):
        if start <= address < start + size:
            return index
    return None


def write_source_map(elf_path, project, segments, source_map_path):
    file_ids = {}
    spans = []
    lines = []
    for start, end, path, source_line in read_line_rows(elf_path, project):
        segment = segment_index(start, segments)
        if segment is None:
            sys.exit(f"{path}:{source_line} has code at ${start:04X}, outside the program's banks, where the "
                     "emulator can't find its source")
        if segment_index(end - 1, segments) != segment:
            sys.exit(f"line {path}:{source_line} at ${start:04X}-${end:04X} crosses a bank boundary")
        file_id = file_ids.setdefault(path, len(file_ids))
        span_id = len(spans)
        spans.append(f"span\tid={span_id},seg={segment},start={start - segments[segment][1]},size={end - start}")
        lines.append(f"line\tid={len(lines)},file={file_id},line={source_line},type=1,span={span_id}")
    output = [f'file\tid={file_id},name="{path}",size=0,mtime=0x00000000,mod=0' for path, file_id in file_ids.items()]
    for index, (name, start, size, bank) in enumerate(segments):
        output.append(f'seg\tid={index},name="{name}",start=0x{start:06X},size=0x{size:04X},'
                      f"addrsize=absolute,type=ro,bank={bank}")
    output += spans + lines
    with open(source_map_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(output) + "\n")


def write_assembly(elf_path, assembly_path, instruction_bytes):
    """The linked program disassembled, with the C source between."""
    flags = [] if instruction_bytes else ["--no-show-raw-insn"]
    with open(assembly_path, "w", encoding="utf-8") as handle:
        handle.write(run_tool("llvm-objdump", "-d", "-S", "--print-imm-hex", *flags, elf_path))


def main():
    arguments = sys.argv[1:]
    if len(arguments) not in (2, 3) or (len(arguments) == 3 and arguments[2] != "--debug"):
        sys.exit("usage: debug_files.py <build directory> <name> [--debug]")
    build, name = arguments[0], arguments[1]
    debug = len(arguments) == 3
    elf = elf_path(build, name)
    if not os.path.exists(elf):
        sys.exit(f"{elf} not found: build first")
    symbols = read_symbols(elf)
    labels_path = os.path.join(build, f"{name}.lbl")
    write_labels(symbols, labels_path)
    write_source_map(elf, project_folder(build), program_segments(symbols), os.path.join(build, "sourcemap.dbg"))
    write_assembly(elf, os.path.join(build, "assembly.s"), instruction_bytes=not debug)
    # Imported here: they use this module's helpers.
    import emulator_map
    import variables
    emulator_map.write_map(labels_path, os.path.join(build, "out.map"))
    variables.write_variables(elf, os.path.join(build, "variables.dbg"), static_stack=not debug)


if __name__ == "__main__":
    main()
