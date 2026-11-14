# gametank-llvm-mos

A modern C build environment for the [GameTank](https://gametank.zone), the 6502 game console,
using [llvm-mos](https://llvm-mos.org) instead of cc65. It has:

- a small SDK for the GameTank: startup code, a linker script for the 2 MB cartridge, and C
  functions for the blitter, the gamepad and frame timing
- a build script that compiles your C and assembly into a cartridge image
- tools that turn the compiler's debug info into the files the GameTank emulator's debugger
  reads, so it can show your C source as it steps through it, and the values of your variables
- an optional tool that turns PNG tiles into GameTank colour data, once per palette

It runs on Windows and Linux.

## Why llvm-mos and not cc65

[cc65](https://cc65.github.io) is the long-standing C compiler for the 6502, and what the
[GameTank SDK](https://github.com/clydeshaffer/gametank_sdk) uses. llvm-mos is a port of LLVM and
Clang to the 6502. For a GameTank game it's the better compiler, for three reasons.

**Newer C.** cc65 is close to C89. It rejects declarations after statements or in a `for` loop,
designated initializers, compound literals, `long long`, floating point, `_Generic`, and every
C23 feature we tried. llvm-mos is Clang, so you get C99 through C23 (`constexpr`, `typeof`,
`#embed`, `enum Direction : uint8_t`...), and C++ too. See the
[feature table](#c-language-features) below.

**Better code.** cc65 compiles one function at a time, passes arguments on a software stack, and
calls runtime routines for much of what's wider than a byte, such as a multiply for every
`grid[y][x]`. llvm-mos has LLVM's optimizer and a real register allocator. Arguments go in A, X
and 32 zero-page "imaginary registers". With link-time optimization the whole program is
optimized at once: functions are inlined across files, and zero page goes to whichever globals
and locals use it most. On the [examples below](#llvm-mos-and-cc65-compared), llvm-mos's code is
3 to 6 times faster, and usually smaller.

**Debugging in C.** Clang writes DWARF debug info, and the build converts it into the emulator's
formats: source lines for all 32 KB of the program, symbols, and where each variable is.

What cc65 has that this doesn't: maturity, a large runtime library, the ca65 macro assembler that
a lot of 6502 code is written for, and the GameTank SDK's audio and asset pipeline. This is only
the compiler setup. It has no audio support, and the program lives in the cartridge's last 32 KB:
the other 126 banks are in the image for data, but nothing here helps you use them yet.

## Using it

### Setting up

1. **Python 3.8 or later.** Only the standard library is used. Most Linux distributions come
   with it; on Windows, get it from [python.org](https://www.python.org/downloads/).
2. **llvm-mos.** Download the [llvm-mos SDK](https://github.com/llvm-mos/llvm-mos-sdk/releases)
   release for your system and unpack it into `dev/`, so that `dev/llvm-mos/bin/clang`
   (`clang.exe` on Windows) exists. It's tested with v23.3.0.
   - Windows: `llvm-mos-windows.7z`, unpacked with [7-Zip](https://www.7-zip.org).
   - Linux: `mkdir -p dev && tar -xJf llvm-mos-linux.tar.xz -C dev`
3. **Rust**, only if you use the graphics tool (`assets/`, see [Graphics](#graphics)): cargo,
   from [rustup](https://rustup.rs).
4. **An emulator** to run the image: the
   [GameTank Emulator](https://github.com/clydeshaffer/GameTankEmulator), or
   [GameTank Emulator Plus](https://github.com/jlennox-ai/GameTankEmulatorPlus), a fork that
   adds C source stepping, variable hovers and other debugging tools. It isn't part of this repo.

### Building

    python build.py          (Windows; or py build.py)
    python3 build.py         (Linux)

That writes `build/game.gtr`, a 2 MB cartridge image, and the debug files next to it. Open it in
the emulator. `build.py debug` makes a debug build in `build-debug/` instead (see
[Debugging](#debugging)).

To name the image after your game, change `NAME` at the top of `build.py`. Every `.c` and `.s` in
`sdk/` and `src/` is built, so new files need no changes to the build.

### What's here

| Path | What |
|---|---|
| `sdk/` | The GameTank support: `gametank.h` is the C API, `crt0.s` the startup code, `link.ld` the memory layout |
| `src/` | Your game. It starts as an example: a block you move with the d-pad, and A, B and C change its colour |
| `assets/` | Graphics for `tools/tile_palettes` (create it if you need it, see [Graphics](#graphics)) |
| `build.py` | The build |
| `tools/` | The build's helpers: the debug file writers, the dead branch finder and the graphics tool |
| `comparison/` | The comparison with cc65 below, and the script that produces it |
| `dev/` | The tools you download (not checked in) |

### The SDK

`sdk/gametank.h`:

| | |
|---|---|
| `gt_read_pad1()` | The buttons held on pad 1 (`GT_BUTTON_UP`, `GT_BUTTON_A`, ...) |
| `gt_fill_rect(x, y, width, height, color)` | Starts a blit filling a rectangle in the framebuffer being drawn. Width and height are 1-127 |
| `gt_clear_screen(color)` | Fills the whole framebuffer being drawn |
| `gt_sprite_sheet_load(sheet, width, height, gram_x, gram_y)` | Copies colour data into graphics RAM (a 256x256 page), across quadrants if it needs to |
| `gt_sprite_draw(x, y, gram_x, gram_y, width, height)` | Starts a blit from graphics RAM to the framebuffer. Colour 0 is transparent |
| `gt_wait_blit()` | Waits for the blit in progress |
| `gt_show_frame()` | Waits for the frame's blits and the next vsync, then shows the frame and starts drawing the other. Call it once a frame |
| `gt_frame_count`, `gt_late_frames` | Vsyncs so far, and frames that took longer than one |
| `GT_COLOR(hue, saturation, luminance)` | A colour byte: hue 0-7, saturation 0-3, luminance 0-7 |
| `GT_ASSERT(condition)`, `gt_panic()` | Halt the CPU (`STP`) where the debugger can see it |
| `GT_DEBUG_FUNCTION` | See [Debugging](#debugging) |

Drawing is double buffered: you draw into one framebuffer while the other is shown, and
`gt_show_frame` swaps them.

**Memory.** The program is the cartridge's last 32 KB, banks 126 and 127, seen at `$8000-$FFFF`.
Banks 0-125 are free, and zero-filled in the image. RAM is `$0000-$1FFF`: zero page (the compiler's
imaginary registers at `$E0-$FF`, the rest for variables), the 6502 stack at `$0100`, data and
BSS from `$0200`, and the C stack, 1 KB, down from `$2000`.

**Startup.** Reset runs `gt_reset` (`crt0.s`), at the top of bank 127, which is always mapped. It
sets up the hardware, clears RAM, maps bank 126 and jumps to llvm-mos's startup: the C stack,
initialised data and BSS. Then `gt_init` (`gametank.s`) sets up the framebuffers and the vsync
interrupt, and `main()` runs. Interrupts stay masked: the vsync NMI counts frames, and the
blitter's IRQ only wakes `WAI`. If `main()` returns, a `BRK` runs, or a `GT_ASSERT` fails, the CPU
halts, so mistakes stop loudly instead of running on.

### Writing code for llvm-mos

- It's C23 (`-std=gnu23`), so `constexpr`, `typeof`, `bool`, `nullptr`, `#embed`, designated
  initializers and declarations anywhere all work.
- Plain local variables are the fast choice: the compiler keeps them in registers and zero page.
  A file-scope variable written in a loop gets stored back on every pass.
- The calling convention: byte arguments in A, X, then `__rc2`, `__rc3`, ...; pointers in pairs
  from `__rc2`; the result in A (and X). A, X, Y and `__rc2`-`__rc19` may be clobbered by a
  call; `__rc20`-`__rc31` must be preserved.
- Assembly is LLVM's syntax: `.section .text.name,"ax",@progbits`, `.globl`, `0x` numbers,
  `#<symbol` and `#>symbol`, numeric local labels (`1:` ... `bne 1b`). Declare zero page symbols
  with `.zeropage name` to get zero page addressing. `sdk/gametank.s` shows all of it.
- Link-time optimization inlines most functions away, and can split a global struct into its
  fields (`g_player.0`, `g_player.1`), so some names you'd expect aren't in the symbol list. Mark
  a function `__attribute__((noinline))` to keep it as its own routine.
- A function that can end without returning its value is an error (`-Werror=return-type`): the
  optimizer would otherwise assume that path never runs, and delete code around it.

### Debugging

Next to the image, the build writes:

| File | What |
|---|---|
| `sourcemap.dbg` | The emulator's source view (ld65's debug info format), for every bank of the program |
| `out.map` | The emulator's symbols (ld65's map format) |
| `variables.dbg` | Where each variable is, PC by PC, with its type: GameTank Emulator Plus's variable hovers |
| `game.lbl` | Every label, VICE-style (`al 008000 .main`) |
| `game.map` | lld's map: sections, symbols, sizes |
| `assembly.s` | The linked program disassembled, with the C source between |
| `game.gtr.elf` | The ELF, with its DWARF debug info |

Each build also lists the `if`s, `else`s, loops and `switch`es the optimizer compiled to nothing:
code that's dead because of values, like a condition testing a field the line before just set.
The compiler doesn't warn about those. It's a list of places to look, not proof:
`tools/no_code_lines.py` explains.

`build.py debug` builds into `build-debug/` with `-Og -fno-inline -fno-static-stack`: every
function stays its own routine and the code follows the source closely, so stepping through it is
easier. `-fno-static-stack` matters for variable hovers. By default llvm-mos gives a function
that can't be re-entered a fixed frame in zero page, which the debug info doesn't describe, so in
the release build those variables show as unavailable.

Even in the debug build, optimized code keeps a value only while it needs it. To see every
variable in a function for the whole function, put `GT_DEBUG_FUNCTION` before it: in the debug
build that compiles just that function without optimization, and elsewhere it does nothing.

### Graphics

`tools/tile_palettes` turns a PNG of tiles into GameTank colour data, once per palette, so one
drawing becomes as many colour versions as you have palettes. For each `assets/*.toml`, the build
writes `<name>.h` and `<name>.c` into `build/assets/` (you `#include "<name>.h"`), and
`<name>_preview.png` to check the colours. For example, `assets/tiles.toml`:

```toml
name = "tiles"
image = "tiles.png"            # next to this file
tile_width = 12
tile_height = 12
tiles = ["solid", "single"]    # left to right in the image

# Every colour in the image, as a shade: saturation 0-3 and luminance 0-7 (the palette gives the
# hue). Fully transparent pixels need no entry.
[colors]
"#ffffff" = "transparent"
"#1c9440" = { saturation = 3, luminance = 4 }
"#22b14c" = { saturation = 3, luminance = 5 }

# A row of tiles per palette: a hue 0-7, and optionally a luminance added to every shade.
[[palettes]]
name = "green"
hue = 7

[[palettes]]
name = "red"
hue = 2
luminance = -2
```

Then, in C:

```c
#include "tiles.h"

gt_sprite_sheet_load(tiles_sheet, TILES_SHEET_WIDTH, TILES_SHEET_HEIGHT, 0, 0);  // once, at startup
gt_sprite_draw(x, y, TILES_X(TILES_SOLID), TILES_Y(TILES_PALETTE_RED), TILES_TILE_WIDTH, TILES_TILE_HEIGHT);
```

A colour the config doesn't list, or a shade pushed out of range by a palette, is an error that
names the pixel. A tile can't be called `h`, `x`, `y`, `sheet_width`, `sheet_height`,
`tile_width` or `tile_height`, or start with `palette_`: those names are taken in the header.

## llvm-mos and cc65 compared

These come from [`comparison/results.md`](comparison/results.md), which has every listing. It's
written by [`comparison/compare.py`](comparison/compare.py), which compiles the same C with both
compilers and runs it on sim65, cc65's 6502 simulator, as a 65C02:

- cc65 V2.19 (Git e47ac50), `-Oirs -Cl`: optimize, inline runtime helpers, register variables,
  and locals at fixed addresses rather than on the software stack (its fastest settings).
- llvm-mos (SDK v23.3.0), with this build's flags: `-Os`, link-time optimization.

### Speed and size

Cycles for one call, passing the arguments included, and bytes of the function itself (cc65's
code also calls into its runtime library, which isn't counted).

| Function | What it does | cc65 cycles | llvm-mos cycles | llvm-mos is | cc65 bytes | llvm-mos bytes |
|---|---|--:|--:|--:|--:|--:|
| `entities_update` | moves 16 structs by their velocities | 4,701 | 1,250 | 3.8x faster | 211 | 81 |
| `clamp_add` | adds and clamps, 4 byte arguments | 321 | 103 | 3.1x faster | 80 | 61 |
| `grid_full_rows` | counts the full rows of a 10x20 grid | 16,654 | 2,682 | 6.2x faster | 76 | 46 |
| `hash_bytes` | a 16-bit hash of 64 bytes | 26,753 | 7,605 | 3.5x faster | 86 | 90 |
| `copy_rows` | copies a 16x16 block between two buffers | 25,489 | 7,146 | 3.6x faster | 95 | 54 |

For example, `grid_full_rows`, the line check of a falling-block game:

```c
uint8_t grid[GRID_HEIGHT][GRID_WIDTH];

uint8_t grid_full_rows(void) {
    uint8_t full = 0;
    uint8_t y;
    uint8_t x;
    for (y = 0; y < GRID_HEIGHT; ++y) {
        for (x = 0; x < GRID_WIDTH; ++x) {
            if (grid[y][x] == 0) {
                break;
            }
        }
        if (x == GRID_WIDTH) {
            ++full;
        }
    }
    return full;
}
```

cc65 works out `grid + y * 10` again for every cell, with a call to its multiply routine
(`mulax10`), and keeps `x` and `y` in memory:

```asm
        stz     M0001
        stz     M0002
        ldx     #$00
L000D:  lda     M0002
        cmp     #$14
        bcs     L0011
        stz     M0003
        ldx     #$00
L000E:  lda     M0003
        cmp     #$0A
        bcs     L000F
        lda     M0002
        jsr     mulax10
        clc
        adc     #<(_grid)
        sta     ptr1
        txa
        adc     #>(_grid)
        sta     ptr1+1
        ldy     M0003
        ldx     #$00
        lda     (ptr1),y
        beq     L000F
        inc     M0003
        bra     L000E
L000F:  lda     M0003
        cmp     #$0A
        bne     L0010
        inc     M0001
L0010:  inc     M0002
        bra     L000D
L0011:  lda     M0001
        rts
```

llvm-mos keeps a pointer to the row (`__rc2`, starting at `grid`, `$2839`) and moves it 10 bytes
a row, with `x` in Y and `y` in X:

```asm
        ldx     #$39
        stx     __rc2
        ldx     #$28
        stx     __rc3
        stz     __rc4
        ldx     #$0
L09F3:  ldy     #$0
L09F5:  lda     (__rc2),y
        beq     L0A00
        iny
        cpy     #$a
        bne     L09F5
        inc     __rc4
L0A00:  inx
        lda     __rc2
        clc
        adc     #$a
        sta     __rc2
        lda     __rc3
        adc     #$0
        sta     __rc3
        cpx     #$14
        bne     L09F3
        lda     __rc4
        rts
```

And `clamp_add`, for how arguments are passed:

```c
uint8_t clamp_add(uint8_t value, int8_t delta, uint8_t low, uint8_t high) {
    int16_t sum = (int16_t)value + delta;
    if (sum < low) {
        return low;
    }
    if (sum > high) {
        return high;
    }
    return (uint8_t)sum;
}
```

cc65's caller makes room on its software stack (`decsp3`) and stores the first three arguments
there. The function pushes the last one (`pusha`), reads them all back through the stack pointer
(`(c_sp),y`), compares 16-bit values with a runtime call (`tosicmp0`), and pops them on the way
out (`incsp4`). llvm-mos gets them in A, X, `__rc2` and `__rc3`, and needs no calls.

<details>
<summary>The two listings</summary>

cc65 (80 bytes, plus the runtime routines, and 321 cycles with the call):

```asm
        jsr     pusha
        ldx     #$00
        ldy     #$02
        lda     (c_sp),y
        bpl     L0002
        dex
L0002:  clc
        iny
        adc     (c_sp),y
        bcc     L0005
        inx
L0005:  sta     M0001
        stx     M0001+1
        ldy     #$01
        cmp     (c_sp),y
        txa
        sbc     #$00
        bvc     L0006
        eor     #$80
L0006:  bpl     L0003
        ldx     #$00
        lda     (c_sp),y
        jmp     incsp4
L0003:  lda     M0001
        ldx     M0001+1
        jsr     pushax
        ldy     #$02
        lda     (c_sp),y
        jsr     tosicmp0
        bmi     L0004
        beq     L0004
        ldx     #$00
        lda     (c_sp)
        jmp     incsp4
L0004:  ldx     #$00
        lda     M0001
        jmp     incsp4
```

llvm-mos (61 bytes, 103 cycles with the call):

```asm
        stx     __rc4
        cpx     #$0
        bpl     L09B4
        ldx     #$ff
        bra     L09B6
L09B4:  ldx     #$0
L09B6:  clc
        adc     __rc4
        sta     __rc5
        tay
        txa
        adc     #$0
        sta     __rc4
        cpy     __rc2
        sbc     #$0
        bvc     L09C9
        eor     #$80
L09C9:  tax
        bmi     L09E4
        ldy     #$0
        cpy     __rc4
        bne     L09D8
        ldx     __rc3
        cpx     __rc5
        bra     L09DC
L09D8:  cpy     __rc4
        ldx     __rc3
L09DC:  stx     __rc2
        bcc     L09E4
        ldx     __rc5
        stx     __rc2
L09E4:  lda     __rc2
        rts
```

</details>

`hash_bytes` is the one where llvm-mos's code is bigger (by 4 bytes): it does the multiply by 33
inline, with shifts and adds, where cc65 calls a runtime routine (`tosumula0`), which is why it's
3.5 times faster.

### C language features

Each program in [`comparison/features/`](comparison/features/) exits 0 when the feature works;
"no" is the compiler's error.

| Feature | Standard | cc65 | llvm-mos |
|---|---|---|---|
| Declarations after statements | C99 | no: `Variable identifier expected` | yes |
| Declarations in for loops | C99 | no: `Variable identifier expected` | yes |
| Designated initializers | C99 | no: `Expression expected` | yes |
| Compound literals | C99 | no: `Expression expected` | yes |
| Inline functions | C99 | yes | yes |
| 64-bit integers: `long long`, `uint64_t` | C99 | no: `Undeclared identifier 'uint64_t'` | yes |
| Floating point | C89 | no: `Floating point type is currently unsupported` | yes |
| Structs passed and returned by value | C89 | no: `Function return type 'struct $anon-struct-0001' of size 3 is unsupported` | yes |
| Anonymous structs and unions | C11 | yes | yes |
| `_Static_assert` | C11 | yes | yes |
| `_Generic` | C11 | no: `Call to undeclared function '_Generic'` | yes |
| `bool`, `true`, `false` and `nullptr` as keywords | C23 | no: `Undeclared identifier 'bool'` | yes |
| `typeof` | C23 | no: `Call to undeclared function 'typeof'` | yes |
| `constexpr` | C23 | no: `',' or ';' expected after top level declarator` | yes |
| Enums with a fixed underlying type: `enum E : uint8_t` | C23 | no: `Identifier or ';' expected after declaration specifiers` | yes |
| Binary literals: `0b1010` | C23 | yes | yes |
| Digit separators: `1'000'000` | C23 | no: `''' expected` | yes |
| Attributes: `[[nodiscard]]`, `[[maybe_unused]]`, `[[fallthrough]]` | C23 | no: `Identifier or ';' expected after declaration specifiers` | yes |
| `#embed`: a file's bytes as an initializer | C23 | no: `Preprocessor directive expected` | yes |
| Classes, templates, constexpr and lambdas | C++ | no: cc65 compiles C only | yes |

### Running it yourself

Put cc65 in `dev/cc65`, with its `bin`, `include`, `asminc`, `cfg` and `lib` folders, then run
`python3 comparison/compare.py` (`python` on Windows). It rewrites `comparison/results.md`.

- Windows: the [snapshot build](https://sourceforge.net/projects/cc65/files/),
  `cc65-snapshot-win64.zip`, unzipped into `dev/cc65`.
- Linux: `git clone https://github.com/cc65/cc65 dev/cc65 && make -C dev/cc65`.

It needs a recent cc65: the timing uses sim65's cycle counter, which the V2.19 release and most
distributions' packages don't have.

## Credits and licenses

This repository is under the [MIT license](LICENSE). It uses, or took parts from:

| What | Used for | License |
|---|---|---|
| [llvm-mos](https://github.com/llvm-mos/llvm-mos) | The compiler, assembler and linker. Downloaded, not included | Apache 2.0 with LLVM Exceptions |
| [llvm-mos SDK](https://github.com/llvm-mos/llvm-mos-sdk) | The `mos-common` configuration, linker scripts (`c.ld`, `imag-regs.ld`), startup libraries and C library. Downloaded, not included; parts of it are linked into your image, which the LLVM Exceptions allow without attribution | Apache 2.0 with LLVM Exceptions (some of its other targets' code is under cc65's zlib license or MIT) |
| [GameTank](https://github.com/clydeshaffer/gametank), by Clyde Shaffer | The console itself: `sdk/` is written for its registers and hardware | No license stated |
| [GameTank Emulator](https://github.com/clydeshaffer/GameTankEmulator), by Clyde Shaffer | The colour table in `tools/tile_palettes/src/gametank_palette.rs` is its `src/gametank_palette.h`. The debug files are written in the formats it reads | MIT |
| [GameTank Emulator Plus](https://github.com/jlennox-ai/GameTankEmulatorPlus) | Reads `variables.dbg`, the format `tools/variables.py` writes | MIT |
| Vania, by Joseph Lennox | `sdk/gametank.inc`'s register definitions, and the blit, vsync, gamepad and bank-switching code in `sdk/`, came from its cube prototype | MIT |
| [cc65](https://github.com/cc65/cc65) | The comparison: cc65, ca65, ld65 and sim65. Downloaded, not included. `sourcemap.dbg` and `out.map` are in ld65's debug info and map formats | zlib |
| [VICE](https://vice-emu.sourceforge.io) | The label file's format only | (format only) |
| Rust crates, for `tools/tile_palettes`: [png](https://crates.io/crates/png), [serde](https://crates.io/crates/serde), [toml](https://crates.io/crates/toml), and what they use | Reading PNGs and configs. Downloaded by cargo, not included | MIT or Apache 2.0, except: zlib-rs (Zlib), simd-adler32 and winnow (MIT), memchr (Unlicense or MIT), adler2 (0BSD, MIT or Apache 2.0), miniz_oxide (MIT, Zlib or Apache 2.0), unicode-ident ((MIT or Apache 2.0) and Unicode 3.0) |
