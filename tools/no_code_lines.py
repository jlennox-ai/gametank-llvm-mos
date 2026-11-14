"""Lists the branches of C code a build compiled to nothing: an if, else, loop or
switch whose condition and whole body have no machine code. That's what code the optimizer
proved dead looks like (a condition that's always false, given what the code stored just
before), and neither the compiler's warnings nor its static analyzer report it, since it's
only dead because of values. So this asks the debug info: a branch whose lines have no
addresses in the DWARF line table has no code.

Single lines without code of their own are normal (a constant initializer folded into later
code, `x |= 1` merged into its neighbours), so they aren't listed; a whole branch is. Nor are
a switch's cases on their own: the compiler often attributes a case's code to the switch
line.

usage: no_code_lines.py <build directory> <name>      (build or build-debug)
       no_code_lines.py --elf <file.elf>
"""
import os
import re
import sys

import debug_files

ROOT = debug_files.ROOT
FUNCTION_DEFINITION = re.compile(r"^[A-Za-z_][\w\s\*]*\b\w+\s*\([^;]*\)\s*\{?\s*$")
BRANCH = re.compile(r"^(\}\s*)?(if|else if|else|while|for|do|switch)\b")


def code_of(line):
    """A source line without its // comment, stripped."""
    return line.split("//")[0].strip()


def matching_brace(source, start):
    """The line number (1-based) of the brace closing the first one opened on or after start.
    A brace closing the previous block at the start of the first line (`} else {`) is skipped."""
    depth = 0
    seen_open = False
    for number in range(start, len(source) + 1):
        code = code_of(source[number - 1])
        if number == start:
            code = code.lstrip("}").strip()
        depth += code.count("{") - code.count("}")
        seen_open = seen_open or "{" in code
        if seen_open and depth <= 0:
            return number
    sys.exit(f"unbalanced braces from line {start}")


def function_bodies(source):
    """Yields (first line, last line) of each function definition's body, 1-based."""
    number = 1
    while number <= len(source):
        line = source[number - 1]
        if FUNCTION_DEFINITION.match(line) and not line.startswith(("typedef", "struct")):
            last = matching_brace(source, number)
            yield number + 1, last
            number = last
        number += 1


def branch_end(source, start, last):
    """The last line of the branch starting at line start: its closing brace, or its single
    statement's line."""
    number = start
    while number <= last:
        code = code_of(source[number - 1])
        if "{" in code.lstrip("}"):
            return matching_brace(source, number)
        if code.endswith(";"):
            return number
        number += 1
    return last


def dead_branches(source, lines_with_code):
    """Yields (first, last) for each outermost branch none of whose lines has code."""
    for first, last in function_bodies(source):
        number = first
        while number <= last:
            code = code_of(source[number - 1])
            if BRANCH.match(code):
                end = branch_end(source, number, last)
                if not any(line in lines_with_code for line in range(number, end + 1)):
                    yield number, end
                    number = end
            number += 1


def report(elf_path):
    lines_with_code = {}
    for _, _, path, line in debug_files.read_line_rows(elf_path):
        lines_with_code.setdefault(os.path.normcase(path), set()).add(line)
    findings = 0
    for path in sorted(lines_with_code):
        full_path = os.path.join(ROOT, path)
        if not path.lower().endswith(".c") or not os.path.exists(full_path):
            continue
        with open(full_path, encoding="utf-8") as handle:
            source = handle.read().splitlines()
        for first, last in dead_branches(source, lines_with_code[path]):
            span = f"{first}" if first == last else f"{first}-{last}"
            print(f"{path}:{span}: {code_of(source[first - 1])}")
            findings += 1
    print(f"{findings} branch(es) with no code")


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "--elf":
        elf_path = sys.argv[2]
    elif len(sys.argv) == 3:
        elf_path = debug_files.elf_path(sys.argv[1], sys.argv[2])
    else:
        sys.exit(__doc__.split("usage: ")[1])
    if not os.path.exists(elf_path):
        sys.exit(f"{elf_path} not found: build first")
    report(elf_path)


if __name__ == "__main__":
    main()
