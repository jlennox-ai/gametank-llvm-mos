#!/usr/bin/env python3
"""Compares llvm-mos's code with cc65's, and writes comparison/results.md (which README.md quotes):

- Speed and size: builds bench.c and examples.c with each compiler and runs them on sim65 (cc65's
  6502 simulator, as a 65C02). bench.c times each function in examples.c with sim65's cycle
  counter. Sizes come from llvm-nm for llvm-mos, and from ld65's map and labels for cc65.
- C language features: builds each program in features/ with each compiler and runs it on sim65;
  it exits 0 when the feature works.
- The code: each function's source, and what each compiler made of it.

Needs llvm-mos in dev/llvm-mos (README.md, "Setting up") and cc65 in dev/cc65: a snapshot build
(Windows) or a build of its source (Linux), with its bin, include, asminc, cfg and lib folders.
Builds go to comparison/build/.

Python 3.8 or later, standard library only.

usage: compare.py
"""
import os
import re
import subprocess
import sys

COMPARISON = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(COMPARISON)
BUILD = os.path.join(COMPARISON, "build")
SIM65_SUPPORT = os.path.join(COMPARISON, "sim65")
RESULTS = os.path.join(COMPARISON, "results.md")
EXECUTABLE_SUFFIX = ".exe" if os.name == "nt" else ""
LLVM_BIN = os.path.join(ROOT, "dev", "llvm-mos", "bin")
CC65_HOME = os.path.join(ROOT, "dev", "cc65")

# -Oirs: optimize, inline small runtime functions, and allow register variables. -Cl: locals at
# fixed addresses instead of on cc65's software stack, which is much faster (but no recursion).
CC65_FLAGS = ["-t", "sim65c02", "-Oirs", "-Cl"]
# build.py's flags, with sim65/link.ld in place of sdk/link.ld.
LLVM_MOS_FLAGS = ["--config", "mos-common.cfg", "-mcpu=mosw65c02", "-mlto-zp=200", "-Os", "-L", SIM65_SUPPORT]
LLVM_MOS_STANDARDS = {".c": "-std=gnu23", ".cpp": "-std=gnu++23"}
# exit-custom: main() returning calls exit(), which ends in sim65.s's _Exit.
LLVM_MOS_LIBRARIES = ["-linit-stack", "-lcopy-data", "-lzero-bss", "-lexit-custom",
                      os.path.join(SIM65_SUPPORT, "sim65.s")]

FUNCTIONS = ("entities_update", "clamp_add", "grid_full_rows", "hash_bytes", "copy_rows")
BENCH_SOURCES = ("bench.c", "examples.c")

FEATURE_TITLE = re.compile(r"^// (.+) \((C\d\d|C\+\+)\)$")
BENCH_LINE = re.compile(r"^(\w+) (\d+) (\d+)$")
CC65_LABEL = re.compile(r"^al ([0-9A-F]+) \.(\S+)$")
CC65_SEGMENT = re.compile(r"^(\w+)\s+([0-9A-F]{6})\s+([0-9A-F]{6})\s+([0-9A-F]{6})\s+[0-9A-F]{5}$")
CC65_MODULE_SEGMENT = re.compile(r"^\s+(\w+)\s+Offs=([0-9A-F]+)\s+Size=([0-9A-F]+)")
CC65_CALL = re.compile(r"^\s*(?:\w+:)?\s*(?:jsr|jmp)\s+(\w+)\s*$")
NM_SIZE_LINE = re.compile(r"^[0-9a-f]+ ([0-9a-f]+) \w (\S+)$")
# "a53:  bpl $a59 <clamp_add+0xa>" or "a5e:  sta $2023  ; 0x2023 <entities+0x1>"
OBJDUMP_LINE = re.compile(r"^\s*([0-9a-f]+):\s+(\w+)(?:\s+([^;]*?))?\s*(?:;\s*0x[0-9a-f]+ <([^>]+)>)?\s*$")
ADDRESS_OPERAND = re.compile(r"(?<![#\w])\$([0-9a-f]+)(?:\s*<([^>]+)>)?")
BRANCHES = ("bcc", "bcs", "beq", "bmi", "bne", "bpl", "bra", "bvc", "bvs", "jmp", "bbr", "bbs")
# The compiler's imaginary registers, __rc0-__rc31: zero page $E0-$FF (sim65/link.ld).
IMAGINARY_REGISTERS = range(0xe0, 0x100)


class CommandError(Exception):
    def __init__(self, command, output):
        super().__init__(f"{os.path.basename(command[0])} failed:\n{output}")
        self.output = output


def tool(folder, name):
    return os.path.join(folder, name + EXECUTABLE_SUFFIX)


def run(command, check=True):
    """Runs a command from the comparison folder; returns (exit code, its output and errors)."""
    environment = dict(os.environ, CC65_HOME=CC65_HOME)
    result = subprocess.run(command, cwd=COMPARISON, env=environment, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    if check and result.returncode != 0:
        raise CommandError(command, result.stdout)
    return result.returncode, result.stdout


def build_cc65(sources, folder, name):
    """Compiles, assembles and links sources (relative to the comparison folder) into
    folder/name, a sim65 program, with folder/name.map and folder/name.lbl."""
    os.makedirs(folder, exist_ok=True)
    objects = []
    for source in sources:
        stem = os.path.join(folder, os.path.splitext(os.path.basename(source))[0])
        run([tool(os.path.join(CC65_HOME, "bin"), "cc65"), *CC65_FLAGS, "-o", stem + ".s", source])
        run([tool(os.path.join(CC65_HOME, "bin"), "ca65"), "-t", "sim65c02", "-o", stem + ".o", stem + ".s"])
        objects.append(stem + ".o")
    program = os.path.join(folder, name)
    run([tool(os.path.join(CC65_HOME, "bin"), "ld65"), "-t", "sim65c02", "-m", program + ".map", "-Ln",
         program + ".lbl", "-o", program, *objects, "sim65c02.lib"])
    return program


def build_llvm_mos(sources, folder, name):
    """Compiles and links sources into folder/name, a sim65 program, and folder/name.elf."""
    os.makedirs(folder, exist_ok=True)
    program = os.path.join(folder, name)
    standard = LLVM_MOS_STANDARDS[os.path.splitext(sources[0])[1]]
    run([tool(LLVM_BIN, "clang"), *LLVM_MOS_FLAGS, standard, "-o", program, *sources, *LLVM_MOS_LIBRARIES])
    return program


def run_sim65(program):
    return run([tool(os.path.join(CC65_HOME, "bin"), "sim65"), program], check=False)


def first_line(text):
    return text.strip().splitlines()[0].strip() if text.strip() else ""


def versions():
    _, cc65 = run([tool(os.path.join(CC65_HOME, "bin"), "cc65"), "--version"])
    _, clang = run([tool(LLVM_BIN, "clang"), "--version"])
    return first_line(cc65), first_line(clang)


# Speed and size.

def bench_results(program):
    """Runs a bench build: {function: (cycles, check value)}."""
    code, output = run_sim65(program)
    if code != 0:
        raise CommandError([program], output)
    results = {}
    for line in output.splitlines():
        match = BENCH_LINE.match(line.strip())
        if match is None:
            raise CommandError([program], f"unexpected output: {line}")
        results[match.group(1)] = (int(match.group(2)), int(match.group(3)))
    if tuple(results) != FUNCTIONS:
        raise CommandError([program], f"timed {', '.join(results)}, not {', '.join(FUNCTIONS)}")
    return results


def llvm_mos_sizes(program):
    _, output = run([tool(LLVM_BIN, "llvm-nm"), "-S", "--defined-only", program + ".elf"])
    sizes = {}
    for line in output.splitlines():
        match = NM_SIZE_LINE.match(line.strip())
        if match and match.group(2) in FUNCTIONS:
            sizes[match.group(2)] = int(match.group(1), 16)
    return sizes


def cc65_sizes(program):
    """Each function's size: the distance to the next function, or for the last, to the end of
    examples.o's code. cc65 places a module's functions in the order they're defined."""
    addresses = {}
    with open(program + ".lbl", encoding="utf-8") as handle:
        for line in handle:
            match = CC65_LABEL.match(line.strip())
            if match and match.group(2).startswith("_") and match.group(2)[1:] in FUNCTIONS:
                addresses[match.group(2)[1:]] = int(match.group(1), 16)
    code_start = None
    examples_code = None
    module = None
    with open(program + ".map", encoding="utf-8") as handle:
        for line in handle:
            if not line.startswith(" ") and line.rstrip().endswith(":"):
                module = os.path.basename(line.rstrip()[:-1])
            match = CC65_MODULE_SEGMENT.match(line)
            if match and module == "examples.o" and match.group(1) == "CODE":
                examples_code = (int(match.group(2), 16), int(match.group(3), 16))
            match = CC65_SEGMENT.match(line.strip())
            if match and match.group(1) == "CODE":
                code_start = int(match.group(2), 16)
    if code_start is None or examples_code is None or len(addresses) != len(FUNCTIONS):
        raise CommandError([program], "couldn't find the functions in ld65's map and labels")
    ordered = sorted((address, name) for name, address in addresses.items())
    examples_end = code_start + examples_code[0] + examples_code[1]
    sizes = {}
    for index, (address, name) in enumerate(ordered):
        end = ordered[index + 1][0] if index + 1 < len(ordered) else examples_end
        sizes[name] = end - address
    return sizes


# The code.

def function_source(name):
    """The function's definition in examples.c, with the comment before it."""
    with open(os.path.join(COMPARISON, "examples.c"), encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    definition = re.compile(r"^\w[\w\s\*]*\b" + name + r"\(")
    start = next(index for index, line in enumerate(lines) if definition.match(line))
    end = next(index for index in range(start, len(lines)) if lines[index] == "}")
    while start > 0 and lines[start - 1].startswith("//"):
        start -= 1
    return "\n".join(lines[start:end + 1])


def cc65_listing(assembly_path, name):
    """The function's code from cc65's assembly output (its static locals left out), and the
    runtime routines it calls."""
    with open(assembly_path, encoding="utf-8") as handle:
        lines = handle.read().splitlines()
    start = lines.index(f".proc\t_{name}: near")
    end = lines.index(".endproc", start)
    listing = []
    calls = []
    segment = None
    for line in lines[start + 1:end]:
        if line.startswith(".segment"):
            segment = line.split('"')[1]
            continue
        if segment != "CODE" or not line.strip():
            continue
        label, _, instruction = line.partition("\t")
        listing.append(f"{label:<8}{instruction}".replace("\t", " ").rstrip())
        match = CC65_CALL.match(line.replace("\t", " "))
        if match and not match.group(1).startswith("L") and match.group(1) not in calls:
            calls.append(match.group(1))
    return "\n".join(listing), calls


def symbol_reference(symbolized):
    """llvm-objdump's "entities+0x1" as "entities+1"."""
    name, _, offset = symbolized.partition("+")
    return f"{name}+{int(offset, 16)}" if offset else name


def llvm_mos_listing(program, name):
    """The function's code, disassembled from the linked program, laid out like cc65's: branch
    targets labelled (L and the address), and addresses named: the imaginary registers, globals
    and functions."""
    _, output = run([tool(LLVM_BIN, "llvm-objdump"), "-d", "--no-show-raw-insn", "--print-imm-hex",
                     f"--disassemble-symbols={name}", program + ".elf"])
    instructions = []  # (address, mnemonic, operands, the symbol objdump gives an address operand)
    for line in output.splitlines():
        match = OBJDUMP_LINE.match(line)
        if match:
            instructions.append((int(match.group(1), 16), match.group(2), (match.group(3) or "").replace("\t", " "),
                                 match.group(4)))
    if not instructions:
        raise CommandError([program], f"no code for {name}")
    addresses = {instruction[0] for instruction in instructions}
    targets = set()
    lines = []
    for address, mnemonic, operands, operand_symbol in instructions:
        def name_address(operand):
            value = int(operand.group(1), 16)
            if value in IMAGINARY_REGISTERS:
                return f"__rc{value - IMAGINARY_REGISTERS.start}"
            if mnemonic.startswith(BRANCHES) and value in addresses:
                targets.add(value)
                return f"L{value:04X}"
            if operand.group(2) and "+" not in operand.group(2):
                return operand.group(2)
            if operand_symbol:
                return symbol_reference(operand_symbol)
            return f"${operand.group(1)}"
        lines.append((address, mnemonic, ADDRESS_OPERAND.sub(name_address, operands).strip()))
    listing = []
    for address, mnemonic, operands in lines:
        label = f"L{address:04X}:" if address in targets else ""
        listing.append(f"{label:<8}{mnemonic:<8}{operands}".rstrip())
    return "\n".join(listing)


# Language features.

def feature_result(build, source, folder):
    """'yes', or why not: the compiler's first error, or a wrong result."""
    try:
        program = build([source], folder, "program")
    except CommandError as error:
        errors = [line for line in error.output.splitlines() if re.search(r"\b(error|fatal)\b", line, re.IGNORECASE)]
        message = first_line(errors[0] if errors else error.output)
        message = re.sub(r"^(?:.*?:\d+(?::\d+)?: )?(?:error|fatal): ", "", message, flags=re.IGNORECASE)
        return f"no: `{message}`"
    code, _ = run_sim65(program)
    return "yes" if code == 0 else "builds, but runs wrong"


def feature_results():
    """[(title, standard, cc65 result, llvm-mos result)] for each program in features/."""
    results = []
    for file_name in sorted(os.listdir(os.path.join(COMPARISON, "features"))):
        stem, extension = os.path.splitext(file_name)
        if extension not in LLVM_MOS_STANDARDS:
            continue
        source = os.path.join("features", file_name)
        with open(os.path.join(COMPARISON, source), encoding="utf-8") as handle:
            match = FEATURE_TITLE.match(handle.readline().strip())
        if match is None:
            raise CommandError([source], "the first line isn't \"// Title (standard)\"")
        folder = os.path.join(BUILD, "features", stem)
        if extension == ".cpp":
            cc65 = "no: cc65 compiles C only"
        else:
            cc65 = feature_result(build_cc65, source, os.path.join(folder, "cc65"))
        llvm_mos = feature_result(build_llvm_mos, source, os.path.join(folder, "llvm-mos"))
        results.append((match.group(1), match.group(2), cc65, llvm_mos))
        print(f"{file_name}: cc65 {cc65}; llvm-mos {llvm_mos}")
    return results


def table_cell(text):
    return text.replace("|", "\\|")


def write_results(cc65_version, llvm_mos_version, cc65_bench, llvm_mos_bench, cc65_size, llvm_mos_size,
                  features, cc65_program, llvm_mos_program):
    lines = [
        "# llvm-mos and cc65, compared",
        "",
        "Written by [`compare.py`](compare.py) (rerun it rather than editing this), with:",
        "",
        f"- **cc65**: {cc65_version}, `cc65 {' '.join(CC65_FLAGS)}`",
        f"- **llvm-mos**: {llvm_mos_version}, "
        f"`clang {' '.join(flag for flag in LLVM_MOS_FLAGS if flag not in ('-L', SIM65_SUPPORT))}`, "
        "the flags `build.py` uses (link-time optimization included)",
        "",
        "Both run on sim65, cc65's simulator, as a 65C02.",
        "",
        "## Speed and size",
        "",
        "The functions are in [`examples.c`](examples.c), timed by [`bench.c`](bench.c): the cycles for one",
        "call (passing its arguments included), and the bytes of the function itself. cc65's code also",
        "calls routines in its runtime library, which aren't counted in its size (they're listed with each",
        "function below).",
        "",
        "| Function | cc65 cycles | llvm-mos cycles | llvm-mos is | cc65 bytes | llvm-mos bytes |",
        "|---|--:|--:|--:|--:|--:|",
    ]
    for name in FUNCTIONS:
        speedup = cc65_bench[name][0] / llvm_mos_bench[name][0]
        lines.append(f"| `{name}` | {cc65_bench[name][0]:,} | {llvm_mos_bench[name][0]:,} | "
                     f"{speedup:.1f}x faster | {cc65_size[name]} | {llvm_mos_size[name]} |")
    lines += [
        "",
        "## C language features",
        "",
        "Each program in [`features/`](features/) exits 0 on sim65 when its feature works.",
        "",
        "| Feature | Standard | cc65 | llvm-mos |",
        "|---|---|---|---|",
    ]
    for title, standard, cc65, llvm_mos in features:
        lines.append(f"| {table_cell(title)} | {standard} | {table_cell(cc65)} | {table_cell(llvm_mos)} |")
    lines += [
        "",
        "## The code",
        "",
        "cc65's is its assembly output; llvm-mos's is disassembled from the linked program, with the",
        "compiler's imaginary registers (zero page `$E0-$FF`) named `__rc0`-`__rc31`.",
    ]
    for name in FUNCTIONS:
        cc65_code, calls = cc65_listing(os.path.join(os.path.dirname(cc65_program), "examples.s"), name)
        runtime = f" It calls cc65's runtime: {', '.join(f'`{call}`' for call in calls)}." if calls else ""
        lines += [
            "",
            f"### `{name}`",
            "",
            "```c",
            function_source(name),
            "```",
            "",
            f"**cc65**: {cc65_size[name]} bytes, {cc65_bench[name][0]:,} cycles.{runtime}",
            "",
            "```asm",
            cc65_code,
            "```",
            "",
            f"**llvm-mos**: {llvm_mos_size[name]} bytes, {llvm_mos_bench[name][0]:,} cycles.",
            "",
            "```asm",
            llvm_mos_listing(llvm_mos_program, name),
            "```",
        ]
    with open(RESULTS, "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n")


def main():
    if len(sys.argv) != 1:
        sys.exit(__doc__.split("usage: ")[1])
    for required in (tool(LLVM_BIN, "clang"), tool(os.path.join(CC65_HOME, "bin"), "sim65")):
        if not os.path.exists(required):
            sys.exit(f"{required} not found: see compare.py's description")
    try:
        cc65_version, llvm_mos_version = versions()
        cc65_program = build_cc65(BENCH_SOURCES, os.path.join(BUILD, "bench", "cc65"), "bench")
        llvm_mos_program = build_llvm_mos(BENCH_SOURCES, os.path.join(BUILD, "bench", "llvm-mos"), "bench")
        cc65_bench = bench_results(cc65_program)
        llvm_mos_bench = bench_results(llvm_mos_program)
        for name in FUNCTIONS:
            if cc65_bench[name][1] != llvm_mos_bench[name][1]:
                raise CommandError([name], f"check values differ: cc65 {cc65_bench[name][1]}, "
                                           f"llvm-mos {llvm_mos_bench[name][1]}")
            print(f"{name}: cc65 {cc65_bench[name][0]} cycles, llvm-mos {llvm_mos_bench[name][0]} cycles")
        features = feature_results()
        write_results(cc65_version, llvm_mos_version, cc65_bench, llvm_mos_bench, cc65_sizes(cc65_program),
                      llvm_mos_sizes(llvm_mos_program), features, cc65_program, llvm_mos_program)
    except CommandError as error:
        sys.exit(str(error))
    print(f"Wrote {RESULTS}")


if __name__ == "__main__":
    main()
