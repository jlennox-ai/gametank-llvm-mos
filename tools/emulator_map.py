"""Writes <build>/out.map, the symbol list the GameTank emulator loads (the label box and
breakpoints in its code stepper, F7), from the label file <build>/<name>.lbl. The build
folder is <project>/build or <project>/build-debug.

The emulator reads the "Exports list by value" section of a map file in cc65's ld65 format,
which is the only map format it knows, so this writes that section from the label file's
symbols. lld's own map is <build>/<name>.map.

usage: emulator_map.py <build directory> <name>"""
import os
import re
import sys

LABEL_LINE = re.compile(r"^al ([0-9A-F]+) \.(\S+)$")


def read_symbols(path):
    """Returns the distinct (address, name) pairs in a VICE-style label file."""
    symbols = set()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            match = LABEL_LINE.match(line.strip())
            if match is None:
                sys.exit(f"{path}: unexpected line: {line.strip()}")
            name = match.group(2)
            # The emulator stops reading the list at a line with a dash in it.
            if "-" in name:
                sys.exit(f"{path}: the emulator can't read the symbol name {name}")
            symbols.add((int(match.group(1), 16), name))
    return symbols


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: emulator_map.py <build directory> <name>")
    build = sys.argv[1]
    labels_path = os.path.join(build, f"{sys.argv[2]}.lbl")
    if not os.path.exists(labels_path):
        sys.exit(f"{labels_path} not found: build first")
    lines = ["Exports list by value:", "-" * len("Exports list by value:")]
    for address, name in sorted(read_symbols(labels_path)):
        lines.append(f"{name:<32} {address:06X} RLA")
    with open(os.path.join(build, "out.map"), "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
