// The functions compared (declared in examples.h): the kind of code a GameTank game is made of.
#include "examples.h"

NOT_ZERO_PAGE Entity entities[ENTITY_COUNT];
NOT_ZERO_PAGE uint8_t grid[GRID_HEIGHT][GRID_WIDTH];

// Moves every live entity by its velocity, turning it around at the edges.
void entities_update(void) {
    uint8_t i;
    for (i = 0; i < ENTITY_COUNT; ++i) {
        Entity* entity = &entities[i];
        if (!entity->alive) {
            continue;
        }
        entity->x += entity->dx;
        entity->y += entity->dy;
        if (entity->x >= ENTITY_LIMIT) {
            entity->dx = -entity->dx;
        }
        if (entity->y >= ENTITY_LIMIT) {
            entity->dy = -entity->dy;
        }
    }
}

// value + delta, kept within low-high: byte arguments, and arithmetic past a byte.
uint8_t clamp_add(uint8_t value, int8_t delta, uint8_t low, uint8_t high) {
    int16_t sum = (int16_t)value + delta;
    if (sum < low) {
        return low;
    }
    if (sum > high) {
        return high;
    }
    return (uint8_t)sum;
}

// How many rows of the grid have no empty (0) cell: a falling-block game's line check.
uint8_t grid_full_rows(void) {
    uint8_t full = 0;
    uint8_t y;
    uint8_t x;
    for (y = 0; y < GRID_HEIGHT; ++y) {
        for (x = 0; x < GRID_WIDTH; ++x) {
            if (grid[y][x] == 0) {
                break;
            }
        }
        if (x == GRID_WIDTH) {
            ++full;
        }
    }
    return full;
}

// A 16-bit hash of length bytes (djb2: hash * 33 + byte): 16-bit arithmetic, and multiplying
// by a constant.
uint16_t hash_bytes(const uint8_t* data, uint8_t length) {
    uint16_t hash = 5381;
    uint8_t i;
    for (i = 0; i < length; ++i) {
        hash = hash * 33 + data[i];
    }
    return hash;
}

// Copies a width x height block of a sheet source_width wide into rows ROW_STRIDE apart: how a
// sprite sheet gets into graphics RAM.
void copy_rows(uint8_t* destination, const uint8_t* source, uint8_t width, uint8_t height,
    uint8_t source_width) {
    uint8_t x;
    for (; height != 0; --height) {
        for (x = 0; x < width; ++x) {
            destination[x] = source[x];
        }
        destination += ROW_STRIDE;
        source += source_width;
    }
}
