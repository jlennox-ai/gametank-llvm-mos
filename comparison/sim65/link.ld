/* lld linker script for llvm-mos programs run by sim65, cc65's 6502 simulator, as a 65C02:
 * compare.py uses it to time llvm-mos's code on the same simulator as cc65's. sim65.s has the
 * rest of the support.
 *
 * Zero page matches the GameTank's (sdk/link.ld): the compiler's imaginary registers at $E0-$FF,
 * the rest for variables. The program loads at $0200, and the C stack grows down from sim65's
 * peripherals at $FFC0.
 *
 * The output is a sim65 program: its header, then the memory image from $0200. */

/* Imaginary (zero page) registers. */
__rc0 = 0xe0;
INCLUDE imag-regs.ld
ASSERT(__rc31 == 0xff, "Inconsistent zero page map.")

__stack = 0xffc0;
__stack_size = 0x400;

MEMORY {
  zp : ORIGIN = 0x00, LENGTH = __rc0
  ram : ORIGIN = 0x200, LENGTH = __stack - __stack_size - 0x200
}

REGION_ALIAS("c_readonly", ram)
REGION_ALIAS("c_writeable", ram)

SECTIONS { INCLUDE c.ld }

OUTPUT_FORMAT {
  BYTE(0x73) BYTE(0x69) BYTE(0x6d) BYTE(0x36) BYTE(0x35) /* "sim65" */
  BYTE(2)               /* header version */
  BYTE(1)               /* CPU: 65C02 */
  BYTE(pv_stack)        /* the zero page pointer sim65's calls take arguments through */
  SHORT(ORIGIN(ram))    /* load address */
  SHORT(_start)         /* start address: the .init sections, then main() */
  TRIM(ram)
}
