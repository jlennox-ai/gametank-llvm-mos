// Declarations in for loops (C99)
#include <stdint.h>

int main(void) {
    uint8_t total = 0;
    for (uint8_t i = 0; i < 4; ++i) {
        total += i;
    }
    return total == 6 ? 0 : 1;
}
