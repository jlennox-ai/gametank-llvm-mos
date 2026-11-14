// The example program: a player (player.c) moved around the screen with pad 1's d-pad, above a
// brick floor. A, B and C change the player's palette. Its tiles are assets/tiles.png, converted by
// gametank_add_tiles (CMakeLists.txt) into tiles.h and tiles.c.
#include <stdint.h>
#include "gametank.h"
#include "tiles.h"
#include "player.h"

#define BACKGROUND_COLOR GT_COLOR(5, 1, 1)

static void floor_draw(void) {
    for (uint8_t x = 0; x < GT_SCREEN_SIZE; x += TILES_TILE_WIDTH) {
        gt_sprite_draw(x, FLOOR_Y, TILES_X(TILES_BRICK), TILES_Y(TILES_PALETTE_RED), TILES_TILE_WIDTH,
            TILES_TILE_HEIGHT);
    }
}

int main(void) {
    // Into graphics RAM once, where every gt_sprite_draw copies from.
    gt_sprite_sheet_load(tiles_sheet, TILES_SHEET_WIDTH, TILES_SHEET_HEIGHT, 0, 0);

    Player player = player_create();
    for (;;) {
        player_update(&player, gt_read_pad1());

        gt_clear_screen(BACKGROUND_COLOR);
        floor_draw();
        player_draw(&player);
        gt_show_frame();
    }
}
