// Anonymous structs and unions (C11)
#include <stdint.h>

typedef struct {
    uint8_t kind;
    union {
        struct {
            uint8_t x;
            uint8_t y;
        };
        uint16_t packed;
    };
} Event;

int main(void) {
    Event event;
    event.packed = 0;
    event.x = 1;
    return event.packed == 1 ? 0 : 1;
}
