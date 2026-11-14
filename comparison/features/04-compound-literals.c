// Compound literals (C99)
#include <stdint.h>

typedef struct {
    uint8_t x;
    uint8_t y;
} Point;

static uint8_t point_sum(const Point* point) {
    return point->x + point->y;
}

int main(void) {
    return point_sum(&(Point){ 3, 4 }) == 7 ? 0 : 1;
}
