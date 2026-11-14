// `constexpr` (C23)
#include <stdint.h>

constexpr uint8_t TILE_SIZE = 12;
static uint8_t tile[TILE_SIZE];

int main(void) {
    return sizeof(tile) == 12 ? 0 : 1;
}
