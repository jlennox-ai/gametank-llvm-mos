# gametank-llvm-mos

A modern C build environment for the [GameTank](https://gametank.zone), the 6502 game console,
using [llvm-mos](https://llvm-mos.org) instead of cc65. It has:

- a small SDK for the GameTank: startup code, a linker script for the 2 MB cartridge, and C
  functions for the blitter, the gamepad and frame timing
- a build script that compiles your C and assembly into a cartridge image
- tools that turn the compiler's debug info into the files the GameTank emulator's debugger
  reads, so it can show your C source as it steps through it, and the values of your variables
- an optional tool that turns PNG tiles into GameTank color data, once per palette

It runs on Windows and Linux.

## llvm-mos vs cc65

- [cc65](https://cc65.github.io) A the long-standing C compiler for the 6502 (
[GameTank SDK](https://github.com/clydeshaffer/gametank_sdk) uses it).
- llvm-mos is a port of LLVM and Clang to the 6502.

**Newer C.** cc65 is close to C89. llvm-mos is Clang, so you get C99 through C23 (`constexpr`, `typeof`,
`#embed`, `enum Foo : uint8_t`...), and C++ too. See [feature table](#c-language-features) below.

**Better code.** cc65 compiles one function at a time, passes arguments on a software stack, and
calls runtime routines for much of what's wider than a byte, such as a multiply for every
`grid[y][x]`. llvm-mos has LLVM's optimizer and a real register allocator. Arguments go in A, X
and 32 zero-page "imaginary registers". With link-time optimization the whole program is
optimized at once: functions are inlined across files, and zero page goes to whichever globals
and locals use it most. On the [examples below](#llvm-mos-and-cc65-compared), llvm-mos's code is
3 to 6 times faster, and usually smaller.

**Debugging in C.** Clang writes DWARF debug info which can be used by [GameTank Emulator Plus](https://github.com/jlennox-ai/GameTankEmulatorPlus).

## Downsides / TODO

- **No audio tooling:** It's bring your own right now.
- **No bank switching:** Your program is stuck to 32 KB. the rest of the 2 MB cartridge can't be used until there are bank-switching helpers.

## Using it

### Setting up

1. **Python 3.8 or later.** Windows users can get it from [python.org](https://www.python.org/downloads/).
2. **llvm-mos.** Download the [llvm-mos SDK](https://github.com/llvm-mos/llvm-mos-sdk/releases)
   release for your system and unpack it into `dev/`, so that `dev/llvm-mos/bin/clang`
   (`clang.exe` on Windows) exists. It's tested with v23.3.0.
   - Windows: `llvm-mos-windows.7z`, unpacked with [7-Zip](https://www.7-zip.org).
   - Linux: `mkdir -p dev && tar -xJf llvm-mos-linux.tar.xz -C dev`
3. **Rust**, only if you use the graphics tool (`assets/`, see [Graphics](#graphics)): cargo,
   from [rustup](https://rustup.rs).
4. **An emulator** to run the image: the
   [GameTank Emulator](https://github.com/clydeshaffer/GameTankEmulator), or
   [GameTank Emulator Plus](https://github.com/jlennox-ai/GameTankEmulatorPlus)

### Building

Inside your game's source directory:

    python build.py
    
Your game will be written to `build/<dir name>.gtr`

### SDK

`sdk/gametank.h`:

| | |
|---|---|
| `gt_read_pad1()` | The buttons held on pad 1 (`GT_BUTTON_UP`, `GT_BUTTON_A`, ...) |
| `gt_fill_rect(x, y, width, height, color)` | Starts a blit filling a rectangle. Width and height are 1-127 |
| `gt_clear_screen(color)` | Fills the whole framebuffer being drawn |
| `gt_sprite_sheet_load(sheet, width, height, gram_x, gram_y)` | Copies color data into graphics RAM (a 256x256 page), across quadrants if it needs to |
| `gt_sprite_draw(x, y, gram_x, gram_y, width, height)` | Starts a blit from graphics RAM to the framebuffer. |
| `gt_wait_blit()` | Waits for the blit in progress |
| `gt_show_frame()` | Waits for the frame's blits and the next vsync |
| `gt_frame_count`, `gt_late_frames` | Vsyncs so far, and frames that took longer than one |
| `GT_COLOR(hue, saturation, luminance)` | A color byte: hue 0-7, saturation 0-3, luminance 0-7 |
| `GT_ASSERT(condition)`, `gt_panic()` | Halt the CPU (`STP`) where the debugger can see it |
| `GT_DEBUG_FUNCTION` | See [Debugging](#debugging) |

### Debugging

`build.py debug` builds into `build-debug/`. Useful for GameTank Emulator Plus's debug features.

| File | What |
|---|---|
| `sourcemap.dbg` | The emulator's source view (ld65's debug info format), for every bank of the program |
| `out.map` | The emulator's symbols (ld65's map format) |
| `variables.dbg` | Where each variable is, PC by PC, with its type: GameTank Emulator Plus's variable hovers |
| `game.lbl` | Every label, VICE-style (`al 008000 .main`) |
| `game.map` | lld's map: sections, symbols, sizes |
| `assembly.s` | The linked program disassembled, with the C source between |
| `game.gtr.elf` | The ELF, with its DWARF debug info |

Even in the debug build, optimized code keeps a value only while it needs it. To see every
variable in a function for the whole function, put `GT_DEBUG_FUNCTION` before it to de-optimize just that function.

### Graphics

`tools/tile_palettes` turns a PNG of tiles into GameTank color data, once per palette, so one
drawing becomes as many color versions as you have palettes. For each `assets/*.toml`, the build
writes `<name>.h` and `<name>.c` into `build/assets/` (you `#include "<name>.h"`), and
`<name>_preview.png` to check the colors. For example, `assets/tiles.toml`:

```toml
name = "tiles"
image = "tiles.png"            # next to this file
tile_width = 12
tile_height = 12
tiles = ["solid", "single"]    # left to right in the image

# Every color in the image, as a shade: saturation 0-3 and luminance 0-7 (the palette gives the
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

A color the config doesn't list, or a shade pushed out of range by a palette, is an error that
names the pixel. A tile can't be called `h`, `x`, `y`, `sheet_width`, `sheet_height`,
`tile_width` or `tile_height`, or start with `palette_`: those names are taken in the header.

## llvm-mos vs cc65 compared

### Compiler output

| Function | What it does | cc65 cycles | llvm-mos cycles | Change | cc65 bytes | llvm-mos bytes |
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
(`mulax10`), and keeps `x` and `y` in memory. llvm-mos keeps a pointer to the row (`__rc2`,
starting at `grid`, `$2839`) and moves it 10 bytes a row, with `x` in Y and `y` in X:

<table>
<tr><th>cc65: 76 bytes, 16,654 cycles</th><th>llvm-mos: 46 bytes, 2,682 cycles</th></tr>
<tr>
<td valign="top">

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

</td>
<td valign="top">

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

</td>
</tr>
</table>

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
<summary>6502 output</summary>

<table>
<tr><th>cc65: 80 bytes, 321 cycles</th><th>llvm-mos: 61 bytes, 103 cycles</th></tr>
<tr>
<td valign="top">

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

</td>
<td valign="top">

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

</td>
</tr>
</table>

</details>

`hash_bytes` is the one where llvm-mos's code is bigger (by 4 bytes): it does the multiply by 33
inline, with shifts and adds, where cc65 calls a runtime routine (`tosumula0`), which is why it's
3.5 times faster.

### C language features

| Feature | Standard | cc65 | llvm-mos |
|---|---|---|---|
| Variable declarations after statements | C99 | no | yes |
| Variable declarations in for loops | C99 | no | yes |
| Designated initializers | C99 | no | yes |
| Compound literals | C99 | no | yes |
| 64-bit integers: `uint64_t` | C99 | no | yes |
| Floating point | C89 | no | yes |
| Structs passed and returned by value | C89 | no | yes |
| Anonymous structs and unions | C11 | yes | yes |
| `_Static_assert` | C11 | yes | yes |
| `_Generic` | C11 | no | yes |
| `bool`, `true`, `false` and `nullptr` as keywords | C23 | no | yes |
| `typeof` | C23 | no | yes |
| `constexpr` | C23 | no | yes |
| Enums with a fixed underlying type: `enum E : uint8_t` | C23 | no | yes |
| Binary literals: `0b1010` | C23 | yes | yes |
| Digit separators: `1'000'000` | C23 | no | yes |
| Attributes: `[[nodiscard]]`, `[[maybe_unused]]`, `[[fallthrough]]` | C23 | no | yes |
| `#embed`: a file's bytes as an initializer | C23 | no | yes |
| Classes, templates, constexpr and lambdas | C++ | no | yes |


## Credits and licenses

This repository is under the [MIT license](LICENSE). It uses, or took parts from:

| What | Used for | License |
|---|---|---|
| [llvm-mos](https://github.com/llvm-mos/llvm-mos) | The compiler, assembler and linker. Downloaded, not included | Apache 2.0 with LLVM Exceptions |
| [llvm-mos SDK](https://github.com/llvm-mos/llvm-mos-sdk) | The `mos-common` configuration, linker scripts (`c.ld`, `imag-regs.ld`), startup libraries and C library. Downloaded, not included; parts of it are linked into your image, which the LLVM Exceptions allow without attribution | Apache 2.0 with LLVM Exceptions (some of its other targets' code is under cc65's zlib license or MIT) |
| [GameTank](https://github.com/clydeshaffer/gametank), by Clyde Shaffer | The console itself: `sdk/` is written for its registers and hardware | No license stated |
| [GameTank Emulator](https://github.com/clydeshaffer/GameTankEmulator), by Clyde Shaffer | The color table in `tools/tile_palettes/src/gametank_palette.rs` is its `src/gametank_palette.h`. The debug files are written in the formats it reads | MIT |
| [GameTank Emulator Plus](https://github.com/jlennox-ai/GameTankEmulatorPlus) | Reads `variables.dbg`, the format `tools/variables.py` writes | MIT |
