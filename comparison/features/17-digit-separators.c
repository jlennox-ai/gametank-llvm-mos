// Digit separators: `1'000'000` (C23)
#include <stdint.h>

int main(void) {
    uint32_t big = 1'000'000;
    return big == 1000000 ? 0 : 1;
}
