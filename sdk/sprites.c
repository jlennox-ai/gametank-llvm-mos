// Sprites: colour data loaded into graphics RAM, and blits from there to the screen (declared in
// gametank.h). Graphics RAM page 0 only: gt_init leaves it selected.
#include <stdint.h>
#include "gametank.h"

#define DMA_FLAGS   (*(volatile uint8_t*)0x2007)
// The blitter's parameters, while DMA_FLAGS has DMA_ENABLE set.
#define DMA_VX      (*(volatile uint8_t*)0x4000)
#define DMA_VY      (*(volatile uint8_t*)0x4001)
#define DMA_GX      (*(volatile uint8_t*)0x4002)
#define DMA_GY      (*(volatile uint8_t*)0x4003)
#define DMA_WIDTH   (*(volatile uint8_t*)0x4004)
#define DMA_HEIGHT  (*(volatile uint8_t*)0x4005)
#define DMA_START   (*(volatile uint8_t*)0x4006)
// With DMA_ENABLE and DMA_CPU_TO_VRAM clear, $4000-$7FFF is a 128x128 quadrant of graphics RAM.
#define GRAM_WINDOW ((volatile uint8_t*)0x4000)

#define DMA_ENABLE      0x01
#define DMA_GCARRY      0x10 // source coordinates carry across 16-pixel tiles
#define DMA_CPU_TO_VRAM 0x20

#define GRAM_PAGE_SIZE 256
#define QUADRANT_SIZE 128
#define QUADRANT_BIT  0x80 // in a graphics RAM coordinate
#define QUADRANT_MASK 0x7F
#define BLIT_MAX_SIZE 127
// Past the screen's right and bottom edges, where gt_init's clipping stops a blit drawing.
#define OFFSCREEN 0x80

// gametank.S's state: DMA_FLAGS's value between blits (the register is write-only), and whether
// a blit has started since gt_wait_blit last waited.
extern uint8_t gt_dma_mirror;
extern uint8_t gt_blit_pending;

static void start_blit(void) {
    DMA_START = 1;
    gt_blit_pending = 1;
}

// The CPU's window shows the quadrant the last blit read from, so a one-pixel blit from the
// quadrant, drawn off screen, selects it.
static void select_cpu_quadrant(uint8_t gram_x, uint8_t gram_y) {
    gt_wait_blit();
    DMA_FLAGS = gt_dma_mirror;
    DMA_VX = OFFSCREEN;
    DMA_VY = OFFSCREEN;
    DMA_GX = gram_x & QUADRANT_BIT;
    DMA_GY = gram_y & QUADRANT_BIT;
    DMA_WIDTH = 1;
    DMA_HEIGHT = 1;
    start_blit();
    gt_wait_blit();
}

// Copies width x height bytes of a sheet sheet_width wide into graphics RAM, all within the
// quadrant gram_x, gram_y is in.
static void load_within_quadrant(const uint8_t* sheet, uint8_t sheet_width, uint8_t width, uint8_t height,
    uint8_t gram_x, uint8_t gram_y) {
    select_cpu_quadrant(gram_x, gram_y);
    DMA_FLAGS = gt_dma_mirror & ~(DMA_ENABLE | DMA_CPU_TO_VRAM);
    volatile uint8_t* row = GRAM_WINDOW + (uint16_t)(gram_y & QUADRANT_MASK) * QUADRANT_SIZE + (gram_x & QUADRANT_MASK);
    for (uint8_t y = 0; y < height; ++y) {
        for (uint8_t x = 0; x < width; ++x) {
            row[x] = sheet[x];
        }
        sheet += sheet_width;
        row += QUADRANT_SIZE;
    }
    DMA_FLAGS = gt_dma_mirror;
}

// The CPU sees one quadrant at a time, so a sheet crossing a quadrant's edge is copied a quadrant
// at a time: it can cross at most one edge each way.
void gt_sprite_sheet_load(const uint8_t* sheet, uint8_t width, uint8_t height, uint8_t gram_x, uint8_t gram_y) {
    GT_ASSERT((width > 0) && (height > 0));
    GT_ASSERT(gram_x + width <= GRAM_PAGE_SIZE);
    GT_ASSERT(gram_y + height <= GRAM_PAGE_SIZE);

    uint8_t left_width = width;
    if ((gram_x & QUADRANT_MASK) + width > QUADRANT_SIZE) {
        left_width = QUADRANT_SIZE - (gram_x & QUADRANT_MASK);
    }
    uint8_t top_height = height;
    if ((gram_y & QUADRANT_MASK) + height > QUADRANT_SIZE) {
        top_height = QUADRANT_SIZE - (gram_y & QUADRANT_MASK);
    }
    uint8_t right_width = width - left_width;
    uint8_t bottom_height = height - top_height;

    load_within_quadrant(sheet, width, left_width, top_height, gram_x, gram_y);
    if (right_width > 0) {
        load_within_quadrant(sheet + left_width, width, right_width, top_height, gram_x + left_width, gram_y);
    }
    if (bottom_height > 0) {
        const uint8_t* lower = sheet + (uint16_t)top_height * width;
        load_within_quadrant(lower, width, left_width, bottom_height, gram_x, gram_y + top_height);
        if (right_width > 0) {
            load_within_quadrant(lower + left_width, width, right_width, bottom_height, gram_x + left_width,
                gram_y + top_height);
        }
    }
}

void gt_sprite_draw(uint8_t x, uint8_t y, uint8_t gram_x, uint8_t gram_y, uint8_t width, uint8_t height) {
    GT_ASSERT((width > 0) && (width <= BLIT_MAX_SIZE));
    GT_ASSERT((height > 0) && (height <= BLIT_MAX_SIZE));

    gt_wait_blit();
    // Not DMA_OPAQUE: colour 0 is transparent.
    DMA_FLAGS = gt_dma_mirror | DMA_GCARRY;
    DMA_VX = x;
    DMA_VY = y;
    DMA_GX = gram_x;
    DMA_GY = gram_y;
    DMA_WIDTH = width;
    DMA_HEIGHT = height;
    start_blit();
}
