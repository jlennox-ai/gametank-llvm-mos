"""Writes <build>/variables.dbg for a build: what the emulator's source view needs to
show a variable's value when it's hovered. It comes from the ELF's DWARF debug info (via
llvm-dwarfdump), in the same tab and key=value line format as sourcemap.dbg:

  registers   base                         the address of the imaginary register __rc0
  scope       id, parent, ranges           a function or block: where its variables exist
  type        id, kind, name, size, ...    base, pointer, typedef, struct, union, enum, array
  member      type, name, membertype, offset, bitoffset, bitsize   (a struct's fields)
  enumerator  type, name, value
  var         id, name, type, scope
  location    var, low, high, ops          where var is for PCs in [low, high)

ids are DWARF offsets (scope 0 is the whole program, for globals). ranges, low and high are hex
addresses ("8323-833f+8349-8600"); a location that holds for the whole scope is 0-10000.

ops is the variable's DWARF location expression as a space-separated list, evaluated by the
emulator on a stack:
  reg:R          the variable is in register R (A, X, Y, RCn, or RSn: RC2n and RC2n+1)
  breg:R:N       push R's value + N (then, without stack_value, that's the variable's address)
  addr:N         push address N
  lit:N          push N
  plus:N, plus, minus, mul, div, mod, and, or, xor, shl, shr, neg, not, deref (2 bytes)
  convert:N      truncate the top of the stack to N bytes
  stack_value    the top of the stack is the variable's value, not its address
  piece:N        the location so far is the next N bytes of the variable
  unknown:NAME   an operation the emulator can't evaluate
  unavailable:WHY  the location isn't trustworthy (WHY has _ for spaces)

With a static stack (the release build: llvm-mos's default, and on unless -fno-static-stack),
a function that can't be re-entered keeps its frame and its callee-saved registers (RC20-RC31)
at fixed zero-page addresses instead, but the debug info still names the registers and the C
stack pointer (RS0). Those locations are written as unavailable rather than wrong;
build.py's debug build has no static stack, so its locations are all real.
"""
import os
import re
import sys

import debug_files

DIE = re.compile(r"^0x([0-9a-f]+):( +)(DW_TAG_\w+|NULL)\s*$")
ATTRIBUTE = re.compile(r"^\s+(DW_AT_\w+)\t\((.*)$")
REFERENCE = re.compile(r"^\(?0x([0-9a-f]+)")
RANGE = re.compile(r"\[0x([0-9a-f]+), 0x([0-9a-f]+)\)")
LOCATION_ENTRY = re.compile(r"^\s*\[0x([0-9a-f]+), 0x([0-9a-f]+)\): (.*)$")
OPERATION = re.compile(r"^DW_OP_(\w+)\s*(.*)$")
REGISTER_OFFSET = re.compile(r"^(\w+)([+-]\d+)$")
WHOLE_SCOPE = (0, 0x10000)
SCOPE_TAGS = ("DW_TAG_subprogram", "DW_TAG_lexical_block", "DW_TAG_inlined_subroutine")
VARIABLE_TAGS = ("DW_TAG_variable", "DW_TAG_formal_parameter")


class Die:
    def __init__(self, offset, tag, parent):
        self.offset = offset
        self.tag = tag
        self.parent = parent
        self.attributes = {}
        self.children = []


def parenthesis_change(text):
    text = RANGE.sub("", text)
    return text.count("(") - text.count(")")


def read_dies(elf_path):
    """Parses llvm-dwarfdump --debug-info into DIEs; returns {offset: Die} and the compile units."""
    dies = {}
    units = []
    stack = []  # (depth, Die)
    lines = debug_files.run_tool("llvm-dwarfdump", "--debug-info", elf_path).splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        index += 1
        match = DIE.match(line)
        if match:
            depth = len(match.group(2))
            while stack and stack[-1][0] >= depth:
                stack.pop()
            if match.group(3) == "NULL":
                continue
            parent = stack[-1][1] if stack else None
            die = Die(int(match.group(1), 16), match.group(3), parent)
            dies[die.offset] = die
            if parent is None:
                units.append(die)
            else:
                parent.children.append(die)
            stack.append((depth, die))
            continue
        match = ATTRIBUTE.match(line)
        if match and stack:
            value = match.group(2)
            # Location and range lists go on over several lines, until the parentheses close
            # (not counting the ")" that ends each "[low, high)" range).
            depth = 1 + parenthesis_change(value)
            while depth > 0 and index < len(lines):
                value += "\n" + lines[index]
                depth += parenthesis_change(lines[index])
                index += 1
            stack[-1][1].attributes[match.group(1)] = value[:-1] if value.endswith(")") else value
    return dies, units


def read_address_tables(elf_path):
    """Returns {addr_base: [addresses]}: .debug_addr's tables, by the offset of their first entry."""
    tables = {}
    offset = 0
    current = None
    for line in debug_files.run_tool("llvm-dwarfdump", "--debug-addr", elf_path).splitlines():
        match = re.match(r"^Address table header: length = 0x([0-9a-f]+)", line)
        if match:
            # DWARF 5, 32-bit: a 4-byte length, then version, address size and segment size.
            current = []
            tables[offset + 8] = current
            offset += 4 + int(match.group(1), 16)
            continue
        match = re.match(r"^0x([0-9a-f]+)$", line.strip())
        if match and current is not None:
            current.append(int(match.group(1), 16))
    return tables


def string_attribute(die, name):
    value = die.attributes.get(name)
    if value is None:
        return None
    match = re.match(r'^"(.*)"$', value.strip())
    return debug_files.unescape(match.group(1)) if match else value.strip()


def number_attribute(die, name):
    value = die.attributes.get(name)
    return None if value is None else int(value.strip().split()[0], 0)


def reference_attribute(die, name):
    value = die.attributes.get(name)
    if value is None:
        return None
    match = REFERENCE.match(value.strip())
    return int(match.group(1), 16) if match else None


def origin(die, dies):
    """The DIE an inlined or out-of-line copy refers back to, for its name and type."""
    reference = reference_attribute(die, "DW_AT_abstract_origin")
    return dies[reference] if reference is not None and reference in dies else die


def scope_ranges(die):
    if "DW_AT_ranges" in die.attributes:
        return [(int(low, 16), int(high, 16)) for low, high in RANGE.findall(die.attributes["DW_AT_ranges"])]
    low = number_attribute(die, "DW_AT_low_pc")
    high = number_attribute(die, "DW_AT_high_pc")
    if low is None or high is None:
        return []
    # high_pc is the end address, or (as a plain length) how far past low_pc it is.
    return [(low, high if high > low else low + high)]


def type_records(die, dies):
    tag = die.tag
    name = string_attribute(die, "DW_AT_name")
    size = number_attribute(die, "DW_AT_byte_size")
    target = reference_attribute(die, "DW_AT_type") or 0
    quoted = f',name="{name}"' if name else ""
    if tag == "DW_TAG_base_type":
        encoding = (die.attributes.get("DW_AT_encoding") or "").strip()
        kind = ("bool" if "boolean" in encoding else "float" if "float" in encoding
                else "signed" if "signed" in encoding and "unsigned" not in encoding else "unsigned")
        return [f"type\tid={die.offset},kind=base{quoted},size={size or 1},encoding={kind}"]
    if tag == "DW_TAG_pointer_type":
        return [f"type\tid={die.offset},kind=pointer,size={size or 2},target={target}"]
    if tag in ("DW_TAG_typedef", "DW_TAG_const_type", "DW_TAG_volatile_type", "DW_TAG_restrict_type"):
        return [f"type\tid={die.offset},kind=typedef{quoted},target={target}"]
    if tag in ("DW_TAG_structure_type", "DW_TAG_union_type"):
        kind = "struct" if tag == "DW_TAG_structure_type" else "union"
        records = [f"type\tid={die.offset},kind={kind}{quoted},size={size or 0}"]
        for member in die.children:
            if member.tag != "DW_TAG_member":
                continue
            bit_size = number_attribute(member, "DW_AT_bit_size") or 0
            bit_offset = number_attribute(member, "DW_AT_data_bit_offset")
            byte_offset = number_attribute(member, "DW_AT_data_member_location") or 0
            if bit_offset is None:
                bit_offset = byte_offset * 8
            records.append(f'member\ttype={die.offset},name="{string_attribute(member, "DW_AT_name")}",'
                           f"membertype={reference_attribute(member, 'DW_AT_type') or 0},"
                           f"offset={bit_offset // 8},bitoffset={bit_offset},bitsize={bit_size}")
        return records
    if tag == "DW_TAG_enumeration_type":
        records = [f"type\tid={die.offset},kind=enum{quoted},size={size or 1},target={target}"]
        for enumerator in die.children:
            if enumerator.tag == "DW_TAG_enumerator":
                records.append(f'enumerator\ttype={die.offset},name="{string_attribute(enumerator, "DW_AT_name")}",'
                               f"value={number_attribute(enumerator, 'DW_AT_const_value')}")
        return records
    if tag == "DW_TAG_array_type":
        counts = []
        for subrange in die.children:
            if subrange.tag != "DW_TAG_subrange_type":
                continue
            count = number_attribute(subrange, "DW_AT_count")
            if count is None:
                upper = number_attribute(subrange, "DW_AT_upper_bound")
                count = 0 if upper is None else upper + 1
            counts.append(str(count))
        return [f"type\tid={die.offset},kind=array,target={target},count={'x'.join(counts) or '0'}"]
    if tag == "DW_TAG_subroutine_type":
        return [f"type\tid={die.offset},kind=function,size=2"]
    return []


def frame_register(die):
    """The register a function's frame base is in (its DW_AT_frame_base), or None."""
    value = die.attributes.get("DW_AT_frame_base")
    match = re.fullmatch(r"\s*DW_OP_regx? ?(\w+)\s*", value) if value else None
    return match.group(1) if match else None


def convert_expression(text, dies, addresses, frame):
    """A DWARF location expression, as llvm-dwarfdump prints it, in variables.dbg's ops form.
    frame is the register holding the enclosing function's frame base, for DW_OP_fbreg."""
    tokens = []
    for operation in re.split(r",\s*(?=DW_OP_)", text.strip()):
        match = OPERATION.match(operation.strip())
        if match is None:
            tokens.append("unknown:" + operation.strip().replace(" ", "_").replace(",", "_"))
            continue
        name, argument = match.group(1), match.group(2).strip()
        if re.fullmatch(r"reg\d+", name) or name == "regx":
            tokens.append(f"reg:{argument}")
        elif re.fullmatch(r"breg\d+", name) or name == "bregx":
            register = REGISTER_OFFSET.match(argument)
            tokens.append(f"breg:{register.group(1)}:{int(register.group(2))}" if register else f"unknown:{name}")
        elif name == "fbreg":
            # The frame base is the register's value: the address is that plus the offset.
            tokens.append(f"breg:{frame}:{int(argument)}" if frame else "unknown:fbreg")
        elif re.fullmatch(r"lit\d+", name):
            tokens.append(f"lit:{name[3:]}")
        elif name in ("constu", "consts", "const1u", "const1s", "const2u", "const2s", "const4u", "const4s"):
            tokens.append(f"lit:{int(argument.split()[0], 0)}")
        elif name in ("stack_value", "plus", "minus", "mul", "div", "mod", "and", "or", "xor", "shl", "shr", "neg",
                      "not", "deref"):
            tokens.append(name)
        elif name == "plus_uconst":
            tokens.append(f"plus:{int(argument, 0)}")
        elif name == "piece":
            tokens.append(f"piece:{int(argument, 0)}")
        elif name == "convert":
            reference = REFERENCE.match(argument)
            base = dies.get(int(reference.group(1), 16)) if reference else None
            size = number_attribute(base, "DW_AT_byte_size") if base else None
            tokens.append(f"convert:{size}" if size else "unknown:convert")
        elif name == "addrx":
            index = int(argument, 0)
            tokens.append(f"addr:{addresses[index]}" if addresses and index < len(addresses) else "unknown:addrx")
        elif name == "addr":
            tokens.append(f"addr:{int(argument, 0)}")
        else:
            tokens.append(f"unknown:{name}")
    return " ".join(tokens)


STATIC_STACK_REGISTER = re.compile(r"^(reg|breg):(RC(2\d|3[01])|RS(0|1[0-5]))(:|$)")
STATIC_STACK_UNAVAILABLE = "unavailable:not_tracked_with_a_static_stack_(use_the_debug_build)"


def without_static_stack_registers(ops):
    """ops, or unavailable if it uses a register a static stack replaces (see the top)."""
    if any(STATIC_STACK_REGISTER.match(operation) for operation in ops.split()):
        return STATIC_STACK_UNAVAILABLE
    return ops


def location_records(variable_id, die, dies, addresses, symbol_addresses, name, static_stack, frame):
    """Where the variable is: its location list, a single expression, a constant, or (for a
    variable defined in assembly, declared in C) its symbol's address."""
    location = die.attributes.get("DW_AT_location")
    entries = []
    if location is not None:
        if "loclist" in location:
            for line in location.splitlines()[1:]:
                match = LOCATION_ENTRY.match(line)
                if match:
                    entries.append((int(match.group(1), 16), int(match.group(2), 16),
                                    convert_expression(match.group(3), dies, addresses, frame)))
        else:
            entries.append((*WHOLE_SCOPE, convert_expression(location, dies, addresses, frame)))
    elif "DW_AT_const_value" in die.attributes:
        entries.append((*WHOLE_SCOPE, f"lit:{number_attribute(die, 'DW_AT_const_value')} stack_value"))
    elif name in symbol_addresses:
        entries.append((*WHOLE_SCOPE, f"addr:{symbol_addresses[name]}"))
    if static_stack:
        entries = [(low, high, without_static_stack_registers(ops)) for low, high, ops in entries]
    return [f"location\tvar={variable_id},low={low:x},high={high:x},ops={ops}" for low, high, ops in entries]


def read_symbol_addresses(elf_path):
    """Returns ({data symbol: address}, the address of __rc0)."""
    addresses = {}
    register_base = None
    for line in debug_files.run_tool("llvm-nm", "--defined-only", elf_path).splitlines():
        match = debug_files.NM_LINE.match(line.strip())
        if match is None:
            continue
        if match.group(3) == "__rc0":
            register_base = int(match.group(1), 16)
        elif match.group(2) not in ("a", "A", "t", "T"):
            addresses.setdefault(match.group(3), int(match.group(1), 16))
    if register_base is None:
        sys.exit(f"{elf_path} has no __rc0 symbol")
    return addresses, register_base


def write_variables(elf_path, output_path, static_stack):
    dies, units = read_dies(elf_path)
    address_tables = read_address_tables(elf_path)
    symbol_addresses, register_base = read_symbol_addresses(elf_path)
    records = [f"registers\tbase={register_base}"]
    defined_globals = set()
    pending_declarations = []

    def visit(die, scope, addresses, frame):
        nonlocal records
        records += type_records(die, dies)
        child_scope = scope
        frame = frame_register(die) or frame
        if die.tag in SCOPE_TAGS:
            ranges = scope_ranges(die)
            if ranges:
                text = "+".join(f"{low:x}-{high:x}" for low, high in ranges)
                records.append(f"scope\tid={die.offset},parent={scope},ranges={text}")
                child_scope = die.offset
            elif die.tag != "DW_TAG_lexical_block":
                return  # a declaration, or a function with no code: nothing to look up in it
        if die.tag in VARIABLE_TAGS:
            source = origin(die, dies)
            name = string_attribute(source, "DW_AT_name") or string_attribute(die, "DW_AT_name")
            type_id = reference_attribute(source, "DW_AT_type") or reference_attribute(die, "DW_AT_type") or 0
            if name:
                if "DW_AT_declaration" in die.attributes and "DW_AT_location" not in die.attributes:
                    pending_declarations.append((die, name, type_id))
                else:
                    if scope == 0:
                        defined_globals.add(name)
                    records.append(f'var\tid={die.offset},name="{name}",type={type_id},scope={scope}')
                    records.extend(location_records(die.offset, die, dies, addresses, {}, name, static_stack, frame))
        for child in die.children:
            visit(child, child_scope, addresses, frame)

    for unit in units:
        addresses = address_tables.get(number_attribute(unit, "DW_AT_addr_base"), [])
        for child in unit.children:
            visit(child, 0, addresses, None)
    # extern declarations of variables defined in assembly (gt_frame_count): placed by symbol.
    for die, name, type_id in pending_declarations:
        if name in defined_globals or name not in symbol_addresses:
            continue
        defined_globals.add(name)
        records.append(f'var\tid={die.offset},name="{name}",type={type_id},scope=0')
        records.extend(location_records(die.offset, die, dies, [], symbol_addresses, name, static_stack, None))
    with open(output_path, "w", encoding="utf-8") as handle:
        handle.write("\n".join(records) + "\n")


def main():
    arguments = sys.argv[1:]
    if len(arguments) not in (2, 3) or (len(arguments) == 3 and arguments[2] != "--no-static-stack"):
        sys.exit("usage: variables.py <build directory> <name> [--no-static-stack]")
    build, name = arguments[0], arguments[1]
    write_variables(debug_files.elf_path(build, name), os.path.join(build, "variables.dbg"),
                    static_stack=len(arguments) == 2)


if __name__ == "__main__":
    main()
