// 64-bit integers: `long long`, `uint64_t` (C99)
#include <stdint.h>

int main(void) {
    uint64_t big = 0x123456789ULL;
    big *= 16;
    return big == 0x1234567890ULL ? 0 : 1;
}
