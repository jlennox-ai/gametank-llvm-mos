; Startup code for llvm-mos C programs on the GameTank (link.ld has the memory layout).
;
; gt_reset brings the hardware to a known state, clears RAM (it powers up random), maps the
; program's lower bank into the ROM window and jumps to llvm-mos's _start. That runs the
; .init sections in order: the C stack (.init.100), copying initialised data and zeroing BSS
; (.init.200), gt_init in gametank.s (.init.300), then main(). Interrupts stay masked for
; good: the vsync NMI is always taken, and the blitter's IRQ only wakes WAI (see
; gt_wait_blit in gametank.s).
;
; Everything run before _start is in .boot, at the top of the always-mapped bank 127: it runs
; before bank 126 is mapped, and the interrupt handlers must not depend on it.

.include "gametank.inc"

PROGRAM_BANK = 126              ; the cartridge bank link.ld puts at $8000-$BFFF
RAM_END_PAGE = 0x20             ; RAM is $0000-$1FFF

    .zeropage __rc2, __rc3, __rc4

    .section .zp.bss,"aw",@nobits
    .globl gt_frame_count
    .globl gt_nmi_wake
    .zeropage gt_frame_count, gt_nmi_wake
gt_frame_count:     .zero 1     ; counts vsyncs
gt_nmi_wake:        .zero 1     ; set by the NMI, so a WAI can tell an NMI wake from a blit's

    .section .boot,"ax",@progbits

    .globl gt_reset
gt_reset:
    sei
    cld
    ldx #0xff
    txs
    ; Both control registers power up random: set them before touching RAM.
    stz DMA_FLAGS
    lda #(BANK_CLIP_X | BANK_CLIP_Y) ; RAM bank 0
    sta BANK_FLAGS

    ; Clear all of RAM, the 6502 stack included (so no JSR until it's done).
    ldx #0
1:  stz 0, x
    inx
    bne 1b
    lda #0x01
    sta __rc3                   ; __rc2/__rc3 point at each page in turn: __rc2 is already 0
    ldy #0
2:  lda #0
    sta (__rc2), y
    iny
    bne 2b
    inc __rc3
    lda __rc3
    cmp #RAM_END_PAGE
    bne 2b
    stz __rc3

    lda #VIA_SPI_OUTPUTS
    sta VIA_DDRA
    stz VIA_ORA
    lda #PROGRAM_BANK
    jsr set_rom_bank
    jmp _start

; Maps cartridge bank A (0-127) at ROM_WINDOW by clocking it into the cartridge's shift
; register through the VIA, most significant bit first.
set_rom_bank:
    ora #0x80                   ; high bit selects flash rather than save RAM
    sta __rc4
    ldy #8
1:  lda #0
    asl __rc4
    rol                         ; A = next bit
    asl                         ; onto the MOSI line, clock low
    sta VIA_ORA
    ora #VIA_SPI_CLOCK          ; rising clock shifts the bit in
    sta VIA_ORA
    dey
    bne 1b
    lda #VIA_SPI_SELECT         ; rising select latches the new bank
    sta VIA_ORA
    rts

    .globl gt_nmi
gt_nmi:
    pha
    inc gt_frame_count
    lda #1
    sta gt_nmi_wake
    pla
    rti

; Interrupts are never unmasked, so this only runs on a BRK: the program has crashed.
    .globl gt_irq
gt_irq:
    stp

; main() returning, or exit(), is a bug in a game: halt where a debugger can see it. crt0.o
; (from llvm-mos) falls through into .after_main once main() returns.
    .section .after_main,"ax",@progbits
    .globl __after_main
__after_main:
    stp

    .section .text._Exit,"ax",@progbits
    .globl _Exit
_Exit:
    stp
