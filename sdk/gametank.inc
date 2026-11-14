; GameTank hardware registers and flags (llvm-mos assembler syntax).

BANK_FLAGS      = 0x2005    ; write-only
DMA_FLAGS       = 0x2007    ; write-only
GAMEPAD1        = 0x2008
GAMEPAD2        = 0x2009

VIA             = 0x2800
VIA_ORA         = VIA + 0x1
VIA_DDRA        = VIA + 0x3

; Blitter parameter registers (when DMA_FLAGS has DMA_ENABLE set)
DMA_VX          = 0x4000
DMA_VY          = 0x4001
DMA_GX          = 0x4002
DMA_GY          = 0x4003
DMA_WIDTH       = 0x4004    ; bit 7 = horizontal flip
DMA_HEIGHT      = 0x4005    ; bit 7 = vertical flip
DMA_START       = 0x4006    ; write 1 to start a blit (also acknowledges the blit IRQ)
DMA_COLOR       = 0x4007

; With DMA_ENABLE clear, $4000-$7FFF maps straight to a 128x128 buffer.
GRAM_WINDOW     = 0x4000

; DMA_FLAGS bits
DMA_ENABLE      = 0b00000001 ; blitter owns $4000-$7FFF
DMA_PAGE_OUT    = 0b00000010 ; framebuffer shown on screen
DMA_NMI         = 0b00000100 ; NMI on vsync
DMA_COLORFILL   = 0b00001000
DMA_GCARRY      = 0b00010000 ; source coordinates carry across 16px tiles
DMA_CPU_TO_VRAM = 0b00100000 ; CPU window targets the framebuffer instead of GRAM
DMA_IRQ         = 0b01000000 ; IRQ when a blit finishes
DMA_OPAQUE      = 0b10000000 ; also copy color 0

; BANK_FLAGS bits
BANK_GRAM_MASK  = 0b00000111
BANK_VRAM_PAGE  = 0b00001000 ; framebuffer the blitter draws into
BANK_CLIP_X     = 0b00010000
BANK_CLIP_Y     = 0b00100000
BANK_RAM_MASK   = 0b11000000 ; 8 KB RAM bank at $0000-$1FFF (crt0.S selects bank 0)

; VIA port A bits that drive the 2 MB cartridge's bank shift register
VIA_SPI_CLOCK   = 0b00000001
VIA_SPI_MOSI    = 0b00000010
VIA_SPI_SELECT  = 0b00000100
VIA_SPI_OUTPUTS = VIA_SPI_CLOCK | VIA_SPI_MOSI | VIA_SPI_SELECT

ROM_WINDOW      = 0x8000    ; movable 16 KB ROM bank
