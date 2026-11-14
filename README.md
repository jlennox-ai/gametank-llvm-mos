# gametank-llvm-mos

A modern C build environment for the [GameTank](https://gametank.zone)
using [llvm-mos](https://llvm-mos.org) for Windows and Linux.

## Setup

1. **gametank-llvm-mos**: Download the bundle for your system from
   [releases](https://github.com/jlennox-ai/gametank-llvm-mos/releases) and unpack it anywhere.
2. **`GAMETANK_LLVM_MOS`**: Set the environment variable to the full path for the `gametank-llvm-mos` directory you unpacked.
3. **CMake 3.21+, and Ninja**: Linux: `apt install cmake ninja-build`. Windows:
   [CMake](https://cmake.org/download/) and [Ninja](https://github.com/ninja-build/ninja/releases)
   on your `PATH` (Visual Studio's "C++ CMake tools" include both).
4. **Python 3.8+**: For writing the debug files. Windows users can get it from
   [python.org](https://www.python.org/downloads/).
7. **An emulator**:
   [GameTank Emulator](https://github.com/clydeshaffer/GameTankEmulator) or
   [GameTank Emulator Plus](https://github.com/jlennox-ai/GameTankEmulatorPlus)
   
## Project setup

1. Copy `example/` to a new location.
2. Edit `CMakeLists.txt` to add your C files and graphics.
3. Edit or make a new `build.bat`/`build.sh` and away you go.

## SDK

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

## Debugging

`build.sh debug` (the `debug` preset) builds into `build-debug/`. Useful for GameTank Emulator
Plus's debug features.

| File | What |
|---|---|
| `sourcemap.dbg` | The emulator's source view (ld65's debug info format), for every bank of the program |
| `out.map` | The emulator's symbols (ld65's map format) |
| `variables.dbg` | Where each variable is, PC by PC, with its type: GameTank Emulator Plus's variable hovers |
| `<name>.lbl` | Every label, VICE-style (`al 008000 .main`) |
| `<name>.map` | lld's map: sections, symbols, sizes |
| `assembly.s` | The linked program disassembled, with the C source between |
| `<name>.gtr.elf` | The ELF, with its DWARF debug info |
| `compile_commands.json` | For clangd: use the one in `dev/llvm-mos/bin`, which knows the 6502 |

Even in the debug build, optimized code keeps a value only while it needs it. To see every
variable in a function for the whole function, put `GT_DEBUG_FUNCTION` before it to de-optimize just that function.

## Downsides / TODO

- **Not well used**: This was made by an LLM for my personal project :) Battle testers welcome.
- **No audio tooling**: It's bring your own right now.
- **No bank switching**: Your program is stuck to 32 KB. the rest of the 2 MB cartridge can't be used until there are bank-switching helpers.

## llvm-mos vs cc65

- [cc65](https://cc65.github.io) A long-standing C compiler for the 6502 ([GameTank SDK](https://github.com/clydeshaffer/gametank_sdk) uses it).
- [llvm-mos](https://github.com/llvm-mos/llvm-mos) is a port of LLVM and Clang to the 6502.

**Newer C**: cc65 is close to C89. llvm-mos is Clang, so you get C99 through C23 (`constexpr`, `typeof`,
`#embed`, `enum E : uint8_t`...), and C++. See [feature table](#c-language-features).

**Better code**: llvm-mos has LLVM's optimizer and a real register allocator. With link-time optimization the whole
program is optimized at once: functions are inlined across files, and zero page goes to whichever globals
and locals use it most. llvm-mos's code is 3 to 6 times faster and usually smaller.

**Debugging in C**: Clang writes DWARF debug info which can be used by [GameTank Emulator Plus](https://github.com/jlennox-ai/GameTankEmulatorPlus).

### Compiler output comparison

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
| [GameTank](https://github.com/clydeshaffer/gametank) | The console itself: `sdk/` is written for its registers and hardware | No license stated |
| [GameTank Emulator](https://github.com/clydeshaffer/GameTankEmulator) | The color table in `tools/tile_palettes/src/gametank_palette.rs` is its `src/gametank_palette.h`. The debug files are written in the formats it reads | MIT |
| [GameTank Emulator Plus](https://github.com/jlennox-ai/GameTankEmulatorPlus) | Supports `variables.dbg`, part of the debug output. | MIT |

🤖 This SDK was created by AI.