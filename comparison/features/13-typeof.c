// `typeof` (C23)
#include <stdint.h>

#define SWAP(left, right) do { typeof(left) swapped = (left); (left) = (right); (right) = swapped; } while (0)

int main(void) {
    uint8_t first = 1;
    uint8_t second = 2;
    SWAP(first, second);
    return (first == 2 && second == 1) ? 0 : 1;
}
