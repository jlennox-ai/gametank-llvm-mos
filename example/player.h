// The player (player.c): moved with pad 1's d-pad, above the floor, and drawn as the player tile.
#ifndef PLAYER_H
#define PLAYER_H

#include <stdint.h>
#include "gametank.h"
#include "tiles.h"

// The top of the floor: a row of tiles along the bottom of the screen, which main.c draws.
#define FLOOR_Y (GT_SCREEN_SIZE - TILES_TILE_HEIGHT)

typedef struct {
    uint8_t x;
    uint8_t y;
    uint8_t palette; // TILES_PALETTE_*
} Player;

// A player in the middle of the screen, in green.
Player player_create(void);

// Moves the player by the d-pad buttons held (gt_read_pad1()), and changes its palette for A, B
// and C.
void player_update(Player* player, uint8_t buttons);

// Starts the blit that draws the player.
void player_draw(const Player* player);

#endif
