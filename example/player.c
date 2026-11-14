// The player (declared in player.h).
#include "player.h"

#define PLAYER_MAX_X (GT_SCREEN_SIZE - TILES_TILE_WIDTH)
#define PLAYER_MAX_Y (FLOOR_Y - TILES_TILE_HEIGHT)

Player player_create(void) {
    return (Player){
        .x = PLAYER_MAX_X / 2,
        .y = PLAYER_MAX_Y / 2,
        .palette = TILES_PALETTE_GREEN,
    };
}

void player_update(Player* player, uint8_t buttons) {
    if ((buttons & GT_BUTTON_LEFT) && (player->x > 0)) { --player->x; }
    if ((buttons & GT_BUTTON_RIGHT) && (player->x < PLAYER_MAX_X)) { ++player->x; }
    if ((buttons & GT_BUTTON_UP) && (player->y > 0)) { --player->y; }
    if ((buttons & GT_BUTTON_DOWN) && (player->y < PLAYER_MAX_Y)) { ++player->y; }

    if (buttons & GT_BUTTON_A) { player->palette = TILES_PALETTE_RED; }
    if (buttons & GT_BUTTON_B) { player->palette = TILES_PALETTE_BLUE; }
    if (buttons & GT_BUTTON_C) { player->palette = TILES_PALETTE_YELLOW; }
}

void player_draw(const Player* player) {
    gt_sprite_draw(player->x, player->y, TILES_X(TILES_PLAYER), TILES_Y(player->palette), TILES_TILE_WIDTH,
        TILES_TILE_HEIGHT);
}
