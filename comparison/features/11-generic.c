// `_Generic` (C11)
#include <stdint.h>

#define BITS(value) _Generic((value), uint8_t: 8, uint16_t: 16, default: 0)

int main(void) {
    uint8_t small = 0;
    uint16_t large = 0;
    return (BITS(small) == 8 && BITS(large) == 16) ? 0 : 1;
}
