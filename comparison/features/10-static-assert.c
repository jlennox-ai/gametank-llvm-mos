// `_Static_assert` (C11)
#include <stdint.h>

_Static_assert(sizeof(uint16_t) == 2, "uint16_t is two bytes");

int main(void) {
    return 0;
}
