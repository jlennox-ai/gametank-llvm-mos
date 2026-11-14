// Classes, templates, constexpr and lambdas (C++)
#include <stdint.h>

template <typename T>
constexpr T clamp(T value, T low, T high) {
    return value < low ? low : (value > high ? high : value);
}

class Counter {
public:
    void add(uint8_t amount) { _total += amount; }
    uint8_t total() const { return _total; }

private:
    uint8_t _total = 0;
};

int main() {
    static_assert(clamp<uint8_t>(200, 0, 100) == 100);
    Counter counter;
    auto addTwice = [&counter](uint8_t amount) {
        counter.add(amount);
        counter.add(amount);
    };
    addTwice(5);
    return counter.total() == 10 ? 0 : 1;
}
