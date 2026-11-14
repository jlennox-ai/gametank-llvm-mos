// Structs passed and returned by value (C89)
#include <stdint.h>

typedef struct {
    uint8_t x;
    uint8_t y;
    uint8_t z;
} Vector;

static Vector vector_add(Vector left, Vector right) {
    Vector sum;
    sum.x = left.x + right.x;
    sum.y = left.y + right.y;
    sum.z = left.z + right.z;
    return sum;
}

int main(void) {
    Vector left;
    Vector right;
    Vector sum;
    left.x = 1;
    left.y = 2;
    left.z = 3;
    right.x = 10;
    right.y = 20;
    right.z = 30;
    sum = vector_add(left, right);
    return (sum.x == 11 && sum.y == 22 && sum.z == 33) ? 0 : 1;
}
