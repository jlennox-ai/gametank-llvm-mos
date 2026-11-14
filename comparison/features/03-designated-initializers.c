// Designated initializers (C99)
#include <stdint.h>

typedef struct {
    uint8_t x;
    uint8_t y;
    uint8_t color;
} Sprite;

static const Sprite player = { .color = 7, .x = 10 };
static const uint8_t table[4] = { [3] = 9 };

int main(void) {
    return (player.x == 10 && player.y == 0 && player.color == 7 && table[3] == 9) ? 0 : 1;
}
