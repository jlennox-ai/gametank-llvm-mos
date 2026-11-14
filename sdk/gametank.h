// GameTank hardware support for llvm-mos C programs. crt0.s starts the program, gametank.s,
// gametank.c and sprites.c implement these, and link.ld lays out the cartridge.
#ifndef GAMETANK_H
#define GAMETANK_H

#define GT_SCREEN_SIZE 128

// A colour byte: hue 0-7, saturation 0-3, luminance 0-7.
#define GT_COLOR(hue, saturation, luminance) \
    ((unsigned char)(((hue) << 5) | ((saturation) << 3) | (luminance)))
#define GT_COLOR_BLACK 0x00
#define GT_COLOR_WHITE 0x07

// gt_read_pad1() bits.
#define GT_BUTTON_RIGHT 0x01
#define GT_BUTTON_LEFT  0x02
#define GT_BUTTON_DOWN  0x04
#define GT_BUTTON_UP    0x08
#define GT_BUTTON_B     0x10
#define GT_BUTTON_C     0x20
#define GT_BUTTON_A     0x40
#define GT_BUTTON_START 0x80

// Put before a function to see all its variables in the emulator's source view, everywhere in
// it: in the debug build (build.py <project> debug), the function is compiled without
// optimization, so every variable keeps a place in memory for its whole scope (optimized code
// drops values it no longer needs, which shows as "optimized out"). Elsewhere it does nothing.
//   GT_DEBUG_FUNCTION static void player_update(void) {
#ifdef GT_DEBUG_BUILD
#define GT_DEBUG_FUNCTION __attribute__((optnone, noinline))
#else
#define GT_DEBUG_FUNCTION
#endif

// Counts vsyncs (60 a second), wrapping at 256.
extern volatile unsigned char gt_frame_count;

// Frames that took longer than a vsync to draw, wrapping at 256.
extern unsigned char gt_late_frames;

// Halts the CPU: the emulator stops where a debugger can see it.
__attribute__((noreturn)) void gt_panic(void);

#define GT_ASSERT(condition) do { if (!(condition)) { gt_panic(); } } while (0)

// Returns the buttons held on pad 1 (GT_BUTTON_* bits).
unsigned char gt_read_pad1(void);

// Starts a blit filling a rectangle of the framebuffer being drawn. Anything past the right
// or bottom edge is clipped. Width and height must be 1-127.
void gt_fill_rect(unsigned char x, unsigned char y, unsigned char width,
    unsigned char height, unsigned char color);

// Fills the whole framebuffer being drawn.
void gt_clear_screen(unsigned char color);

// Waits for the blit in progress, if any.
void gt_wait_blit(void);

// Waits for this frame's blits and the next vsync, then shows what was drawn and starts
// drawing into the other framebuffer. Call it once at the end of every frame.
void gt_show_frame(void);

// Sprites (sprites.c), drawn from graphics RAM: 256x256 pixels, as four 128x128 quadrants.
// Graphics RAM page 0 only: gt_init leaves it selected.

// Copies a sheet of colour bytes, width x height a row at a time (like tools/tile_palettes's
// output), into graphics RAM with its top left corner at gram_x, gram_y. It must fit in the
// 256x256 page; it can span quadrants. It waits for the blit in progress, and takes a while
// (about 15 cycles a byte), so load sheets at startup.
//   gt_sprite_sheet_load(tiles_sheet, TILES_SHEET_WIDTH, TILES_SHEET_HEIGHT, 0, 0);
void gt_sprite_sheet_load(const unsigned char* sheet, unsigned char width, unsigned char height,
    unsigned char gram_x, unsigned char gram_y);

// Starts a blit of the width x height pixels at gram_x, gram_y in graphics RAM to x, y in the
// framebuffer being drawn. Colour 0 is transparent. Anything past the right or bottom edge is
// clipped. Width and height must be 1-127.
//   gt_sprite_draw(x, y, TILES_X(TILES_SOLID), TILES_Y(TILES_PALETTE_RED), TILES_TILE_WIDTH,
//       TILES_TILE_HEIGHT);
void gt_sprite_draw(unsigned char x, unsigned char y, unsigned char gram_x, unsigned char gram_y,
    unsigned char width, unsigned char height);

#endif
