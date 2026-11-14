// The example program: a block moved around the screen with pad 1's d-pad. A, B and C change
// its colour. Replace src/ with your game: every .c and .s in src/ is built.
#include <stdint.h>
#include "gametank.h"

#define BACKGROUND_COLOR GT_COLOR(5, 1, 1)
#define BLOCK_SIZE 12
#define BLOCK_MAX (GT_SCREEN_SIZE - BLOCK_SIZE)

typedef struct {
    uint8_t x;
    uint8_t y;
    uint8_t color;
} Block;

static void block_update(Block* block, uint8_t buttons) {
    if ((buttons & GT_BUTTON_LEFT) && (block->x > 0)) { --block->x; }
    if ((buttons & GT_BUTTON_RIGHT) && (block->x < BLOCK_MAX)) { ++block->x; }
    if ((buttons & GT_BUTTON_UP) && (block->y > 0)) { --block->y; }
    if ((buttons & GT_BUTTON_DOWN) && (block->y < BLOCK_MAX)) { ++block->y; }

    if (buttons & GT_BUTTON_A) { block->color = GT_COLOR(2, 3, 4); }
    if (buttons & GT_BUTTON_B) { block->color = GT_COLOR(7, 3, 4); }
    if (buttons & GT_BUTTON_C) { block->color = GT_COLOR(0, 3, 5); }
}

int main(void) {
    Block block = {
        .x = BLOCK_MAX / 2,
        .y = BLOCK_MAX / 2,
        .color = GT_COLOR_WHITE,
    };
    for (;;) {
        block_update(&block, gt_read_pad1());
        gt_clear_screen(BACKGROUND_COLOR);
        gt_fill_rect(block.x, block.y, BLOCK_SIZE, BLOCK_SIZE, block.color);
        gt_show_frame();
    }
}
