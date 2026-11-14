// Binary literals: `0b1010` (C23)
#include <stdint.h>

int main(void) {
    uint8_t mask = 0b10100101;
    return mask == 0xA5 ? 0 : 1;
}
