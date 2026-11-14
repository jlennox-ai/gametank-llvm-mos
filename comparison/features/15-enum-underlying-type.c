// Enums with a fixed underlying type: `enum E : uint8_t` (C23)
#include <stdint.h>

enum Direction : uint8_t {
    DIRECTION_UP,
    DIRECTION_DOWN,
    DIRECTION_LEFT,
    DIRECTION_RIGHT,
};

int main(void) {
    enum Direction direction = DIRECTION_LEFT;
    return (sizeof(direction) == 1 && direction == 2) ? 0 : 1;
}
