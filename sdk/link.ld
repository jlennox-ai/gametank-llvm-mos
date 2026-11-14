/* lld linker script for llvm-mos C programs on a GameTank 2 MB flash cartridge. The output
 * (-o) is the whole cartridge image (.gtr); lld writes the ELF next to it (.gtr.elf).
 *
 *   banks 0-125   free for data (written as zeros)
 *   bank 126      $8000-$BFFF, mapped into the ROM window by crt0.S and left there
 *   bank 127      $C000-$FFFF, always mapped (the reset code and vectors live at its end)
 *
 * So the program sees 32 KB of contiguous ROM at $8000-$FFFF. Bank 126 must stay mapped
 * while any C code runs, since code and data from it are spread over both banks.
 *
 * RAM is $0000-$1FFF: zero page (the compiler's imaginary registers at $E0-$FF, the rest for
 * variables, given out by -mlto-zp, gametank_add_rom's ZERO_PAGE), the 6502 stack at $0100,
 * then DATA, BSS and NOINIT from $0200 up and the C stack down from $2000.
 *
 * A project can use its own linker script instead: gametank_add_rom's LINKER_SCRIPT. */

/* The program's banks, the only place they're set: crt0.S maps __gt_program_bank at $8000, and
 * tools/debug_files.py reads both for the emulator's source map. They're the image's last 32 KB,
 * so they're consecutive, and the hardware always maps the last bank at $C000. */
__gt_program_bank = 126;
__gt_fixed_bank = 127;
ASSERT(__gt_fixed_bank == __gt_program_bank + 1, "The program's two banks must be consecutive.")

/* Imaginary (zero page) registers. */
__rc0 = 0xe0;
INCLUDE imag-regs.ld
ASSERT(__rc31 == 0xff, "Inconsistent zero page map.")

__stack = 0x2000;
__stack_size = 0x400;

MEMORY {
  zp : ORIGIN = 0x00, LENGTH = __rc0
  ram : ORIGIN = 0x200, LENGTH = __stack - __stack_size - 0x200
  /* Not in the CPU's address space: just the image's banks before the program's. */
  free_banks : ORIGIN = 0x1000000, LENGTH = __gt_program_bank * 0x4000
  rom : ORIGIN = 0x8000, LENGTH = 0x7f00
  boot : ORIGIN = 0xff00, LENGTH = 0xfa
}

REGION_ALIAS("c_readonly", rom)
REGION_ALIAS("c_writeable", ram)

SECTIONS {
  INCLUDE c.ld

  /* crt0.S: reset and the interrupt handlers. Nothing calls them, so KEEP them. */
  .boot : { KEEP(*(.boot .boot.*)) } >boot
}

OUTPUT_FORMAT {
  FULL(free_banks)
  FULL(rom)
  FULL(boot)
  SHORT(gt_nmi)
  SHORT(gt_reset)
  SHORT(gt_irq)
}
