// Declarations after statements (C99)
#include <stdint.h>

int main(void) {
    uint8_t total = 0;
    total += 2;
    uint8_t doubled = total * 2;
    return doubled == 4 ? 0 : 1;
}
