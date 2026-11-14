// Inline functions (C99)
#include <stdint.h>

static inline uint8_t twice(uint8_t value) {
    return value * 2;
}

int main(void) {
    return twice(21) == 42 ? 0 : 1;
}
