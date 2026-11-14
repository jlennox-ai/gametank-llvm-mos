// 64-bit integers: `long long`, `uint64_t` (C99)
// The values are volatile so the arithmetic runs on the 6502, not in the compiler.
#include <stdint.h>

static volatile uint64_t big = 0x123456789ULL;
static volatile uint64_t factor = 16;

int main(void) {
    uint64_t product = big * factor;
    return (product == 0x1234567890ULL && product / 3 == 0x611722830ULL) ? 0 : 1;
}
