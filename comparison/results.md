# llvm-mos and cc65, compared

Written by [`compare.py`](compare.py) (rerun it rather than editing this), with:

- **cc65**: cc65 V2.19 - Git e47ac50, `cc65 -t sim65c02 -Oirs -Cl`
- **llvm-mos**: clang version 24.0.0git (https://github.com/llvm-mos/llvm-mos cd9145597347753c7cabd1c34d24722d4d8a8f96), `clang --config mos-common.cfg -mcpu=mosw65c02 -mlto-zp=200 -Os`, the flags `build.py` uses (link-time optimization included)

Both run on sim65, cc65's simulator, as a 65C02.

## Speed and size

The functions are in [`examples.c`](examples.c), timed by [`bench.c`](bench.c): the cycles for one
call (passing its arguments included), and the bytes of the function itself. cc65's code also
calls routines in its runtime library, which aren't counted in its size (they're listed with each
function below).

| Function | cc65 cycles | llvm-mos cycles | llvm-mos is | cc65 bytes | llvm-mos bytes |
|---|--:|--:|--:|--:|--:|
| `entities_update` | 4,701 | 1,250 | 3.8x faster | 211 | 81 |
| `clamp_add` | 321 | 103 | 3.1x faster | 80 | 61 |
| `grid_full_rows` | 16,654 | 2,682 | 6.2x faster | 76 | 46 |
| `hash_bytes` | 26,753 | 7,605 | 3.5x faster | 86 | 90 |
| `copy_rows` | 25,489 | 7,146 | 3.6x faster | 95 | 54 |

## C language features

Each program in [`features/`](features/) exits 0 on sim65 when its feature works.

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

## The code

cc65's is its assembly output; llvm-mos's is disassembled from the linked program, with the
compiler's imaginary registers (zero page `$E0-$FF`) named `__rc0`-`__rc31`.

### `entities_update`

```c
// Moves every live entity by its velocity, turning it around at the edges.
void entities_update(void) {
    uint8_t i;
    for (i = 0; i < ENTITY_COUNT; ++i) {
        Entity* entity = &entities[i];
        if (!entity->alive) {
            continue;
        }
        entity->x += entity->dx;
        entity->y += entity->dy;
        if (entity->x >= ENTITY_LIMIT) {
            entity->dx = -entity->dx;
        }
        if (entity->y >= ENTITY_LIMIT) {
            entity->dy = -entity->dy;
        }
    }
}
```

**cc65**: 211 bytes, 4,701 cycles. It calls cc65's runtime: `mulax5`, `ldaidx`.

```asm
        stz     M0001
L000D:  lda     M0001
        cmp     #$10
        bcc     L0011
        rts
L0011:  ldx     #$00
        lda     M0001
        jsr     mulax5
        clc
        adc     #<(_entities)
        tay
        txa
        adc     #>(_entities)
        tax
        tya
        sta     M0002
        stx     M0002+1
        sta     ptr1
        stx     ptr1+1
        ldy     #$04
        lda     (ptr1),y
        jeq     L0010
        lda     M0002
        ldx     M0002+1
        sta     ptr2
        stx     ptr2+1
        sta     ptr1
        stx     ptr1+1
        lda     (ptr1)
        sta     sreg
        lda     M0002
        ldx     M0002+1
        ldy     #$02
        jsr     ldaidx
        clc
        adc     sreg
        sta     (ptr2)
        lda     M0002
        ldx     M0002+1
        sta     ptr2
        stx     ptr2+1
        sta     ptr1
        stx     ptr1+1
        dey
        lda     (ptr1),y
        sta     sreg
        lda     M0002
        ldx     M0002+1
        ldy     #$03
        jsr     ldaidx
        clc
        adc     sreg
        ldy     #$01
        sta     (ptr2),y
        lda     M0002+1
        sta     ptr1+1
        lda     M0002
        sta     ptr1
        lda     (ptr1)
        cmp     #$78
        bcc     L0007
        lda     M0002+1
        sta     sreg+1
        lda     M0002
        sta     sreg
        ldx     M0002+1
        iny
        jsr     ldaidx
        eor     #$FF
        clc
        adc     #$01
        cmp     #$80
        sta     (sreg),y
L0007:  lda     M0002+1
        sta     ptr1+1
        lda     M0002
        sta     ptr1
        ldy     #$01
        lda     (ptr1),y
        cmp     #$78
        bcc     L0010
        lda     M0002+1
        sta     sreg+1
        lda     M0002
        sta     sreg
        ldx     M0002+1
        ldy     #$03
        jsr     ldaidx
        eor     #$FF
        clc
        adc     #$01
        cmp     #$80
        sta     (sreg),y
L0010:  inc     M0001
        jmp     L000D
```

**llvm-mos**: 81 bytes, 1,250 cycles.

```asm
        stz     __rc4
L095B:  ldx     __rc4
        lda     entities+4,x
        tax
        beq     L099E
        ldx     __rc4
        lda     entities+2,x
        sta     __rc3
        clc
        adc     entities,x
        sta     __rc5
        sta     entities,x
        lda     entities+3,x
        sta     __rc2
        clc
        adc     entities+1,x
        tay
        sta     entities+1,x
        ldx     __rc5
        cpx     #$78
        bcc     L0990
        sec
        lda     #$0
        sbc     __rc3
        ldx     __rc4
        sta     entities+2,x
L0990:  cpy     #$78
        bcc     L099E
        sec
        lda     #$0
        sbc     __rc2
        ldx     __rc4
        sta     entities+3,x
L099E:  clc
        lda     __rc4
        adc     #$5
        sta     __rc4
        cmp     #$50
        bne     L095B
        rts
```

### `clamp_add`

```c
// value + delta, kept within low-high: byte arguments, and arithmetic past a byte.
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

**cc65**: 80 bytes, 321 cycles. It calls cc65's runtime: `pusha`, `incsp4`, `pushax`, `tosicmp0`.

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

**llvm-mos**: 61 bytes, 103 cycles.

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

### `grid_full_rows`

```c
// How many rows of the grid have no empty (0) cell: a falling-block game's line check.
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

**cc65**: 76 bytes, 16,654 cycles. It calls cc65's runtime: `mulax10`.

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

**llvm-mos**: 46 bytes, 2,682 cycles.

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

### `hash_bytes`

```c
// A 16-bit hash of length bytes (djb2: hash * 33 + byte): 16-bit arithmetic, and multiplying
// by a constant.
uint16_t hash_bytes(const uint8_t* data, uint8_t length) {
    uint16_t hash = 5381;
    uint8_t i;
    for (i = 0; i < length; ++i) {
        hash = hash * 33 + data[i];
    }
    return hash;
}
```

**cc65**: 86 bytes, 26,753 cycles. It calls cc65's runtime: `pusha`, `pushax`, `tosumula0`, `incsp3`.

```asm
        jsr     pusha
        ldx     #$15
        lda     #$05
        sta     M0001
        stx     M0001+1
        stz     M0002
L0008:  lda     M0002
        cmp     (c_sp)
        bcs     L0003
        lda     M0001
        ldx     M0001+1
        jsr     pushax
        lda     #$21
        jsr     tosumula0
        sta     sreg
        stx     sreg+1
        ldy     #$02
        lda     (c_sp),y
        tax
        dey
        lda     (c_sp),y
        ldy     M0002
        sta     ptr1
        stx     ptr1+1
        lda     (ptr1),y
        clc
        adc     sreg
        ldx     sreg+1
        bcc     L0007
        inx
L0007:  sta     M0001
        stx     M0001+1
        inc     M0002
        bra     L0008
L0003:  lda     M0001
        ldx     M0001+1
        jmp     incsp3
```

**llvm-mos**: 90 bytes, 7,605 cycles.

```asm
        ldx     #$15
        tay
        bne     L0A1D
        jmp     L0A6C
L0A1D:  sta     __rc7
        lda     #$5
        stz     __rc8
        sta     __rc4
        stx     __rc5
L0A27:  ldx     __rc5
        stx     __rc6
        lsr     __rc6
        lda     __rc4
        ror
        tax
        lda     #$0
        ror
        lsr     __rc6
        stx     __rc9
        ror     __rc9
        ror
        lsr     __rc6
        ldx     __rc9
        stx     __rc6
        ror     __rc6
        ror
        clc
        adc     __rc4
        tax
        lda     __rc6
        adc     __rc5
        sta     __rc4
        clc
        ldy     __rc8
        txa
        adc     (__rc2),y
        tax
        lda     __rc4
        adc     #$0
        sta     __rc5
        txa
        iny
        sty     __rc6
        sty     __rc8
        stx     __rc4
        ldx     __rc5
        ldy     __rc7
        cpy     __rc6
        bne     L0A27
        rts
L0A6C:  lda     #$5
        rts
```

### `copy_rows`

```c
// Copies a width x height block of a sheet source_width wide into rows ROW_STRIDE apart: how a
// sprite sheet gets into graphics RAM.
void copy_rows(uint8_t* destination, const uint8_t* source, uint8_t width, uint8_t height,
    uint8_t source_width) {
    uint8_t x;
    for (; height != 0; --height) {
        for (x = 0; x < width; ++x) {
            destination[x] = source[x];
        }
        destination += ROW_STRIDE;
        source += source_width;
    }
}
```

**cc65**: 95 bytes, 25,489 cycles. It calls cc65's runtime: `pusha`, `addeqysp`, `incsp7`.

```asm
        jsr     pusha
        ldy     #$01
L000D:  lda     (c_sp),y
        beq     L0003
        stz     M0001
L000E:  lda     M0001
        ldy     #$02
        cmp     (c_sp),y
        bcs     L0007
        ldy     #$06
        lda     (c_sp),y
        tax
        dey
        lda     (c_sp),y
        clc
        adc     M0001
        bcc     L000A
        inx
L000A:  sta     sreg
        stx     sreg+1
        dey
        lda     (c_sp),y
        tax
        dey
        lda     (c_sp),y
        ldy     M0001
        sta     ptr1
        stx     ptr1+1
        lda     (ptr1),y
        sta     (sreg)
        inc     M0001
        bra     L000E
L0007:  ldy     #$05
        ldx     #$00
        lda     #$80
        jsr     addeqysp
        ldx     #$00
        lda     (c_sp)
        ldy     #$03
        jsr     addeqysp
        ldy     #$01
        lda     (c_sp),y
        sec
        sbc     #$01
        sta     (c_sp),y
        bra     L000D
L0003:  jmp     incsp7
```

**llvm-mos**: 54 bytes, 7,146 cycles.

```asm
        cpx     #$0
        beq     L0AA4
        sta     __rc8
        tay
        beq     L0AA4
L0A78:  ldy     #$0
L0A7A:  lda     (__rc4),y
        sta     (__rc2),y
        lda     __rc8
        iny
        sty     __rc7
        cmp     __rc7
        bne     L0A7A
        lda     __rc2
        clc
        adc     #$80
        sta     __rc2
        lda     __rc3
        adc     #$0
        sta     __rc3
        lda     __rc4
        clc
        adc     __rc6
        sta     __rc4
        lda     __rc5
        adc     #$0
        sta     __rc5
        dex
        bne     L0A78
L0AA4:  rts
```
