// Attributes: `[[nodiscard]]`, `[[maybe_unused]]`, `[[fallthrough]]` (C23)
#include <stdint.h>

[[nodiscard]] static uint8_t twice(uint8_t value) {
    return value * 2;
}

int main(void) {
    [[maybe_unused]] uint8_t unused = 0;
    uint8_t result = twice(2);
    switch (result) {
    case 4:
        result = 0;
        [[fallthrough]];
    default:
        break;
    }
    return result;
}
