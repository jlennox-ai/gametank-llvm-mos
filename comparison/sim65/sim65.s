; sim65 support for llvm-mos programs (link.ld has the memory layout): the reset state, printing
; (llvm-mos's printf and putchar print through __putchar) and exit.
;
; sim65 provides write() and exit() as calls: a JSR or JMP to their address runs them and then
; returns as an RTS would. They take their arguments as cc65's runtime passes them: the last in
; A and X, the others on cc65's parameter stack, which the zero page pointer named in the
; program's header (pv_stack) points at, first argument highest.

PV_WRITE = 0xfff7
PV_EXIT = 0xfff9
STDOUT = 1

    .section .zp.bss,"aw",@nobits
    .globl pv_stack
    .zeropage pv_stack
pv_stack:           .zero 2

    .section .bss.pv_arguments,"aw",@nobits
; write()'s first two arguments, as cc65's parameter stack holds them: the buffer, then the file.
pv_write_buffer:    .zero 2
pv_write_file:      .zero 2
character:          .zero 1

; Runs first from _start, before llvm-mos's .init sections (the C stack is .init.100).
; .init sections run straight into each other, so this ends without an RTS.
    .section .init.50,"ax",@progbits
    cld
    ldx #0xff
    txs

; void __putchar(char c)
; Writes c to standard output.
    .section .text.__putchar,"ax",@progbits
    .globl __putchar
__putchar:
    sta character
    lda #<character
    sta pv_write_buffer
    lda #>character
    sta pv_write_buffer + 1
    lda #STDOUT
    sta pv_write_file
    stz pv_write_file + 1
    lda #<pv_write_buffer
    sta pv_stack
    lda #>pv_write_buffer
    sta pv_stack + 1
    lda #1                      ; count
    ldx #0
    jmp PV_WRITE                ; returns to __putchar's caller

; void _Exit(int status)
; Ends the simulation, with the status's low byte as sim65's exit code. exit() (after main()
; returns, too) ends here, once it has run the atexit handlers.
    .section .text._Exit,"ax",@progbits
    .globl _Exit
_Exit:
    jmp PV_EXIT
