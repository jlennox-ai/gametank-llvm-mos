; GameTank hardware helpers for llvm-mos C programs (declared in gametank.h).
;
; Drawing is double buffered: one framebuffer is shown while the blitter draws into the
; other, and gt_show_frame swaps them at vsync.
;
; llvm-mos passes byte arguments in A, X, then __rc2, __rc3, ... and returns a byte in A.
; A, X, Y and __rc2-__rc19 are the caller's to save; __rc20-__rc31 must be preserved.

.include "gametank.inc"

    .zeropage __rc2, __rc3, __rc4
    .zeropage gt_frame_count, gt_nmi_wake

    .section .zp.bss,"aw",@nobits
    .globl gt_late_frames
    ; Also used by sprites.c, which starts blits of its own.
    .globl dma_mirror, blit_pending
    .zeropage dma_mirror, bank_mirror, blit_pending, shown_frame, gt_late_frames
dma_mirror:         .zero 1     ; DMA_FLAGS and BANK_FLAGS are write-only
bank_mirror:        .zero 1
blit_pending:       .zero 1     ; a blit has started since the last wait for one
shown_frame:        .zero 1     ; gt_frame_count when the last frame was shown
gt_late_frames:     .zero 1     ; frames that took longer than a vsync to draw

; Runs once from _start, after BSS is zeroed and before main() (see crt0.s): shows
; framebuffer 0, draws into framebuffer 1, and turns on the vsync NMI. Finishes at a vsync,
; so main()'s first frame gets a whole frame's time. .init sections run straight into each
; other, so this ends without an RTS.
    .section .init.300,"ax",@progbits
gt_init:
    lda #(BANK_CLIP_X | BANK_CLIP_Y | BANK_VRAM_PAGE)
    sta bank_mirror
    sta BANK_FLAGS
    lda #(DMA_ENABLE | DMA_NMI | DMA_IRQ)
    sta dma_mirror
    sta DMA_FLAGS
    lda gt_frame_count
1:  cmp gt_frame_count
    beq 1b
    lda gt_frame_count
    sta shown_frame

; void gt_wait_blit(void)
; Sleeps until the blit in progress (if any) is done; a vsync NMI also wakes WAI, so it goes
; back to sleep after one. The blitter's IRQ stays raised until the next blit starts, so
; waiting again before then returns at once. Preserves X and Y.
    .section .text.gt_wait_blit,"ax",@progbits
    .globl gt_wait_blit
gt_wait_blit:
    lda blit_pending
    beq 2f
1:  stz gt_nmi_wake
    wai
    lda gt_nmi_wake
    bne 1b
    stz blit_pending
2:  rts

; Starts the blit whose parameters are already written.
    .section .text.start_blit,"ax",@progbits
start_blit:
    lda #1
    sta DMA_START
    sta blit_pending
    rts

; void gt_show_frame(void)
; Waits for this frame's blits and the next vsync, then shows the framebuffer they drew and
; points the blitter at the other. If a vsync has already passed since the last frame was
; shown (this one took too long), it doesn't wait for another, and counts a late frame.
    .section .text.gt_show_frame,"ax",@progbits
    .globl gt_show_frame
gt_show_frame:
    jsr gt_wait_blit
    lda shown_frame
    cmp gt_frame_count
    beq 1f
    inc gt_late_frames
1:  cmp gt_frame_count
    beq 1b
    lda gt_frame_count
    sta shown_frame

    lda dma_mirror
    eor #DMA_PAGE_OUT
    sta dma_mirror
    sta DMA_FLAGS
    lda bank_mirror
    eor #BANK_VRAM_PAGE
    sta bank_mirror
    sta BANK_FLAGS
    rts

; void gt_fill_rect(unsigned char x, unsigned char y, unsigned char width,
;                   unsigned char height, unsigned char color)
; x in A, y in X, width in __rc2, height in __rc3, color in __rc4.
; Starts a blit filling the rectangle with color (opaque, so colour 0 is black rather than
; transparent). Anything past the right or bottom edge is clipped. Width and height must be
; 1-127: the blitter takes bit 7 as a flip.
    .section .text.gt_fill_rect,"ax",@progbits
    .globl gt_fill_rect
gt_fill_rect:
    tay
    jsr gt_wait_blit
    sty DMA_VX
    stx DMA_VY
    lda __rc2
    jsr check_blit_size
    sta DMA_WIDTH
    lda __rc3
    jsr check_blit_size
    sta DMA_HEIGHT
    lda __rc4
    eor #0xff                   ; DMA_COLOR takes the colour inverted
    sta DMA_COLOR
    lda dma_mirror
    ora #(DMA_COLORFILL | DMA_OPAQUE)
    sta DMA_FLAGS
    jmp start_blit

; Halts unless A is a valid blit width or height (1-127).
    .section .text.check_blit_size,"ax",@progbits
check_blit_size:
    cmp #0
    beq 1f
    cmp #0x80
    bcs 1f
    rts
1:  stp

; unsigned char gt_read_pad1(void)
; Returns the buttons held on pad 1 (GT_BUTTON_* bits).
    .section .text.gt_read_pad1,"ax",@progbits
    .globl gt_read_pad1
gt_read_pad1:
    lda GAMEPAD2                ; resets pad 1's select line
    lda GAMEPAD1                ; first read: up, down, A, start (active low)
    eor #0xff
    and #0b00110000
    asl
    asl
    sta __rc2
    lda GAMEPAD1                ; second read: up, down, left, right, B, C
    eor #0xff
    and #0b00111111
    ora __rc2
    rts

; void gt_panic(void)
; Halts the CPU: the emulator stops where a debugger can see it.
    .section .text.gt_panic,"ax",@progbits
    .globl gt_panic
gt_panic:
    stp
